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
    bio: str | None = None


class DoctorNextAvailable(BaseModel):
    doctor: DoctorRead
    next_slot: datetime | None = Field(
        default=None, description="Earliest bookable slot, or null if none in the window"
    )


class DayAvailability(BaseModel):
    date: date
    free_slots: int


class AvailabilitySummary(BaseModel):
    doctor_id: uuid.UUID
    timezone: str
    slot_minutes: int
    days: list[DayAvailability]


class PatientRead(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None = None


class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ()\-]{7,20}$")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("name must contain at least 2 characters")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()


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
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional note for the doctor, e.g. 'child, age 4' or 'follow-up'",
    )

    @field_validator("starts_at")
    @classmethod
    def must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "starts_at must include a timezone offset, e.g. 2026-10-28T10:00:00+03:00"
            )
        return value

    @field_validator("notes")
    @classmethod
    def blank_notes_are_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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
    reference: str
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    status: str
    notes: str | None = None
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
