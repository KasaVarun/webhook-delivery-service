import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import DeliveryStatus
from app.schemas.event import EventRead
from app.schemas.webhook import WebhookRead


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Delivery UUID.")
    event_id: uuid.UUID = Field(description="Associated event UUID.")
    webhook_id: uuid.UUID = Field(description="Associated webhook UUID.")
    status: DeliveryStatus = Field(description="Current delivery state.")
    attempt_count: int = Field(description="Number of completed HTTP attempts.")
    last_http_status: int | None = Field(description="Most recent HTTP response status, if available.")
    last_error: str | None = Field(description="Most recent transport or HTTP error.")
    last_attempt_at: datetime | None = Field(description="Most recent attempt timestamp.")
    delivered_at: datetime | None = Field(description="Successful delivery timestamp.")
    created_at: datetime = Field(description="Creation timestamp in UTC.")
    updated_at: datetime = Field(description="Last update timestamp in UTC.")


class EventDeliveriesRead(BaseModel):
    event: EventRead = Field(description="The requested event.")
    deliveries: list[DeliveryRead] = Field(description="All deliveries created for the event.")


class MetricsRead(BaseModel):
    total_events: int = Field(description="Total persisted events.")
    total_deliveries: int = Field(description="Total persisted deliveries.")
    successful_deliveries: int = Field(description="Deliveries whose latest attempt succeeded.")
    failed_deliveries: int = Field(description="Deliveries that exhausted their retry budget.")
    pending_deliveries: int = Field(description="Deliveries not yet terminally succeeded or failed.")
    average_attempts_per_delivery: float = Field(
        description="Mean attempt_count across all persisted deliveries; 0.0 when no deliveries exist."
    )