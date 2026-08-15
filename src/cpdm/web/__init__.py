"""Web layer: Flask blueprints translating HTTP into core-layer calls."""

from cpdm.web.api import cleaning as cleaning_api
from cpdm.web.api import compute as compute_api
from cpdm.web.api import console as console_api
from cpdm.web.api import docs as docs_api
from cpdm.web.api import files as files_api
from cpdm.web.api import groups as groups_api
from cpdm.web.api import scales as scales_api
from cpdm.web.api import table as table_api
from cpdm.web.views import views_bp

BLUEPRINTS = (
    views_bp,
    files_api.bp,
    cleaning_api.bp,
    groups_api.bp,
    scales_api.bp,
    table_api.bp,
    compute_api.bp,
    console_api.bp,
    docs_api.bp,
)


def register_blueprints(app):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
    return app
