"""Header mapping, value replacement, text trimming and cleaning recipes."""

import json

from flask import Blueprint, jsonify, send_file

from cpdm.core import cleaning, recipes, state
from cpdm.web.api.support import api_route, ok, payload, uploaded_file

bp = Blueprint("cleaning_api", __name__, url_prefix="/api")


@api_route(bp, "/clean_headers", methods=["POST"])
def clean_headers():
    body = payload()
    cols = cleaning.update_headers(
        state.session, body.get("header_map", {}), body.get("ignored_cols", [])
    )
    return ok(cols=cols)


@api_route(bp, "/get_unique_values", methods=["POST"])
def get_unique_values():
    return jsonify(
        cleaning.unique_text_values(state.session, payload().get("ignored_cols", []))
    )


@api_route(bp, "/clean_values", methods=["POST"])
def clean_values():
    changed = cleaning.apply_value_replacements(
        state.session, payload().get("replacements", {})
    )
    return ok(columns_processed=changed)


@api_route(bp, "/text_rules/preview", methods=["POST"])
def preview_text_rules():
    """What a rule chain would do. Read-only: the dataset is not touched."""
    body = payload()
    return jsonify(
        cleaning.preview_text_rules(
            state.session,
            body.get("stage", cleaning.STAGE_HEADERS),
            body.get("rules", []),
            body.get("columns"),
        )
    )


@api_route(bp, "/text_rules/apply", methods=["POST"])
def apply_text_rules():
    body = payload()
    result = cleaning.apply_text_rules(
        state.session,
        body.get("stage", cleaning.STAGE_HEADERS),
        body.get("rules", []),
        body.get("columns"),
    )
    return ok(result=result)


@api_route(bp, "/text_rules/leftovers", methods=["POST"])
def find_leftovers():
    """Headers and values the rules did not catch — stage 3 of the wizard."""
    body = payload()
    return jsonify(
        cleaning.find_leftovers(
            state.session, body.get("columns"), bool(body.get("strict_ascii"))
        )
    )


@api_route(bp, "/text_rules/fix_leftovers", methods=["POST"])
def fix_leftovers():
    body = payload()
    result = cleaning.fix_leftovers(
        state.session,
        headers=body.get("headers"),
        values=body.get("values"),
        columns=body.get("columns"),
    )
    return ok(result=result)


@api_route(bp, "/clean_text_pattern", methods=["POST"])
def clean_text_pattern():
    """Pre-wizard endpoint: one value rule, kept as an adapter."""
    body = payload()
    processed = cleaning.trim_values(
        state.session, body.get("mode"), body.get("delimiter", "")
    )
    return ok(columns_processed=processed)


@api_route(bp, "/remove_non_english_advanced", methods=["POST"])
def remove_non_english_advanced():
    body = payload()
    result = cleaning.scrub_non_english(
        state.session,
        body.get("header_cfg", {}),
        body.get("value_cfg", {}),
        body.get("exempt_cols", []),
    )
    return ok(result=result)


@api_route(bp, "/export_cleaning_rules", methods=["GET"])
def export_cleaning_rules():
    stream, filename = recipes.export_rules(state.session)
    return send_file(
        stream, mimetype="application/json", as_attachment=True, download_name=filename
    )


@api_route(bp, "/apply_cleaning_rules_file", methods=["POST"])
def apply_cleaning_rules_file():
    file_storage = uploaded_file()
    try:
        rules_data = json.load(file_storage)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Not a valid JSON cleaning file: {exc}") from exc
    return ok(result=recipes.apply_rules(state.session, rules_data))
