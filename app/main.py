from flask import Flask, jsonify

from app.api.routes_health import health_bp
from app.api.routes_upload import upload_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp)

    # Единый обработчик ошибок
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "code": 400, "details": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "code": 404, "details": str(e)}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large", "code": 413, "details": str(e)}), 413

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "Unprocessable entity", "code": 422, "details": str(e)}), 422

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error", "code": 500, "details": str(e)}), 500


    import os
    from flask import send_from_directory

    @app.route("/test")
    def test_ui():
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), "static"),
            "test_ui.html"
        )

    return app
