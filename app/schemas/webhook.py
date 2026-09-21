import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class WebhookCreate(BaseModel):
    name: str = Field(..., description="Human-readable destination name.", examples=["Accounting service"])
    url: AnyHttpUrl = Field(..., description="Absolute HTTP or HTTPS destination URL.", examples=["https://example.com/hooks/events"])

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value

    @field_validator("url")
    @classmethod
    def http_scheme_only(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("url must use http or https")
        return value


class WebhookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Webhook UUID.")
    name: str = Field(description="Human-readable destination name.")
    url: str = Field(description="Configured destination URL.")
    created_at: datetime = Field(description="Creation timestamp in UTC.")
    updated_at: datetime = Field(description="Last update timestamp in UTC.")