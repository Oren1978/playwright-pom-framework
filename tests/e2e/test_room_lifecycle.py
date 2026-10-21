"""
Hybrid end-to-end flows: set up through the API (fast, reliable), act and
verify in the UI (what users see), confirm through the API (what is stored).
"""

import pytest

from api.client import HarborApi
from data.factories import RoomData, a_booking, a_room
from pages.rooms_page import RoomsPage


@pytest.mark.smoke
def test_full_room_lifecycle(api: HarborApi, room_factory, admin_page):
    original = a_room()
    created = room_factory(original)

    rooms = RoomsPage(admin_page).open()
    rooms.expect_room(original)

    changed = original.but(number=a_room().number, type="Suite", price=420, accessible=True)
    rooms.edit(original.number, changed)
    rooms.expect_status(f"Room {changed.number} updated")
    rooms.expect_room(changed)
    rooms.expect_no_room(original.number)
    assert (
        RoomData(**{k: v for k, v in api.get_room(created["id"]).json().items() if k != "id"})
        == changed
    )

    rooms.delete(changed.number)
    rooms.expect_status(f"Room {changed.number} deleted")
    rooms.expect_no_room(changed.number)
    assert api.get_room(created["id"]).status == 404


def test_room_with_booking_cannot_be_deleted_from_ui(
    api: HarborApi, room_factory, booking_factory, admin_page
):
    room = room_factory()
    booking_factory(a_booking(room["id"]))

    rooms = RoomsPage(admin_page).open()
    rooms.delete(room["number"])
    rooms.expect_form_error("room has bookings")
    assert api.get_room(room["id"]).status == 200


def test_ui_reflects_rooms_created_elsewhere(room_factory, admin_page):
    rooms = RoomsPage(admin_page).open()
    newcomer = a_room()
    room_factory(newcomer)
    admin_page.reload()
    rooms.expect_room(newcomer)
