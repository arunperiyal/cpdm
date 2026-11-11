"""CPDM — Comprehensive Package for Data Management.

``create_app()`` builds the Flask application: templates and static files ship
inside this package, documentation and samples are read from the project root.
"""

import os

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from cpdm.paths import STATIC_DIR, TEMPLATES_DIR
from cpdm.core import state
from cpdm.core.sessions import LocalSessionStore

__version__ = "0.2.0"


def asset_version(filename):
    """A stamp that changes when the file does.

    Appended to every static URL, so a browser that has cached the old
    JavaScript fetches the new one after an update instead of running last
    week's code against this week's API.
    """
    try:
        return str(int(os.path.getmtime(os.path.join(STATIC_DIR, filename))))
    except OSError:
        return __version__


def create_app(**config):
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR,
    )
    app.config.update(
        {
            "JSON_SORT_KEYS": False,
            "CPDM_MAX_UPLOAD_BYTES": 50 * 1024 * 1024,
            **config,
        }
    )
    app.config.setdefault("MAX_CONTENT_LENGTH", app.config["CPDM_MAX_UPLOAD_BYTES"])
    app.config.setdefault("CPDM_REQUIRE_AUTH", False)
    app.config.setdefault("CPDM_AUTH_TOKEN", None)
    app.config.setdefault("CPDM_SESSION_ROOT", "data/sessions")

    if app.config["CPDM_REQUIRE_AUTH"] and not app.config["CPDM_AUTH_TOKEN"]:
        raise RuntimeError("CPDM_AUTH_TOKEN is required when authentication is enabled.")

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(error):
        return jsonify({"error": "Request exceeds the configured upload size limit."}), 413

    @app.before_request
    def require_api_authentication():
        if not app.config["CPDM_REQUIRE_AUTH"] or not request.path.startswith("/api/"):
            return None
        expected = f"Bearer {app.config['CPDM_AUTH_TOKEN']}"
        if request.headers.get("Authorization") != expected:
            return jsonify({"error": "Authentication required."}), 401
        return None

    @app.before_request
    def activate_session_context():
        session_id = request.headers.get("X-CPDM-Session")
        if not session_id:
            return None
        g.cpdm_session_token = state.begin(
            LocalSessionStore(app.config["CPDM_SESSION_ROOT"]),
            session_id,
            request.headers.get("X-CPDM-Owner", "local"),
        )
        return None

    @app.after_request
    def persist_session_context(response):
        state.end(getattr(g, "cpdm_session_token", None))
        return response

    @app.url_defaults
    def stamp_static(endpoint, values):
        if endpoint == "static" and "filename" in values:
            values["v"] = asset_version(values["filename"])

    from cpdm.web import register_blueprints

    register_blueprints(app)
    return app
