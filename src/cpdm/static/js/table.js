/* Table menu: look at the data and change its shape.

   Header edits the column names, Rows pages through the data and deletes,
   Columns reorders and drops, Sort orders the rows, Filter keeps or drops them
   by test. All five render into the shared #modal-table shell. */

const tableUI = {
    view: null,         // 'header' | 'rows' | 'columns' | 'sort' | 'filter'
    columns: [],        // the column report
    rows: 0,
    operators: [],
    noValueOperators: [],
    page: null,         // the current page of rows
    offset: 0,
    limit: 25,
    selectedRows: new Set(),
    order: [],          // working copy for Columns
    doomed: new Set(),  // columns ticked for deletion
    renames: {},
    sortKeys: [{ column: '', descending: false }],
    conditions: [{ column: '', operator: 'equals', value: '' }],
    match: 'all',
    action: 'keep'
};

const TABLE_TITLES = {
    header: 'Table -> Header',
    rows: 'Table -> Rows',
    columns: 'Table -> Columns',
    sort: 'Table -> Sort',
    filter: 'Table -> Filter'
};

/* --- opening ------------------------------------------------------------ */

function openTableView(view) {
    withDataset(() => {
        tableUI.view = view;
        tableUI.selectedRows = new Set();
        tableUI.doomed = new Set();
        tableUI.renames = {};
        tableUI.offset = 0;

        loadTableColumns()
            .then(() => (view === 'rows' ? loadTablePage(0) : null))
            .then(() => {
                renderTableView();
                openModal('modal-table');
            })
            .catch(reportError);
    });
}

function loadTableColumns() {
    return apiGet('/api/table/columns').then(data => {
        tableUI.columns = data.columns;
        tableUI.rows = data.rows;
        tableUI.operators = data.operators;
        tableUI.noValueOperators = data.no_value_operators;
        tableUI.order = data.columns.map(entry => entry.name);
    });
}

function loadTablePage(offset) {
    return apiGet(`/api/table/page?offset=${offset}&limit=${tableUI.limit}`)
        .then(page => { tableUI.page = page; tableUI.offset = page.offset; });
}

function tableStatus(message, kind = 'muted') {
    const box = document.getElementById('table-status');
    if (box) box.innerHTML = `<span class="${kind}">${message}</span>`;
}

function renderTableView() {
    document.getElementById('table-modal-header').innerText = TABLE_TITLES[tableUI.view];
    const render = {
        header: renderTableHeader,
        rows: renderTableRows,
        columns: renderTableColumns,
        sort: renderTableSort,
        filter: renderTableFilter
    }[tableUI.view];
    render();
}

/* after anything structural, reload and redraw without closing the dialogue */
function tableRefresh(message, kind = 'log-success') {
    return loadTableColumns()
        .then(() => (tableUI.view === 'rows' ? loadTablePage(tableUI.offset) : null))
        .then(() => {
            renderTableView();
            if (message) tableStatus(message, kind);
            refreshStatus();
        })
        .catch(reportError);
}

/* --- Header ------------------------------------------------------------- */

