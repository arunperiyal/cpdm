/* File menu: opening and exporting the dataset. */

function triggerFileSelect() { document.getElementById('file-input').click(); }

function uploadFile() {
    const input = document.getElementById('file-input');
    if (!input.files.length) return;
    const file = input.files[0];

    log(`> Uploading ${escapeHtml(file.name)}...`, 'info');
    apiUpload('/api/upload', file)
        .then(data => {
            log(`[SUCCESS] Loaded file '${escapeHtml(data.filename)}' with ${data.rows} rows and ${data.cols.length} columns.`, 'success');
            refreshStatus();
        })
        .catch(reportError)
        .finally(() => { input.value = ''; });
}

function exportFile(format = 'xlsx') {
    getState().then(state => {
        if (!state.has_file) { logError('No dataset loaded to export.'); return; }
        log(`> Generating .${format} download...`, 'info');
        window.location.href = `/api/export?format=${encodeURIComponent(format)}`;
    }).catch(reportError);
}
