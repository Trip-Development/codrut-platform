from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import select

from codrut.contracts.generation import (
    GenerationError,
    GenerationMessage,
    GenerationProviderKey,
    GenerationPurpose,
    GenerationRequest,
    TokenUsage,
)
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User  # noqa: F401
from codrut.modules.practice.budget import (
    BudgetExceeded,
    release,
    reserve,
    settle,
)
from codrut.modules.practice.generation_provider import (
    LocalGenerationProvider,
    VertexGenerationProvider,
    build_generation_provider,
)
from codrut.modules.practice.models import (
    BudgetReservationState,
    PracticeBudgetReservation,
    PracticeProgramSettings,
    PracticeTheme,
    ProgramMode,
)
from codrut.modules.practice.pricing import (
    estimate_cost,
    estimate_pessimistic_cost,
)


def test_estimate_cost_with_thinking_measured_case() -> None:
    """Test cost calculation with thinking: 54 input, 34 output, 902 thinking.

    Expected: 0.0024 USD
    (54 / 1_000_000 * 0.30 + (34 + 902) / 1_000_000 * 2.50 = 0.0023562 -> 0.0024 USD)
    """
    settings = Settings()
    usage = TokenUsage(prompt_tokens=54, output_tokens=34, thought_tokens=902)
    cost = estimate_cost(usage, settings)

    assert cost == Decimal("0.0024")


def test_estimate_cost_without_thinking_measured_case() -> None:
    """Test cost calculation without thinking: 54 input, 34 output, 0 thinking.

    Expected: 0.0001 USD
    (54 / 1_000_000 * 0.30 + 34 / 1_000_000 * 2.50 = 0.0001012 -> 0.0001 USD)
    """
    settings = Settings()
    usage = TokenUsage(prompt_tokens=54, output_tokens=34, thought_tokens=0)
    cost = estimate_cost(usage, settings)

    assert cost == Decimal("0.0001")


def test_estimate_pessimistic_cost() -> None:
    settings = Settings()
    cost = estimate_pessimistic_cost(
        prompt_tokens=100,
        max_output_tokens=1024,
        thinking_budget=1024,
        settings=settings,
    )
    # 100/1e6*0.30 + (1024+1024)/1e6*2.50 = 0.00003 + 0.00512 = 0.00515 -> 0.0052
    assert cost == Decimal("0.0052")


@pytest.mark.asyncio
async def test_local_generation_provider_returns_result_without_network() -> None:
    settings = Settings(generation_provider="local")
    provider = build_generation_provider(settings)

    assert isinstance(provider, LocalGenerationProvider)
    assert provider.key == GenerationProviderKey.local

    request = GenerationRequest(
        messages=(
            GenerationMessage(role="user", text="Salut, putem discuta despre proiect?"),
        ),
        system_instruction="Ești un coleg cooperant.",
        purpose=GenerationPurpose.actor,
        max_output_tokens=1024,
        temperature=0.7,
        thinking_budget=0,
    )

    result = await provider.generate(request)

    assert result.provider == GenerationProviderKey.local
    assert result.finish_reason == "STOP"
    assert result.text == "Local generation response for actor."
    assert result.usage.prompt_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.thought_tokens == 0
    assert result.estimated_usd >= Decimal("0.0000")


def test_build_generation_provider_missing_credentials_raises_error() -> None:
    settings = Settings(
        generation_provider="vertex",
        vertex_credentials_path="/nonexistent/path/cody-vertex.json",
    )
    with pytest.raises(DomainError) as exc_info:
        build_generation_provider(settings)

    assert exc_info.value.code == "credentials_missing"


