"""Scales: declaring them on a group, numerising and scoring them."""

from flask import Blueprint, jsonify, request

from cpdm.core import groups, scales, state
from cpdm.web.api.support import api_route, ok, payload

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
    scale = scales.create_scale(state.session, body.get("group"), body.get("name"))
    return ok(scale=scale, defined_scales=state.session.defined_scales)


@api_route(bp, "/delete_scale", methods=["POST"])
def delete_scale():
    defined = scales.delete_scale(state.session, payload().get("scale_name", ""))
    return ok(defined_scales=defined)


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


@api_route(bp, "/scales/score/preview", methods=["GET", "POST"])
def preview_scoring():
    names = payload().get("names") if request.method == "POST" else None
    return jsonify({"plans": scales.preview_scoring(state.session, names)})


@api_route(bp, "/scales/score", methods=["POST"])
def apply_scoring():
    applied = scales.apply_scoring(state.session, payload().get("names"))
    return ok(applied=applied)


@api_route(bp, "/numerise", methods=["POST"])
def numerise():
    body = payload()
    cols = scales.numerise(
        state.session,
        prefix=body.get("prefix", "Scale_"),
        target_scale=body.get("target_scale"),
    )
    return ok(cols=cols)
