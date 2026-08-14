"""Opening, exporting and inspecting the working dataset."""

from flask import Blueprint, jsonify, request, send_file

from cpdm.core import state, tabular_io
from cpdm.web.api.support import api_route, uploaded_file

bp = Blueprint("files_api", __name__, url_prefix="/api")


@api_route(bp, "/upload", methods=["POST"])
def upload():
    return jsonify(tabular_io.load_into(state.session, uploaded_file()))


@api_route(bp, "/export", methods=["GET"])
def export():
    stream, filename, mimetype = tabular_io.export(
        state.session, request.args.get("format", "xlsx")
    )
    return send_file(stream, mimetype=mimetype, as_attachment=True, download_name=filename)


@api_route(bp, "/get_state", methods=["GET"])
def get_state():
    return jsonify(state.session.state())
