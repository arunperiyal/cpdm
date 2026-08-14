/* Fields -> Groups: build a tree of column sets.

   A root group is a construct (Demographics, Wellbeing); a subgroup is a facet
   of its parent — a subscale — and may only take columns the parent holds.
   Columns can be ticked in the list or typed as a spec (names, ranges, globs). */

const groupsUI = {
    tree: [],
    editing: null,      // {mode: 'create'|'edit', name, parent, kind}
    eligible: [],
    selected: new Set(),
    anchor: null
};

function openGroupsModal() {
    withDataset(() => {
        groupsUI.editing = null;
        refreshGroups().then(() => openModal('modal-groups'));
    });
}

function refreshGroups() {
    return apiGet('/api/groups')
        .then(data => {
            groupsUI.tree = data.groups;
            renderGroupsTree();
            renderGroupsEditor();
        })
        .catch(reportError);
}

/* --- tree -------------------------------------------------------------- */

function renderGroupsTree() {
    const container = document.getElementById('groups-tree');

    const node = (group, depth) => `
        <div class="group-node ${groupsUI.editing && groupsUI.editing.name === group.name ? 'active' : ''}"
             style="margin-left:${depth * 16}px">
            <div class="group-node-main">
                <span class="group-name">${escapeHtml(group.name)}</span>
                <span class="group-badge">${escapeHtml(group.kind)}</span>
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
    groupsUI.editing = { mode: 'create', name: '', parent, kind: null };
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
    groupsUI.editing = { mode: 'edit', name, parent: group.parent, kind: group.own_kind };
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

    const kindField = editing.parent
        ? `<div class="muted">Subgroups inherit the kind of their root group.</div>`
        : `<select id="group-kind" style="width:100%;">
               ${['scale', 'demographics', 'other'].map(kind => `
                   <option value="${kind}" ${editing.kind === kind ? 'selected' : ''}>
                       ${kind === 'scale' ? 'Scale (items to be scored)'
                         : kind === 'demographics' ? 'Demographics'
                         : 'Other (kept out of scoring)'}
                   </option>`).join('')}
           </select>`;

    editor.innerHTML = `
        <div class="modal-header" style="font-size:15px; margin-bottom:12px;">${title}</div>

        <label class="muted">Group name</label>
        <input type="text" id="group-name" value="${escapeHtml(editing.name)}"
               placeholder="e.g. Wellbeing, or Positive affect" style="width:100%; margin:4px 0 12px;">

        <label class="muted">Kind</label>
        <div style="margin:4px 0 12px;">${kindField}</div>

        <label class="muted">Type columns (names, ranges like <code>WB1:WB5</code> or <code>3:9</code>, globs like <code>WB*</code>)</label>
        <div style="display:flex; gap:8px; margin:4px 0 4px;">
            <input type="text" id="group-spec" placeholder="WB1:WB5, DS*" style="flex:1;"
                   onkeydown="if (event.key === 'Enter') groupsApplySpec()">
            <button class="btn btn-secondary" onclick="groupsApplySpec()">Add to selection</button>
        </div>
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
    groupsUI.visible = visible;

    document.getElementById('group-columns').innerHTML = visible.map((col, index) => `
        <label class="col-pick" title="${escapeHtml(col)}">
            <input type="checkbox" ${groupsUI.selected.has(col) ? 'checked' : ''}
                   onclick="groupsToggleColumn(${index}, event)">
            <span>${escapeHtml(col)}</span>
        </label>`).join('') || '<div class="muted">No columns available.</div>';

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
