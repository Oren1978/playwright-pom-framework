"""
Fixtures: the only place that knows how tests get an app, a client, a
logged-in browser and clean data. Tests declare what they need by name.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import APIRequestContext, BrowserContext, Page, Playwright

from api.client import HarborApi
from data.factories import BookingData, RoomData, a_room
from pages.login_page import LoginPage
from pages.rooms_page import RoomsPage
from support.server import running_app
from support.settings import SETTINGS

LAYER_BY_FOLDER = {"api": "api", "ui": "ui", "e2e": "e2e"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Markers by folder, so a test cannot be filed in one layer and tagged as another."""
    for item in items:
        folder = Path(str(item.fspath)).parent.name
        if folder in LAYER_BY_FOLDER:
            item.add_marker(getattr(pytest.mark, LAYER_BY_FOLDER[folder]))
        if not item.get_closest_marker("smoke"):
            item.add_marker(pytest.mark.regression)


# ------------------------------------------------------------------ report


def pytest_html_report_title(report) -> None:
    report.title = "Harbor Hotel test report"


@pytest.hookimpl(optionalhook=True)
def pytest_metadata(metadata: dict) -> None:
    """Report what matters for reproducing a run, and nothing from the local machine."""
    for key in [k for k in metadata if k not in ("Python", "Platform", "Plugins")]:
        metadata.pop(key)
    metadata["System under test"] = "Harbor Hotel (bundled app or --base-url)"
    metadata["Injected API latency"] = f"{os.environ.get('HARBOR_LATENCY_MS', '0') or '0'} ms"


# ------------------------------------------------------------------ app


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> Iterator[str]:
    """--base-url targets an existing deployment; otherwise start the bundled app."""
    external = pytestconfig.getoption("base_url")
    if external:
        yield external.rstrip("/")
        return
    with running_app(SETTINGS.server_start_timeout_s) as url:
        yield url


# ------------------------------------------------------------------ API


@pytest.fixture(scope="session")
def anonymous_api(playwright: Playwright, base_url: str) -> Iterator[HarborApi]:
    ctx = playwright.request.new_context(base_url=base_url)
    yield HarborApi(ctx)
    ctx.dispose()


def _new_admin_token(playwright: Playwright, base_url: str) -> str:
    """Log in from a throwaway context. Logging in through a shared context would
    store the session cookie in it and silently turn an anonymous client into an
    authenticated one (a real bug this suite had before this helper existed)."""
    ctx = playwright.request.new_context(base_url=base_url)
    try:
        return HarborApi(ctx).token(SETTINGS.admin_user, SETTINGS.admin_password)
    finally:
        ctx.dispose()


@pytest.fixture(scope="session")
def admin_token(playwright: Playwright, base_url: str) -> str:
    """Shared session for the whole run. Tests that end a session must use
    `own_session_page` instead, or every test after them loses its login."""
    return _new_admin_token(playwright, base_url)


@pytest.fixture(scope="session")
def admin_request(
    playwright: Playwright, base_url: str, admin_token: str
) -> Iterator[APIRequestContext]:
    ctx = playwright.request.new_context(
        base_url=base_url, extra_http_headers={"Authorization": f"Bearer {admin_token}"}
    )
    yield ctx
    ctx.dispose()


@pytest.fixture(scope="session")
def api(admin_request: APIRequestContext) -> HarborApi:
    return HarborApi(admin_request)


# ------------------------------------------------------------------ data with cleanup


@pytest.fixture
def created_room_ids(api: HarborApi) -> Iterator[list[int]]:
    """Every room a test creates is registered here and removed afterwards,
    together with its bookings, even when the test fails."""
    ids: list[int] = []
    yield ids
    for room_id in ids:
        for booking in api.list_bookings(room_id=room_id):
            api.delete_booking(booking["id"])
        api.delete_room(room_id)  # 404 is fine: the test may have deleted it


@pytest.fixture
def room_factory(api: HarborApi, created_room_ids: list[int]) -> Callable[..., dict]:
    def create(room: RoomData | None = None, **overrides) -> dict:
        created = api.create_room(room or a_room(**overrides))
        created_room_ids.append(created["id"])
        return created

    return create


@pytest.fixture
def track_room(api: HarborApi, created_room_ids: list[int]) -> Callable[[str], None]:
    """For rooms created through the UI: register them for cleanup by number."""

    def track(number: str) -> None:
        room = api.find_room(number)
        if room:
            created_room_ids.append(room["id"])

    return track


@pytest.fixture
def booking_factory(api: HarborApi) -> Callable[[BookingData], dict]:
    return api.create_booking  # cleaned up through the room that owns it


# ------------------------------------------------------------------ browser


@pytest.fixture
def admin_context(context: BrowserContext, base_url: str, admin_token: str) -> BrowserContext:
    """Logged in through the API, not the UI: fast and independent of the login
    screen. The login screen itself is covered once, in tests/ui/test_login.py."""
    context.add_cookies([{"name": "token", "value": admin_token, "url": base_url}])
    return context


@pytest.fixture
def admin_page(admin_context: BrowserContext) -> Page:
    return admin_context.new_page()


@pytest.fixture
def own_session_page(context: BrowserContext, playwright: Playwright, base_url: str) -> Page:
    """A page logged in with its own, private session: safe to log out."""
    token = _new_admin_token(playwright, base_url)
    context.add_cookies([{"name": "token", "value": token, "url": base_url}])
    return context.new_page()


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture
def rooms_page(admin_page: Page) -> RoomsPage:
    return RoomsPage(admin_page).open()
