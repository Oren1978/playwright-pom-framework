"""Base page object. Pages own every selector; tests only call intent-level methods."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


class BasePage:
    path: str = "/"

    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.goto(self.path)
        return self

    def expect_at(self, path: str | None = None) -> None:
        target = re.escape(path or self.path) + r"(\?.*)?$"
        expect(self.page).to_have_url(re.compile(target))
