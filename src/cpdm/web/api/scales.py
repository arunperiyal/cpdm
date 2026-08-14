"""Numerisation and scoring. Scales are defined in Fields -> Groups."""

from flask import Blueprint

from cpdm.core import scales, state
from cpdm.web.api.support import api_route, ok, payload

bp = Blueprint("scales_api", __name__, url_prefix="/api")


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
