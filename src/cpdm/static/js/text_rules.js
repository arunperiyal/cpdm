/* Clean -> Remove Non-English: a two-stage wizard (headers, then values).

   Each stage takes an ordered chain of rules and a set of target columns, and
   nothing is written until a preview has been offered. Rendered into the shared
   #modal-clean shell. */

const TRIMMER_MODES = [
    ['non_english_to_end', 'Cut from the first non-English character to the end'],
    ['delimiter', 'Cut at a delimiter'],
    ['strip_non_english', 'Strip non-English characters'],
    ['tidy', 'Tidy up leftovers']
];

function defaultTrimmerRules() {
    return [{ mode: 'non_english_to_end', strict_ascii: false }, { mode: 'tidy' }];
}

const TRIMMER_STAGES = ['headers', 'values', 'leftovers'];

const trimmer = {
    stage: 'headers',
    rules: { headers: defaultTrimmerRules(), values: defaultTrimmerRules() },
    selected: { headers: null, values: null },   // Sets of column names
    cols: [],
    numeric: new Set(),
    ignored: new Set(),
    visible: [],        // column names currently listed, in render order
    anchor: null,       // last clicked row, for shift-click ranges
    preview: null,
    showUnchanged: false,
    leftovers: null,    // stage 3: what the rules could not catch
    fixes: { headers: {}, values: {} },
    groups: []          // stage 2 targets whole groups rather than loose columns
};

/* --- entry points ----------------------------------------------------- */

function trimmerLoadGroups() {
    return apiGet('/api/groups')
        .then(data => {
            const flat = [];
            const walk = (nodes, depth) => nodes.forEach(node => {
                flat.push({ name: node.name, depth, columns: node.columns });
                walk(node.children, depth + 1);
            });
            walk(data.groups, 0);
            trimmer.groups = flat;
        })
        .catch(() => { trimmer.groups = []; });
}

function openTextRulesWizard(stage = 'headers') {
    withDataset(state => {
        trimmer.cols = state.cols;
        trimmer.numeric = new Set(state.numeric_columns || []);
        trimmer.ignored = new Set(state.ignored_columns || []);
        trimmer.selected = { headers: null, values: null };
        trimmer.stage = stage;
        trimmer.preview = null;
        trimmer.anchor = null;
        trimmerLoadGroups().then(() => {
            renderTrimmer();
            openModal('modal-clean');
        });
    });
}

/* Kept so the Clean menu and the wizard's quick button share one dialogue. */
function openRemoveNonEnglishModal() { openTextRulesWizard('headers'); }
function openTextTrimmer() { openTextRulesWizard('values'); }

/* --- selection helpers ------------------------------------------------- */

function trimmerEligible() {
    return trimmer.stage === 'values'
        ? trimmer.cols.filter(col => !trimmer.numeric.has(col))
        : trimmer.cols;
}

function trimmerSelection() {
    if (!trimmer.selected[trimmer.stage]) {
        // start with everything eligible except columns already being ignored
        const eligible = trimmerEligible();
        const preselected = eligible.filter(col => !trimmer.ignored.has(col));
        trimmer.selected[trimmer.stage] = new Set(preselected.length ? preselected : eligible);
    }
    return trimmer.selected[trimmer.stage];
}

/* null means "every eligible column", which keeps the recipe robust when a
   later wave has slightly different columns. */
function trimmerColumnsPayload() {
    const selection = trimmerSelection();
    const eligible = trimmerEligible();
    if (eligible.every(col => selection.has(col))) return null;
    return Array.from(selection);
}

function trimmerRules() { return trimmer.rules[trimmer.stage]; }

/* --- rule editing ------------------------------------------------------ */

function trimmerAddRule() {
    trimmerRules().push({ mode: 'delimiter', delimiters: ['/'], keep: 'before' });
    trimmer.preview = null;
    renderTrimmerRules();
}

function trimmerRemoveRule(index) {
    trimmerRules().splice(index, 1);
    trimmer.preview = null;
    renderTrimmerRules();
}

function trimmerMoveRule(index, delta) {
    const rules = trimmerRules();
    const target = index + delta;
    if (target < 0 || target >= rules.length) return;
    [rules[index], rules[target]] = [rules[target], rules[index]];
    trimmer.preview = null;
    renderTrimmerRules();
}

