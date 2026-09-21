from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Webhook
from app.schemas.webhook import WebhookCreate


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, webhook_in: WebhookCreate) -> Webhook:
        webhook = Webhook(name=webhook_in.name, url=str(webhook_in.url))
        self.session.add(webhook)
        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def list(self) -> list[Webhook]:
        result = await self.session.scalars(select(Webhook).order_by(Webhook.created_at.desc()))
        return list(result)