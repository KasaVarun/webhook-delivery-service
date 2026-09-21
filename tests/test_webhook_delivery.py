import uuid
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import SessionLocal
from app.models import Delivery, DeliveryStatus, Event, Webhook
from app.services import DeliveryService


async def create_webhook(client: AsyncClient, name: str = "orders") -> dict:
    response = await client.post(
        "/webhooks", json={"name": name, "url": "https://receiver.example/hooks"}
    )
    assert response.status_code == 201
    return response.json()


async def create_event(client: AsyncClient, event_id: str = "event-1") -> dict:
    response = await client.post(
        "/events",
        json={"event_id": event_id, "event_type": "order.created", "payload": {"order_id": 42}},
    )
    assert response.status_code == 201
    return response.json()


async def seed_delivery() -> uuid.UUID:
    async with SessionLocal() as session:
        webhook = Webhook(name="orders", url="https://receiver.example/hooks")
        event = Event(event_id=str(uuid.uuid4()), event_type="order.created", payload={"order_id": 42})
        session.add_all([webhook, event])
        await session.flush()
        delivery = Delivery(webhook_id=webhook.id, event_id=event.id)
        session.add(delivery)
        await session.commit()
        return delivery.id


async def get_delivery(delivery_id: uuid.UUID) -> Delivery:
    async with SessionLocal() as session:
        delivery = await session.get(Delivery, delivery_id)
        assert delivery is not None
        return delivery


def post_response(status_code: int) -> Callable[..., Awaitable[httpx.Response]]:
    async def post(_: httpx.AsyncClient, url: str, **__: object) -> httpx.Response:
        return httpx.Response(status_code, request=httpx.Request("POST", url))

    return post


async def test_health_and_database_health_failure(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (await client.get("/health")).json() == {"status": "ok", "database": "ok"}

    async def unavailable() -> bool:
        return False

    monkeypatch.setattr("app.routes.health.database_is_healthy", unavailable)
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


async def test_create_webhook_invalid_url_and_list_webhooks(client: AsyncClient) -> None:
    created = await create_webhook(client, "first")
    invalid = await client.post("/webhooks", json={"name": "bad", "url": "ftp://receiver.example/hooks"})
    listed = await client.get("/webhooks")

    assert invalid.status_code == 422
    assert listed.status_code == 200
    assert [webhook["id"] for webhook in listed.json()] == [created["id"]]


async def test_create_event_and_reject_duplicate_event(client: AsyncClient) -> None:
    created = await create_event(client, "idempotent-event")
    duplicate = await client.post(
        "/events",
        json={"event_id": "idempotent-event", "event_type": "order.created", "payload": {}},
    )

    assert created["event_id"] == "idempotent-event"
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "event_id already exists"}


async def test_successful_delivery_is_awaited_and_persisted(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await create_webhook(client)
    monkeypatch.setattr("app.routes.events.delivery_service.deliver", AsyncMock())
    event = await create_event(client)
    history = await client.get(f"/events/{event['event_id']}/deliveries")
    delivery_id = uuid.UUID(history.json()["deliveries"][0]["id"])
    monkeypatch.setattr(httpx.AsyncClient, "post", post_response(204))
    await DeliveryService(SessionLocal, Settings(max_delivery_attempts=1)).deliver(delivery_id)
    history = await client.get(f"/events/{event['event_id']}/deliveries")

    assert history.status_code == 200
    [delivery] = history.json()["deliveries"]
    assert delivery["status"] == "succeeded"
    assert delivery["attempt_count"] == 1
    assert delivery["last_http_status"] == 204


async def test_network_failure_is_persisted(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    delivery_id = await seed_delivery()

    async def post(_: httpx.AsyncClient, url: str, **__: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    monkeypatch.setattr("app.services.asyncio.sleep", AsyncMock())
    await DeliveryService(SessionLocal, Settings(max_delivery_attempts=1)).deliver(delivery_id)
    delivery = await get_delivery(delivery_id)

    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.attempt_count == 1
    assert delivery.last_http_status is None
    assert delivery.last_error is not None and "ConnectError" in delivery.last_error


async def test_non_2xx_response_is_persisted(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    delivery_id = await seed_delivery()
    monkeypatch.setattr(httpx.AsyncClient, "post", post_response(502))
    monkeypatch.setattr("app.services.asyncio.sleep", AsyncMock())

    await DeliveryService(SessionLocal, Settings(max_delivery_attempts=1)).deliver(delivery_id)
    delivery = await get_delivery(delivery_id)

    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.attempt_count == 1
    assert delivery.last_http_status == 502
    assert delivery.last_error == "HTTP 502"


async def test_retry_exhaustion_makes_exactly_four_attempts(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    delivery_id = await seed_delivery()
    post = AsyncMock(side_effect=[httpx.Response(500) for _ in range(4)])
    sleep = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    monkeypatch.setattr("app.services.asyncio.sleep", sleep)

    await DeliveryService(SessionLocal, Settings(max_delivery_attempts=4)).deliver(delivery_id)
    delivery = await get_delivery(delivery_id)

    assert post.await_count == 4
    assert sleep.await_count == 3
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.attempt_count == 4
    assert delivery.last_http_status == 500


async def test_delivery_lookup_and_event_delivery_history_not_found(client: AsyncClient) -> None:
    delivery_id = await seed_delivery()
    delivery = await client.get(f"/deliveries/{delivery_id}")
    unknown_delivery = await client.get(f"/deliveries/{uuid.uuid4()}")

    assert delivery.status_code == 200
    assert delivery.json()["id"] == str(delivery_id)
    assert unknown_delivery.status_code == 404

    async with SessionLocal() as session:
        event = await session.get(Event, delivery.json()["event_id"])
        assert event is not None
        event_id = event.event_id

    history = await client.get(f"/events/{event_id}/deliveries")
    unknown_history = await client.get(f"/events/missing-event/deliveries")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()["deliveries"]] == [str(delivery_id)]
    assert unknown_history.status_code == 404


async def test_metrics(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    await create_webhook(client)
    monkeypatch.setattr("app.routes.events.delivery_service.deliver", AsyncMock())
    event = await create_event(client)
    history = await client.get(f"/events/{event['event_id']}/deliveries")
    delivery_id = uuid.UUID(history.json()["deliveries"][0]["id"])
    monkeypatch.setattr(httpx.AsyncClient, "post", post_response(200))
    await DeliveryService(SessionLocal, Settings(max_delivery_attempts=1)).deliver(delivery_id)
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "total_events": 1,
        "total_deliveries": 1,
        "successful_deliveries": 1,
        "failed_deliveries": 0,
        "pending_deliveries": 0,
        "average_attempts_per_delivery": 1.0,
    }


async def test_event_id_database_unique_constraint_independently(client: AsyncClient) -> None:
    async with SessionLocal() as session:
        session.add(Event(event_id="database-unique", event_type="order.created", payload={}))
        await session.commit()
        session.add(Event(event_id="database-unique", event_type="order.updated", payload={}))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()