from __future__ import annotations

import logging
import sys

import uvicorn

from vocab_bot.config import Settings, load_dotenv_if_present
from vocab_bot.webapi.app import create_app


def main() -> None:
    load_dotenv_if_present()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc

    uvicorn.run(
        create_app(settings),
        host=settings.webapp_api_host,
        port=settings.webapp_api_port,
        proxy_headers=True,
        log_config=None,
    )


if __name__ == "__main__":
    main()
