"""CPDM — Comprehensive Package for Data Management.

``create_app()`` builds the Flask application: templates and static files ship
inside this package, documentation and samples are read from the project root.
"""

import os

from flask import Flask

from cpdm.paths import STATIC_DIR, TEMPLATES_DIR

__version__ = "0.2.0"


def asset_version(filename):
    """A stamp that changes when the file does.

    Appended to every static URL, so a browser that has cached the old
    JavaScript fetches the new one after an update instead of running last
    week's code against this week's API.
    """
    try:
        return str(int(os.path.getmtime(os.path.join(STATIC_DIR, filename))))
    except OSError:
        return __version__


def create_app(**config):
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR,
    )
    app.config.update(JSON_SORT_KEYS=False, **config)

    @app.url_defaults
    def stamp_static(endpoint, values):
        if endpoint == "static" and "filename" in values:
            values["v"] = asset_version(values["filename"])

    from cpdm.web import register_blueprints

    register_blueprints(app)
    return app
