/* Scales menu: declare a scale on a group, describe it, then score the data.

   A scale has Items (its columns, each Direct or Reverse) and Options (its
   ordered response set, each with a score). Scoring the data maps answers to
   those scores within the scale's own columns, then flips the reverse items. */

const scaleUI = {
    detail: null,       // the scale being edited in either assign dialogue
    options: [],        // working copy: [{label, score}]
    items: []           // working copy: [{column, type}]
};

/* --- declaring scales on groups ---------------------------------------- */

function openCreateScaleModal() {
    withDataset(() => refreshScales().then(() => openModal('modal-create-scale')));
}

function refreshScales() {
    return apiGet('/api/scales')
        .then(data => {
            renderScaleList(data.scales);
            renderScaleForm(data.groups);
        })
        .catch(reportError);
}

function renderScaleList(scales) {
    document.getElementById('scale-list').innerHTML = scales.length
        ? scales.map(scale => `
            <div class="form-row">
                <div>
                    <strong>${escapeHtml(scale.name)}</strong>
                    <span class="muted" style="display:block;">
                        group '${escapeHtml(scale.group)}' —
                        ${scale.column_count} item(s), ${scale.reverse_items} reverse;
                        ${scale.option_count} option(s), ${scale.scored_options} scored
                    </span>
                </div>
                <span style="display:flex; gap:4px;">
                    <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                            data-name="${escapeHtml(scale.name)}"
                            onclick="openAssignScoringModal(this.dataset.name)">Scoring</button>
                    <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                            data-name="${escapeHtml(scale.name)}"
                            onclick="openAssignTypesModal(this.dataset.name)">Types</button>
                    <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                            data-name="${escapeHtml(scale.name)}"
                            onclick="renameScaleItems(this.dataset.name)">Rename items</button>
                    <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                            data-name="${escapeHtml(scale.name)}"
                            onclick="removeScale(this.dataset.name)">Delete</button>
                </span>
            </div>`).join('')
        : '<div class="muted">No scales yet.</div>';
}

function renderScaleForm(groups) {
    const free = groups.filter(group => !group.taken_by && group.column_count);
    const select = document.getElementById('scale-group');

    select.innerHTML = free.map(group => {
        const indent = '&nbsp;'.repeat(group.depth * 4) + (group.depth ? '&#8627; ' : '');
        return `<option value="${escapeHtml(group.name)}">
                    ${indent}${escapeHtml(group.name)} (${group.column_count} col)
                </option>`;
    }).join('');

    const note = document.getElementById('scale-form-note');
    if (!groups.length) {
        note.innerHTML = 'Build a group first in <strong>Fields &#8594; Groups</strong> — a scale reads its columns from one.';
    } else if (!free.length) {
        note.innerHTML = 'Every group with columns already has a scale. Add another group, or delete a scale below.';
    } else {
        note.textContent = 'The scale takes the group’s columns. Leave the name blank to reuse the group name.';
    }
    select.disabled = !free.length;
    previewScaleGroup();
}

/* Show the items and options the chosen group would give the scale. */
function previewScaleGroup() {
    const group = document.getElementById('scale-group').value;
    const box = document.getElementById('scale-group-preview');
    if (!group) { box.innerHTML = ''; return; }

    apiPost('/api/scales/inspect_group', { group })
        .then(data => {
            box.innerHTML = `
                <div class="scale-preview">
                    <div>
                        <strong class="muted">Items (${data.items.length})</strong>
                        <div class="chip-list">${data.items.map(col =>
                            `<span class="chip">${escapeHtml(col)}</span>`).join('')}</div>
                    </div>
                    <div>
                        <strong class="muted">Options found in the data (${data.options.length})</strong>
                        <div class="chip-list">${data.options.map(label =>
                            `<span class="chip">${escapeHtml(label)}</span>`).join('') ||
                            '<span class="muted">none</span>'}</div>
                        ${data.truncated ? '<div class="log-error" style="font-size:11px;">Too many distinct answers — this group looks like free text.</div>' : ''}
                    </div>
                </div>`;
        })
        .catch(reportError);
}

