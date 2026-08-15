"""The Table menu: the header row, rows, columns, sorting and filtering."""

from flask import Blueprint, jsonify, request

from cpdm.core import state, table
from cpdm.web.api.support import api_route, ok, payload

bp = Blueprint("table_api", __name__, url_prefix="/api")


@api_route(bp, "/table/page", methods=["GET"])
def table_page():
    return jsonify(table.page(
        state.session,
        offset=request.args.get("offset", 0, type=int),
        limit=request.args.get("limit", table.PAGE_SIZE, type=int),
    ))


@api_route(bp, "/table/columns", methods=["GET"])
def table_columns():
    return jsonify({
        "columns": table.column_report(state.session),
        "operators": [{"value": key, "label": label}
                      for key, label in table.OPERATORS.items()],
        "no_value_operators": list(table.NO_VALUE_OPERATORS),
        "rows": int(len(state.session.require_df())),
    })


@api_route(bp, "/table/rename", methods=["POST"])
def table_rename():
    return ok(result=table.rename_columns(state.session, payload().get("map", {})))


@api_route(bp, "/table/reorder", methods=["POST"])
def table_reorder():
    return ok(columns=table.reorder_columns(state.session, payload().get("order", [])))


@api_route(bp, "/table/drop_columns", methods=["POST"])
def table_drop_columns():
    return ok(result=table.drop_columns(state.session, payload().get("columns", [])))


@api_route(bp, "/table/drop_rows", methods=["POST"])
def table_drop_rows():
    return ok(result=table.drop_rows(state.session, payload().get("index", [])))


@api_route(bp, "/table/drop_blank_rows", methods=["POST"])
def table_drop_blank_rows():
    return ok(result=table.drop_blank_rows(state.session))


@api_route(bp, "/table/drop_duplicates", methods=["POST"])
def table_drop_duplicates():
    return ok(result=table.drop_duplicate_rows(
        state.session, payload().get("columns"), payload().get("keep", "first")
    ))


@api_route(bp, "/table/sort", methods=["POST"])
def table_sort():
    return ok(result=table.sort_rows(state.session, payload().get("keys", [])))


@api_route(bp, "/table/filter/count", methods=["POST"])
def table_filter_count():
    body = payload()
    return jsonify(table.count_matches(
        state.session, body.get("conditions", []), body.get("match", table.MATCH_ALL)
    ))


@api_route(bp, "/table/filter", methods=["POST"])
def table_filter():
    body = payload()
    return ok(result=table.filter_rows(
        state.session,
        body.get("conditions", []),
        body.get("match", table.MATCH_ALL),
        body.get("action", table.KEEP),
    ))
