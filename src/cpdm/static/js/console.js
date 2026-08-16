/* The command prompt, with a recallable history (arrow up / down). */

const commandHistory = [];
let historyCursor = 0;

/* Tab completes the word being typed. The browser would move focus instead,
   so the default is suppressed; a unique candidate is filled in, and an
   ambiguous one fills in as far as the candidates agree and lists them. */
function completeCommand(input) {
    return apiPost('/api/command/complete', { line: input.value })
        .then(result => {
            if (!result.total) return;

            const chosen = result.total === 1 ? result.candidates[0] : result.common;
            if (chosen && chosen.length > result.prefix.length) {
                const head = input.value.slice(0, input.value.length - result.prefix.length);
                const quoted = /[\s"']/.test(chosen) ? `"${chosen.replace(/"/g, '\\"')}"` : chosen;
                input.value = head + quoted + (result.total === 1 ? ' ' : '');
            }

            if (result.total > 1) {
                const shown = result.candidates.slice(0, 24).map(escapeHtml).join('   ');
                log(shown + (result.total > 24 ? `   … and ${result.total - 24} more` : ''), 'info');
            }
        })
        .catch(() => {});      // completion is a convenience; never interrupt typing
}

function handleCommand(event) {
    const input = event.target;

    if (event.key === 'Tab') {
        event.preventDefault();
        completeCommand(input);
        return;
    }

    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        if (!commandHistory.length) return;
        event.preventDefault();
        historyCursor += (event.key === 'ArrowUp' ? -1 : 1);
        historyCursor = Math.max(0, Math.min(commandHistory.length, historyCursor));
        input.value = commandHistory[historyCursor] || '';
        return;
    }

    if (event.key !== 'Enter') return;

    const command = input.value.trim();
    if (!command) return;

    commandHistory.push(command);
    historyCursor = commandHistory.length;
    log(`py-data&gt; ${escapeHtml(command)}`, 'info');
    input.value = '';

    apiPost('/api/command', { command })
        .then(data => {
            if (data.clear) {
                document.getElementById('pane-output').innerHTML = '';
            } else if (data.html) {
                log(data.html);
            } else if (data.output) {
                log(escapeHtml(data.output));
            }
            refreshStatus();
        })
        .catch(reportError);
}
