from fastapi import APIRouter, HTTPException, status

from app.database import database_is_healthy

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Check service readiness",
    description="Verifies the application can execute a database query.",
    responses={503: {"description": "Database is unavailable."}},
)
async def health() -> dict[str, str]:
    if not await database_is_healthy():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable")
    return {"status": "ok", "database": "ok"}