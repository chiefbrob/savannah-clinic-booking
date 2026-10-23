from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.patient import Patient

BOOKED = "booked"
CANCELLED = "cancelled"
COMPLETED = "completed"
STATUSES = (BOOKED, CANCELLED, COMPLETED)


class Appointment(Base, TimestampMixin):
    """A booked slot.

    The invariant "a booked slot is not available to anyone else" is enforced by
    the database, not by application logic: ``ix_appointments_no_double_booking``
    is a **partial** unique index over ``(doctor_id, starts_at)`` that only
    covers rows whose status is ``booked``. Cancelling flips the status, which
    removes the row from the index and frees the slot atomically.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointment_time_order"),
        CheckConstraint(
            "status IN ('booked', 'cancelled', 'completed')", name="ck_appointment_status"
        ),
        CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL",
            name="ck_appointment_cancelled_at",
        ),
        Index(
            "ix_appointments_no_double_booking",
            "doctor_id",
            "starts_at",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
        Index("ix_appointments_patient_starts_at", "patient_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BOOKED)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def reference(self) -> str:
        """Short human-friendly reference, e.g. CLN-4F2A9C."""
        return f"CLN-{self.id.hex[:6].upper()}"

    doctor: Mapped[Doctor] = relationship(back_populates="appointments", lazy="raise")
    patient: Mapped[Patient] = relationship(back_populates="appointments", lazy="raise")
