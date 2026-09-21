from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.delivery import DeliveryRepository
from app.schemas.delivery import MetricsRead

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    response_model=MetricsRead,
    summary="Get delivery metrics",
    description="Returns counts by persisted delivery state and the mean persisted attempt count.",
)
async def metrics(session: AsyncSession = Depends(get_session)) -> MetricsRead:
    return MetricsRead(**await DeliveryRepository(session).metrics())