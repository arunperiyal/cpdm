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
    showUnchanged: false
};

/* --- entry points ----------------------------------------------------- */

function openTextRulesWizard(stage = 'headers') {
    withDataset(state => {
        trimmer.cols = state.cols;
        trimmer.numeric = new Set(state.numeric_columns || []);
        trimmer.ignored = new Set(state.ignored_columns || []);
        trimmer.selected = { headers: null, values: null };
        trimmer.stage = stage;
        trimmer.preview = null;
        trimmer.anchor = null;
        renderTrimmer();
        openModal('modal-clean');
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
}

function trimmerSelectAll(all) {
    const selection = trimmerSelection();
    trimmer.visible.forEach(col => { if (all) selection.add(col); else selection.delete(col); });
    trimmer.preview = null;
    renderTrimmerColumns();
}

/* --- rendering --------------------------------------------------------- */

function renderTrimmer() {
    const isHeaders = trimmer.stage === 'headers';
    document.getElementById('clean-modal-header').innerText =
        `Clean -> Remove Non-English: Step ${isHeaders ? 1 : 2} of 2 — ${isHeaders ? 'Column Headers' : 'Cell Values'}`;

    document.getElementById('clean-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>${isHeaders ? 'Stage 1: clean the header row' : 'Stage 2: clean the cell values'}</strong>
            <span>${isHeaders
                ? 'Rules run in order against each column name. Nothing changes until you apply, and Preview shows the exact result first.'
                : 'Rules run in order against every cell of the selected columns. Numeric columns are skipped automatically.'}</span>
        </div>

        <div class="trimmer-grid">
            <div class="rule-card">
                <strong style="color:#89b4fa;">Rules (applied in order)</strong>
                <div id="trimmer-rules"></div>
                <button class="btn btn-secondary" style="margin-top:10px; padding:4px 10px; font-size:12px;"
                        onclick="trimmerAddRule()">+ Add rule</button>
            </div>

            <div class="rule-card">
                <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                    <strong style="color:#f38ba8; margin:0;">Apply to columns</strong>
                    <span>
                        <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;" onclick="trimmerSelectAll(true)">All</button>
                        <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;" onclick="trimmerSelectAll(false)">None</button>
                    </span>
                </div>
                <input type="text" id="trimmer-search" placeholder="Search columns..."
                       style="width:100%; margin:8px 0; font-size:12px;" oninput="renderTrimmerColumns()">
                <div id="trimmer-columns" class="trimmer-cols"></div>
                <div class="muted" style="margin-top:6px;">Shift-click to select a range.</div>
            </div>
        </div>

        <div id="trimmer-preview"></div>`;

    renderTrimmerRules();
    renderTrimmerColumns();
    renderTrimmerPreview();
    renderTrimmerFooter();
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
            <label class="col-pick ${skipped ? 'col-skipped' : ''}"
                   title="${skipped ? 'Numeric column — no text to trim' : safe}">
                <input type="checkbox" ${selection.has(col) ? 'checked' : ''} ${skipped ? 'disabled' : ''}
                       onclick="trimmerToggleColumn(${index}, event)">
                <span>${safe}</span>
            </label>`;
    }).join('') || '<div class="muted">No columns match.</div>';

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

    if (preview.stage === 'headers') {
        summary = `${preview.columns_affected} of ${preview.columns_scanned} header(s) change`;
        body = rows.length ? `
            <table class="preview-table">
                <thead><tr><th>Before</th><th>After</th><th>Note</th></tr></thead>
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
                    <strong style="color:#a6e3a1;">Preview — ${escapeHtml(preview.description)}</strong>
                    <div class="muted">${summary}</div>
                </div>
                ${toggle}
            </div>
            ${body}
        </div>`;
}

function renderTrimmerFooter() {
    const isHeaders = trimmer.stage === 'headers';
    document.getElementById('clean-modal-footer').innerHTML = `
        <span id="trimmer-selection-count" class="muted" style="margin-right:auto;"></span>
        <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Cancel</button>
        ${isHeaders
            ? '<button class="btn btn-secondary" onclick="trimmerGoToValues()">Skip headers &rarr;</button>'
            : '<button class="btn btn-secondary" onclick="trimmerGoToHeaders()">&larr; Back</button>'}
        <button class="btn btn-secondary" onclick="trimmerPreview()">Preview</button>
        <button class="btn btn-primary" onclick="trimmerApply()">
            ${isHeaders ? 'Apply &amp; continue &rarr;' : 'Apply &amp; finish'}</button>`;
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
        renderTrimmer();
    }).catch(reportError);
}

function trimmerGoToValues() { return trimmerGoToStage('values'); }
function trimmerGoToHeaders() { return trimmerGoToStage('headers'); }

/* --- preview & apply ---------------------------------------------------- */

function trimmerRequestBody() {
    return {
        stage: trimmer.stage,
        rules: trimmerRules(),
        columns: trimmerColumnsPayload()
    };
}

function trimmerPreview() {
    return apiPost('/api/text_rules/preview', trimmerRequestBody())
        .then(preview => {
            trimmer.preview = preview;
            renderTrimmerPreview();
        })
        .catch(reportError);
}

function trimmerApply() {
    const isHeaders = trimmer.stage === 'headers';

    return apiPost('/api/text_rules/apply', trimmerRequestBody())
        .then(data => {
            const result = data.result;
            if (isHeaders) {
                log(`[SUCCESS] ${escapeHtml(result.description)}: ${result.headers_changed} header(s) changed.`, 'success');
                return trimmerGoToValues();
            }
            log(`[SUCCESS] ${escapeHtml(result.description)}: ${result.cells_changed} cell(s) changed across ${result.columns_cleaned} column(s).`, 'success');
            log('> Tip: Clean -> Save Cleaning File (.json) records these rules for the next wave.', 'info');
            closeModal('modal-clean');
            refreshStatus();
            return null;
        })
        .catch(reportError);
}