function submitCreateScale() {
    const group = document.getElementById('scale-group').value;
    const name = document.getElementById('scale-name').value.trim();
    if (!group) { logError('Pick a group to build the scale on.'); return; }

    const rename = document.getElementById('scale-rename').checked;

    apiPost('/api/create_scale', { group, name: name || null, rename })
        .then(data => {
            const scored = data.scale.options.filter(option => option.score !== null).length;
            log(`[SUCCESS] Scale '${escapeHtml(data.scale.name)}' declared on group '${escapeHtml(data.scale.group)}' with ${data.scale.options.length} option(s) found in the data.`, 'success');
            if (rename) log(`[INFO] Items renamed to '${escapeHtml(data.scale.name)}_1', '${escapeHtml(data.scale.name)}_2', …`, 'info');
            log(scored
                ? '> Answers were already numbers, so the scale is scored. Set the keying in Scales -> Assign Scoring Type.'
                : '> Next: Scales -> Assign Scoring to put the options in order and score them.', 'info');
            document.getElementById('scale-name').value = '';
            return refreshScales();
        })
        .catch(reportError);
}

function removeScale(name) {
    apiPost('/api/delete_scale', { scale_name: name })
        .then(data => {
            log(`[INFO] Scale '${escapeHtml(name)}' removed. Its group and columns stay.`, 'info');
            if (data.restored.length) {
                log(`[INFO] Put back the answers in ${data.restored.length} column(s) that its scoring had replaced.`, 'info');
            }
            refreshStatus();
            return refreshScales();
        })
        .catch(reportError);
}

/* --- shared scale picker ------------------------------------------------ */

function loadScaleDetail(name, render) {
    return apiGet(`/api/scales/${encodeURIComponent(name)}`)
        .then(detail => {
            scaleUI.detail = detail;
            scaleUI.options = detail.options.map(option => ({ ...option }));
            scaleUI.items = detail.items.map(item => ({ ...item }));
            render();
        })
        .catch(reportError);
}

function scalePicker(selectId, current, handler) {
    return getState().then(state => {
        const names = state.defined_scales;
        if (!names.length) return null;
        const options = names.map(name =>
            `<option value="${escapeHtml(name)}" ${name === current ? 'selected' : ''}>${escapeHtml(name)}</option>`
        ).join('');
        return `<label class="muted">Scale</label>
                <select id="${selectId}" style="width:100%; margin:4px 0 14px;"
                        onchange="${handler}(this.value)">${options}</select>`;
    });
}

/* --- Assign Scoring: numbers for the options ---------------------------- */

function openAssignScoringModal(name) {
    withDataset(state => {
        if (!state.defined_scales.length) {
            logError('No scales yet. Declare one in Scales -> Create Scale.');
            return;
        }
        openModal('modal-assign-scoring');
        loadScaleDetail(name || state.defined_scales[0], renderAssignScoring);
    });
}

function renderAssignScoring() {
    const detail = scaleUI.detail;

    scalePicker('scoring-scale', detail.name, 'switchScoringScale').then(picker => {
        const rows = scaleUI.options.map((option, index) => `
            <div class="option-row">
                <span class="rule-actions">
                    <button class="btn btn-secondary" title="Move up" onclick="moveOption(${index}, -1)">&uarr;</button>
                    <button class="btn btn-secondary" title="Move down" onclick="moveOption(${index}, 1)">&darr;</button>
                </span>
                <input type="text" value="${escapeHtml(option.label)}" class="option-label"
                       oninput="editOption(${index}, 'label', this.value)">
                <input type="number" step="any" class="option-score"
                       value="${option.score === null || option.score === undefined ? '' : option.score}"
                       placeholder="—" title="Leave blank to treat this answer as missing"
                       oninput="editOption(${index}, 'score', this.value)">
                <button class="btn btn-secondary" title="Remove" onclick="removeOption(${index})">&times;</button>
            </div>`).join('');

        document.getElementById('assign-scoring-body').innerHTML = `
            ${picker}
            <div class="hint-box">
                <strong>Score each answer</strong>
                <span>The order is the response order — set it here, then <em>Number 1…n</em>
                fills the scores in. Leave a score blank for an answer that should count as
                missing, such as “not applicable”; blanks stay out of the scale's range.</span>
            </div>

            <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px;">
                <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                        onclick="autoscoreOptions(1, 1)">Number 1…n</button>
                <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                        onclick="autoscoreOptions(${scaleUI.options.length}, -1)">Number n…1</button>
                <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                        onclick="refreshOptionsFromData()">Find new answers in the data</button>
            </div>

            <div class="option-head">
                <span>Order</span><span>Option</span><span>Score</span><span></span>
            </div>
            <div id="option-rows">${rows || '<div class="muted">No options yet.</div>'}</div>

            <div style="display:flex; gap:8px; margin-top:10px;">
                <input type="text" id="new-option" placeholder="Add an option that is not in the data"
                       style="flex:1;" onkeydown="if (event.key === 'Enter') addOption()">
                <button class="btn btn-secondary" onclick="addOption()">Add</button>
            </div>

            <div class="muted" style="margin-top:10px;">${scoringRangeNote()}</div>`;
    });
}

