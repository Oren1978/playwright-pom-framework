"""The login screen: the only place the UI login flow is exercised."""

import pytest
from playwright.sync_api import expect

from pages.login_page import LoginPage
from pages.rooms_page import RoomsPage
from support.settings import SETTINGS


@pytest.mark.smoke
def test_admin_can_sign_in(login_page: LoginPage):
    login_page.open()
    login_page.login(SETTINGS.admin_user, SETTINGS.admin_password)
    rooms = RoomsPage(login_page.page)
    rooms.expect_at()
    expect(rooms.heading).to_be_visible()


@pytest.mark.parametrize(
    "username, password",
    [
        ("admin", "wrong-password"),
        ("nobody", SETTINGS.admin_password),
    ],
    ids=["wrong-password", "unknown-user"],
)
def test_wrong_credentials_show_a_generic_error(login_page: LoginPage, username, password):
    login_page.open()
    login_page.login(username, password)
    # Same message for both cases: the UI must not reveal which part was wrong.
    login_page.expect_error("Invalid username or password")
    login_page.expect_at()


def test_empty_form_is_validated_before_any_request(login_page: LoginPage):
    requests: list[str] = []
    login_page.page.on("request", lambda r: requests.append(r.url))
    login_page.open()
    requests.clear()
    login_page.login("", "")
    login_page.expect_error("Username and password are required")
    assert not [u for u in requests if "/api/auth/login" in u]


def test_admin_area_redirects_anonymous_users_to_login(page):
    page.goto(RoomsPage.path)
    LoginPage(page).expect_at()


def test_logout_ends_the_session(own_session_page):
    rooms_page = RoomsPage(own_session_page).open()
    rooms_page.logout()
    LoginPage(rooms_page.page).expect_at()
    rooms_page.page.goto(RoomsPage.path)
    LoginPage(rooms_page.page).expect_at()