function renderTableHeader() {
    const rows = tableUI.columns.map((entry, index) => `
        <div class="form-row" style="align-items:center;">
            <span class="col-index">${entry.position}</span>
            <div style="flex:1; min-width:0;">
                <span style="font-size:12px; word-break:break-word;">${escapeHtml(entry.name)}</span>
                <span class="muted" style="display:block;">
                    ${entry.dtype}, ${entry.filled} filled, ${entry.blank} blank, ${entry.distinct} distinct
                    ${entry.group ? ` · group ${escapeHtml(entry.group)}` : ''}
                    ${entry.scale ? ` · scale ${escapeHtml(entry.scale)}` : ''}
                </span>
            </div>
            <input type="text" value="${escapeHtml(entry.name)}" style="flex:1;"
                   data-index="${index}" oninput="tableEditName(this)">
        </div>`).join('');

    document.getElementById('table-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>The header row</strong>
            <span>What each column is called, what it holds, and where it belongs. Edit a
            name on the right to rename the column outright — groups, scales and remembered
            answers follow it.</span>
        </div>
        <div id="table-status" class="trimmer-status"></div>
        <div class="col-header-row">
            <div style="width:30px;">#</div><div style="flex:1;">Column</div><div style="flex:1;">Rename to</div>
        </div>
        ${rows}`;

    document.getElementById('table-modal-footer').innerHTML = `
        <span class="muted" style="margin-right:auto;">${tableUI.columns.length} column(s), ${tableUI.rows} row(s)</span>
        <button class="btn btn-secondary" onclick="closeModal('modal-table')">Close</button>
        <button class="btn btn-primary" onclick="tableApplyRenames()">Apply renames</button>`;
}

/* Columns are identified by position throughout: a header can hold quotes,
   newlines or any script, and a name that travels through an HTML attribute
   and back is not guaranteed to come back byte for byte. */
function tableEditName(input) {
    const name = tableUI.columns[Number(input.dataset.index)].name;
    tableUI.renames[name] = input.value;
}

function tableApplyRenames() {
    const map = {};
    Object.entries(tableUI.renames).forEach(([old, name]) => {
        if (name.trim() && name.trim() !== old) map[old] = name.trim();
    });
    if (!Object.keys(map).length) { tableStatus('Nothing renamed yet.', 'diff-warn'); return; }

    apiPost('/api/table/rename', { map })
        .then(data => {
            log(`[SUCCESS] Renamed ${data.result.renamed} column(s).`, 'success');
            tableUI.renames = {};
            return tableRefresh(`Renamed ${data.result.renamed} column(s).`);
        })
        .catch(error => { tableStatus(escapeHtml(error.message), 'log-error'); reportError(error); });
}

/* --- Rows --------------------------------------------------------------- */

function renderTableRows() {
    const page = tableUI.page;
    const from = page.total ? page.offset + 1 : 0;
    const to = Math.min(page.offset + page.limit, page.total);

    const head = page.columns.map(col => `<th>${escapeHtml(col)}</th>`).join('');
    const body = page.rows.map((row, index) => {
        const label = page.index[index];
        const cells = row.map(value => value === null
            ? '<td class="muted">—</td>'
            : `<td>${escapeHtml(String(value))}</td>`).join('');
        return `
            <tr>
                <td><input type="checkbox" ${tableUI.selectedRows.has(label) ? 'checked' : ''}
                           data-index="${index}" onclick="tableToggleRow(this)"></td>
                <td class="muted">${escapeHtml(label)}</td>
                ${cells}
            </tr>`;
    }).join('');

    document.getElementById('table-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>The rows</strong>
            <span>Tick any row to delete it. Rows are identified by the number on the left,
            which does not change when the table is sorted or filtered.</span>
        </div>
        <div id="table-status" class="trimmer-status"></div>
        <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px; flex-wrap:wrap;">
            <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                    onclick="tableDropBlankRows()">Drop blank rows</button>
            <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;"
                    onclick="tableDropDuplicates()">Drop duplicate rows</button>
            <span class="muted" style="margin-left:auto;">rows ${from}–${to} of ${page.total}</span>
        </div>
        <div class="table-scroll">
            <table class="data-table">
                <thead><tr><th></th><th>#</th>${head}</tr></thead>
                <tbody>${body}</tbody>
            </table>
        </div>`;

    document.getElementById('table-modal-footer').innerHTML = `
        <span class="muted" style="margin-right:auto;">${tableUI.selectedRows.size} row(s) ticked</span>
        <button class="btn btn-secondary" onclick="closeModal('modal-table')">Close</button>
        <button class="btn btn-secondary" ${page.offset === 0 ? 'disabled' : ''}
                onclick="tableGoToPage(${Math.max(0, page.offset - page.limit)})">&larr; Previous</button>
        <button class="btn btn-secondary" ${to >= page.total ? 'disabled' : ''}
                onclick="tableGoToPage(${page.offset + page.limit})">Next &rarr;</button>
        <button class="btn btn-primary" onclick="tableDropRows()">Delete ticked rows</button>`;
}

function tableGoToPage(offset) {
    loadTablePage(offset).then(renderTableView).catch(reportError);
}

function tableToggleRow(checkbox) {
    const label = tableUI.page.index[Number(checkbox.dataset.index)];
    if (checkbox.checked) tableUI.selectedRows.add(label);
    else tableUI.selectedRows.delete(label);
    renderTableView();
}

function tableDropRows() {
    const index = Array.from(tableUI.selectedRows);
    if (!index.length) { tableStatus('No rows ticked.', 'diff-warn'); return; }
    if (!window.confirm(`Delete ${index.length} row(s)? This cannot be undone.`)) return;

    apiPost('/api/table/drop_rows', { index })
        .then(data => {
            log(`[SUCCESS] Deleted ${data.result.removed} row(s); ${data.result.rows} remain.`, 'success');
            tableUI.selectedRows = new Set();
            return tableRefresh(`Deleted ${data.result.removed} row(s).`);
        })
        .catch(reportError);
}

function tableDropBlankRows() {
    apiPost('/api/table/drop_blank_rows', {})
        .then(data => {
            log(`[SUCCESS] Dropped ${data.result.removed} blank row(s); ${data.result.rows} remain.`, 'success');
            return tableRefresh(`Dropped ${data.result.removed} blank row(s).`);
        })
        .catch(reportError);
}

function tableDropDuplicates() {
    if (!window.confirm('Delete rows that repeat an earlier row exactly?')) return;
    apiPost('/api/table/drop_duplicates', {})
        .then(data => {
            log(`[SUCCESS] Dropped ${data.result.removed} duplicate row(s); ${data.result.rows} remain.`, 'success');
            return tableRefresh(`Dropped ${data.result.removed} duplicate row(s).`);
        })
        .catch(reportError);
}

/* --- Columns ------------------------------------------------------------ */

function renderTableColumns() {
    const rows = tableUI.order.map((name, index) => {
        const entry = tableUI.columns.find(item => item.name === name) || {};
        return `
            <div class="form-row" style="align-items:center;">
                <span class="rule-actions">
                    <button class="btn btn-secondary" title="Move up" onclick="tableMoveColumn(${index}, -1)">&uarr;</button>
                    <button class="btn btn-secondary" title="Move down" onclick="tableMoveColumn(${index}, 1)">&darr;</button>
                </span>
                <div style="flex:1; min-width:0;">
                    <span style="font-size:12px;">${escapeHtml(name)}</span>
                    <span class="muted" style="display:block;">
                        ${entry.dtype || ''}, ${entry.filled || 0} filled
                        ${entry.group ? ` · group ${escapeHtml(entry.group)}` : ''}</span>
                </div>
                <label class="muted" style="display:flex; align-items:center; gap:6px; margin:0;">
                    <input type="checkbox" ${tableUI.doomed.has(name) ? 'checked' : ''}
                           data-index="${index}" onclick="tableToggleDoomed(this)"> delete
                </label>
            </div>`;
    }).join('');

    document.getElementById('table-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>The columns</strong>
            <span>Reorder with the arrows, or tick a column to delete it. Deleting takes the
            column out of any group that held it; the rest of the table is untouched.</span>
        </div>
        <div id="table-status" class="trimmer-status"></div>
        ${rows}`;

    document.getElementById('table-modal-footer').innerHTML = `
        <span class="muted" style="margin-right:auto;">${tableUI.doomed.size} ticked for deletion</span>
        <button class="btn btn-secondary" onclick="closeModal('modal-table')">Close</button>
        <button class="btn btn-secondary" onclick="tableDropColumns()">Delete ticked</button>
        <button class="btn btn-primary" onclick="tableApplyOrder()">Save order</button>`;
}

function tableMoveColumn(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= tableUI.order.length) return;
    const order = tableUI.order;
    [order[index], order[target]] = [order[target], order[index]];
    renderTableView();
}

function tableToggleDoomed(checkbox) {
    const name = tableUI.order[Number(checkbox.dataset.index)];
    if (checkbox.checked) tableUI.doomed.add(name); else tableUI.doomed.delete(name);
    renderTableView();
}

function tableApplyOrder() {
    apiPost('/api/table/reorder', { order: tableUI.order })
        .then(data => {
            log(`[SUCCESS] Column order saved: ${escapeHtml(data.columns.slice(0, 6).join(', '))}${data.columns.length > 6 ? ', …' : ''}`, 'success');
            return tableRefresh('Column order saved.');
        })
        .catch(reportError);
}

function tableDropColumns() {
    const columns = Array.from(tableUI.doomed);
    if (!columns.length) { tableStatus('Nothing ticked.', 'diff-warn'); return; }
    if (!window.confirm(`Delete ${columns.length} column(s) and their data? This cannot be undone.`)) return;

    apiPost('/api/table/drop_columns', { columns })
        .then(data => {
            log(`[SUCCESS] Deleted column(s): ${escapeHtml(data.result.dropped.join(', '))}.`, 'success');
            tableUI.doomed = new Set();
            return tableRefresh(`Deleted ${data.result.dropped.length} column(s).`);
        })
        .catch(error => { tableStatus(escapeHtml(error.message), 'log-error'); reportError(error); });
}

/* --- Sort --------------------------------------------------------------- */

function tableColumnOptions(selected) {
    return '<option value="">— choose a column —</option>' + tableUI.columns.map((entry, index) =>
        `<option value="${index}" ${entry.name === selected ? 'selected' : ''}>
            ${escapeHtml(entry.name)}
         </option>`).join('');
}

/* '' for the placeholder, otherwise the column name behind that position */
function tableColumnAt(value) {
    if (value === '') return '';
    const entry = tableUI.columns[Number(value)];
    return entry ? entry.name : '';
}

function renderTableSort() {
    const rows = tableUI.sortKeys.map((key, index) => `
        <div class="form-row" style="align-items:center; gap:8px;">
            <span class="rule-index">${index + 1}</span>
            <select style="flex:1;" onchange="tableSetSort(${index}, 'column', tableColumnAt(this.value))">
                ${tableColumnOptions(key.column)}
            </select>
            <select onchange="tableSetSort(${index}, 'descending', this.value === 'desc')">
                <option value="asc" ${key.descending ? '' : 'selected'}>A → Z, low → high</option>
                <option value="desc" ${key.descending ? 'selected' : ''}>Z → A, high → low</option>
            </select>
            <button class="btn btn-secondary" onclick="tableRemoveSort(${index})">&times;</button>
        </div>`).join('');

    document.getElementById('table-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>Sort the rows</strong>
            <span>The first column decides; the ones below it break ties. Text sorts without
            regard to case, and blanks go last. Sorting reorders the table itself, so an
            export afterwards comes out in this order.</span>
        </div>
        <div id="table-status" class="trimmer-status"></div>
        ${rows}
        <button class="btn btn-secondary" style="margin-top:10px; font-size:12px; padding:4px 10px;"
                onclick="tableAddSort()">+ Add a tie-breaker</button>`;

    document.getElementById('table-modal-footer').innerHTML = `
        <span class="muted" style="margin-right:auto;">${tableUI.rows} row(s)</span>
        <button class="btn btn-secondary" onclick="closeModal('modal-table')">Close</button>
        <button class="btn btn-primary" onclick="tableApplySort()">Sort rows</button>`;
}

function tableSetSort(index, field, value) { tableUI.sortKeys[index][field] = value; }
function tableAddSort() { tableUI.sortKeys.push({ column: '', descending: false }); renderTableView(); }
function tableRemoveSort(index) {
    tableUI.sortKeys.splice(index, 1);
    if (!tableUI.sortKeys.length) tableUI.sortKeys.push({ column: '', descending: false });
    renderTableView();
}

function tableApplySort() {
    const keys = tableUI.sortKeys.filter(key => key.column);
    if (!keys.length) { tableStatus('Choose a column first.', 'diff-warn'); return; }

    apiPost('/api/table/sort', { keys })
        .then(data => {
            const how = data.result.sorted_by
                .map(key => `${key.column} ${key.descending ? '↓' : '↑'}`).join(', ');
            log(`[SUCCESS] Sorted by ${escapeHtml(how)}.`, 'success');
            return tableRefresh(`Sorted by ${escapeHtml(how)}.`);
        })
        .catch(error => { tableStatus(escapeHtml(error.message), 'log-error'); reportError(error); });
}

/* --- Filter ------------------------------------------------------------- */

function renderTableFilter() {
    const rows = tableUI.conditions.map((condition, index) => {
        const needsValue = !tableUI.noValueOperators.includes(condition.operator);
        return `
            <div class="form-row" style="align-items:center; gap:8px; flex-wrap:wrap;">
                <span class="rule-index">${index + 1}</span>
                <select style="flex:1; min-width:140px;" onchange="tableSetCondition(${index}, 'column', tableColumnAt(this.value))">
                    ${tableColumnOptions(condition.column)}
                </select>
                <select onchange="tableSetCondition(${index}, 'operator', this.value)">
                    ${tableUI.operators.map(op =>
                        `<option value="${op.value}" ${op.value === condition.operator ? 'selected' : ''}>${escapeHtml(op.label)}</option>`).join('')}
                </select>
                <input type="text" style="flex:1; min-width:120px;" value="${escapeHtml(condition.value || '')}"
                       placeholder="${needsValue ? 'value' : 'not needed'}" ${needsValue ? '' : 'disabled'}
                       oninput="tableSetCondition(${index}, 'value', this.value)">
                <button class="btn btn-secondary" onclick="tableRemoveCondition(${index})">&times;</button>
            </div>`;
    }).join('');

    document.getElementById('table-modal-body').innerHTML = `
        <div class="hint-box">
            <strong>Keep or drop rows by test</strong>
            <span>Count first — it says how many rows match without changing anything — then
            decide whether those are the rows to keep or the rows to remove.</span>
        </div>
        <div id="table-status" class="trimmer-status"></div>
        ${rows}
        <button class="btn btn-secondary" style="margin-top:10px; font-size:12px; padding:4px 10px;"
                onclick="tableAddCondition()">+ Add a test</button>

        <div style="display:flex; gap:16px; margin-top:14px; flex-wrap:wrap;">
            <label class="muted" style="margin:0;">Rows must match
                <select onchange="tableUI.match = this.value">
                    <option value="all" ${tableUI.match === 'all' ? 'selected' : ''}>every test</option>
                    <option value="any" ${tableUI.match === 'any' ? 'selected' : ''}>any test</option>
                </select>
            </label>
            <label class="muted" style="margin:0;">Then
                <select onchange="tableUI.action = this.value">
                    <option value="keep" ${tableUI.action === 'keep' ? 'selected' : ''}>keep the matching rows</option>
                    <option value="drop" ${tableUI.action === 'drop' ? 'selected' : ''}>drop the matching rows</option>
                </select>
            </label>
        </div>`;

    document.getElementById('table-modal-footer').innerHTML = `
        <span class="muted" style="margin-right:auto;">${tableUI.rows} row(s) now</span>
        <button class="btn btn-secondary" onclick="closeModal('modal-table')">Close</button>
        <button class="btn btn-secondary" onclick="tableCountFilter()">Count matches</button>
        <button class="btn btn-primary" onclick="tableApplyFilter()">Apply filter</button>`;
}

function tableSetCondition(index, field, value) {
    tableUI.conditions[index][field] = value;
    if (field === 'operator') renderTableView();
}
function tableAddCondition() {
    tableUI.conditions.push({ column: '', operator: 'equals', value: '' });
    renderTableView();
}
function tableRemoveCondition(index) {
    tableUI.conditions.splice(index, 1);
    if (!tableUI.conditions.length) tableUI.conditions.push({ column: '', operator: 'equals', value: '' });
    renderTableView();
}

function tableFilterBody() {
    return {
        conditions: tableUI.conditions.filter(condition => condition.column),
        match: tableUI.match,
        action: tableUI.action
    };
}

function tableCountFilter() {
    const body = tableFilterBody();
    if (!body.conditions.length) { tableStatus('Add a test first.', 'diff-warn'); return; }

    apiPost('/api/table/filter/count', body)
        .then(data => tableStatus(
            `${data.matched} of ${data.total} row(s) match — keeping them leaves ${data.remaining_if_kept}, dropping them leaves ${data.remaining_if_dropped}.`,
            'log-success'))
        .catch(error => { tableStatus(escapeHtml(error.message), 'log-error'); reportError(error); });
}

function tableApplyFilter() {
    const body = tableFilterBody();
    if (!body.conditions.length) { tableStatus('Add a test first.', 'diff-warn'); return; }
    if (!window.confirm(`This deletes rows from the table. Continue?`)) return;

    apiPost('/api/table/filter', body)
        .then(data => {
            log(`[SUCCESS] Filter ${data.result.action === 'keep' ? 'kept' : 'dropped'} ${data.result.matched} matching row(s); ${data.result.rows} remain.`, 'success');
            return tableRefresh(`${data.result.removed} row(s) removed, ${data.result.rows} remain.`);
        })
        .catch(error => { tableStatus(escapeHtml(error.message), 'log-error'); reportError(error); });
}
