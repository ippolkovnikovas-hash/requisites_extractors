"""
Скрипт для создания недостающих __init__.py и папок в проекте.
Запускать из корня проекта: python fix_structure.py
"""
from pathlib import Path

dirs = [
    "app/exporters",
    "app/core",
    "app/schemas",
    "app/services",
    "app/validators",
    "app/llm",
    "app/web",
    "scripts",
    "logs",
    "uploads",
    "exports",
    "processed",
]

for d in dirs:
    path = Path(d)
    path.mkdir(parents=True, exist_ok=True)
    init = path / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
        print(f"  created  {init}")
    else:
        print(f"  exists   {init}")

print("\nDone.")