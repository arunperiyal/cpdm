"""Shared plumbing for the JSON endpoints."""

from functools import wraps

from flask import jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge


def api_route(blueprint, rule, **options):
    """Register a JSON endpoint that turns exceptions into error responses.

    ``ValueError`` (an invalid request or an unloaded dataset) becomes 400;
    anything else becomes 500. Handlers can therefore just raise.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except RequestEntityTooLarge:
                return jsonify(
                    {"error": "Request exceeds the configured upload size limit."}
                ), 413
            except TimeoutError as exc:
                message = str(exc) or "The operation timed out."
                return jsonify({"error": message}), 504
            except Exception as exc:  # pragma: no cover - unexpected failures
                return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

        blueprint.add_url_rule(rule, view_func=wrapper, **options)
        return wrapper

    return decorator


def payload():
    """The JSON body of the current request, tolerating an empty one."""
    return request.get_json(silent=True) or {}


def uploaded_file(field="file"):
    if field not in request.files:
        raise ValueError("No file uploaded.")
    return request.files[field]


def ok(**fields):
    return jsonify({"status": "ok", **fields})
