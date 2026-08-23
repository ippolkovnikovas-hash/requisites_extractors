"""
Запуск приложения — единственная точка входа.

Приложение локальное и однопользовательское, поэтому:
  - слушает `127.0.0.1`, а не `0.0.0.0` — наружу в сеть ничего не торчит;
  - открывает браузер само, чтобы запуск был в один шаг;
  - debug выключен по умолчанию (включается через FLASK_DEBUG в .env).

Использование:
  python scripts/run_app.py
  python scripts/run_app.py --no-browser
"""

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()


def _open_browser(url: str) -> None:
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Requisites Extractor")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="не открывать браузер автоматически",
    )
    parser.add_argument("--host", default=settings.flask_host)
    parser.add_argument("--port", type=int, default=settings.flask_port)
    args = parser.parse_args()

    setup_logging()
    settings.ensure_dirs()

    url = f"http://{args.host}:{args.port}/"
    print(f"\n  Requisites Extractor запущен: {url}")
    print("  Остановить — Ctrl+C\n")

    if not args.no_browser and not settings.flask_debug:
        _open_browser(url)

    app.run(host=args.host, port=args.port, debug=settings.flask_debug)


if __name__ == "__main__":
    main()
