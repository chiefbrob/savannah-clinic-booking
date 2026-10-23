"""Seed the clinic with the 5 doctors from the brief and a handful of patients.

Idempotent: running it twice does not duplicate rows. Ids are derived from the
email address with UUIDv5, so they are stable across environments — the demo
links in the README keep working after a re-seed.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import time

from sqlalchemy import select

from app.core.db import session_scope
from app.models import Doctor, DoctorSchedule, Patient

NAMESPACE = uuid.UUID("6f1c0a8e-2b8d-4c1a-9d3b-8f2a5c7e4b10")

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
WEEKDAYS = (MON, TUE, WED, THU, FRI)


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


DOCTORS = [
    {
        "name": "Dr. Amina Wanjiru",
        "specialty": "General Practice",
        "email": "amina.wanjiru@clinic.example",
        "bio": "Family medicine, 12 years. Long-term conditions, screenings and everyday illness.",
        "windows": [(day, "08:00", "16:00") for day in WEEKDAYS],
    },
    {
        "name": "Dr. Peter Otieno",
        "specialty": "Paediatrics",
        "email": "peter.otieno@clinic.example",
        "bio": "Paediatrics. Newborn checks, childhood vaccinations and growth reviews.",
        "windows": [(day, "09:00", "17:00") for day in WEEKDAYS],
    },
    {
        "name": "Dr. Grace Mwangi",
        "specialty": "Obstetrics & Gynaecology",
        "email": "grace.mwangi@clinic.example",
        "bio": "Obstetrics and gynaecology. Antenatal care, family planning and postnatal reviews.",
        # Split shift: mornings on Mon/Wed/Fri, afternoons on Tue/Thu.
        "windows": [
            (MON, "08:00", "13:00"),
            (WED, "08:00", "13:00"),
            (FRI, "08:00", "13:00"),
            (TUE, "14:00", "18:00"),
            (THU, "14:00", "18:00"),
        ],
    },
    {
        "name": "Dr. Samuel Kiptoo",
        "specialty": "Cardiology",
        "email": "samuel.kiptoo@clinic.example",
        "bio": "Cardiology. Blood pressure review, ECG interpretation and cardiac risk assessment.",
        "windows": [(day, "10:00", "18:00") for day in WEEKDAYS],
    },
    {
        "name": "Dr. Fatuma Hassan",
        "specialty": "Dermatology",
        "email": "fatuma.hassan@clinic.example",
        "bio": "Dermatology. Eczema, acne, skin infections and allergy patch testing.",
        "windows": [(day, "08:00", "12:00") for day in (MON, TUE, WED, THU, FRI, SAT)],
    },
]

PATIENTS = [
    ("Brian Obare", "brian.obare@example.com", "+254700000001"),
    ("Mary Achieng", "mary.achieng@example.com", "+254700000002"),
    ("James Mutua", "james.mutua@example.com", "+254700000003"),
    ("Faith Njeri", "faith.njeri@example.com", "+254700000004"),
    ("Daniel Barasa", "daniel.barasa@example.com", "+254700000005"),
    ("Halima Yusuf", "halima.yusuf@example.com", "+254700000006"),
]


def _time(value: str) -> time:
    hours, minutes = (int(part) for part in value.split(":"))
    return time(hour=hours, minute=minutes)


async def seed() -> dict[str, int]:
    created = {"doctors": 0, "schedules": 0, "patients": 0}
    async with session_scope() as session:
        for spec in DOCTORS:
            existing = await session.scalar(select(Doctor).where(Doctor.email == spec["email"]))
            if existing is not None:
                # Keep re-seeding useful: fill in a missing profile blurb.
                if existing.bio is None and spec.get("bio"):
                    existing.bio = spec["bio"]
                continue
            doctor = Doctor(
                id=stable_id(f"doctor:{spec['email']}"),
                name=spec["name"],
                specialty=spec["specialty"],
                email=spec["email"],
                bio=spec.get("bio"),
                timezone="Africa/Nairobi",
            )
            session.add(doctor)
            for weekday, start, end in spec["windows"]:
                session.add(
                    DoctorSchedule(
                        doctor_id=doctor.id,
                        weekday=weekday,
                        start_time=_time(start),
                        end_time=_time(end),
                    )
                )
                created["schedules"] += 1
            created["doctors"] += 1

        for name, email, phone in PATIENTS:
            existing = await session.scalar(select(Patient).where(Patient.email == email))
            if existing is not None:
                continue
            session.add(
                Patient(id=stable_id(f"patient:{email}"), name=name, email=email, phone=phone)
            )
            created["patients"] += 1

    return created


def main() -> None:
    created = asyncio.run(seed())
    print(
        "seed complete: "
        f"{created['doctors']} doctors, {created['schedules']} working windows, "
        f"{created['patients']} patients added "
        "(existing rows were left alone)"
    )


if __name__ == "__main__":
    main()
