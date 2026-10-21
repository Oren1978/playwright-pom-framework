"""Bookings API: date rules and the no-overlap business rule."""

from datetime import timedelta

import pytest

from api.client import HarborApi
from data.factories import a_booking


@pytest.mark.smoke
def test_guest_can_book_a_room(api: HarborApi, room_factory, booking_factory):
    room = room_factory()
    booking = booking_factory(a_booking(room["id"]))
    assert [b["id"] for b in api.list_bookings(room_id=room["id"])] == [booking["id"]]


def test_checkout_must_be_after_checkin(api: HarborApi, room_factory):
    room = room_factory()
    bad = a_booking(room["id"])
    payload = {**bad.to_api(), "checkout": bad.checkin.isoformat()}
    response = api.post_booking(payload)
    assert response.status == 422
    assert "checkout must be after checkin" in response.text()


@pytest.mark.parametrize(
    "shift_days, nights",
    [
        (0, 3),  # identical stay
        (1, 1),  # inside existing stay
        (-1, 2),  # overlaps the first night
        (2, 4),  # overlaps the last night
        (-2, 7),  # encloses the existing stay
    ],
    ids=["identical", "inside", "overlaps-start", "overlaps-end", "encloses"],
)
def test_overlapping_booking_is_rejected(
    api: HarborApi, room_factory, booking_factory, shift_days, nights
):
    room = room_factory()
    first = a_booking(room["id"], starts_in_days=30, nights=3)
    booking_factory(first)
    clash = a_booking(room["id"], starts_in_days=30 + shift_days, nights=nights)
    assert api.post_booking(clash.to_api()).status == 409


def test_back_to_back_bookings_are_allowed(api: HarborApi, room_factory, booking_factory):
    room = room_factory()
    first = booking_factory(a_booking(room["id"], starts_in_days=30, nights=3))
    second = a_booking(room["id"], starts_in_days=33, nights=2)
    assert second.checkin.isoformat() == first["checkout"]
    assert api.post_booking(second.to_api()).status == 201


def test_same_dates_in_another_room_are_allowed(api: HarborApi, room_factory, booking_factory):
    room_a, room_b = room_factory(), room_factory()
    booking_factory(a_booking(room_a["id"]))
    assert api.post_booking(a_booking(room_b["id"]).to_api()).status == 201


def test_booking_an_unknown_room_returns_404(api: HarborApi):
    assert api.post_booking(a_booking(room_id=999_999).to_api()).status == 404


def test_booking_dates_round_trip_exactly(api: HarborApi, room_factory, booking_factory):
    room = room_factory()
    data = a_booking(room["id"], starts_in_days=45, nights=1)
    created = booking_factory(data)
    assert created["checkin"] == data.checkin.isoformat()
    assert created["checkout"] == (data.checkin + timedelta(days=1)).isoformat()
