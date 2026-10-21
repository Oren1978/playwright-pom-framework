"""Rooms API: contract, validation boundaries and business rules."""

import pytest

from api.client import HarborApi
from data.factories import a_booking, a_room


@pytest.mark.smoke
def test_room_crud_round_trip(api: HarborApi, room_factory, created_room_ids):
    room = a_room()
    created = room_factory(room)
    assert created == {"id": created["id"], **room.to_api()}

    updated = room.but(price=room.price + 50, accessible=not room.accessible)
    response = api.put_room(created["id"], updated.to_api())
    assert response.status == 200
    assert api.get_room(created["id"]).json()["price"] == updated.price

    assert api.delete_room(created["id"]).status == 204
    assert api.get_room(created["id"]).status == 404


def test_duplicate_room_number_is_rejected(api: HarborApi, room_factory):
    existing = room_factory()
    response = api.post_room(a_room(number=existing["number"]).to_api())
    assert response.status == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.parametrize(
    "price, expected",
    [
        (0, 422),
        (1, 201),
        (10_000, 201),
        (10_001, 422),
        (-5, 422),
    ],
    ids=["zero", "min", "max", "above-max", "negative"],
)
def test_price_boundaries(api: HarborApi, created_room_ids, price, expected):
    response = api.post_room(a_room(price=price).to_api())
    assert response.status == expected
    if response.ok:
        created_room_ids.append(response.json()["id"])


@pytest.mark.parametrize(
    "field, value",
    [
        ("type", "Penthouse"),
        ("number", ""),
        ("number", "has space"),
        ("number", "X" * 11),
    ],
    ids=["unknown-type", "empty-number", "invalid-chars", "too-long"],
)
def test_invalid_room_fields_are_rejected(api: HarborApi, field, value):
    payload = {**a_room().to_api(), field: value}
    assert api.post_room(payload).status == 422


def test_writes_require_authentication(anonymous_api: HarborApi):
    assert anonymous_api.post_room(a_room().to_api()).status == 401


def test_room_with_bookings_cannot_be_deleted(api: HarborApi, room_factory, booking_factory):
    room = room_factory()
    booking_factory(a_booking(room["id"]))
    response = api.delete_room(room["id"])
    assert response.status == 409
    assert api.get_room(room["id"]).status == 200
