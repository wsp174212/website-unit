"""SiteUnit configuration.

Priority: CLI args > environment variables > defaults.

All runtime-affecting knobs live here so tests can override the data
directory (and therefore the SQLite file + logo cache) via ``configure()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# Cloud metadata endpoints are never legitimate navigation targets, even for a
# local-first tool that otherwise permits private/LAN addresses. Blocking these
# unconditionally closes the worst SSRF hole (instance credential leak).
_ALWAYS_BLOCKED_HOSTS = {
    "169.254.169.254",       # AWS / Aliyun / GCP IMDS (IPv4)
    "metadata.google.internal",  # GCP IMDS (DNS)
    "metadata.azure.com",    # Azure IMDS
}


@dataclass
class Settings:
    # server
    host: str = "127.0.0.1"
    port: int =8010
    reload: bool = False

    # storage
    data_dir: Path = field(default_factory=lambda: _project_root() / "data")
    db_path: Path = field(init=False)
    logo_dir: Path = field(init=False)
    backup_dir: Path = field(init=False)

    # fetching (metadata + logo)
    allow_private_network_fetch: bool = True
    verify_tls: bool = True
    fetch_connect_timeout: float = 5.0
    fetch_read_timeout: float = 10.0
    fetch_redirect_limit: int = 5
    max_html_size: int = 2 * 1024 * 1024
    max_logo_size: int = 512 * 1024

    # health check
    health_concurrency: int = 6
    health_request_timeout: float = 8.0

    # logging
    log_level: str = "INFO"

    # ui prefs are client-side; nothing here.

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.db_path = self.data_dir / "sites.db"
        self.logo_dir = self.data_dir / "logos"
        self.backup_dir = self.data_dir / "backups"

    # ---- environment loading ----
    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        if v := os.environ.get("SITEUNIT_HOST"):
            s.host = v
        if v := os.environ.get("SITEUNIT_PORT"):
            try:
                s.port = int(v)
            except ValueError:
                pass
        if v := os.environ.get("SITEUNIT_DATA_DIR"):
            s.data_dir = Path(v)
        if v := os.environ.get("SITEUNIT_ALLOW_PRIVATE_NETWORK_FETCH"):
            s.allow_private_network_fetch = v.lower() in ("1", "true", "yes")
        if v := os.environ.get("SITEUNIT_VERIFY_TLS"):
            s.verify_tls = v.lower() in ("1", "true", "yes")
        if v := os.environ.get("SITEUNIT_FETCH_CONNECT_TIMEOUT"):
            try:
                s.fetch_connect_timeout = float(v)
            except ValueError:
                pass
        if v := os.environ.get("SITEUNIT_FETCH_READ_TIMEOUT"):
            try:
                s.fetch_read_timeout = float(v)
            except ValueError:
                pass
        if v := os.environ.get("SITEUNIT_MAX_HTML_SIZE"):
            try:
                s.max_html_size = int(v)
            except ValueError:
                pass
        if v := os.environ.get("SITEUNIT_MAX_LOGO_SIZE"):
            try:
                s.max_logo_size = int(v)
            except ValueError:
                pass
        if v := os.environ.get("SITEUNIT_LOG_LEVEL"):
            s.log_level = v
        s.__post_init__()
        return s

    def apply(self, **overrides) -> "Settings":
        """Return a new Settings with ``overrides`` applied (re-deriving paths)."""
        merged = {**self.__dict__}
        for k, v in overrides.items():
            if v is not None and hasattr(self, k):
                merged[k] = v
        new = Settings()
        for k, v in merged.items():
            if k in ("db_path", "logo_dir", "backup_dir"):
                continue
            setattr(new, k, v)
        new.__post_init__()
        return new


# module-level singleton; run.py and tests call configure()
settings: Settings = Settings.from_env()


def configure(**overrides) -> Settings:
    """Override the singleton in place (so ``from .config import settings``
    holders see the change). Used by run.py CLI and tests."""
    for k, v in overrides.items():
        if v is None:
            continue
        if k in ("db_path", "logo_dir", "backup_dir"):
            continue
        if hasattr(settings, k):
            setattr(settings, k, v)
    settings.__post_init__()  # re-derive db_path / logo_dir / backup_dir
    return settings


def always_blocked_hosts() -> set[str]:
    return set(_ALWAYS_BLOCKED_HOSTS)
