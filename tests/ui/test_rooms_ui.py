"""Rooms screen behavior, verified against the API as the source of truth."""

import pytest

from api.client import HarborApi
from data.factories import a_room
from pages.rooms_page import RoomsPage


@pytest.mark.smoke
def test_room_created_in_ui_is_stored(rooms_page: RoomsPage, api: HarborApi, track_room):
    room = a_room()
    rooms_page.create(room)
    track_room(room.number)

    rooms_page.expect_status(f"Room {room.number} created")
    rooms_page.expect_room(room)
    stored = api.find_room(room.number)
    assert stored is not None
    assert {k: stored[k] for k in room.to_api()} == room.to_api()


def test_duplicate_number_shows_server_error(rooms_page: RoomsPage, room_factory):
    existing = room_factory()
    rooms_page.create(a_room(number=existing["number"]))
    rooms_page.expect_form_error(f"room {existing['number']} already exists")


def test_required_fields_are_validated(rooms_page: RoomsPage):
    rooms_page.create_button.click()
    rooms_page.expect_form_error("Room number and price are required")
