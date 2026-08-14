/* Fields & Scales menus: categorisation, scale definitions, numerise, scoring. */

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
                        from group '${escapeHtml(scale.group)}' — ${scale.column_count} column(s)
                    </span>
                </div>
                <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;"
                        data-name="${escapeHtml(scale.name)}"
                        onclick="removeScale(this.dataset.name)">Delete</button>
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
}

function submitCreateScale() {
    const group = document.getElementById('scale-group').value;
    const name = document.getElementById('scale-name').value.trim();
    if (!group) { logError('Pick a group to build the scale on.'); return; }

    apiPost('/api/create_scale', { group, name: name || null })
        .then(data => {
            log(`[SUCCESS] Scale '${escapeHtml(data.scale.name)}' declared on group '${escapeHtml(data.scale.group)}'.`, 'success');
            document.getElementById('scale-name').value = '';
            return refreshScales();
        })
        .catch(reportError);
}

function removeScale(name) {
    apiPost('/api/delete_scale', { scale_name: name })
        .then(() => {
            log(`[INFO] Scale '${escapeHtml(name)}' removed. Its group and columns are untouched.`, 'info');
            return refreshScales();
        })
        .catch(reportError);
}

/* --- numerise ---------------------------------------------------------- */

function openNumeriseModal() {
    withDataset(state => {
        const select = document.getElementById('num-target-scale');
        select.innerHTML = '<option value="">-- All Scale Groups --</option>' +
            state.defined_scales.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');
        openModal('modal-numerise');
    });
}

function applyNumerise() {
    const prefix = document.getElementById('num-prefix').value;
    const targetScale = document.getElementById('num-target-scale').value;

    apiPost('/api/numerise', { prefix, target_scale: targetScale || null })
        .then(data => {
            log(`[SUCCESS] Scale column headers renamed with prefix '${escapeHtml(prefix)}'.`, 'success');
            log('Updated Columns: ' + escapeHtml(data.cols.join(', ')));
            closeModal('modal-numerise');
        })
        .catch(reportError);
}

/* --- scoring ----------------------------------------------------------- */

function openScoringModal() {
    withDataset(state => {
        const scaleCols = scaleColumnsOf(state);
        if (!scaleCols.length) {
            logError('No columns belong to a scale yet. Build one in Fields -> Groups.');
            return;
        }

        document.getElementById('scoring-body').innerHTML = scaleCols.map(col => {
            const group = state.categories[col].replace('Scale: ', '');
            const safe = escapeHtml(col);
            return `
                <div class="form-row">
                    <div>
                        <strong>${safe}</strong>
                        <span style="font-size:11px; color:#89b4fa; display:block;">[${escapeHtml(group)}]</span>
                    </div>
                    <div>
                        <label style="font-size:12px;">Type: </label>
                        <select class="scoring-type" data-col="${safe}">
                            <option value="Direct">Direct</option>
                            <option value="Reverse">Reverse</option>
                        </select>
                        <label style="font-size:12px; margin-left:10px;">Max Score: </label>
                        <input type="number" class="scoring-max" data-col="${safe}" value="5" style="width:60px;">
                    </div>
                </div>`;
        }).join('');

        openModal('modal-scoring');
    });
}

function applyScoring() {
    const configs = {};
    document.querySelectorAll('.scoring-type').forEach(select => {
        const col = select.dataset.col;
        const maxInput = document.querySelector(`.scoring-max[data-col="${CSS.escape(col)}"]`);
        configs[col] = {
            type: select.value,
            scale_max: parseInt(maxInput.value, 10) || 5
        };
    });

    apiPost('/api/scoring', { configs })
        .then(data => {
            log(`[SUCCESS] Applied scoring transformation to ${data.columns_scored} column(s).`, 'success');
            closeModal('modal-scoring');
        })
        .catch(reportError);
}
