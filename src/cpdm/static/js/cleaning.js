/* Clean menu: the two-step wizard, the text trimmer, and cleaning recipes.
   All of these reuse the single #modal-clean shell. */

/* --- step 1: headers & column selection ------------------------------ */

function startCleaningWizard() {
    withDataset(state => {
        renderHeaderCleanStep(state.cols, state.ignored_columns || []);
        openModal('modal-clean');
    });
}

function toggleAllColumns(selectAll) {
    document.querySelectorAll('.col-process-chk').forEach(chk => { chk.checked = selectAll; });
}

function renderHeaderCleanStep(cols, ignoredCols = []) {
    document.getElementById('clean-modal-header').innerText =
        'Clean -> Step 1: Header Mapping & Column Selection';
    const ignored = new Set(ignoredCols);

    let html = `
        <div class="hint-box" style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
            <div>
                <strong>Column Selection &amp; Header Mapping</strong>
                <span>Uncheck any columns you want to <strong>ignore</strong> during unique value replacement.</span>
            </div>
            <button class="btn btn-secondary" style="color:#89b4fa; border:1px solid #89b4fa; white-space:nowrap;"
                    onclick="openTextTrimmer()">&#9889; Remove Non-English / Trim Text</button>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span class="muted" style="font-weight:bold;">Total Columns: ${cols.length}</span>
            <div>
                <button class="btn btn-secondary" style="padding:3px 8px; font-size:11px;" onclick="toggleAllColumns(true)">Select All</button>
                <button class="btn btn-secondary" style="padding:3px 8px; font-size:11px; margin-left:4px;" onclick="toggleAllColumns(false)">Deselect All</button>
            </div>
        </div>

        <div class="col-header-row">
            <div style="width:110px; text-align:center;">Clean Values?</div>
            <div style="flex:1;">Original Header</div>
            <div style="width:45%;">New Mapped Header</div>
        </div>`;

    cols.forEach(col => {
        const safe = escapeHtml(col);
        html += `
            <div class="form-row" style="align-items:flex-start; margin-bottom:8px; gap:10px;">
                <div style="width:110px; text-align:center; padding-top:5px;">
                    <input type="checkbox" class="col-process-chk" data-old="${safe}"
                           ${ignored.has(col) ? '' : 'checked'}
                           style="cursor:pointer; transform:scale(1.1);"
                           title="Include in unique value replacement">
                </div>
                <div class="muted" style="color:#cdd6f4; flex:1; word-break:break-word; max-height:80px; overflow-y:auto;" title="${safe}">${safe}</div>
                <textarea class="header-clean-input" data-old="${safe}"
                          style="width:45%; height:60px; font-size:11px; background:#11111b; color:#cdd6f4; border:1px solid #45475a; border-radius:4px; padding:4px; resize:vertical;">${safe}</textarea>
            </div>`;
    });

    document.getElementById('clean-modal-body').innerHTML = html;
    document.getElementById('clean-modal-footer').innerHTML = `
        <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Cancel</button>
        <button class="btn btn-primary" onclick="submitHeaderCleaning()">Save Mapping &amp; Proceed to Value Replacement -&gt;</button>`;
}

function submitHeaderCleaning() {
    const headerMap = {};
    const ignoredCols = [];

    document.querySelectorAll('.col-process-chk').forEach(chk => {
        if (!chk.checked) ignoredCols.push(chk.dataset.old);
    });
    document.querySelectorAll('.header-clean-input').forEach(input => {
        headerMap[input.dataset.old] = input.value.trim() || input.dataset.old;
    });

    apiPost('/api/clean_headers', { header_map: headerMap, ignored_cols: ignoredCols })
        .then(() => {
            log(`[SUCCESS] Header mapping applied. Ignored ${ignoredCols.length} column(s) from value replacement.`, 'success');
            // The server now holds the ignore list under the post-rename names.
            renderValueCleanStep();
        })
        .catch(reportError);
}

/* --- step 2: global value replacement -------------------------------- */

