/* The command prompt, with a recallable history (arrow up / down). */

const commandHistory = [];
let historyCursor = 0;

function handleCommand(event) {
    const input = event.target;

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
