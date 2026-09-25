"""
Веб-слой приложения.

Собственной фабрики здесь больше нет: приложение одно, и собирается оно в
`app.main.create_app()` — вместе с API. Эта функция оставлена как совместимый
псевдоним, чтобы `from app.web import create_app` продолжал работать.

Импорт внутри функции, а не на уровне модуля: `app.main` импортирует
`app.web.routes`, и импорт на верхнем уровне замкнул бы цикл.
"""

from flask import Flask


def create_app() -> Flask:
    from app.main import create_app as _create_app

    return _create_app()
