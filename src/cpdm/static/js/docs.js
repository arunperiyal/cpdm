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

/* --- About CPDM: a read-only card, no controls beyond Close -------------- */

function openAboutModal() {
    const body = document.getElementById('about-body');
    body.innerHTML = '<p class="muted">Reading...</p>';
    openModal('modal-about');

    apiGet('/api/about')
        .then(info => { body.innerHTML = renderAbout(info); })
        .catch(error => {
            body.innerHTML = `<p class="log-error">${escapeHtml(error.message)}</p>`;
        });
}

function renderAbout(info) {
    const deps = Object.entries(info.dependencies)
        .map(([name, version]) => version
            ? `${escapeHtml(name)} ${escapeHtml(version)}`
            : `<span class="muted">${escapeHtml(name)} — not installed</span>`)
        .join(' · ');

    const people = info.contributors.map(person =>
        `<div>${escapeHtml(person.name)} <span class="muted">${escapeHtml(person.email)}</span></div>`
    ).join('');

    const loaded = info.loaded
        ? `${escapeHtml(info.loaded.filename)} — ${info.loaded.rows} row(s), ${info.loaded.columns} column(s),
           ${info.loaded.groups} group(s), ${info.loaded.scales} scale(s)`
        : 'nothing loaded';

    return `
        <div class="about">
            <div class="about-title">
                <strong>${escapeHtml(info.name)}</strong>
                <span class="muted">version ${escapeHtml(info.version)}</span>
            </div>
            <div class="muted about-full-name">${escapeHtml(info.full_name)}</div>

            <p>${escapeHtml(info.summary)}</p>

            <dl class="about-facts">
                <dt>Licence</dt>
                <dd class="${info.licence.declared ? '' : 'diff-warn'}">
                    ${escapeHtml(info.licence.summary)}
                </dd>

                <dt>Contributors</dt>
                <dd>${people}</dd>

                <dt>Source</dt>
                <dd><a href="${escapeHtml(info.repository)}" target="_blank" rel="noopener">${escapeHtml(info.repository)}</a></dd>

                ${info.commit ? `<dt>Code running</dt>
                <dd><code>${escapeHtml(info.commit)}</code></dd>` : ''}

                <dt>Running on</dt>
                <dd>Python ${escapeHtml(info.python)} · ${escapeHtml(info.platform)}</dd>

                <dt>Built with</dt>
                <dd>${deps}</dd>

                <dt>Loaded now</dt>
                <dd>${loaded}</dd>
            </dl>

            <p class="muted">
                Everything runs on this machine and nothing is sent anywhere. The workspace
                holds one dataset at a time, in memory — export before you close it.
            </p>
        </div>`;
}