function trimmerSetMode(index, mode) {
    let rule = { mode };
    if (mode === 'delimiter') rule = { mode, delimiters: ['/'], keep: 'before' };
    else if (mode !== 'tidy') rule = { mode, strict_ascii: false };

    trimmerRules()[index] = rule;
    trimmer.preview = null;
    renderTrimmerRules();
}

/* Field edits do not re-render, so typing in a delimiter box keeps focus. */
function trimmerSetDelimiters(index, text) {
    trimmerRules()[index].delimiters = text.split(/\s+/).filter(Boolean);
    trimmer.preview = null;
}

function trimmerSetKeep(index, side) {
    trimmerRules()[index].keep = side;
    trimmer.preview = null;
}

function trimmerSetStrict(index, strict) {
    trimmerRules()[index].strict_ascii = strict;
    trimmer.preview = null;
}

/* --- column picker ----------------------------------------------------- */

function trimmerToggleColumn(index, event) {
    const selection = trimmerSelection();
    const name = trimmer.visible[index];
    const checked = event.target.checked;

    if (event.shiftKey && trimmer.anchor !== null) {
        const [from, to] = [trimmer.anchor, index].sort((a, b) => a - b);
        for (let i = from; i <= to; i += 1) {
            const col = trimmer.visible[i];
            if (checked) selection.add(col); else selection.delete(col);
        }
    } else if (checked) {
        selection.add(name);
    } else {
        selection.delete(name);
    }

    trimmer.anchor = index;
    trimmer.preview = null;
    renderTrimmerColumns();
    renderTrimmerGroups();
}

function trimmerSelectAll(all) {
    const selection = trimmerSelection();
    trimmer.visible.forEach(col => { if (all) selection.add(col); else selection.delete(col); });
    trimmer.preview = null;
    renderTrimmerColumns();
    renderTrimmerGroups();
}

/* --- keyboard ----------------------------------------------------------- */

const trimmerListCtrl = {
    containerId: 'trimmer-columns',
    state: trimmer,
    names: () => trimmer.visible,   // one entry per rendered row
    has: name => trimmerSelection().has(name),
    set: (name, on) => {
        if (trimmer.stage === 'values' && trimmer.numeric.has(name)) return;
        const selection = trimmerSelection();
        if (on) selection.add(name); else selection.delete(name);
        trimmer.preview = null;
    },
    redraw: () => { renderTrimmerColumns(); renderTrimmerGroups(); }
};

function trimmerListKeys(event) { columnListKeys(event, trimmerListCtrl); }

/* --- targeting whole groups (stage 2) ----------------------------------- */

function trimmerGroupState(group) {
    const selection = trimmerSelection();
    const usable = group.columns.filter(col => !trimmer.numeric.has(col));
    if (!usable.length) return 'empty';
    const taken = usable.filter(col => selection.has(col)).length;
    if (taken === usable.length) return 'all';
    return taken ? 'some' : 'none';
}

function trimmerToggleGroup(index) {
    const group = trimmer.groups[index];
    const selection = trimmerSelection();
    const on = trimmerGroupState(group) !== 'all';

    group.columns.forEach(col => {
        if (trimmer.numeric.has(col)) return;
        if (on) selection.add(col); else selection.delete(col);
    });
    trimmer.preview = null;
    renderTrimmerColumns();
    renderTrimmerGroups();
}

function trimmerGroupsOnly(index) {
    trimmerSelection().clear();
    trimmerToggleGroup(index);
}

