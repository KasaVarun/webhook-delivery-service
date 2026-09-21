import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.delivery import DeliveryRepository
from app.repositories.event import EventRepository
from app.schemas.delivery import DeliveryRead, EventDeliveriesRead

router = APIRouter(tags=["deliveries"])


@router.get(
    "/deliveries/{delivery_id}",
    response_model=DeliveryRead,
    summary="Get a delivery",
    description="Returns persisted state for a single delivery UUID.",
    responses={404: {"description": "Delivery was not found."}},
)
async def get_delivery(delivery_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> DeliveryRead:
    delivery = await DeliveryRepository(session).get(delivery_id)
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery not found")
    return delivery


@router.get(
    "/events/{event_id}/deliveries",
    response_model=EventDeliveriesRead,
    summary="List an event's deliveries",
    description="Returns an event and every delivery created for it.",
    responses={404: {"description": "Event was not found."}},
)
async def list_event_deliveries(event_id: str, session: AsyncSession = Depends(get_session)) -> EventDeliveriesRead:
    event = await EventRepository(session).get_by_event_id(event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")
    deliveries = await DeliveryRepository(session).list_for_event(event.id)
    return EventDeliveriesRead(event=event, deliveries=deliveries)