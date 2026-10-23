from __future__ import annotations

import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), nullable=False, default="General Practice")
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Working hours are interpreted in this timezone.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Nairobi")

    schedules: Mapped[list[DoctorSchedule]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="doctor",
        lazy="raise",
    )


class DoctorSchedule(Base):
    """One recurring working window, e.g. Monday 08:00-16:00.

    A doctor may have several windows on the same day (a split shift, e.g.
    Monday 08:00-12:00 and 14:00-17:00), which is why the unique constraint is
    on the start time as well.
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        UniqueConstraint("doctor_id", "weekday", "start_time", name="uq_doctor_schedule_window"),
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_doctor_schedule_weekday"),
        CheckConstraint("end_time > start_time", name="ck_doctor_schedule_time_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 0 = Monday ... 6 = Sunday (ISO weekday order).
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)

    doctor: Mapped[Doctor] = relationship(back_populates="schedules", lazy="raise")
