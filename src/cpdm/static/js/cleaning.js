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

/* --- quick text trimmer (values only) -------------------------------- */

function openTextTrimmer() {
    withDataset(() => {
        document.getElementById('clean-modal-header').innerText = 'Clean -> Language & Text Trimming Tool';
        document.getElementById('clean-modal-body').innerHTML = `
            <div class="hint-box">
                <strong>Automatic Text Scrubber</strong>
                <span>Choose how to trim or remove non-English / non-Latin characters across all active columns.</span>
            </div>
            <div class="rule-card">
                <label>
                    <input type="radio" name="scrub_mode" value="non_english_to_end" checked>
                    <strong style="display:inline;">Remove from the first non-English character to the end</strong>
                    <div class="muted">e.g. "WhatsApp (&#3381;&#3390;&#3377;&#3405;&#3377;&#3390;&#3370;&#3405;&#3370;&#3405;)" -&gt; "WhatsApp ("</div>
                </label>
                <label>
                    <input type="radio" name="scrub_mode" value="delimiter_to_end">
                    <strong style="display:inline;">Remove after a specific character / delimiter</strong>
                    <div class="muted" style="margin-bottom:6px;">Cuts the text at the character you enter (e.g. / - ( ,)</div>
                    <input type="text" id="scrub-delimiter" placeholder="e.g. / or - or (" style="width:200px; font-size:12px;">
                </label>
                <label style="margin-bottom:0;">
                    <input type="radio" name="scrub_mode" value="strip_non_english">
                    <strong style="display:inline;">Strip all non-English characters entirely</strong>
                    <div class="muted">Removes non-ASCII scripts anywhere in the string, keeping English words and punctuation.</div>
                </label>
            </div>`;

        document.getElementById('clean-modal-footer').innerHTML = `
            <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Cancel</button>
            <button class="btn btn-primary" onclick="submitTextTrimming()">Apply Text Trimming</button>`;

        openModal('modal-clean');
    });
}

function submitTextTrimming() {
    const mode = document.querySelector('input[name="scrub_mode"]:checked').value;
    const delimiter = document.getElementById('scrub-delimiter')?.value || '';

    if (mode === 'delimiter_to_end' && !delimiter) {
        logError('Please enter a character/delimiter for the delimiter rule.');
        return;
    }

    apiPost('/api/clean_text_pattern', { mode, delimiter })
        .then(data => {
            log(`[SUCCESS] Text trimming applied across ${data.columns_processed} active column(s).`, 'success');
            startCleaningWizard();  // reload step 1 so the cleaned text is visible
        })
        .catch(reportError);
}

/* --- Clean -> Remove Non-English (headers + values + exemptions) ------ */

function ruleOptions(group, delimiterId) {
    return `
        <label><input type="radio" name="${group}" value="none" checked> Do not modify</label>
        <label><input type="radio" name="${group}" value="non_english_to_end"> Remove from 1st non-English character to the end</label>
        <label><input type="radio" name="${group}" value="strip_non_english"> Strip all non-English characters entirely</label>
        <label style="display:flex; align-items:center; gap:8px; margin-bottom:0;">
            <input type="radio" name="${group}" value="delimiter_to_end"> Remove after character/delimiter:
            <input type="text" id="${delimiterId}" placeholder="e.g. / or -" style="width:80px; font-size:11px;">
        </label>`;
}

function openRemoveNonEnglishModal() {
    withDataset(state => {
        document.getElementById('clean-modal-header').innerText = 'Clean -> Remove Non-English / Text Trimmer';

        const colsHtml = state.cols.map(col => {
            const safe = escapeHtml(col);
            return `
                <label style="display:flex; align-items:center; gap:6px; font-size:11px; color:#cdd6f4; background:#11111b; padding:4px 8px; border-radius:4px; border:1px solid #313244;">
                    <input type="checkbox" class="exempt-col-chk" value="${safe}">
                    <span>${safe}</span>
                </label>`;
        }).join('');

        document.getElementById('clean-modal-body').innerHTML = `
            <div style="display:flex; gap:20px; flex-wrap:wrap;">
                <div style="flex:1.2; min-width:320px; display:flex; flex-direction:column; gap:15px;">
                    <div class="rule-card">
                        <strong style="color:#89b4fa;">1. Column Headers Rule</strong>
                        ${ruleOptions('header_mode', 'hdr-delimiter')}
                    </div>
                    <div class="rule-card">
                        <strong style="color:#a6e3a1;">2. Cell Values Rule</strong>
                        ${ruleOptions('value_mode', 'val-delimiter')}
                    </div>
                </div>
                <div class="rule-card" style="flex:1; min-width:240px; display:flex; flex-direction:column;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <strong style="color:#f38ba8; margin:0;">3. Exempt Columns</strong>
                        <span class="muted">Checked = skip cleaning</span>
                    </div>
                    <div style="flex:1; max-height:280px; overflow-y:auto; display:flex; flex-direction:column; gap:4px; padding-right:4px;">
                        ${colsHtml}
                    </div>
                </div>
            </div>`;

        document.getElementById('clean-modal-footer').innerHTML = `
            <button class="btn btn-secondary" onclick="closeModal('modal-clean')">Cancel</button>
            <button class="btn btn-primary" onclick="submitRemoveNonEnglish()">Execute Cleaning Rules</button>`;

        openModal('modal-clean');
    });
}

function submitRemoveNonEnglish() {
    const headerMode = document.querySelector('input[name="header_mode"]:checked').value;
    const valueMode = document.querySelector('input[name="value_mode"]:checked').value;

    if (headerMode === 'none' && valueMode === 'none') {
        logError('Select at least one cleaning rule for headers or values.');
        return;
    }

    const exemptCols = Array.from(document.querySelectorAll('.exempt-col-chk:checked')).map(c => c.value);

    apiPost('/api/remove_non_english_advanced', {
        header_cfg: { mode: headerMode, delimiter: document.getElementById('hdr-delimiter')?.value || '' },
        value_cfg: { mode: valueMode, delimiter: document.getElementById('val-delimiter')?.value || '' },
        exempt_cols: exemptCols
    })
        .then(data => {
            const res = data.result;
            log(`[SUCCESS] Advanced cleaning applied! Modified ${res.headers_changed} header(s) and cleaned cell values across ${res.columns_cleaned} column(s) (exempted ${res.exempt_columns_count}).`, 'success');
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
            log(`[SUCCESS] Rules applied! Mapped ${res.headers_changed} header(s), ignored ${res.ignored_columns_count} column(s), and applied replacements from ${res.columns_replaced} entry group(s).`, 'success');
            refreshStatus();
        })
        .catch(reportError)
        .finally(() => { input.value = ''; });
}
