"""HTML pages: the workspace, the documentation browser, sample downloads."""

from flask import Blueprint, abort, render_template, send_from_directory

from cpdm.core import docs_library, samples

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index():
    """The workspace. Doc links are baked into the Help menu at render time."""
    return render_template("index.html", doc_sections=docs_library.index())


@views_bp.route("/docs")
@views_bp.route("/docs/<section>/<slug>")
def docs(section=None, slug=None):
    """The documentation browser: sidebar of pages plus the rendered page."""
    sections = docs_library.index()

    if section is None or slug is None:
        default = docs_library.default_doc()
        if default is None:
            return render_template(
                "docs.html",
                sections=sections,
                samples=samples.listing(),
                doc=None,
                missing="No Markdown files found in docs/theory or docs/help.",
            )
        section, slug = default["section"], default["slug"]

    doc = docs_library.get(section, slug)
    if doc is None:
        abort(404)

    return render_template(
        "docs.html",
        sections=sections,
        samples=samples.listing(),
        doc=doc,
        missing=None,
    )


@views_bp.route("/samples/<path:filename>")
def sample_file(filename):
    """Download one of the bundled example datasets."""
    try:
        directory, safe_name = samples.resolve(filename)
    except ValueError:
        abort(404)
    return send_from_directory(directory, safe_name, as_attachment=True)
