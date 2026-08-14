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

document.addEventListener('DOMContentLoaded', () => {
    refreshStatus();
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            document.querySelectorAll('.modal').forEach(m => { m.style.display = 'none'; });
        }
    });
});
