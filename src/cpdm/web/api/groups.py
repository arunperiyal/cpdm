"""Field groups: the tree of column sets behind Fields -> Groups."""

from flask import Blueprint, jsonify

from cpdm.core import column_spec, groups, state
from cpdm.web.api.support import api_route, ok, payload

bp = Blueprint("groups_api", __name__, url_prefix="/api")


@api_route(bp, "/groups", methods=["GET"])
def list_groups():
    session = state.session
    return jsonify({
        "groups": groups.tree(session),
        "kinds": [{"value": kind, "label": groups.KIND_LABELS[kind]} for kind in groups.KINDS],
        "cols": list(session.df.columns) if session.df is not None else [],
    })


@api_route(bp, "/groups/eligible", methods=["POST"])
def eligible():
    """Columns a new or edited group is allowed to take."""
    parent = payload().get("parent")
    return jsonify({"columns": groups.eligible_columns(state.session, parent)})


@api_route(bp, "/groups/resolve_spec", methods=["POST"])
def resolve_spec():
    """Preview a typed column spec — no changes, just what it matches."""
    body = payload()
    session = state.session
    session.require_df()

    allowed = groups.eligible_columns(session, body.get("parent"))
    result = column_spec.parse(body.get("spec", ""), session.df.columns, allowed=allowed)
    result["summary"] = column_spec.describe(result)
    return jsonify(result)


@api_route(bp, "/groups/create", methods=["POST"])
def create():
    body = payload()
    result = groups.create_group(
        state.session,
        body.get("name"),
        parent=body.get("parent"),
        kind=body.get("kind", groups.KIND_SCALE),
        columns=body.get("columns"),
        spec=body.get("spec"),
    )
    return ok(group=result["group"], moved=result["moved"],
              groups=groups.tree(state.session))


@api_route(bp, "/groups/update", methods=["POST"])
def update():
    body = payload()
    result = groups.update_group(
        state.session,
        body.get("name"),
        new_name=body.get("new_name"),
        kind=body.get("kind"),
        columns=body.get("columns"),
        spec=body.get("spec"),
    )
    return ok(
        group=result["group"],
        moved=result["moved"],
        columns_dropped_from_subgroups=result["columns_dropped_from_subgroups"],
        groups=groups.tree(state.session),
    )


@api_route(bp, "/groups/delete", methods=["POST"])
def delete():
    removed = groups.delete_group(state.session, payload().get("name"))
    return ok(removed=removed, groups=groups.tree(state.session))
