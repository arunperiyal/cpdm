"""CPDM — Comprehensive Package for Data Management.

``create_app()`` builds the Flask application: templates and static files ship
inside this package, documentation and samples are read from the project root.
"""

from flask import Flask

from cpdm.paths import STATIC_DIR, TEMPLATES_DIR

__version__ = "0.2.0"


def create_app(**config):
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR,
    )
    app.config.update(JSON_SORT_KEYS=False, **config)

    from cpdm.web import register_blueprints

    register_blueprints(app)
    return app