function renderValueCleanStep(extraIgnoredCols = []) {
    document.getElementById('clean-modal-header').innerText = 'Clean -> Step 2: Text Value Replacement';
    const body = document.getElementById('clean-modal-body');
    body.innerHTML = '<p class="muted">Loading unmapped text unique values across dataset...</p>';

    apiPost('/api/get_unique_values', { ignored_cols: extraIgnoredCols })
        .then(data => {
            const uniques = data.uniques || [];

            if (!uniques.length) {
                body.innerHTML = `
                    <div style="padding:20px; text-align:center;" class="muted">
                        <p style="margin-bottom:8px; font-weight:bold;">All values are mapped, or no non-numeric text columns are selected.</p>
                        <span>(Deselected columns and previously mapped values are hidden.)</span>
                    </div>`;
            } else {
                let html = `
                    <div class="hint-box">
                        <strong>Global Unique Value Mapping (${uniques.length} unique text string(s) found)</strong>
                        <span>Mapping a text value here replaces it globally across <strong>all active columns</strong> where it appears.</span>
                    </div>
                    <div class="col-header-row">
                        <div style="flex:1;">Original Text Value</div>
                        <div style="flex:1;">New Replacement Target</div>
                    </div>`;

                uniques.forEach(item => {
                    const safe = escapeHtml(item.value);
                    const tooltip = escapeHtml(`Found in ${item.columns.length} column(s):\n` + item.columns.join('\n'));
                    html += `
                        <div class="form-row" style="align-items:center; margin-bottom:8px; gap:10px;">
                            <div style="flex:1; overflow:hidden;" title="${tooltip}">
                                <span style="font-size:11px; color:#cdd6f4; display:block; word-break:break-word;">${safe}</span>
                                <span class="muted">Found in ${item.columns.length} column(s)</span>
                            </div>
                            <input type="text" class="val-clean-input" data-old="${safe}" value="${safe}" style="flex:1;">
                        </div>`;
                });
                body.innerHTML = html;
            }

            document.getElementById('clean-modal-footer').innerHTML = `
                <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Finish / Close</button>
                <button class="btn btn-primary" onclick="submitValueCleaning()">Apply Cell Replacements Globally</button>`;
        })
        .catch(reportError);
}

function submitValueCleaning() {
    const replacements = {};
    document.querySelectorAll('.val-clean-input').forEach(input => {
        const oldValue = input.dataset.old;
        const newValue = input.value.trim();
        if (oldValue && newValue && oldValue !== newValue) replacements[oldValue] = newValue;
    });

    if (!Object.keys(replacements).length) {
        log('[INFO] No value changes to apply.', 'info');
        closeModal('modal-clean');
        return;
    }

    apiPost('/api/clean_values', { replacements })
        .then(() => {
            log('[SUCCESS] Cell value replacements applied globally across dataset.', 'success');
            log('> Tip: Save your recipe via Clean -> Save Cleaning File (.json).', 'info');
            closeModal('modal-clean');
        })
        .catch(reportError);
}

/* --- cleaning recipes ------------------------------------------------- */

function exportCleaningRules() {
    getState().then(state => {
        if (!state.has_cleaning_rules) {
            logError('No cleaning/mapping actions recorded yet.');
            return;
        }
        log('> Generating cleaning rules .json download...', 'info');
        window.location.href = '/api/export_cleaning_rules';
    }).catch(reportError);
}

function triggerRulesFileSelect() { document.getElementById('rules-file-input').click(); }

function applyCleaningRulesFile() {
    const input = document.getElementById('rules-file-input');
    if (!input.files.length) return;
    const file = input.files[0];

    log(`> Uploading and applying rules from ${escapeHtml(file.name)}...`, 'info');
    apiUpload('/api/apply_cleaning_rules_file', file)
        .then(data => {
            const res = data.result;
            log(res.version === 2
                ? `[SUCCESS] Recipe replayed: ${res.steps_applied} step(s), ${res.text_rule_steps} of them text rules — ${res.headers_changed} header(s) and ${res.cells_changed} cell(s) changed.`
                : `[SUCCESS] Rules applied! Mapped ${res.headers_changed} header(s), ignored ${res.ignored_columns_count} column(s), and applied replacements from ${res.columns_replaced} entry group(s).`,
                'success');
            refreshStatus();
        })
        .catch(reportError)
        .finally(() => { input.value = ''; });
}
