/* Fields & Scales menus: categorisation, scale definitions, numerise, scoring. */

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