function renderTrimmerGroups() {
    const box = document.getElementById('trimmer-groups');
    if (!box) return;

    if (!trimmer.groups.length) {
        box.innerHTML = `
            <div class="group-prompt">
                <span>Cleaning values usually differs by construct — the item columns want
                one rule, free text another. <strong>Group your columns first</strong> and you
                can aim this stage a group at a time.</span>
                <button class="btn btn-secondary" style="padding:3px 10px; font-size:12px; white-space:nowrap;"
                        onclick="closeModal('modal-clean'); openGroupsModal();">Open Fields &#8594; Groups</button>
            </div>`;
        return;
    }

    box.innerHTML = `
        <div class="muted" style="margin-bottom:5px;">Target a group (click to toggle, double-click for only that one):</div>
        <div class="chip-list">${trimmer.groups.map((group, index) => {
            const state = trimmerGroupState(group);
            const indent = '&nbsp;'.repeat(group.depth * 2);
            return `<span class="chip group-chip chip-${state}"
                          title="${escapeHtml(group.columns.join(', '))}"
                          onclick="trimmerToggleGroup(${index})"
                          ondblclick="trimmerGroupsOnly(${index})">
                        ${indent}${escapeHtml(group.name)} (${group.columns.length})
                    </span>`;
        }).join('')}</div>`;
}
function trimmerSearchKeys(event) { columnSearchKeys(event, trimmerListCtrl); }

/* --- shortcuts ---------------------------------------------------------- */

function trimmerShortcutBar() {
    const keys = [
        ['type', 'filter the columns'],
        ['Enter', 'take the matches'],
        ['Shift+Enter', 'drop them'],
        ['↓ ↑', 'walk the list'],
        ['Space', 'tick'],
        ['Shift+Space', 'extend'],
        ['Ctrl+A', 'take all listed'],
        ['Esc', 'clear the filter']
    ];
    return `<div class="shortcut-bar">${keys.map(([key, what]) =>
        `<span><kbd>${key}</kbd> ${what}</span>`).join('')}</div>`;
}

/* --- rendering --------------------------------------------------------- */