function scoringRangeNote() {
    const scores = scaleUI.options
        .map(option => option.score)
        .filter(score => score !== null && score !== undefined && score !== '');
    if (!scores.length) return 'No scores yet — nothing can be applied until at least one option is scored.';

    const min = Math.min(...scores.map(Number));
    const max = Math.max(...scores.map(Number));
    const blanks = scaleUI.options.length - scores.length;
    return `Range ${min} to ${max}; reverse items will use ${min + max} − value.`
        + (blanks ? ` ${blanks} option(s) left blank, treated as missing.` : '');
}

function switchScoringScale(name) { loadScaleDetail(name, renderAssignScoring); }

function editOption(index, field, value) {
    scaleUI.options[index][field] = field === 'score'
        ? (value === '' ? null : Number(value))
        : value;
    document.querySelector('#assign-scoring-body .muted:last-child').textContent = scoringRangeNote();
}

function moveOption(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= scaleUI.options.length) return;
    [scaleUI.options[index], scaleUI.options[target]] = [scaleUI.options[target], scaleUI.options[index]];
    renderAssignScoring();
}

function removeOption(index) {
    scaleUI.options.splice(index, 1);
    renderAssignScoring();
}

function addOption() {
    const input = document.getElementById('new-option');
    const label = input.value.trim();
    if (!label) return;
    scaleUI.options.push({ label, score: null });
    input.value = '';
    renderAssignScoring();
}

function autoscoreOptions(start, step) {
    scaleUI.options.forEach((option, index) => { option.score = start + index * step; });
    renderAssignScoring();
}

function refreshOptionsFromData() {
    saveOptions(true)
        .then(() => apiPost('/api/scales/options/refresh', { name: scaleUI.detail.name }))
        .then(data => {
            log(data.added.length
                ? `[INFO] Added ${data.added.length} answer(s) found in the data: ${escapeHtml(data.added.join(', '))}.`
                : '[INFO] No new answers in the data.', 'info');
            scaleUI.detail = data.scale;
            scaleUI.options = data.scale.options.map(option => ({ ...option }));
            renderAssignScoring();
        })
        .catch(reportError);
}

function saveOptions(quiet) {
    return apiPost('/api/scales/options', {
        name: scaleUI.detail.name,
        options: scaleUI.options
    }).then(data => {
        if (!quiet) {
            const scored = data.scale.options.filter(o => o.score !== null).length;
            log(`[SUCCESS] Scale '${escapeHtml(data.scale.name)}': ${data.scale.options.length} option(s), ${scored} scored.`, 'success');
            log(scored
                ? '> The scale\'s columns now hold those scores. Scales -> View Scoring shows the result.'
                : '> Nothing is scored yet, so the data is untouched.', 'info');
            refreshStatus();
        }
        scaleUI.detail = data.scale;
        return data.scale;
    });
}

function submitOptions() {
    saveOptions(false)
        .then(() => {
            closeModal('modal-assign-scoring');
            refreshScales();
        })
        .catch(reportError);
}

/* --- Assign Scoring Type: Direct or Reverse per item -------------------- */

function openAssignTypesModal(name) {
    withDataset(state => {
        if (!state.defined_scales.length) {
            logError('No scales yet. Declare one in Scales -> Create Scale.');
            return;
        }
        openModal('modal-assign-types');
        loadScaleDetail(name || state.defined_scales[0], renderAssignTypes);
    });
}

function renderAssignTypes() {
    const detail = scaleUI.detail;

    scalePicker('types-scale', detail.name, 'switchTypesScale').then(picker => {
        const range = (detail.score_min === null)
            ? 'This scale has no scored options yet, so reverse items cannot be flipped. Set them in Assign Scoring first.'
            : `Reverse items become ${detail.score_min + detail.score_max} − value, from the scale's own range (${detail.score_min}…${detail.score_max}).`;

        const rows = scaleUI.items.map((item, index) => `
            <div class="form-row">
                <span>${escapeHtml(item.column)}</span>
                <select onchange="editItemType(${index}, this.value)">
                    <option value="Direct" ${item.type === 'Direct' ? 'selected' : ''}>Direct</option>
                    <option value="Reverse" ${item.type === 'Reverse' ? 'selected' : ''}>Reverse</option>
                </select>
            </div>`).join('');

        document.getElementById('assign-types-body').innerHTML = `
            ${picker}
            <div class="hint-box">
                <strong>Which items are reverse-keyed?</strong>
                <span>${range}</span>
            </div>
            <div style="display:flex; gap:8px; margin-bottom:10px;">
                <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                        onclick="setAllItemTypes('Direct')">All direct</button>
                <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                        onclick="setAllItemTypes('Reverse')">All reverse</button>
            </div>
            <div class="scroll-box">${rows || '<div class="muted">This scale has no items.</div>'}</div>`;
    });
}

