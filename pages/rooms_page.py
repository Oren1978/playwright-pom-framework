from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from data.factories import RoomData
from pages.base_page import BasePage


class RoomsPage(BasePage):
    path = "/admin/rooms"

    def __init__(self, page: Page):
        super().__init__(page)
        self.heading = page.get_by_role("heading", name="Rooms")
        self.number = page.get_by_label("Number")
        self.type = page.get_by_label("Type")
        self.price = page.get_by_label("Price")
        self.accessible = page.get_by_label("Accessible")
        self.create_button = page.get_by_role("button", name="Create room")
        self.save_button = page.get_by_role("button", name="Save changes")
        self.form_error = page.get_by_role("alert")
        self.status = page.get_by_role("status")
        self.table = page.get_by_role("table", name="Rooms")
        self.logout_button = page.get_by_role("button", name="Log out")

    def open(self) -> RoomsPage:
        super().open()
        # The table is filled by an async fetch; wait for the result, not for time.
        expect(self.table.get_by_text("Loading...")).to_have_count(0)
        return self

    # ---- queries
    def row(self, number: str) -> Locator:
        return self.table.locator(f'tr[data-room-number="{number}"]')

    # ---- actions
    def _fill(self, room: RoomData) -> None:
        self.number.fill(room.number)
        self.type.select_option(room.type)
        self.price.fill(str(room.price))
        self.accessible.set_checked(room.accessible)

    def create(self, room: RoomData) -> None:
        self._fill(room)
        self.create_button.click()

    def edit(self, current_number: str, updated: RoomData) -> None:
        self.page.get_by_role("button", name=f"Edit room {current_number}").click()
        expect(self.number).to_have_value(current_number)
        self._fill(updated)
        self.save_button.click()

    def delete(self, number: str) -> None:
        self.page.get_by_role("button", name=f"Delete room {number}").click()

    def logout(self) -> None:
        self.logout_button.click()

    # ---- assertions (web-first: they retry until the UI settles)
    def expect_room(self, room: RoomData) -> None:
        expect(self.row(room.number).get_by_role("cell")).to_have_text(
            [
                room.number,
                room.type,
                str(room.price),
                "Yes" if room.accessible else "No",
                "Edit Delete",
            ]
        )

    def expect_no_room(self, number: str) -> None:
        expect(self.row(number)).to_have_count(0)

    def expect_status(self, text: str) -> None:
        expect(self.status).to_have_text(text)

    def expect_form_error(self, text: str) -> None:
        expect(self.form_error).to_contain_text(text)
