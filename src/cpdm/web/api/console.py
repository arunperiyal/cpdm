"""The workspace command prompt."""

from flask import Blueprint, jsonify

from cpdm.core import console, state
from cpdm.web.api.support import api_route, payload

bp = Blueprint("console_api", __name__, url_prefix="/api")


@api_route(bp, "/command", methods=["POST"])
def command():
    return jsonify(console.execute(state.session, payload().get("command", "")))
