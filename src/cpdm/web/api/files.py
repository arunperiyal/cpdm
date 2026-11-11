"""Opening, exporting and inspecting the working dataset."""

from flask import Blueprint, current_app, jsonify, request, send_file

from cpdm.core import services, state
from cpdm.core.analysis import AnalysisRunner
from cpdm.core.operations import UploadPolicy
from cpdm.core.sessions import LocalSessionStore
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


@api_route(bp, "/analysis/capabilities", methods=["GET"])
def analysis_capabilities():
    return jsonify({"capabilities": AnalysisRunner().capability_metadata()})


@api_route(bp, "/sessions", methods=["POST"])
def create_session():
    owner = request.headers.get("X-CPDM-Owner", "local")
    metadata = LocalSessionStore(current_app.config["CPDM_SESSION_ROOT"]).create(owner)
    return jsonify(metadata.as_dict()), 201


@api_route(bp, "/sessions/<session_id>", methods=["DELETE"])
def close_session(session_id):
    owner = request.headers.get("X-CPDM-Owner", "local")
    metadata = LocalSessionStore(current_app.config["CPDM_SESSION_ROOT"]).close(
        session_id, owner
    )
    return jsonify(metadata.as_dict())
