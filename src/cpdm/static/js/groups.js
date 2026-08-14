/* Fields -> Groups: build a tree of column sets.

   A root group is a construct (Demographics, Wellbeing); a subgroup is a facet
   of its parent — a subscale — and may only take columns the parent holds.
   Columns can be ticked in the list or typed as a spec (names, ranges, globs). */

const groupsUI = {
    view: 'build',      // 'build' = edit the tree, 'assign' = one row per column
    tree: [],
    editing: null,      // {mode: 'create'|'edit', name, parent, kind}
    eligible: [],
    selected: new Set(),
    anchor: null,
    columns: [],
    assignments: {},    // column -> deepest group holding it, or null
    pending: {},        // unsaved changes from the assign view
    onlyUngrouped: false
};

function openGroupsModal(view = 'build') {
    withDataset(() => {
        groupsUI.editing = null;
        groupsUI.pending = {};
        groupsUI.view = view;
        refreshGroups().then(() => openModal('modal-groups'));
    });
}

function groupsSetView(view) {
    groupsUI.view = view;
    renderGroupsView();
}

function renderGroupsView() {
    const building = groupsUI.view === 'build';
    document.getElementById('groups-build').style.display = building ? '' : 'none';
    document.getElementById('groups-assign').style.display = building ? 'none' : '';
    document.getElementById('tab-build').classList.toggle('active', building);
    document.getElementById('tab-assign').classList.toggle('active', !building);
    if (!building) renderGroupsAssign();
    renderGroupsStatus();
}

function refreshGroups() {
    return apiGet('/api/groups')
        .then(data => {
            groupsUI.tree = data.groups;
            groupsUI.columns = data.cols;
            groupsUI.assignments = data.assignments;
            groupsUI.ungrouped = data.ungrouped;
            renderGroupsTree();
            renderGroupsEditor();
            renderGroupsView();
        })
        .catch(reportError);
}

function renderGroupsStatus() {
    const note = document.getElementById('groups-ungrouped-note');
    const count = (groupsUI.ungrouped || []).length;
    note.textContent = count
        ? `${count} of ${groupsUI.columns.length} column(s) ungrouped`
        : `all ${groupsUI.columns.length} column(s) grouped`;

    const pending = Object.keys(groupsUI.pending).length;
    document.getElementById('groups-assign-status').textContent =
        pending ? `${pending} unsaved change(s)` : '';
}

/* --- tree -------------------------------------------------------------- */

function renderGroupsTree() {
    const container = document.getElementById('groups-tree');

    const node = (group, depth) => `
        <div class="group-node ${groupsUI.editing && groupsUI.editing.name === group.name ? 'active' : ''}"
             style="margin-left:${depth * 16}px">
            <div class="group-node-main">
                <span class="group-name">${escapeHtml(group.name)}</span>
                <span class="group-badge kind-${escapeHtml(group.kind)}">${escapeHtml(group.label)}</span>
                <span class="muted">${group.column_count} col(s)</span>
            </div>
            <div class="group-node-actions">
                <button class="btn btn-secondary" data-name="${escapeHtml(group.name)}"
                        title="Add a subgroup" onclick="groupsNewChild(this.dataset.name)">+ Sub</button>
                <button class="btn btn-secondary" data-name="${escapeHtml(group.name)}"
                        onclick="groupsEdit(this.dataset.name)">Edit</button>
                <button class="btn btn-secondary" data-name="${escapeHtml(group.name)}"
                        onclick="groupsDelete(this.dataset.name)">Delete</button>
            </div>
        </div>
        ${group.children.map(child => node(child, depth + 1)).join('')}`;

    container.innerHTML = groupsUI.tree.length
        ? groupsUI.tree.map(group => node(group, 0)).join('')
        : '<div class="muted" style="padding:10px 0;">No groups yet. Create one to start.</div>';
}

/* --- editor ------------------------------------------------------------ */

function groupsNewRoot() {
    groupsUI.editing = { mode: 'create', name: '', parent: null, kind: 'scale' };
    groupsLoadEligible(null, []);
}

function groupsNewChild(parent) {
    groupsUI.editing = { mode: 'create', name: '', parent, kind: 'other' };
    groupsLoadEligible(parent, []);
}

function groupsFind(name, nodes = groupsUI.tree) {
    for (const node of nodes) {
        if (node.name === name) return node;
        const found = groupsFind(name, node.children);
        if (found) return found;
    }
    return null;
}

