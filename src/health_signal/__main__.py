"""Local run entry point: `python -m health_signal` / the `health-signal` console script.

For real deployment (e.g. Posit Connect) a consumer serves the `create_app(config)` ASGI object
directly; this launcher is a development/demo convenience.
"""
import argparse

import uvicorn

from .app import create_app
from .config import load_config


def _parse(argv=None):
    p = argparse.ArgumentParser(prog="health-signal", description="Run the health-signal dashboard.")
    p.add_argument("--config", default="dashboard.yaml", help="Path to the dashboard config YAML.")
    p.add_argument("--host", default="127.0.0.1", help="Bind host.")
    p.add_argument("--port", type=int, default=8000, help="Bind port.")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse(argv)
    uvicorn.run(create_app(load_config(args.config)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
