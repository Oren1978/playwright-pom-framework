"""
Harbor Hotel: a small, self-contained system under test.

Shipped inside the repository on purpose. The test suite starts it
automatically, so every run is offline, deterministic and independent of
public demo sites that can be slow, rate limited or down.

Business rules live here, once (single source of truth):
* room numbers are unique
* a booking needs checkout after checkin
* bookings for the same room may not overlap
* a room with bookings cannot be deleted
"""

from __future__ import annotations

import asyncio
import os
import secrets
from datetime import date
from itertools import count
from pathlib import Path
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator, model_validator

STATIC = Path(__file__).parent / "static"

# Demo-only credentials. Override with environment variables; never reuse real ones.
ADMIN_USER = os.environ.get("HARBOR_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("HARBOR_ADMIN_PASSWORD", "harbor-demo")

ROOM_TYPES = ("Single", "Double", "Twin", "Family", "Suite")


class RoomIn(BaseModel):
    number: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    type: str
    price: int = Field(gt=0, le=10_000)
    accessible: bool = False

    @field_validator("type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in ROOM_TYPES:
            raise ValueError(f"type must be one of {', '.join(ROOM_TYPES)}")
        return value


class Room(RoomIn):
    id: int


class BookingIn(BaseModel):
    room_id: int
    guest_name: str = Field(min_length=2, max_length=60)
    checkin: date
    checkout: date

    @model_validator(mode="after")
    def checkout_after_checkin(self) -> BookingIn:
        if self.checkout <= self.checkin:
            raise ValueError("checkout must be after checkin")
        return self


class Booking(BookingIn):
    id: int


class Credentials(BaseModel):
    username: str
    password: str


class Store:
    """In-memory store guarded by a lock: enough for a demo, safe for parallel tests."""

    def __init__(self) -> None:
        self.lock = Lock()
        self.rooms: dict[int, Room] = {}
        self.bookings: dict[int, Booking] = {}
        self.tokens: set[str] = set()
        self._room_ids = count(1)
        self._booking_ids = count(1)

    def next_room_id(self) -> int:
        return next(self._room_ids)

    def next_booking_id(self) -> int:
        return next(self._booking_ids)


store = Store()
app = FastAPI(title="Harbor Hotel (system under test)")


@app.middleware("http")
async def injected_latency(request: Request, call_next):
    """Optional API latency (HARBOR_LATENCY_MS) used in CI to prove the suite
    has no timing assumptions: tests must pass unchanged on a slow backend."""
    delay_ms = int(os.environ.get("HARBOR_LATENCY_MS", "0") or 0)
    if delay_ms and request.url.path.startswith("/api/"):
        await asyncio.sleep(delay_ms / 1000)
    return await call_next(request)


def require_auth(request: Request) -> None:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() or request.cookies.get("token", "")
    if token not in store.tokens:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")


# ------------------------------------------------------------------ auth


@app.post("/api/auth/login")
def login(creds: Credentials, response: Response) -> dict:
    ok_user = secrets.compare_digest(creds.username, ADMIN_USER)
    ok_pass = secrets.compare_digest(creds.password, ADMIN_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password")
    token = secrets.token_urlsafe(24)
    store.tokens.add(token)
    response.set_cookie("token", token, httponly=True, samesite="strict")
    return {"token": token}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    store.tokens.discard(request.cookies.get("token", ""))
    response.delete_cookie("token")
    return {"ok": True}


# ------------------------------------------------------------------ rooms


@app.get("/api/rooms")
def list_rooms() -> list[Room]:
    return sorted(store.rooms.values(), key=lambda r: r.id)


@app.get("/api/rooms/{room_id}")
def get_room(room_id: int) -> Room:
    if room_id not in store.rooms:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room not found")
    return store.rooms[room_id]


def _ensure_unique_number(number: str, exclude_id: int | None = None) -> None:
    if any(r.number == number and r.id != exclude_id for r in store.rooms.values()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"room {number} already exists")


@app.post("/api/rooms", status_code=201, dependencies=[Depends(require_auth)])
def create_room(data: RoomIn) -> Room:
    with store.lock:
        _ensure_unique_number(data.number)
        room = Room(id=store.next_room_id(), **data.model_dump())
        store.rooms[room.id] = room
    return room


@app.put("/api/rooms/{room_id}", dependencies=[Depends(require_auth)])
def update_room(room_id: int, data: RoomIn) -> Room:
    with store.lock:
        get_room(room_id)
        _ensure_unique_number(data.number, exclude_id=room_id)
        room = Room(id=room_id, **data.model_dump())
        store.rooms[room_id] = room
    return room


@app.delete("/api/rooms/{room_id}", status_code=204, dependencies=[Depends(require_auth)])
def delete_room(room_id: int) -> Response:
    with store.lock:
        get_room(room_id)
        if any(b.room_id == room_id for b in store.bookings.values()):
            raise HTTPException(status.HTTP_409_CONFLICT, "room has bookings")
        del store.rooms[room_id]
    return Response(status_code=204)


# ------------------------------------------------------------------ bookings


@app.get("/api/bookings", dependencies=[Depends(require_auth)])
def list_bookings(room_id: int | None = None) -> list[Booking]:
    items = sorted(store.bookings.values(), key=lambda b: b.id)
    return [b for b in items if room_id is None or b.room_id == room_id]


@app.post("/api/bookings", status_code=201)
def create_booking(data: BookingIn) -> Booking:
    with store.lock:
        get_room(data.room_id)
        for b in store.bookings.values():
            overlaps = data.checkin < b.checkout and b.checkin < data.checkout
            if b.room_id == data.room_id and overlaps:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "room is already booked for these dates"
                )
        booking = Booking(id=store.next_booking_id(), **data.model_dump())
        store.bookings[booking.id] = booking
    return booking


@app.delete("/api/bookings/{booking_id}", status_code=204, dependencies=[Depends(require_auth)])
def delete_booking(booking_id: int) -> Response:
    with store.lock:
        if store.bookings.pop(booking_id, None) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "booking not found")
    return Response(status_code=204)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ------------------------------------------------------------------ pages


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse("/admin/rooms")


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(STATIC / "login.html")


@app.get("/admin/rooms")
def rooms_page(request: Request) -> Response:
    if request.cookies.get("token", "") not in store.tokens:
        return RedirectResponse("/login?next=/admin/rooms")
    # no-store: after logout the browser must not show this page from its cache.
    # (Found by tests/ui/test_login.py::test_logout_ends_the_session.)
    return FileResponse(STATIC / "rooms.html", headers={"Cache-Control": "no-store"})


@app.get("/static/{name}")
def static_file(name: str) -> FileResponse:
    path = (STATIC / name).resolve()
    if path.parent != STATIC.resolve() or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return FileResponse(path)