function groupsEdit(name) {
    const group = groupsFind(name);
    if (!group) return;
    groupsUI.editing = { mode: 'edit', name, parent: group.parent, kind: group.kind };
    groupsLoadEligible(group.parent, group.columns);
}

function groupsLoadEligible(parent, selected) {
    return apiPost('/api/groups/eligible', { parent })
        .then(data => {
            groupsUI.eligible = data.columns;
            groupsUI.selected = new Set(selected);
            groupsUI.anchor = null;
            renderGroupsTree();
            renderGroupsEditor();
        })
        .catch(reportError);
}

function groupsCancelEdit() {
    groupsUI.editing = null;
    renderGroupsTree();
    renderGroupsEditor();
}

function renderGroupsEditor() {
    const editor = document.getElementById('groups-editor');
    const editing = groupsUI.editing;

    if (!editing) {
        editor.innerHTML = `
            <div class="muted" style="padding:14px; text-align:center;">
                Pick a group to edit, or create one.<br>
                Subgroups can only hold columns from the group above them.
            </div>`;
        return;
    }

    const title = editing.mode === 'create'
        ? (editing.parent ? `New subgroup of '${escapeHtml(editing.parent)}'` : 'New group')
        : `Editing '${escapeHtml(editing.name)}'`;

    // any group at any depth can be a scale — a container can hold several
    const kindField = `
        <select id="group-kind" style="width:100%;">
            ${['scale', 'demographics', 'other'].map(kind => `
                <option value="${kind}" ${editing.kind === kind ? 'selected' : ''}>
                    ${kind === 'scale' ? 'Scale — its columns are scored together as this scale'
                      : kind === 'demographics' ? 'Demographics — background variables'
                      : 'Container — organise only, no scoring'}
                </option>`).join('')}
        </select>`;

    const scopeNote = editing.parent
        ? `Positions count within '${escapeHtml(editing.parent)}': <code>1:4</code> is the first four columns listed below.`
        : `Positions count within the table: <code>7:15</code> is the seventh to fifteenth column.`;

    editor.innerHTML = `
        <div class="modal-header" style="font-size:15px; margin-bottom:12px;">${title}</div>

        <label class="muted">Group name</label>
        <input type="text" id="group-name" value="${escapeHtml(editing.name)}"
               placeholder="e.g. Wellbeing, or Positive affect" style="width:100%; margin:4px 0 12px;">

        <label class="muted">Kind</label>
        <div style="margin:4px 0 12px;">${kindField}</div>

        <label class="muted">Type columns — names, ranges (<code>WB1:WB5</code>, <code>1:4</code>) or globs (<code>WB*</code>)</label>
        <div style="display:flex; gap:8px; margin:4px 0 4px;">
            <input type="text" id="group-spec" placeholder="1:4, WB*" style="flex:1;"
                   onkeydown="if (event.key === 'Enter') groupsApplySpec()">
            <button class="btn btn-secondary" onclick="groupsApplySpec()">Add to selection</button>
        </div>
        <div class="muted" style="margin-bottom:4px;">${scopeNote}</div>
        <div id="group-spec-result" class="muted" style="margin-bottom:12px;"></div>

        <div style="display:flex; justify-content:space-between; align-items:center;">
            <label class="muted">Columns <span id="group-col-count"></span></label>
            <span>
                <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;" onclick="groupsSelectAll(true)">All</button>
                <button class="btn btn-secondary" style="padding:2px 8px; font-size:11px;" onclick="groupsSelectAll(false)">None</button>
            </span>
        </div>
        <input type="text" id="group-search" placeholder="Search columns..."
               style="width:100%; margin:6px 0; font-size:12px;" oninput="renderGroupsColumns()">
        <div id="group-columns" class="trimmer-cols"></div>
        <div class="muted" style="margin-top:6px;">Shift-click to select a range.</div>

        <div style="display:flex; gap:8px; margin-top:14px;">
            <button class="btn btn-primary" onclick="groupsSave()">
                ${editing.mode === 'create' ? 'Create group' : 'Save changes'}</button>
            <button class="btn btn-secondary" onclick="groupsCancelEdit()">Cancel</button>
        </div>`;

    renderGroupsColumns();
}

