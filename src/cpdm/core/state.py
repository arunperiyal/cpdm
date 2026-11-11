"""The process-wide session.

CPDM is a single-user desktop-style tool, so one module-level dataset is shared
by every request. Import ``session`` rather than constructing a Dataset; it is
reset in place so existing references stay valid.
"""

from contextvars import ContextVar
from cpdm.core.dataset import Dataset
from cpdm.core.contracts import ContractError
from cpdm.core.sessions import LocalSessionStore, SessionLock

_default_session = Dataset()
_active_session = ContextVar("cpdm_active_session", default=None)
_active_context = ContextVar("cpdm_active_context", default=None)


def _current_session():
    return _active_session.get() or _default_session


class _SessionProxy:
    def __getattr__(self, name):
        return getattr(_current_session(), name)

    def __setattr__(self, name, value):
        if name == "_internal":
            object.__setattr__(self, name, value)
        else:
            setattr(_current_session(), name, value)


session = _SessionProxy()


def begin(store=None, session_id=None, owner_id="local"):
    """Activate a persisted session for the current request context."""
    if not session_id:
        return None
    store = store or LocalSessionStore("data/sessions")
    try:
        _, dataset = store.load(session_id, owner_id)
    except ContractError as error:
        if "has no saved dataset" not in str(error):
            raise
        metadata = store._read_metadata(session_id)
        if metadata.owner_id != str(owner_id):
            raise
        dataset = Dataset()
    token = _active_session.set(dataset)
    context = {"store": store, "session_id": session_id, "owner_id": owner_id}
    _active_context.set(context)
    return token


def end(token=None):
    """Persist and clear the current request's session context."""
    context = _active_context.get()
    dataset = _active_session.get()
    if context and dataset is not None and dataset.df is not None:
        with SessionLock(context["session_id"]):
            context["store"].save(context["session_id"], dataset)
    _active_context.set(None)
    if token is not None:
        _active_session.reset(token)


def reset():
    """Drop all working state (used by tests)."""
    _default_session.reset()
    return _default_session