function switchTypesScale(name) { loadScaleDetail(name, renderAssignTypes); }

function editItemType(index, type) { scaleUI.items[index].type = type; }

function setAllItemTypes(type) {
    scaleUI.items.forEach(item => { item.type = type; });
    renderAssignTypes();
}

function submitItemTypes() {
    const items = {};
    scaleUI.items.forEach(item => { items[item.column] = item.type; });

    apiPost('/api/scales/items', { name: scaleUI.detail.name, items })
        .then(data => {
            const reversed = data.scale.items.filter(item => item.type === 'Reverse').length;
            log(`[SUCCESS] Scale '${escapeHtml(data.scale.name)}': ${reversed} of ${data.scale.items.length} item(s) reverse-keyed, and the columns re-scored.`, 'success');
            closeModal('modal-assign-types');
            refreshStatus();
            refreshScales();
        })
        .catch(reportError);
}

/* --- View Scoring: what the scoring currently does ---------------------- */

function openViewScoringModal() {
    withDataset(state => {
        if (!state.defined_scales.length) {
            logError('No scales yet. Declare one in Scales -> Create Scale.');
            return;
        }
        document.getElementById('view-scoring-body').innerHTML = '<p class="muted">Reading the scales...</p>';
        openModal('modal-view-scoring');

        apiPost('/api/scales/status', {})
            .then(data => renderScoringStatus(data.plans))
            .catch(error => {
                document.getElementById('view-scoring-body').innerHTML =
                    `<p class="log-error">${escapeHtml(error.message)}</p>`;
            });
    });
}

function renderScoringStatus(plans) {
    if (!plans.length) {
        document.getElementById('view-scoring-body').innerHTML = `
            <div class="muted" style="padding:14px; text-align:center;">
                No scale has scored options yet, so nothing is being scored.<br>
                Set the scores in <strong>Scales &#8594; Assign Scoring</strong>.
            </div>`;
        return;
    }

    document.getElementById('view-scoring-body').innerHTML = `
        <div class="hint-box">
            <strong>Scoring is applied as you define it</strong>
            <span>Each item below holds its option's score, with reverse items flipped.
            The answers are kept, so editing a score or a keying re-derives the column
            rather than scoring what is already scored — and deleting a scale puts the
            answers back.</span>
        </div>
        ${plans.map(plan => `
            <div class="preview-box">
                <div class="preview-head">
                    <div>
                        <strong style="color:#a6e3a1;">${escapeHtml(plan.scale)}</strong>
                        <div class="muted">scores ${plan.score_min}…${plan.score_max}; ${escapeHtml(plan.reversal_note)}</div>
                    </div>
                    <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                            data-name="${escapeHtml(plan.scale)}"
                            onclick="openAssignScoringModal(this.dataset.name)">Edit scoring</button>
                </div>
                ${plan.unscored_options.length ? `<div class="diff-warn" style="margin-bottom:8px;">
                    Unscored option(s), counted as missing: ${escapeHtml(plan.unscored_options.join(', '))}</div>` : ''}
                <table class="preview-table">
                    <thead><tr><th>Item</th><th>Type</th><th>Scored</th><th>Blank</th><th>Not recognised</th></tr></thead>
                    <tbody>${plan.items.map(item => `
                        <tr>
                            <td>${escapeHtml(item.column)}</td>
                            <td class="${item.type === 'Reverse' ? 'diff-after' : 'muted'}">${item.type}</td>
                            <td>${item.scored_cells}</td>
                            <td class="muted">${item.blank_cells}</td>
                            <td class="diff-warn">${escapeHtml(item.unmapped.join(', '))}</td>
                        </tr>`).join('')}</tbody>
                </table>
            </div>`).join('')}`;
}

/* --- renaming a scale's items ------------------------------------------- */

function renameScaleItems(name) {
    const prefix = window.prompt(
        `Rename the items of '${name}' to <prefix>_1, <prefix>_2, …`, name);
    if (prefix === null) return;

    apiPost('/api/scales/rename_items', { name, prefix: prefix.trim() || null })
        .then(data => {
            const count = Object.keys(data.renamed).length;
            log(count
                ? `[SUCCESS] Renamed ${count} item(s): ${escapeHtml(data.columns.join(', '))}.`
                : '[INFO] The items already have those names.', 'success');
            refreshScales();
            refreshStatus();
        })
        .catch(reportError);
}
