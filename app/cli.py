"""SiteUnit maintenance CLI.

  python -m app.cli db-info
  python -m app.cli backup [dest.zip|dest.db]
  python -m app.cli cleanup-logos
  python -m app.cli check-sites
  python -m app.cli refresh-metadata

Runs against the configured data dir (SITEUNIT_DATA_DIR / CLI overrides).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from . import db, logos, services
from .config import settings


def cmd_db_info(_: argparse.Namespace) -> int:
    print(db.db_info())
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    dest = args.dest or settings.backup_dir / (
        "siteunit-backup-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".db"
    )
    db.backup_db(dest)
    print(f"backed up to {dest}")
    return 0


def cmd_cleanup_logos(_: argparse.Namespace) -> int:
    removed = logos.garbage_collect(db.referenced_logos())
    print(f"removed {removed} orphan logo file(s)")
    return 0


def cmd_check_sites(_: argparse.Namespace) -> int:
    res = asyncio.run(services.check_health(None))
    counts: dict[str, int] = {}
    for r in res["results"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"checked {res['checked']}: {counts}")
    return 0


def cmd_refresh_metadata(_: argparse.Namespace) -> int:
    sites = db.list_sites(archived=False)
    ids = [s["id"] for s in sites]
    res = asyncio.run(services.refresh_metadata_bulk(ids))
    print(f"refreshed {res['updated']}/{res['checked']}")
    for r in res["results"]:
        if not r["ok"]:
            print(f"  id {r['id']}: {r['error']}")
    return 0


COMMANDS = {
    "db-info": cmd_db_info,
    "backup": cmd_backup,
    "cleanup-logos": cmd_cleanup_logos,
    "check-sites": cmd_check_sites,
    "refresh-metadata": cmd_refresh_metadata,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="SiteUnit maintenance")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("dest", nargs="?", help="backup destination (for backup)")
    args = parser.parse_args(argv)
    # ensure db is initialized
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logo_dir.mkdir(parents=True, exist_ok=True)
    db.init_db()
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
