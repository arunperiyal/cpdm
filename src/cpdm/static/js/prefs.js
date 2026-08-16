/* File -> Preferences: how the workspace looks and behaves.

   Preferences are kept in this browser, not on the server, so a workspace
   hosted for several people lets each of them have their own theme and text
   size without touching anyone else's. They apply the moment you choose them;
   there is no Save button to forget.

   applyPrefs() is also called from a small script in the page head, before the
   first paint, so the window never flashes the wrong colours on load. */

const PREFS_KEY = 'cpdm.preferences';

const PREF_DEFAULTS = {
    theme: 'dark',
    font: 'default',
    fontSize: 14,
    density: 'comfortable',
    motion: 'full',
    rowsPerPage: 25,
    logLimit: 300
};

const PREF_CHOICES = {
    theme: [
        ['dark', 'Dark'],
        ['light', 'Light'],
        ['contrast', 'High contrast'],
        ['system', 'Match the system']
    ],
    font: [
        ['default', 'Segoe UI / Verdana (default)'],
        ['system', 'The system interface font'],
        ['serif', 'Serif — Georgia'],
        ['mono', 'Monospace throughout'],
        ['dyslexic', 'Wide spacing, plain shapes']
    ],
    density: [['comfortable', 'Comfortable'], ['compact', 'Compact']],
    motion: [['full', 'Full'], ['reduced', 'Reduced']],
    rowsPerPage: [[10, '10'], [25, '25'], [50, '50'], [100, '100']],
    logLimit: [[100, '100 lines'], [300, '300 lines'], [1000, '1000 lines'], [0, 'Never trim']]
};

function readPrefs() {
    try {
        return { ...PREF_DEFAULTS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') };
    } catch (error) {
        return { ...PREF_DEFAULTS };
    }
}

function writePrefs(prefs) {
    try {
        localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    } catch (error) {
        /* private browsing, or a full quota: the session still works */
    }
}

/* Turn the stored choices into attributes on <html> that the CSS reads. */
function applyPrefs(prefs = readPrefs()) {
    const root = document.documentElement;

    const theme = prefs.theme === 'system'
        ? (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
            ? 'light' : 'dark')
        : prefs.theme;

    root.dataset.theme = theme;
    root.dataset.font = prefs.font;
    root.dataset.density = prefs.density;
    root.dataset.motion = prefs.motion;
    root.style.setProperty('--font-size', `${prefs.fontSize}px`);
    return prefs;
}

function setPref(key, value) {
    const prefs = readPrefs();
    prefs[key] = value;
    writePrefs(prefs);
    applyPrefs(prefs);
    renderPrefs();

    if (key === 'rowsPerPage' && typeof tableUI === 'object') tableUI.limit = Number(value);
    return prefs;
}

function resetPrefs() {
    writePrefs({ ...PREF_DEFAULTS });
    applyPrefs();
    renderPrefs();
    log('[INFO] Preferences reset to their defaults.', 'info');
}

/* --- the dialogue -------------------------------------------------------- */

function openPrefsModal() {
    renderPrefs();
    openModal('modal-prefs');
}

function prefRow(label, help, control) {
    return `
        <div class="pref-row">
            <div>
                <div class="pref-label">${label}</div>
                <div class="muted">${help}</div>
            </div>
            <div class="pref-control">${control}</div>
        </div>`;
}

function prefSelect(key, current) {
    return `<select data-pref="${key}" onchange="setPref(this.dataset.pref, this.value)">
        ${PREF_CHOICES[key].map(([value, label]) =>
            `<option value="${value}" ${String(value) === String(current) ? 'selected' : ''}>${label}</option>`
        ).join('')}
    </select>`;
}

function prefNumberSelect(key, current) {
    return `<select data-pref="${key}" onchange="setPref(this.dataset.pref, Number(this.value))">
        ${PREF_CHOICES[key].map(([value, label]) =>
            `<option value="${value}" ${Number(value) === Number(current) ? 'selected' : ''}>${label}</option>`
        ).join('')}
    </select>`;
}

function renderPrefs() {
    const body = document.getElementById('prefs-body');
    if (!body) return;
    const prefs = readPrefs();

    body.innerHTML = `
        <div class="hint-box">
            <strong>Preferences</strong>
            <span>Saved in this browser and applied straight away — a workspace shared with
            other people keeps a separate set for each of them.</span>
        </div>

        <div class="pref-section">Appearance</div>
        ${prefRow('Theme', 'Dark, light, or a high-contrast palette. “Match the system” follows your desktop.',
                  prefSelect('theme', prefs.theme))}
        ${prefRow('Interface font', 'What the menus, dialogues and documentation are set in.',
                  prefSelect('font', prefs.font))}
        ${prefRow('Text size', `Everything scales with this. Currently ${prefs.fontSize}px.`,
                  `<input type="range" min="11" max="22" step="1" value="${prefs.fontSize}"
                          data-pref="fontSize"
                          oninput="setPref(this.dataset.pref, Number(this.value))">`)}
        ${prefRow('Density', 'Compact tightens the padding in rows, menus and tables.',
                  prefSelect('density', prefs.density))}
        ${prefRow('Motion', 'Reduced turns off smooth scrolling and transitions.',
                  prefSelect('motion', prefs.motion))}

        <div class="pref-section">Behaviour</div>
        ${prefRow('Rows per page', 'How many rows Table → Rows shows at a time.',
                  prefNumberSelect('rowsPerPage', prefs.rowsPerPage))}
        ${prefRow('Keep in the log', 'The output pane trims itself to this many lines so a long session stays quick.',
                  prefNumberSelect('logLimit', prefs.logLimit))}

        <div class="pref-preview">
            <span class="log-success">success</span>
            <span class="log-info">information</span>
            <span class="log-error">error</span>
            <span class="diff-warn">warning</span>
            <code>monospace 123</code>
            <button class="btn btn-primary" style="padding:3px 10px;">Primary</button>
            <button class="btn btn-secondary" style="padding:3px 10px;">Secondary</button>
        </div>`;
}

/* Follow the desktop if the theme is set to match it. */
if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
        if (readPrefs().theme === 'system') applyPrefs();
    });
}
