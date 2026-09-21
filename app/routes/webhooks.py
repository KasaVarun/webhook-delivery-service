from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.webhook import WebhookRepository
from app.schemas.webhook import WebhookCreate, WebhookRead

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "",
    response_model=WebhookRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a webhook destination",
    description="Stores an HTTP(S) endpoint that receives future accepted events.",
    responses={422: {"description": "Webhook input is invalid."}},
)
async def create_webhook(webhook_in: WebhookCreate, session: AsyncSession = Depends(get_session)) -> WebhookRead:
    return await WebhookRepository(session).create(webhook_in)


@router.get(
    "",
    response_model=list[WebhookRead],
    summary="List webhook destinations",
    description="Returns registered destinations ordered by most recently created.",
)
async def list_webhooks(session: AsyncSession = Depends(get_session)) -> list[WebhookRead]:
    return await WebhookRepository(session).list()