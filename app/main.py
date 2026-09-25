"""
Единая фабрика Flask-приложения.

Раньше фабрик было две — `app.main` только с API и `app.web` только с
интерфейсом, — и поднять их одной командой было нельзя. Теперь регистрируются
оба блюпринта: веб-интерфейс на `/`, JSON API на `/api`.

Обработчики ошибок отдают JSON только для запросов к `/api`. Веб-формы
возвращают свои коды статуса напрямую из view (например, 422 при неподтверждённой
жёсткой ошибке в `/generate`), поэтому до обработчиков не доходят — но если
что-то упадёт в веб-части, пользователь увидит страницу, а не JSON.
"""

import os

from flask import Flask, jsonify, render_template, request, send_from_directory

from app.api.routes_health import health_bp
from app.api.routes_upload import upload_bp
from app.config import settings
from app.web.routes import web_bp

_ERROR_TITLES = {
    400: "Некорректный запрос",
    404: "Страница не найдена",
    413: "Файл слишком большой",
    422: "Данные не прошли проверку",
    500: "Внутренняя ошибка",
    503: "Сервис недоступен",
}


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "web", "templates"),
    )

    app.config["SECRET_KEY"] = settings.flask_secret_key
    app.config["UPLOAD_FOLDER"] = str(settings.upload_folder.resolve())
    app.config["EXPORT_FOLDER"] = str(settings.exports_folder.resolve())
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_size_mb * 1024 * 1024

    app.register_blueprint(web_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp)

    for code in _ERROR_TITLES:
        app.register_error_handler(code, _make_error_handler(code))

    @app.route("/test")
    def test_ui():
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), "static"), "test_ui.html"
        )

    return app


def _make_error_handler(code: int):
    def handler(error):
        if request.path.startswith("/api"):
            return (
                jsonify(
                    {
                        "error": _ERROR_TITLES[code],
                        "code": code,
                        "details": str(error),
                    }
                ),
                code,
            )
        return (
            render_template(
                "error.html", code=code, title=_ERROR_TITLES[code], details=str(error)
            ),
            code,
        )

    return handler
