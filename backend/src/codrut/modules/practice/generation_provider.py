from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol

import httpx
from google.auth.exceptions import TransportError
from google.auth.transport import (
    Request as GoogleAuthRequest,
)
from google.auth.transport import (
    Response as GoogleAuthResponse,
)
from google.oauth2 import service_account

from codrut.contracts.generation import (
    GenerationError,
    GenerationProviderKey,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.practice.pricing import estimate_cost


class HttpxAuthResponse(GoogleAuthResponse):
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._response.headers)

    @property
    def data(self) -> bytes:
        return self._response.content


class HttpxAuthRequest(GoogleAuthRequest):
    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> GoogleAuthResponse:
        try:
            with httpx.Client(timeout=timeout or 10.0) as client:
                res = client.request(
                    method=method,
                    url=url,
                    content=body,
                    headers=headers,
                )
                return HttpxAuthResponse(res)
        except Exception as exc:
            raise TransportError(f"HTTP auth request failed: {exc}") from exc


class GenerationProvider(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate content from the model according to the given request."""
        ...


class LocalGenerationProvider:
    key = GenerationProviderKey.local

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.recorded_requests: list[GenerationRequest] = []

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.recorded_requests.append(request)
        prompt_words = sum(len(m.text.split()) for m in request.messages)
        if request.system_instruction:
            prompt_words += len(request.system_instruction.split())
        prompt_tokens = max(1, prompt_words)
        output_text = f"Local generation response for {request.purpose.value}."
        output_tokens = len(output_text.split())
        thought_tokens = 0

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            thought_tokens=thought_tokens,
        )
        estimated_usd = estimate_cost(usage, self.settings)

        return GenerationResult(
            text=output_text,
            usage=usage,
            provider=self.key,
            model="local-mock",
            region="local",
            finish_reason="STOP",
            estimated_usd=estimated_usd,
        )


class VertexGenerationProvider:
    key = GenerationProviderKey.vertex

    def __init__(
        self,
        settings: Settings,
        credentials: service_account.Credentials,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.credentials = credentials
        self._client = client
        self._auth_request = HttpxAuthRequest()

    def _get_access_token_sync(self) -> str:
        if not self.credentials.valid:
            self.credentials.refresh(self._auth_request)
        token = self.credentials.token
        if not token:
            raise GenerationError(
                "Unable to obtain valid Vertex AI access token",
                code="token_acquisition_failed",
            )
        return token

    async def _get_access_token(self) -> str:
        return await asyncio.to_thread(self._get_access_token_sync)

    def _select_model(self, purpose: GenerationPurpose) -> str:
        if purpose == GenerationPurpose.evaluator:
            return self.settings.vertex_evaluator_model
        return self.settings.vertex_actor_model

    def _build_url(self, model: str) -> str:
        region = self.settings.vertex_region
        project = self.settings.vertex_project_id
        return (
            f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/"
            f"locations/{region}/publishers/google/models/{model}:generateContent"
        )

    def _build_payload(self, request: GenerationRequest) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            contents.append(
                {
                    "role": msg.role,
                    "parts": [{"text": msg.text}],
                }
            )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
                "thinkingConfig": {
                    "thinkingBudget": request.thinking_budget,
                },
            },
        }

        if request.system_instruction is not None:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_instruction}]
            }

        return payload

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        token = await self._get_access_token()
        model = self._select_model(request.purpose)
        url = self._build_url(model)
        payload = self._build_payload(request)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        client = self._client
        owns_client = False
        if client is None:
            client = httpx.AsyncClient(
                timeout=float(self.settings.vertex_timeout_seconds)
            )
            owns_client = True

        try:
            response = await client.post(url, json=payload, headers=headers)
        except Exception as exc:
            raise GenerationError(
                f"Vertex AI network request failed: {type(exc).__name__}",
                code="vertex_network_error",
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code != 200:
            raise GenerationError(
                f"Vertex AI returned HTTP {response.status_code}",
                code="vertex_http_error",
            )

        try:
            data = response.json()
        except Exception as exc:
            raise GenerationError(
                "Invalid JSON response from Vertex AI",
                code="vertex_invalid_json",
            ) from exc

        candidates = data.get("candidates")
        if not candidates or not isinstance(candidates, list):
            raise GenerationError(
                "No candidates returned from Vertex AI",
                code="vertex_no_candidates",
            )

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason != "STOP":
            raise GenerationError(
                f"Generation did not finish normally: {finish_reason}",
                code="vertex_finish_reason_error",
            )

        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))

        usage_metadata = data.get("usageMetadata", {})
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        output_tokens = usage_metadata.get("candidatesTokenCount", 0)
        thought_tokens = usage_metadata.get("thoughtsTokenCount", 0)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            thought_tokens=thought_tokens,
        )
        estimated_usd = estimate_cost(usage, self.settings)

        return GenerationResult(
            text=text,
            usage=usage,
            provider=self.key,
            model=model,
            region=self.settings.vertex_region,
            finish_reason=finish_reason,
            estimated_usd=estimated_usd,
        )


def build_generation_provider(
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> GenerationProvider:
    """Build and initialize the configured generation provider."""
    if settings.generation_provider == "local":
        return LocalGenerationProvider(settings)

    if settings.generation_provider == "vertex":
        cred_path = Path(settings.vertex_credentials_path)
        if not cred_path.is_file():
            raise DomainError(
                f"Vertex credentials file not found at: {settings.vertex_credentials_path}",
                code="credentials_missing",
            )
        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(cred_path),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except Exception as exc:
            raise DomainError(
                "Failed to load Vertex credentials file",
                code="credentials_invalid",
            ) from exc
        return VertexGenerationProvider(settings, credentials=credentials, client=client)

    raise DomainError(
        f"Unsupported generation provider: {settings.generation_provider}",
        code="invalid_provider",
    )
