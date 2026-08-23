"""
Устаревшая точка входа. Оставлена для совместимости — используйте
`python scripts/run_app.py`.

Раньше здесь поднималось отдельное приложение только с API, на `0.0.0.0` и с
включённым debug. Теперь приложение одно (веб-интерфейс + API), слушает
`127.0.0.1` и запускается через `run_app`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_app import app, main  # noqa: E402,F401

if __name__ == "__main__":
    print("run_dev.py устарел — используйте: python scripts/run_app.py")
    main()
