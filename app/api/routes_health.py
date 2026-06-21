from dataclasses import asdict

from flask import Blueprint, jsonify

from app.api.schemas_http import HealthResponse

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    return jsonify(asdict(HealthResponse())), 200
