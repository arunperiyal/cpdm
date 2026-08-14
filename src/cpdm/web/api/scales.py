"""Scales: declaring them on a group, numerising and scoring them."""

import json

from flask import Blueprint, jsonify, request, send_file

from cpdm.core import groups, scales, state
from cpdm.web.api.support import api_route, ok, payload, uploaded_file

bp = Blueprint("scales_api", __name__, url_prefix="/api")


@api_route(bp, "/scales", methods=["GET"])
def list_scales():
    """Declared scales, plus the groups a new one could be built on."""
    session = state.session
    declared = {scale["group"] for scale in session.scales}

    available = []
    if session.df is not None:
        for group in session.groups:
            available.append({
                "name": group["name"],
                "depth": session.group_depth(group),
                "column_count": len(group["columns"]),
                "taken_by": groups.scale_on(session, group["name"]),
            })

    return jsonify({
        "scales": scales.list_scales(session),
        "groups": available,
        "has_groups": bool(available),
    })


@api_route(bp, "/create_scale", methods=["POST"])
def create_scale():
    body = payload()
    scale = scales.create_scale(
        state.session, body.get("group"), body.get("name"),
        rename=bool(body.get("rename")),
    )
    return ok(scale=scale, defined_scales=state.session.defined_scales)


@api_route(bp, "/delete_scale", methods=["POST"])
def delete_scale():
    result = scales.delete_scale(state.session, payload().get("scale_name", ""))
    return ok(defined_scales=result["defined_scales"], restored=result["restored"])


@api_route(bp, "/scales/inspect_group", methods=["POST"])
def inspect_group():
    """The items and options a scale on this group would start with."""
    return jsonify(scales.inspect_group(state.session, payload().get("group")))


@api_route(bp, "/scales/<name>", methods=["GET"])
def describe_scale(name):
    return jsonify(scales.describe(state.session, name))


@api_route(bp, "/scales/options", methods=["POST"])
def set_options():
    body = payload()
    return ok(scale=scales.set_options(state.session, body.get("name"), body.get("options")))


@api_route(bp, "/scales/options/refresh", methods=["POST"])
def refresh_options():
    result = scales.refresh_options(state.session, payload().get("name"))
    return ok(added=result["added"], scale=result["detail"])


@api_route(bp, "/scales/options/autoscore", methods=["POST"])
def autoscore_options():
    body = payload()
    detail = scales.autoscore_options(
        state.session, body.get("name"),
        start=body.get("start", 1), step=body.get("step", 1),
    )
    return ok(scale=detail)


@api_route(bp, "/scales/items", methods=["POST"])
def set_item_types():
    body = payload()
    return ok(scale=scales.set_item_types(state.session, body.get("name"), body.get("items")))


@api_route(bp, "/scales/status", methods=["GET", "POST"])
def scoring_status():
    """What the scoring currently does — Scales -> View Scoring reads this."""
    names = payload().get("names") if request.method == "POST" else None
    return jsonify({"plans": scales.scoring_status(state.session, names)})


@api_route(bp, "/scales/export", methods=["GET"])
def export_scales():
    """Download the scale definitions as a reusable JSON file."""
    stream, filename = scales.export_definitions(
        state.session, request.args.getlist("name") or None
    )
    return send_file(
        stream, mimetype="application/json", as_attachment=True, download_name=filename
    )


def _scale_file():
    """The file's contents, uploaded directly or passed through as JSON."""
    if "file" in request.files:
        try:
            return json.load(request.files["file"])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Not a valid JSON scale file: {exc}") from exc
    body = payload().get("payload")
    if body is None:
        raise ValueError("No scale file supplied.")
    return body


@api_route(bp, "/scales/inspect_file", methods=["POST"])
def inspect_scale_file():
    """What the file holds, and where each scale could go here."""
    return jsonify(scales.inspect_file(state.session, _scale_file()))


@api_route(bp, "/scales/import", methods=["POST"])
def import_scales():
    mapping = payload().get("mapping") if "file" not in request.files else None
    return ok(results=scales.import_definitions(state.session, _scale_file(), mapping))


@api_route(bp, "/scales/rename_items", methods=["POST"])
def rename_items():
    body = payload()
    result = scales.rename_items(state.session, body.get("name"), body.get("prefix"))
    return ok(renamed=result["renamed"], columns=result["columns"])
