from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_now() -> datetime:
    """The current instant, as one dependency.

    Every rule about "the past" and "the next hour" reads the clock through
    this, so tests can pin time instead of sleeping or depending on the wall
    clock. See ``app.dependency_overrides[get_now]`` in the test suite.
    """
    return now_utc()


NowDep = Annotated[datetime, Depends(get_now)]