function renderGroupsColumns() {
    const search = (document.getElementById('group-search')?.value || '').toLowerCase();
    const visible = groupsUI.eligible.filter(col => col.toLowerCase().includes(search));
    const scoped = Boolean(groupsUI.editing && groupsUI.editing.parent);
    groupsUI.visible = visible;

    document.getElementById('group-columns').innerHTML = visible.map((col, index) => {
        // the number to type is the position in the *unfiltered* eligible list
        const position = groupsUI.eligible.indexOf(col) + 1;
        const inTable = groupsUI.columns.indexOf(col) + 1;
        const tableNote = scoped && inTable !== position
            ? `<span class="col-table-pos" title="position in the table">col ${inTable}</span>`
            : '';

        return `
            <label class="col-pick" title="${escapeHtml(col)}">
                <span class="col-index">${position}</span>
                <input type="checkbox" ${groupsUI.selected.has(col) ? 'checked' : ''}
                       onclick="groupsToggleColumn(${index}, event)">
                <span class="col-pick-name">${escapeHtml(col)}</span>
                ${tableNote}
            </label>`;
    }).join('') || '<div class="muted">No columns available.</div>';

    const count = document.getElementById('group-col-count');
    if (count) count.textContent = `— ${groupsUI.selected.size} of ${groupsUI.eligible.length} selected`;
}

function groupsToggleColumn(index, event) {
    const name = groupsUI.visible[index];
    const checked = event.target.checked;

    if (event.shiftKey && groupsUI.anchor !== null) {
        const [from, to] = [groupsUI.anchor, index].sort((a, b) => a - b);
        for (let i = from; i <= to; i += 1) {
            const col = groupsUI.visible[i];
            if (checked) groupsUI.selected.add(col); else groupsUI.selected.delete(col);
        }
    } else if (checked) {
        groupsUI.selected.add(name);
    } else {
        groupsUI.selected.delete(name);
    }

    groupsUI.anchor = index;
    renderGroupsColumns();
}

function groupsSelectAll(all) {
    (groupsUI.visible || groupsUI.eligible).forEach(col => {
        if (all) groupsUI.selected.add(col); else groupsUI.selected.delete(col);
    });
    renderGroupsColumns();
}

function groupsApplySpec() {
    const spec = document.getElementById('group-spec').value.trim();
    if (!spec) return;

    apiPost('/api/groups/resolve_spec', { spec, parent: groupsUI.editing.parent })
        .then(result => {
            result.columns.forEach(col => groupsUI.selected.add(col));
            const problems = [];
            if (result.unknown.length) problems.push(`no match for ${escapeHtml(result.unknown.join(', '))}`);
            if (result.rejected.length) problems.push(`outside the parent group: ${escapeHtml(result.rejected.join(', '))}`);
            document.getElementById('group-spec-result').innerHTML =
                `${result.columns.length} column(s) added` +
                (problems.length ? ` <span class="log-error">— ${problems.join('; ')}</span>` : '');
            renderGroupsColumns();
        })
        .catch(reportError);
}

/* --- saving ------------------------------------------------------------- */

function groupsSave() {
    const editing = groupsUI.editing;
    const name = document.getElementById('group-name').value.trim();
    const kindSelect = document.getElementById('group-kind');
    const columns = Array.from(groupsUI.selected);

    if (!name) { logError('Give the group a name.'); return; }

    const request = editing.mode === 'create'
        ? apiPost('/api/groups/create', {
            name, parent: editing.parent, kind: kindSelect ? kindSelect.value : undefined, columns
        })
        : apiPost('/api/groups/update', {
            name: editing.name, new_name: name,
            kind: kindSelect ? kindSelect.value : undefined, columns
        });

    request
        .then(data => {
            log(`[SUCCESS] Group '${escapeHtml(name)}' ${editing.mode === 'create' ? 'created' : 'updated'} with ${columns.length} column(s).`, 'success');
            Object.entries(data.moved || {}).forEach(([from, cols]) => {
                log(`[INFO] Moved ${cols.length} column(s) out of '${escapeHtml(from)}': ${escapeHtml(cols.join(', '))}.`, 'info');
            });
            if (data.columns_dropped_from_subgroups) {
                log(`[INFO] ${data.columns_dropped_from_subgroups} column(s) left subgroups that no longer contain them.`, 'info');
            }
            groupsUI.editing = null;
            return refreshGroups();
        })
        .catch(reportError);
}

/* --- assign view: one row per column ----------------------------------- */

/* The tree flattened for a dropdown, each entry carrying its depth. */
function groupsFlat(nodes = groupsUI.tree, depth = 0, out = []) {
    nodes.forEach(node => {
        out.push({ name: node.name, depth, kind: node.kind });
        groupsFlat(node.children, depth + 1, out);
    });
    return out;
}

