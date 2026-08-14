"""Scales: declaring them on a group, numerising and scoring them."""

from flask import Blueprint, jsonify

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


@api_route(bp, "/numerise", methods=["POST"])
def numerise():
    body = payload()
    cols = scales.numerise(
        state.session,
        prefix=body.get("prefix", "Scale_"),
        target_scale=body.get("target_scale"),
    )
    return ok(cols=cols)


@api_route(bp, "/scoring", methods=["POST"])
def scoring():
    applied = scales.apply_scoring(state.session, payload().get("configs", {}))
    return ok(columns_scored=len(applied))
