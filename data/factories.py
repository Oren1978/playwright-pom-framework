"""
Test data factories.

Every test asks a factory for data instead of copying payloads. Values are
unique per call, so tests never collide with each other, can run in any
order and in parallel, and a failure never leaves data that breaks the next run.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta

# Mirrors the product spec on purpose instead of importing app code: tests are an
# independent oracle. If the app and this list disagree, a test should fail.
ROOM_TYPES = ("Single", "Double", "Twin", "Family", "Suite")
_sequence = itertools.count(1)


@dataclass(frozen=True)
class RoomData:
    number: str
    type: str = "Double"
    price: int = 180
    accessible: bool = False

    def to_api(self) -> dict:
        return asdict(self)

    def but(self, **changes) -> RoomData:
        """Return a copy with some fields changed: rooms.but(price=250)."""
        return replace(self, **changes)


@dataclass(frozen=True)
class BookingData:
    room_id: int
    guest_name: str
    checkin: date
    checkout: date

    def to_api(self) -> dict:
        return {
            "room_id": self.room_id,
            "guest_name": self.guest_name,
            "checkin": self.checkin.isoformat(),
            "checkout": self.checkout.isoformat(),
        }


def unique_room_number() -> str:
    # Pattern ^[A-Za-z0-9-]+$, max 10 chars, unique across parallel workers.
    return f"R{uuid.uuid4().hex[:6].upper()}"


def a_room(**overrides) -> RoomData:
    n = next(_sequence)
    defaults = {
        "number": unique_room_number(),
        "type": ROOM_TYPES[n % len(ROOM_TYPES)],
        "price": 100 + (n % 9) * 25,
        "accessible": n % 2 == 0,
    }
    return RoomData(**{**defaults, **overrides})


def a_booking(
    room_id: int, *, starts_in_days: int = 30, nights: int = 3, guest_name: str | None = None
) -> BookingData:
    checkin = date.today() + timedelta(days=starts_in_days)
    return BookingData(
        room_id=room_id,
        guest_name=guest_name or f"Guest {next(_sequence)}",
        checkin=checkin,
        checkout=checkin + timedelta(days=nights),
    )
