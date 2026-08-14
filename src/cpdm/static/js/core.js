/* Shared helpers: logging, modals, API calls, session state.
   Loaded first; every other script depends on it. */

function log(msg, type = '') {
    const out = document.getElementById('pane-output');
    const div = document.createElement('div');
    div.className = 'log-entry ' + (type ? 'log-' + type : '');
    div.innerHTML = msg;
    out.appendChild(div);
    out.scrollTop = out.scrollHeight;
}

function logError(msg) { log('Error: ' + msg, 'error'); }

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

/* --- API ------------------------------------------------------------- */

/* Resolves with the parsed body; rejects with an Error carrying the API
   message, so callers can use a single .catch(logError). */
function apiRequest(url, options = {}) {
    return fetch(url, options).then(response =>
        response.json()
            .catch(() => { throw new Error(`${response.status} ${response.statusText}`); })
            .then(data => {
                if (!response.ok || data.error) {
                    throw new Error(data.error || `${response.status} ${response.statusText}`);
                }
                return data;
            })
    );
}

function apiGet(url) { return apiRequest(url); }

function apiPost(url, body) {
    return apiRequest(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
    });
}

function apiUpload(url, file) {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest(url, { method: 'POST', body: formData });
}

function reportError(error) { logError(error.message || error); }

/* --- session state --------------------------------------------------- */

function getState() { return apiGet('/api/get_state'); }

/* Runs `callback(state)` only when a dataset is loaded. */
function withDataset(callback) {
    return getState().then(state => {
        if (!state.has_file) {
            logError('Open a data file first (File -> Open).');
            return null;
        }
        return callback(state);
    }).catch(reportError);
}

function scaleColumnsOf(state) {
    return Object.keys(state.categories).filter(c => state.categories[c].startsWith('Scale:'));
}

function refreshStatus() {
    return getState().then(state => {
        const el = document.getElementById('menu-status');
        if (!el) return state;
        el.textContent = state.has_file
            ? `${state.filename} — ${state.rows} rows x ${state.cols.length} cols`
            : 'No dataset loaded';
        return state;
    }).catch(() => {});
}

/* --- keyboard for the column pickers ----------------------------------- */

/* Both the trimming wizard and the group editor show the same list of
   tickable columns. These helpers give it roving focus so the whole thing can
   be driven from the keyboard: type to filter, Enter to take the matches,
   arrows to walk the list, Space to tick, Shift to extend.

   A controller supplies: names() -> the visible column names in order,
   has(name), set(name, on), redraw(), and a state object to hold the anchor
   and the focused row across redraws. */

function focusColumnRow(container, index) {
    const rows = container.querySelectorAll('.col-pick');
    if (!rows.length) return;
    const target = rows[Math.max(0, Math.min(index, rows.length - 1))];
    target.focus();
    target.scrollIntoView({ block: 'nearest' });
}

/* Restore the focused row after a redraw replaced the list. */
function restoreColumnFocus(containerId, state) {
    if (state.focusRow === null || state.focusRow === undefined) return;
    const container = document.getElementById(containerId);
    if (container) focusColumnRow(container, state.focusRow);
}

function setColumnRange(ctrl, from, to, on) {
    const names = ctrl.names();
    const [low, high] = [from, to].sort((a, b) => a - b);
    for (let i = low; i <= high; i += 1) ctrl.set(names[i], on);
}

function columnListKeys(event, ctrl) {
    const container = event.currentTarget;
    const names = ctrl.names();
    if (!names.length) return;

    const row = event.target.closest('.col-pick');
    const index = row ? Number(row.dataset.row) : 0;
    const state = ctrl.state;

    const move = step => {
        event.preventDefault();
        const next = Math.max(0, Math.min(index + step, names.length - 1));
        state.focusRow = next;
        focusColumnRow(container, next);
    };

    switch (event.key) {
        case 'ArrowDown': return move(1);
        case 'ArrowUp': return move(-1);
        case 'PageDown': return move(10);
        case 'PageUp': return move(-10);
        case 'Home': return move(-names.length);
        case 'End': return move(names.length);
        case ' ':
        case 'Enter': {
            event.preventDefault();
            const on = !ctrl.has(names[index]);
            if (event.shiftKey && state.anchor !== null && state.anchor !== undefined) {
                setColumnRange(ctrl, state.anchor, index, on);
            } else {
                ctrl.set(names[index], on);
            }
            state.anchor = index;
            state.focusRow = index;
            ctrl.redraw();
            return;
        }
        case 'a':
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
                names.forEach(name => ctrl.set(name, true));
                ctrl.redraw();
            }
            return;
        default:
    }
}

function columnSearchKeys(event, ctrl) {
    const names = ctrl.names();

    if (event.key === 'Enter') {
        event.preventDefault();
        names.forEach(name => ctrl.set(name, !event.shiftKey));
        ctrl.redraw();
        return;
    }
    if (event.key === 'ArrowDown' && names.length) {
        event.preventDefault();
        ctrl.state.focusRow = 0;
        focusColumnRow(document.getElementById(ctrl.containerId), 0);
        return;
    }
    if (event.key === 'Escape' && event.target.value) {
        event.stopPropagation();          // clear the filter, keep the dialogue
        event.target.value = '';
        ctrl.redraw();
    }
}

const COLUMN_LIST_HINT =
    'Type to filter, <strong>Enter</strong> takes the matches (<strong>Shift+Enter</strong> drops them), '
    + '<strong>↓</strong> into the list, <strong>Space</strong> ticks, <strong>Shift+Space</strong> extends.';

document.addEventListener('DOMContentLoaded', () => {
    refreshStatus();
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            document.querySelectorAll('.modal').forEach(m => { m.style.display = 'none'; });
        }
    });
});
