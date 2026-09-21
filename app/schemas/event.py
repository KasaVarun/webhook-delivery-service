import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventCreate(BaseModel):
    event_id: str = Field(..., description="Client-assigned idempotency identifier.", examples=["order-1842-paid"])
    event_type: str = Field(..., description="Event category.", examples=["order.paid"])
    payload: dict[str, Any] = Field(..., description="JSON object delivered verbatim to destinations.", examples=[{"order_id": "1842", "total": 42.50}])

    @field_validator("event_id", "event_type")
    @classmethod
    def nonempty_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Event UUID.")
    event_id: str = Field(description="Client event identifier.")
    event_type: str = Field(description="Event category.")
    payload: dict[str, Any] = Field(description="Original JSON event object.")
    created_at: datetime = Field(description="Creation timestamp in UTC.")
    updated_at: datetime = Field(description="Last update timestamp in UTC.")