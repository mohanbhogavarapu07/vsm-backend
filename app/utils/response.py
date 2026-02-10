"""
Consistent JSON response helpers.
Format: { "success": true|false, "data": ..., "message": "..." }
"""
from flask import jsonify
from typing import Any, Optional


def api_success(data: Any = None, message: str = "", status: int = 200):
    """Return a successful JSON response."""
    body = {"success": True, "message": message or "Success"}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def api_error(message: str, status: int = 400, data: Optional[Any] = None):
    """Return an error JSON response."""
    body = {"success": False, "message": message or "Error"}
    if data is not None:
        body["data"] = data
    return jsonify(body), status