function groupsCurrentTarget(column) {
    return Object.prototype.hasOwnProperty.call(groupsUI.pending, column)
        ? groupsUI.pending[column]
        : (groupsUI.assignments[column] || '');
}

function renderGroupsAssign() {
    const flat = groupsFlat();
    const search = (document.getElementById('assign-search')?.value || '').toLowerCase();

    const rows = groupsUI.columns.filter(col => {
        if (search && !col.toLowerCase().includes(search)) return false;
        if (groupsUI.onlyUngrouped && groupsCurrentTarget(col)) return false;
        return true;
    });

    const options = column => {
        const current = groupsCurrentTarget(column);
        const list = flat.map(entry => {
            const indent = '&nbsp;'.repeat(entry.depth * 4) + (entry.depth ? '&#8627; ' : '');
            return `<option value="${escapeHtml(entry.name)}" ${current === entry.name ? 'selected' : ''}>
                        ${indent}${escapeHtml(entry.name)}</option>`;
        }).join('');
        return `<option value="" ${current ? '' : 'selected'}>— ungrouped —</option>${list}`;
    };

    document.getElementById('groups-assign').innerHTML = `
        <div class="hint-box">
            <strong>Assign each column to a group</strong>
            <span>Quicker than the tree when you just need to file every column. Picking a
            subgroup files the column under its parent too. Create the groups first under
            <em>Build groups</em>.</span>
        </div>

        <div style="display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap;">
            <input type="text" id="assign-search" value="${escapeHtml(search)}" placeholder="Search columns..."
                   style="flex:1; min-width:180px; font-size:12px;" oninput="renderGroupsAssign()">
            <label class="muted" style="display:flex; align-items:center; gap:6px; margin:0;">
                <input type="checkbox" ${groupsUI.onlyUngrouped ? 'checked' : ''}
                       onchange="groupsUI.onlyUngrouped = this.checked; renderGroupsAssign();">
                only ungrouped
            </label>
            <button class="btn btn-primary" style="padding:4px 12px; font-size:12px;"
                    onclick="groupsSaveAssignments()">Save assignments</button>
        </div>

        ${flat.length ? '' : '<div class="muted" style="margin-bottom:10px;">No groups yet — create one under <em>Build groups</em> first.</div>'}

        <div class="assign-list">
            ${rows.map(col => `
                <div class="form-row assign-row">
                    <span title="${escapeHtml(col)}">${escapeHtml(col)}</span>
                    <select data-col="${escapeHtml(col)}"
                            onchange="groupsStageAssignment(this.dataset.col, this.value)">
                        ${options(col)}
                    </select>
                </div>`).join('') || '<div class="muted">No columns match.</div>'}
        </div>`;

    const box = document.getElementById('assign-search');
    if (box && search) { box.focus(); box.setSelectionRange(search.length, search.length); }
    renderGroupsStatus();
}

function groupsStageAssignment(column, target) {
    if ((groupsUI.assignments[column] || '') === target) {
        delete groupsUI.pending[column];
    } else {
        groupsUI.pending[column] = target;
    }
    renderGroupsStatus();
}

function groupsSaveAssignments() {
    const assignments = groupsUI.pending;
    if (!Object.keys(assignments).length) {
        log('[INFO] No assignment changes to save.', 'info');
        return;
    }

    apiPost('/api/groups/assign', { assignments })
        .then(data => {
            log(`[SUCCESS] Filed ${data.assigned} column(s) into groups; ${data.cleared} left ungrouped.`, 'success');
            groupsUI.pending = {};
            return refreshGroups();
        })
        .catch(reportError);
}

/* --- deletion ------------------------------------------------------------ */

function groupsDelete(name) {
    const group = groupsFind(name);
    const extra = group && group.children.length ? ` and its ${group.children.length} subgroup(s)` : '';
    if (!window.confirm(`Delete group '${name}'${extra}? The columns and their data stay.`)) return;

    apiPost('/api/groups/delete', { name })
        .then(data => {
            log(`[INFO] Removed group(s): ${escapeHtml(data.removed.join(', '))}. Their columns are Uncategorised again.`, 'info');
            if (groupsUI.editing && data.removed.includes(groupsUI.editing.name)) groupsUI.editing = null;
            return refreshGroups();
        })
        .catch(reportError);
}
