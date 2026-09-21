from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Delivery, Event, Webhook
from app.schemas.event import EventCreate


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_with_deliveries(self, event_in: EventCreate) -> tuple[Event, list[Delivery]]:
        async with self.session.begin():
            event = Event(
                event_id=event_in.event_id,
                event_type=event_in.event_type,
                payload=event_in.payload,
            )
            self.session.add(event)
            await self.session.flush()
            webhooks = list(await self.session.scalars(select(Webhook)))
            deliveries = [Delivery(event_id=event.id, webhook_id=webhook.id) for webhook in webhooks]
            self.session.add_all(deliveries)
        await self.session.refresh(event)
        for delivery in deliveries:
            await self.session.refresh(delivery)
        return event, deliveries

    async def get_by_event_id(self, event_id: str) -> Event | None:
        result = await self.session.scalar(select(Event).where(Event.event_id == event_id))
        return result