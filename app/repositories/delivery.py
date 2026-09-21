import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Delivery, DeliveryStatus, Event, Webhook


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, delivery_id: uuid.UUID) -> Delivery | None:
        return await self.session.scalar(select(Delivery).where(Delivery.id == delivery_id))

    async def get_for_delivery(self, delivery_id: uuid.UUID) -> Delivery | None:
        statement = select(Delivery).options(selectinload(Delivery.event), selectinload(Delivery.webhook)).where(Delivery.id == delivery_id)
        return await self.session.scalar(statement)

    async def list_for_event(self, event_id: uuid.UUID) -> list[Delivery]:
        result = await self.session.scalars(select(Delivery).where(Delivery.event_id == event_id).order_by(Delivery.created_at))
        return list(result)

    async def mark_attempt(self, delivery: Delivery, attempted_at: datetime) -> None:
        delivery.status = DeliveryStatus.DELIVERING
        delivery.attempt_count += 1
        delivery.last_attempt_at = attempted_at
        await self.session.commit()

    async def mark_success(self, delivery: Delivery, status_code: int, completed_at: datetime) -> None:
        delivery.status = DeliveryStatus.SUCCEEDED
        delivery.last_http_status = status_code
        delivery.last_error = None
        delivery.delivered_at = completed_at
        await self.session.commit()

    async def mark_failure(self, delivery: Delivery, status_code: int | None, error: str, exhausted: bool) -> None:
        delivery.last_http_status = status_code
        delivery.last_error = error[:2000]
        delivery.status = DeliveryStatus.FAILED if exhausted else DeliveryStatus.PENDING
        await self.session.commit()

    async def metrics(self) -> dict[str, int | float]:
        event_count = await self.session.scalar(select(func.count()).select_from(Event)) or 0
        delivery_count = await self.session.scalar(select(func.count()).select_from(Delivery)) or 0
        pending_count = await self.session.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.DELIVERING]))
        ) or 0
        succeeded_count = await self.session.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.status == DeliveryStatus.SUCCEEDED)
        ) or 0
        failed_count = await self.session.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.status == DeliveryStatus.FAILED)
        ) or 0
        mean_attempts = await self.session.scalar(select(func.avg(Delivery.attempt_count)))
        return {
            "total_events": int(event_count),
            "total_deliveries": int(delivery_count),
            "successful_deliveries": int(succeeded_count),
            "failed_deliveries": int(failed_count),
            "pending_deliveries": int(pending_count),
            "average_attempts_per_delivery": float(mean_attempts) if mean_attempts is not None else 0.0,
        }