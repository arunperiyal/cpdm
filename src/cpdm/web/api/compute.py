"""Row-wise calculations across scale items."""

from flask import Blueprint

from cpdm.core import compute, state
from cpdm.web.api.support import api_route, ok, payload

bp = Blueprint("compute_api", __name__, url_prefix="/api")


@api_route(bp, "/compute", methods=["POST"])
def row_statistic():
    body = payload()
    new_col = compute.row_statistic(
        state.session,
        body.get("new_col_name"),
        body.get("function_name"),
        body.get("selected_cols", []),
    )
    return ok(new_col=new_col)
