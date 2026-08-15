"""Documentation and sample data, as JSON for the in-app viewer."""

from flask import Blueprint, jsonify

from cpdm.core import about_info, docs_library, samples, state
from cpdm.web.api.support import api_route

bp = Blueprint("docs_api", __name__, url_prefix="/api")


@api_route(bp, "/about", methods=["GET"])
def about():
    """What the About box shows: the app, its licence and who wrote it."""
    return jsonify(about_info.summary(state.session))


@api_route(bp, "/docs", methods=["GET"])
def list_docs():
    return jsonify({"sections": docs_library.index(), "samples": samples.listing()})


@api_route(bp, "/docs/<section>/<slug>", methods=["GET"])
def get_doc(section, slug):
    doc = docs_library.get(section, slug)
    if doc is None:
        return jsonify({"error": f"No document at {section}/{slug}."}), 404
    return jsonify(doc)
