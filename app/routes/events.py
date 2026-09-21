import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal, get_session
from app.repositories.event import EventRepository
from app.schemas.event import EventCreate, EventRead
from app.services import DeliveryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])
delivery_service = DeliveryService(SessionLocal, get_settings())


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Accept an event",
    description="Persists an event and creates one pending delivery per registered webhook before scheduling delivery.",
    responses={409: {"description": "The event_id has already been accepted."}, 422: {"description": "Event input is invalid."}},
)
async def create_event(
    event_in: EventCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EventRead:
    try:
        event, deliveries = await EventRepository(session).create_with_deliveries(event_in)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="event_id already exists") from None

    for delivery in deliveries:
        background_tasks.add_task(delivery_service.deliver, delivery.id)
    logger.info("event_accepted event_id=%s delivery_count=%s", event.event_id, len(deliveries))
    return event