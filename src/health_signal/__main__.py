"""Run entry point: `python -m health_signal` / the `health-signal` console script.

`serve` (the default) runs the dashboard; `assess` writes the Status/Trend/phase tables from the feeds
(spec §6.3.1). For real deployment (e.g. Posit Connect) a consumer serves the `create_app(config)` ASGI
object directly; `serve` is a development/demo convenience.
"""
import argparse
import logging
import sys

import uvicorn

from .analytics import assess
from .analytics.store import SettingsChanged
from .app import create_app
from .config import load_config

_COMMANDS = ("serve", "assess")


def _parse(argv=None):
    p = argparse.ArgumentParser(prog="health-signal", description="Run the health-signal dashboard.")
    commands = p.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the dashboard (the default).")
    serve.add_argument("--config", default="dashboard.yaml", help="Path to the dashboard config YAML.")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve.add_argument("--port", type=int, default=8000, help="Bind port.")
    run = commands.add_parser("assess", help="Write Status/Trend/phase tables from the feeds (needs R + aedseo).")
    run.add_argument("--config", default="dashboard.yaml", help="Path to the dashboard config YAML.")
    run.add_argument("--full", action="store_true", help="Recompute every week instead of only new ones.")
    run.add_argument("--jobs", type=int, default=1, help="Series assessed in parallel processes.")
    argv = list(sys.argv[1:] if argv is None else argv)
    # A bare `health-signal --config ...` predates the subcommands and still serves.
    if not argv or (argv[0] not in _COMMANDS and argv[0] not in ("-h", "--help")):
        argv.insert(0, "serve")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse(argv)
    if args.command == "serve":
        uvicorn.run(create_app(load_config(args.config)), host=args.host, port=args.port)
        return
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        assess(load_config(args.config), full=args.full, jobs=args.jobs)
    except (SettingsChanged, RuntimeError, ValueError) as e:
        # A scheduled run must fail visibly, with the reason rather than a traceback.
        print(f"health-signal assess: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
