from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SlotRead(ORMModel):
    starts_at: datetime = Field(description="Slot start (UTC)")
    ends_at: datetime = Field(description="Slot end (UTC, exclusive)")


class DoctorRead(ORMModel):
    id: uuid.UUID
    name: str
    specialty: str
    email: str
    timezone: str


class PatientRead(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None = None


class AvailabilityResponse(BaseModel):
    doctor_id: uuid.UUID
    date: date
    timezone: str
    slot_minutes: int
    slots: list[SlotRead]


class AppointmentCreate(BaseModel):
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    starts_at: datetime = Field(description="Slot start; must include a timezone offset")

    @field_validator("starts_at")
    @classmethod
    def must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "starts_at must include a timezone offset, e.g. 2026-10-28T10:00:00+03:00"
            )
        return value


class RescheduleRequest(BaseModel):
    starts_at: datetime = Field(description="New slot start; must include a timezone offset")

    @field_validator("starts_at")
    @classmethod
    def must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "starts_at must include a timezone offset, e.g. 2026-10-28T10:00:00+03:00"
            )
        return value


class CancelRequest(BaseModel):
    reason: str = Field(
        min_length=3, max_length=500, description="Why the appointment is cancelled"
    )

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("reason must contain at least 3 non-whitespace characters")
        return cleaned


class AppointmentRead(ORMModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    status: str
    cancel_reason: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    timezone: str
