"""
Simple API authentication — Phase 10.

Provides API key based authentication for the Android app and
external API consumers. The existing dashboard routes remain
unauthenticated (they're served from the Pi's own network).

Usage:
    @require_auth
    def my_protected_route():
        ...

The API key is checked in the X-API-Key header or the 'api_key'
query parameter.
"""

import functools
import logging
from flask import request, jsonify

import config

log = logging.getLogger("auth")


def check_api_key():
    """Return True if the request has a valid API key."""
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if not key:
        return False
    return key == config.API_KEY


def require_auth(f):
    """Decorator: reject requests without a valid API key."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not check_api_key():
            return jsonify(ok=False, error="unauthorized"), 401
        return f(*args, **kwargs)
    return wrapper


def auth_route():
    """POST /api/auth — validate API key and return device info."""
    body = request.get_json(force=True, silent=True) or {}
    key = body.get("api_key") or request.headers.get("X-API-Key")
    device_id = body.get("device_id", "")
    team_id = body.get("team_id", "")

    if not key or key != config.API_KEY:
        return jsonify(ok=False, error="invalid API key"), 401

    return jsonify(ok=True, device_id=device_id, team_id=team_id,
                   server_time=__import__("time").time())
