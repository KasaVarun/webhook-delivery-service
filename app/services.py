import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.repositories.delivery import DeliveryRepository

logger = logging.getLogger(__name__)


class DeliveryService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def deliver(self, delivery_id: uuid.UUID) -> None:
        max_attempts = max(1, self.settings.max_delivery_attempts)
        for attempt_number in range(1, max_attempts + 1):
            async with self.session_factory() as session:
                repository = DeliveryRepository(session)
                delivery = await repository.get_for_delivery(delivery_id)
                if delivery is None or delivery.status == "succeeded":
                    return

                await repository.mark_attempt(delivery, datetime.now(timezone.utc))
                status_code: int | None = None
                error = ""
                try:
                    async with httpx.AsyncClient(timeout=self.settings.webhook_timeout_seconds) as client:
                        response = await client.post(delivery.webhook.url, json=delivery.event.payload)
                    status_code = response.status_code
                    if 200 <= status_code < 300:
                        await repository.mark_success(delivery, status_code, datetime.now(timezone.utc))
                        logger.info("delivery_succeeded delivery_id=%s attempt=%s status=%s", delivery_id, attempt_number, status_code)
                        return
                    error = f"HTTP {status_code}"
                except httpx.HTTPError as exc:
                    error = f"{type(exc).__name__}: {exc}"

                exhausted = attempt_number == max_attempts
                await repository.mark_failure(delivery, status_code, error, exhausted)
                logger.warning("delivery_failed delivery_id=%s attempt=%s exhausted=%s status=%s error=%s", delivery_id, attempt_number, exhausted, status_code, error)

            if not exhausted:
                await asyncio.sleep(min(2 ** (attempt_number - 1), 8))