@pytest.mark.asyncio
async def test_vertex_generation_provider_with_mock_client() -> None:
    settings = Settings(
        generation_provider="vertex",
        vertex_project_id="test-project",
        vertex_region="europe-west4",
        vertex_actor_model="gemini-2.5-flash",
    )

    mock_credentials = MagicMock()
    mock_credentials.valid = True
    mock_credentials.token = "mock-bearer-token-12345"  # noqa: S105

    fake_response_payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "Răspuns generat de test."}
                    ]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 54,
            "candidatesTokenCount": 34,
            "thoughtsTokenCount": 902,
        },
    }

    captured_requests: list[httpx.Request] = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        captured_requests.append(req)
        return httpx.Response(200, json=fake_response_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = VertexGenerationProvider(
            settings=settings,
            credentials=mock_credentials,
            client=client,
        )

        request = GenerationRequest(
            messages=(
                GenerationMessage(role="user", text="Test prompt"),
            ),
            system_instruction="Instrucțiuni de sistem",
            purpose=GenerationPurpose.actor,
            max_output_tokens=512,
            temperature=0.5,
            thinking_budget=1024,
        )

        result = await provider.generate(request)

        assert result.provider == GenerationProviderKey.vertex
        assert result.model == "gemini-2.5-flash"
        assert result.region == "europe-west4"
        assert result.finish_reason == "STOP"
        assert result.text == "Răspuns generat de test."
        assert result.usage.prompt_tokens == 54
        assert result.usage.output_tokens == 34
        assert result.usage.thought_tokens == 902
        assert result.estimated_usd == Decimal("0.0024")

        # Verify outgoing HTTP request details
        assert len(captured_requests) == 1
        http_req = captured_requests[0]
        assert http_req.headers["authorization"] == "Bearer mock-bearer-token-12345"
        body = json.loads(http_req.content.decode("utf-8"))
        assert body["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 1024
        assert body["generationConfig"]["temperature"] == 0.5
        assert body["generationConfig"]["maxOutputTokens"] == 512
        assert body["systemInstruction"]["parts"][0]["text"] == "Instrucțiuni de sistem"


@pytest.mark.asyncio
async def test_vertex_generation_provider_abnormal_finish_reason_raises_error() -> None:
    settings = Settings(generation_provider="vertex")
    mock_credentials = MagicMock()
    mock_credentials.valid = True
    mock_credentials.token = "mock-token"  # noqa: S105

    fake_response_payload = {
        "candidates": [
            {
                "content": {"role": "model", "parts": []},
                "finishReason": "SAFETY",
            }
        ],
    }

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=fake_response_payload))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = VertexGenerationProvider(
            settings=settings,
            credentials=mock_credentials,
            client=client,
        )

        request = GenerationRequest(
            messages=(GenerationMessage(role="user", text="Test"),),
        )

        with pytest.raises(GenerationError) as exc_info:
            await provider.generate(request)

        assert exc_info.value.code == "vertex_finish_reason_error"
        assert "SAFETY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_budget_reservation_lifecycle() -> None:
    """Test budget reservation, cap enforcement, settlement, and release."""
    async with SessionLocal() as session:
        # 1. Setup company, project, participants, program settings
        test_suffix = uuid.uuid4().hex[:8]
        company = Company(name=f"Budget Test Co {test_suffix}")
        session.add(company)
        await session.flush()

        project = CompanyProject(
            company_id=company.id,
            name=f"Budget Test Project {test_suffix}",
            status=CompanyProjectStatus.active,
        )
        session.add(project)
        await session.flush()

        # Add 2 participants to project -> cap with 3.00 USD/participant = 6.00 USD
        p1 = ParticipantProfile(
            company_id=company.id,
            full_name=f"Participant One {test_suffix}",
            email=f"p1_{test_suffix}@example.com",
        )
        p2 = ParticipantProfile(
            company_id=company.id,
            full_name=f"Participant Two {test_suffix}",
            email=f"p2_{test_suffix}@example.com",
        )
        session.add_all([p1, p2])
        await session.flush()

        m1 = ProjectMembership(
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=p1.id,
        )
        m2 = ProjectMembership(
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=p2.id,
        )
        session.add_all([m1, m2])
        await session.flush()

        theme = PracticeTheme(
            slug=f"theme-{test_suffix}",
            name="Theme Test",
        )
        session.add(theme)
        await session.flush()

        program_settings = PracticeProgramSettings(
            project_id=project.id,
            mode=ProgramMode.training,
            theme_id=theme.id,
            usd_cap_per_participant=Decimal("3.00"),
        )
        session.add(program_settings)
        await session.flush()

        prog_id = program_settings.id

        # 2. Test cap enforcement:
        # Cap = 2 * 3.00 = 6.00 USD. Attempting to reserve 6.01 USD must fail.
        with pytest.raises(BudgetExceeded):
            await reserve(session, prog_id, estimated_usd=Decimal("6.0100"))

        # Verify NO reservation row was written on failure
        stmt_check = select(PracticeBudgetReservation).where(
            PracticeBudgetReservation.program_settings_id == prog_id
        )
        rows = (await session.execute(stmt_check)).scalars().all()
        assert len(rows) == 0

        # 3. Reserve 4.00 USD (under 6.00 USD cap) -> Succeeds
        res1_id = await reserve(session, prog_id, estimated_usd=Decimal("4.0000"))
        assert res1_id is not None

        # 4. Attempt to reserve another 2.50 USD (4.00 + 2.50 = 6.50 > 6.00) -> Fails
        with pytest.raises(BudgetExceeded):
            await reserve(session, prog_id, estimated_usd=Decimal("2.5000"))

        # 5. Settle res1 with actual cost 1.50 USD
        await settle(session, res1_id, actual_usd=Decimal("1.5000"))

        # Check row state
        stmt_res1 = select(PracticeBudgetReservation).where(PracticeBudgetReservation.id == res1_id)
        res1_row = (await session.execute(stmt_res1)).scalar_one()
        assert res1_row.state == BudgetReservationState.settled
        assert res1_row.actual_usd == Decimal("1.5000")

        # 6. Now spent is 1.50 USD. Reserving 2.50 USD (1.50 + 2.50 = 4.00 <= 6.00) -> Succeeds!
        res2_id = await reserve(session, prog_id, estimated_usd=Decimal("2.5000"))
        assert res2_id is not None

        # 7. Release res2 -> State becomes 'released', freed from budget
        await release(session, res2_id)
        stmt_res2 = select(PracticeBudgetReservation).where(PracticeBudgetReservation.id == res2_id)
        res2_row = (await session.execute(stmt_res2)).scalar_one()
        assert res2_row.state == BudgetReservationState.released

        # Clean up database records
        await session.rollback()
