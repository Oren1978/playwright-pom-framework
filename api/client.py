"""
API client layer, built on Playwright's own APIRequestContext.

Using Playwright for HTTP (instead of a second library) means API and UI
steps share one tool, one trace and one report. Tests talk to this client,
never to raw URLs, so an endpoint change is fixed in exactly one place.
"""

from __future__ import annotations

from playwright.sync_api import APIRequestContext, APIResponse

from data.factories import BookingData, RoomData


class ApiError(AssertionError):
    pass


class HarborApi:
    def __init__(self, request: APIRequestContext):
        self.request = request

    # ---- helpers
    @staticmethod
    def _expect(response: APIResponse, status: int) -> APIResponse:
        if response.status != status:
            raise ApiError(
                f"{response.url} returned {response.status}, expected {status}: "
                f"{response.text()[:300]}"
            )
        return response

    # ---- auth
    def login(self, username: str, password: str) -> APIResponse:
        return self.request.post(
            "/api/auth/login", data={"username": username, "password": password}
        )

    def token(self, username: str, password: str) -> str:
        return self._expect(self.login(username, password), 200).json()["token"]

    # ---- rooms (raw responses for negative tests, typed helpers for setup)
    def post_room(self, payload: dict) -> APIResponse:
        return self.request.post("/api/rooms", data=payload)

    def create_room(self, room: RoomData) -> dict:
        return self._expect(self.post_room(room.to_api()), 201).json()

    def get_room(self, room_id: int) -> APIResponse:
        return self.request.get(f"/api/rooms/{room_id}")

    def list_rooms(self) -> list[dict]:
        return self._expect(self.request.get("/api/rooms"), 200).json()

    def find_room(self, number: str) -> dict | None:
        return next((r for r in self.list_rooms() if r["number"] == number), None)

    def put_room(self, room_id: int, payload: dict) -> APIResponse:
        return self.request.put(f"/api/rooms/{room_id}", data=payload)

    def delete_room(self, room_id: int) -> APIResponse:
        return self.request.delete(f"/api/rooms/{room_id}")

    # ---- bookings
    def post_booking(self, payload: dict) -> APIResponse:
        return self.request.post("/api/bookings", data=payload)

    def create_booking(self, booking: BookingData) -> dict:
        return self._expect(self.post_booking(booking.to_api()), 201).json()

    def list_bookings(self, room_id: int | None = None) -> list[dict]:
        params = {"room_id": room_id} if room_id is not None else None
        return self._expect(self.request.get("/api/bookings", params=params), 200).json()

    def delete_booking(self, booking_id: int) -> APIResponse:
        return self.request.delete(f"/api/bookings/{booking_id}")
