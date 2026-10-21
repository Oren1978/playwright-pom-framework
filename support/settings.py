"""Single place where test configuration is read. Everything else imports from here."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    admin_user: str = os.environ.get("HARBOR_ADMIN_USER", "admin")
    admin_password: str = os.environ.get("HARBOR_ADMIN_PASSWORD", "harbor-demo")
    server_start_timeout_s: float = 10.0


SETTINGS = Settings()
