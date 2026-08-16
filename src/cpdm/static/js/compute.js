/* Compute menu: row-wise calculations across selected scale items. */

function openComputeModal() {
    withDataset(state => {
        const scaleCols = scaleColumnsOf(state);
        if (!scaleCols.length) {
            logError('No columns belong to a scale yet. Build one in Fields -> Groups.');
            return;
        }

        document.getElementById('compute-cols-list').innerHTML = scaleCols.map((col, index) => {
            const group = state.categories[col].replace('Scale: ', '');
            return `
                <div class="chk-row">
                    <input type="checkbox" class="compute-col-chk" id="compute-col-${index}"
                           data-col="${escapeHtml(col)}" checked>
                    <label for="compute-col-${index}">${escapeHtml(col)}
                        <span style="color:var(--accent); font-size:11px;">(${escapeHtml(group)})</span>
                    </label>
                </div>`;
        }).join('');

        openModal('modal-compute');
    });
}

function applyCompute() {
    const newColName = document.getElementById('compute-target-col').value.trim();
    const functionName = document.getElementById('compute-function').value;
    const selectedCols = Array.from(document.querySelectorAll('.compute-col-chk:checked'))
        .map(chk => chk.dataset.col);

    apiPost('/api/compute', {
        new_col_name: newColName,
        function_name: functionName,
        selected_cols: selectedCols
    })
        .then(data => {
            log(`[SUCCESS] Created column '${escapeHtml(data.new_col)}' applying '${functionName}' across ${selectedCols.length} column(s).`, 'success');
            closeModal('modal-compute');
            refreshStatus();
        })
        .catch(reportError);
}
