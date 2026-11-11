"""Opening, exporting and inspecting the working dataset."""

from flask import Blueprint, current_app, jsonify, request, send_file

from cpdm.core import services, state
from cpdm.core.operations import UploadPolicy
from cpdm.web.api.support import api_route, uploaded_file

bp = Blueprint("files_api", __name__, url_prefix="/api")


@api_route(bp, "/upload", methods=["POST"])
def upload():
    policy = UploadPolicy(current_app.config["CPDM_MAX_UPLOAD_BYTES"])
    service = services.DatasetService(state.session, upload_policy=policy)
    return jsonify(service.load(uploaded_file()))


@api_route(bp, "/export", methods=["GET"])
def export():
    stream, filename, mimetype = services.DatasetService(state.session).export(
        request.args.get("format", "xlsx")
    )
    return send_file(stream, mimetype=mimetype, as_attachment=True, download_name=filename)


@api_route(bp, "/get_state", methods=["GET"])
def get_state():
    return jsonify(state.session.state())