function renderTrimmer() {
    if (trimmer.stage === 'leftovers') return renderTrimmerLeftovers();

    const isHeaders = trimmer.stage === 'headers';
    document.getElementById('clean-modal-header').innerText =
        `Clean -> Remove Non-English: Step ${isHeaders ? 1 : 2} of 3 — ${isHeaders ? 'Column Headers' : 'Cell Values'}`;

    document.getElementById('clean-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>${isHeaders ? 'Stage 1: clean the header row' : 'Stage 2: clean the cell values'}</strong>
            <span>${isHeaders
                ? 'Rules run in order against each column name. Nothing changes until you press Apply, and Preview shows the exact result first.'
                : 'Rules run in order against every cell of the selected columns. Numeric columns are skipped automatically.'}</span>
        </div>
        ${trimmerShortcutBar()}
        <div id="trimmer-status" class="trimmer-status"></div>

        <div class="trimmer-grid">
            <div class="rule-card">
                <strong style="color:var(--accent);">Rules (applied in order)</strong>
                <div id="trimmer-rules"></div>
                <button class="btn btn-secondary" style="margin-top:10px; padding:4px 10px; font-size:12px;"
                        onclick="trimmerAddRule()">+ Add rule</button>
            </div>

            <div class="rule-card">
                <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                    <strong style="color:var(--bad); margin:0;">Apply to columns</strong>
                    <span>
                        <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;" onclick="trimmerSelectAll(true)">All</button>
                        <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;" onclick="trimmerSelectAll(false)">None</button>
                    </span>
                </div>
                ${isHeaders ? '' : '<div id="trimmer-groups" style="margin-top:8px;"></div>'}
                <input type="text" id="trimmer-search" placeholder="Search columns..."
                       style="width:100%; margin:8px 0; font-size:12px;"
                       oninput="renderTrimmerColumns()" onkeydown="trimmerSearchKeys(event)">
                <div id="trimmer-columns" class="trimmer-cols" onkeydown="trimmerListKeys(event)"></div>
            </div>
        </div>

        <div id="trimmer-preview"></div>`;

    renderTrimmerRules();
    renderTrimmerGroups();
    renderTrimmerColumns();
    renderTrimmerPreview();
    renderTrimmerFooter();
    document.getElementById('trimmer-search').focus();
}

function renderTrimmerRules() {
    const rules = trimmerRules();
    const container = document.getElementById('trimmer-rules');

    if (!rules.length) {
        container.innerHTML = '<div class="muted" style="padding:8px 0;">No rules yet — add one below.</div>';
        renderTrimmerPreview();
        return;
    }

    container.innerHTML = rules.map((rule, index) => {
        const options = TRIMMER_MODES.map(([value, label]) =>
            `<option value="${value}" ${rule.mode === value ? 'selected' : ''}>${label}</option>`).join('');

        let extras = '';
        if (rule.mode === 'delimiter') {
            extras = `
                <div class="rule-opts">
                    <input type="text" value="${escapeHtml((rule.delimiters || []).join(' '))}"
                           placeholder="/ ( -" title="Separate several delimiters with spaces"
                           style="width:110px; font-size:11px;"
                           oninput="trimmerSetDelimiters(${index}, this.value)">
                    <select style="font-size:11px;" onchange="trimmerSetKeep(${index}, this.value)">
                        <option value="before" ${rule.keep !== 'after' ? 'selected' : ''}>keep before</option>
                        <option value="after" ${rule.keep === 'after' ? 'selected' : ''}>keep after</option>
                    </select>
                </div>`;
        } else if (rule.mode === 'tidy') {
            extras = '<div class="rule-opts muted">Drops stray brackets and separators, collapses spaces.</div>';
        } else {
            extras = `
                <div class="rule-opts">
                    <label class="muted" style="display:inline-flex; align-items:center; gap:5px; margin:0;">
                        <input type="checkbox" ${rule.strict_ascii ? 'checked' : ''}
                               onchange="trimmerSetStrict(${index}, this.checked)">
                        strict ASCII (also removes café, ₹, curly quotes)
                    </label>
                </div>`;
        }

        return `
            <div class="rule-row">
                <span class="rule-index">${index + 1}</span>
                <div style="flex:1;">
                    <select style="width:100%; font-size:12px;" onchange="trimmerSetMode(${index}, this.value)">${options}</select>
                    ${extras}
                </div>
                <span class="rule-actions">
                    <button class="btn btn-secondary" title="Move up" onclick="trimmerMoveRule(${index}, -1)">&uarr;</button>
                    <button class="btn btn-secondary" title="Move down" onclick="trimmerMoveRule(${index}, 1)">&darr;</button>
                    <button class="btn btn-secondary" title="Remove" onclick="trimmerRemoveRule(${index})">&times;</button>
                </span>
            </div>`;
    }).join('');

    renderTrimmerPreview();
}

function renderTrimmerColumns() {
    const search = (document.getElementById('trimmer-search')?.value || '').toLowerCase();
    const selection = trimmerSelection();
    const isValues = trimmer.stage === 'values';

    trimmer.visible = trimmer.cols.filter(col => col.toLowerCase().includes(search));

    document.getElementById('trimmer-columns').innerHTML = trimmer.visible.map((col, index) => {
        const skipped = isValues && trimmer.numeric.has(col);
        const safe = escapeHtml(col);
        return `
            <label class="col-pick ${skipped ? 'col-skipped' : ''}" tabindex="0" data-row="${index}"
                   title="${skipped ? 'Numeric column — no text to trim' : safe}">
                <input type="checkbox" tabindex="-1"
                       ${selection.has(col) ? 'checked' : ''} ${skipped ? 'disabled' : ''}
                       onclick="trimmerToggleColumn(${index}, event)">
                <span>${safe}</span>
            </label>`;
    }).join('') || '<div class="muted">No columns match.</div>';

    restoreColumnFocus('trimmer-columns', trimmer);

    const count = trimmerEligible().filter(col => selection.has(col)).length;
    const footer = document.getElementById('trimmer-selection-count');
    if (footer) footer.textContent = `${count} column(s) selected`;
}

function trimmerToggleUnchanged() {
    trimmer.showUnchanged = !trimmer.showUnchanged;
    renderTrimmerPreview();
}

function renderTrimmerPreview() {
    const container = document.getElementById('trimmer-preview');
    if (!container) return;

    const preview = trimmer.preview;
    if (!preview) {
        container.innerHTML = `
            <div class="preview-empty muted">
                Press <strong>Preview</strong> to see exactly what these rules would do before anything changes.
            </div>`;
        return;
    }

    const rows = preview.rows.filter(row => trimmer.showUnchanged || row.changed);
    const toggle = `
        <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                onclick="trimmerToggleUnchanged()">${trimmer.showUnchanged ? 'Hide unchanged' : 'Show unchanged'}</button>`;

    let summary;
    let body;

    const nothing = !preview.columns_affected
        ? '<div class="diff-warn" style="margin-bottom:8px;">Nothing changes — these rules may already have been applied.</div>'
        : '';

    if (preview.stage === 'headers') {
        summary = `${preview.columns_affected} of ${preview.columns_scanned} header(s) change`;
        body = rows.length ? `
            <table class="preview-table">
                <thead><tr><th>Now</th><th>After these rules</th><th>Note</th></tr></thead>
                <tbody>${rows.map(row => `
                    <tr>
                        <td class="diff-before">${escapeHtml(row.before)}</td>
                        <td class="${row.changed ? 'diff-after' : ''}">${escapeHtml(row.after)}</td>
                        <td class="diff-warn">${escapeHtml(row.warning)}</td>
                    </tr>`).join('')}</tbody>
            </table>` : '<div class="muted">No headers change under these rules.</div>';
    } else {
        summary = `${preview.cells_changed} cell(s) across ${preview.columns_affected} of ${preview.columns_scanned} column(s) change`
            + (preview.truncated ? ' (previewed on the first 5000 rows)' : '');
        body = rows.length ? rows.map(row => `
            <div class="preview-col">
                <div class="preview-col-head">
                    <strong>${escapeHtml(row.column)}</strong>
                    <span class="muted">${row.cells_changed} of ${row.cells_total} cell(s)</span>
                </div>
                <table class="preview-table">
                    <thead><tr><th>Now</th><th></th><th>After these rules</th></tr></thead>
                    <tbody>${row.examples.map(example => `
                        <tr>
                            <td class="diff-before">${escapeHtml(example.before)}</td>
                            <td class="diff-arrow">&rarr;</td>
                            <td class="diff-after">${escapeHtml(example.after)}</td>
                        </tr>`).join('')}</tbody>
                </table>
            </div>`).join('') : '<div class="muted">No cells change under these rules.</div>';
    }

    container.innerHTML = `
        <div class="preview-box">
            <div class="preview-head">
                <div>
                    <strong style="color:var(--good);">Preview — ${escapeHtml(preview.description)}</strong>
                    <div class="muted">${summary}. <em>Now</em> is the data as it stands, not as the file arrived.</div>
                </div>
                ${toggle}
            </div>
            ${nothing}
            ${body}
        </div>`;
}

function renderTrimmerFooter() {
    const isHeaders = trimmer.stage === 'headers';
    document.getElementById('clean-modal-footer').innerHTML = `
        <span id="trimmer-selection-count" class="muted" style="margin-right:auto;"></span>
        <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Close</button>
        ${isHeaders ? '' : '<button class="btn btn-secondary" onclick="trimmerBack()">&larr; Back</button>'}
        <button class="btn btn-secondary" onclick="trimmerPreview()">Preview</button>
        <button class="btn btn-secondary" onclick="trimmerApply()">Apply</button>
        <button class="btn btn-primary" onclick="trimmerContinue()">Continue &rarr;</button>`;
    renderTrimmerColumns();
}

/* --- stage navigation --------------------------------------------------- */

function trimmerGoToStage(stage) {
    // column names may have just changed, so rebuild the picker from the server
    return getState().then(state => {
        trimmer.cols = state.cols;
        trimmer.numeric = new Set(state.numeric_columns || []);
        trimmer.ignored = new Set(state.ignored_columns || []);
        trimmer.selected[stage] = null;
        trimmer.stage = stage;
        trimmer.preview = null;
        trimmer.anchor = null;

        if (stage === 'leftovers') return loadTrimmerLeftovers();
        return trimmerLoadGroups().then(renderTrimmer);
    }).catch(reportError);
}

function trimmerGoToValues() { return trimmerGoToStage('values'); }
function trimmerGoToHeaders() { return trimmerGoToStage('headers'); }

/* --- stage 3: leftovers the rules could not catch ----------------------- */

function loadTrimmerLeftovers() {
    document.getElementById('clean-modal-header').innerText =
        'Clean -> Remove Non-English: Step 3 of 3 — Leftovers';
    document.getElementById('clean-modal-body').innerHTML =
        '<p class="muted">Looking for what the rules did not catch...</p>';
    document.getElementById('clean-modal-footer').innerHTML = '';

    return apiPost('/api/text_rules/leftovers', {})
        .then(data => {
            trimmer.leftovers = data;
            trimmer.fixes = { headers: {}, values: {} };
            renderTrimmerLeftovers();
        })
        .catch(reportError);
}

function renderTrimmerLeftovers() {
    const data = trimmer.leftovers || { headers: [], values: [] };
    const clean = !data.headers.length && !data.values.length;

    const marks = list => list.map(char =>
        `<span class="leftover-mark">${escapeHtml(char)}</span>`).join('');

    const headerRows = data.headers.map((entry, index) => `
        <div class="leftover-row">
            <div class="leftover-was" title="${escapeHtml(entry.column)}">
                ${escapeHtml(entry.column)} ${marks(entry.marks)}
            </div>
            <input type="text" value="${escapeHtml(entry.column)}"
                   data-kind="headers" data-key="${escapeHtml(entry.column)}"
                   oninput="trimmerEditFix(this)" onkeydown="trimmerLeftoverKeys(event, ${index})">
        </div>`).join('');

    const valueRows = data.values.map((entry, index) => `
        <div class="leftover-row">
            <div class="leftover-was" title="in ${escapeHtml(entry.columns.join(', '))}">
                ${escapeHtml(entry.value)} ${marks(entry.marks)}
                <span class="muted">×${entry.count} in ${entry.columns.length} column(s)</span>
            </div>
            <input type="text" value="${escapeHtml(entry.value)}"
                   data-kind="values" data-key="${escapeHtml(entry.value)}"
                   oninput="trimmerEditFix(this)"
                   onkeydown="trimmerLeftoverKeys(event, ${data.headers.length + index})">
        </div>`).join('');

    document.getElementById('clean-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>Stage 3: fix what is left by hand</strong>
            <span>Everything below still holds a non-English character after your rules ran.
            Edit the text on the right and apply — headers are renamed, and values are
            replaced only where a cell matches exactly, so a fix cannot bleed into a longer
            answer that contains it.</span>
        </div>
        <div class="shortcut-bar">
            <span><kbd>↓ ↑</kbd> next / previous field</span>
            <span><kbd>Enter</kbd> apply the fixes</span>
            <span><kbd>Esc</kbd> close</span>
        </div>
        <div id="trimmer-status" class="trimmer-status"></div>

        ${clean ? `
            <div class="preview-empty muted">
                Nothing left: no header or value holds a non-English character.
            </div>` : `
            ${data.headers.length ? `
                <div class="col-header-row"><div style="flex:1;">Header</div><div style="flex:1;">Replace with</div></div>
                ${headerRows}` : ''}
            ${data.values.length ? `
                <div class="col-header-row" style="margin-top:14px;"><div style="flex:1;">Value</div><div style="flex:1;">Replace with</div></div>
                ${valueRows}` : ''}
            ${data.truncated ? '<div class="diff-warn" style="margin-top:10px;">Only the first few hundred distinct values are listed.</div>' : ''}`}`;

    document.getElementById('clean-modal-footer').innerHTML = `
        <span class="muted" style="margin-right:auto;">
            ${data.headers.length} header(s), ${data.values.length} value(s) left</span>
        <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Close</button>
        <button class="btn btn-secondary" onclick="trimmerBack()">&larr; Back</button>
        <button class="btn btn-secondary" onclick="loadTrimmerLeftovers()">Rescan</button>
        <button class="btn btn-primary" onclick="trimmerApplyFixes()">Apply fixes</button>`;

    const first = document.querySelector('.leftover-row input');
    if (first) first.focus();
}

function trimmerEditFix(input) {
    trimmer.fixes[input.dataset.kind][input.dataset.key] = input.value;
}

function trimmerLeftoverKeys(event, index) {
    const inputs = document.querySelectorAll('.leftover-row input');
    if (event.key === 'Enter') {
        event.preventDefault();
        trimmerApplyFixes();
    } else if (event.key === 'ArrowDown' && index + 1 < inputs.length) {
        event.preventDefault();
        inputs[index + 1].focus();
    } else if (event.key === 'ArrowUp' && index > 0) {
        event.preventDefault();
        inputs[index - 1].focus();
    }
}

function trimmerApplyFixes() {
    const headers = {};
    const values = {};
    Object.entries(trimmer.fixes.headers).forEach(([key, value]) => {
        if (value && value !== key) headers[key] = value;
    });
    Object.entries(trimmer.fixes.values).forEach(([key, value]) => {
        if (value && value !== key) values[key] = value;
    });

    if (!Object.keys(headers).length && !Object.keys(values).length) {
        trimmerStatus('Nothing edited yet.', 'diff-warn');
        return;
    }

    apiPost('/api/text_rules/fix_leftovers', { headers, values })
        .then(data => {
            const result = data.result;
            log(`[SUCCESS] Fixed by hand: ${result.headers_renamed} header(s) renamed, ${result.cells_changed} cell(s) replaced across ${result.columns_changed} column(s).`, 'success');
            refreshStatus();
            return loadTrimmerLeftovers();
        })
        .catch(error => {
            trimmerStatus(escapeHtml(error.message), 'log-error');
            reportError(error);
        });
}

/* --- preview & apply ---------------------------------------------------- */

function trimmerRequestBody() {
    return {
        stage: trimmer.stage,
        rules: trimmerRules(),
        columns: trimmerColumnsPayload()
    };
}

function trimmerStatus(message, kind = 'muted') {
    const box = document.getElementById('trimmer-status');
    if (box) box.innerHTML = `<span class="${kind}">${message}</span>`;
}

function trimmerPreview() {
    trimmerStatus('Working out what would change...');

    return apiPost('/api/text_rules/preview', trimmerRequestBody())
        .then(preview => {
            trimmer.preview = preview;
            renderTrimmerPreview();

            const summary = preview.stage === 'headers'
                ? `${preview.columns_affected} of ${preview.columns_scanned} header(s) would change`
                : `${preview.cells_changed} cell(s) in ${preview.columns_affected} column(s) would change`;
            trimmerStatus(preview.columns_affected
                ? `Preview: ${summary}.`
                : 'Preview: nothing changes under these rules.',
                preview.columns_affected ? 'log-success' : 'diff-warn');

            // the box sits below the fold of a scrolling dialogue, so bring it up
            document.getElementById('trimmer-preview')
                .scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        })
        .catch(error => {
            trimmerStatus(escapeHtml(error.message), 'log-error');
            reportError(error);
        });
}

/* Apply the current chain and stay put, so a second chain can follow. */
function trimmerApply() {
    const isHeaders = trimmer.stage === 'headers';

    return apiPost('/api/text_rules/apply', trimmerRequestBody())
        .then(data => {
            const result = data.result;
            const summary = isHeaders
                ? `${result.headers_changed} header(s) changed`
                : `${result.cells_changed} cell(s) changed across ${result.columns_cleaned} column(s)`;

            log(`[SUCCESS] ${escapeHtml(result.description)}: ${summary}.`, 'success');
            trimmerStatus(`Applied — ${summary}. Continue when you are done here.`, 'log-success');

            trimmer.preview = null;
            refreshStatus();
            return trimmerReloadStage();     // pick up the new column names
        })
        .catch(error => {
            trimmerStatus(escapeHtml(error.message), 'log-error');
            reportError(error);
        });
}

/* Re-read the columns without leaving the stage. */
function trimmerReloadStage() {
    return getState().then(state => {
        trimmer.cols = state.cols;
        trimmer.numeric = new Set(state.numeric_columns || []);
        trimmer.ignored = new Set(state.ignored_columns || []);
        trimmer.selected[trimmer.stage] = null;
        renderTrimmerColumns();
        renderTrimmerPreview();
    }).catch(reportError);
}

function trimmerContinue() {
    const next = TRIMMER_STAGES[TRIMMER_STAGES.indexOf(trimmer.stage) + 1];
    if (!next) {
        log('> Tip: Clean -> Save Cleaning File (.json) records this work for the next wave.', 'info');
        closeModal('modal-clean');
        return Promise.resolve();
    }
    return trimmerGoToStage(next);
}

function trimmerBack() {
    const previous = TRIMMER_STAGES[TRIMMER_STAGES.indexOf(trimmer.stage) - 1];
    return previous ? trimmerGoToStage(previous) : Promise.resolve();
}
