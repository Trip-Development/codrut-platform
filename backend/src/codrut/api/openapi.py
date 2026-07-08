import re

from fastapi.routing import APIRoute


def generate_stable_operation_id(route: APIRoute) -> str:
    """Preserve FastAPI's current operation-id shape under project control."""
    method = sorted(route.methods or {"GET"})[0].lower()
    operation_id = f"{route.name}{route.path_format}"
    normalized_operation_id = re.sub(r"\W", "_", operation_id)
    return f"{normalized_operation_id}_{method}"
