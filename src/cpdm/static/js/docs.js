/* Help menu: read the docs/ Markdown inside the workspace, list sample data. */

function openDocsBrowser() { window.open('/docs', '_blank'); }

function openDocModal(section, slug) {
    const header = document.getElementById('docs-modal-header');
    const body = document.getElementById('docs-modal-body');
    const link = document.getElementById('docs-modal-open');

    header.innerText = 'Documentation';
    body.innerHTML = '<p class="muted">Loading...</p>';
    link.href = `/docs/${section}/${slug}`;
    openModal('modal-docs');

    apiGet(`/api/docs/${section}/${slug}`)
        .then(doc => {
            header.innerText = `${doc.section_label} -> ${doc.title}`;
            body.innerHTML = doc.html;   // rendered from local Markdown files
        })
        .catch(error => {
            body.innerHTML = `<p class="log-error">${escapeHtml(error.message)}</p>`;
        });
}

function openSamplesModal() {
    const header = document.getElementById('docs-modal-header');
    const body = document.getElementById('docs-modal-body');
    const link = document.getElementById('docs-modal-open');

    header.innerText = 'Sample Data Files';
    body.innerHTML = '<p class="muted">Loading...</p>';
    link.href = '/docs';
    openModal('modal-docs');

    apiGet('/api/docs')
        .then(data => {
            const files = data.samples || [];
            if (!files.length) {
                body.innerHTML = '<p class="muted">No sample files found in the samples/ directory.</p>';
                return;
            }
            body.innerHTML = `
                <p class="muted" style="margin-bottom:12px;">
                    Download a file, then load it with File -&gt; Open to follow the Help walkthroughs.
                </p>` +
                files.map(file => `
                    <div class="sample-row">
                        <div>
                            <span class="sample-name">${escapeHtml(file.name)}</span>
                            <span class="sample-desc">${escapeHtml(file.description)} (${file.size_kb} KB)</span>
                        </div>
                        <a class="btn btn-secondary" href="${file.url}">Download</a>
                    </div>`).join('');
        })
        .catch(error => {
            body.innerHTML = `<p class="log-error">${escapeHtml(error.message)}</p>`;
        });
}
