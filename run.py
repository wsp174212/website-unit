"""Launch SiteUnit.

  python run.py                 # defaults from env / built-ins
  python run.py --port 9000     # CLI overrides env
  python run.py --host 0.0.0.0  # expose to LAN
  python run.py --reload        # dev auto-reload

Priority: CLI args > SITEUNIT_* env vars > defaults.
"""

import argparse

import uvicorn

from app import config


def main() -> None:
    parser = argparse.ArgumentParser(description="SiteUnit server")
    parser.add_argument("--host", default=None, help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default 8000)")
    parser.add_argument("--reload", action="store_true", help="auto-reload for development")
    args = parser.parse_args()

    overrides = {}
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    overrides["reload"] = args.reload
    config.configure(**overrides)

    uvicorn.run(
        "app.main:app",
        host=config.settings.host,
        port=config.settings.port,
        reload=config.settings.reload,
    )


if __name__ == "__main__":
    main()
