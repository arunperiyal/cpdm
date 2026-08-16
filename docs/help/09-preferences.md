# Preferences

**File → Preferences** sets how the workspace looks and behaves. Choices apply the moment you make them — there is no Save button to forget — and are kept **in this browser**, not on the server. A workspace hosted for several people therefore gives each of them their own theme and text size without disturbing anyone else.

**Reset to defaults** puts everything back.

## Appearance

| Setting | What it does |
| --- | --- |
| **Theme** | *Dark* (the default), *Light*, *High contrast*, or *Match the system* — which follows your desktop and changes with it. |
| **Interface font** | The default pairing, your system's interface font, a serif face, monospace throughout, or a wide-spaced setting with plain letterforms that some people find easier to read. |
| **Text size** | 11–22px. Everything scales with it, including the documentation pages. |
| **Density** | *Compact* tightens the padding in rows, menus and tables, which fits more on a laptop screen. |
| **Motion** | *Reduced* turns off smooth scrolling and transitions. It is applied automatically anyway if your system asks for reduced motion. |

The panel at the bottom of the dialogue shows the current theme's success, information, error and warning colours, its monospace face and its buttons, so you can judge a setting before closing.

## Behaviour

| Setting | What it does |
| --- | --- |
| **Rows per page** | How many rows [Table → Rows](/docs/help/the-table-menu) shows at a time: 10, 25, 50 or 100. |
| **Keep in the log** | The output pane trims itself to this many lines. A long session otherwise accumulates thousands, and the pane slows down. *Never trim* keeps the lot. |

## What is not here

Anything that changes the **data** belongs to the menus that own it, not to preferences: the app should never quietly behave differently towards your dataset because of a setting you made weeks ago. Confirmation prompts before deleting rows or columns cannot be turned off for the same reason.

Server-side settings — the address and port, whether the service starts at boot — belong to `cpdmctl.sh`, since they apply to everyone using that server rather than to one browser. See the README.

## If the theme looks wrong after an update

The stylesheets are versioned, so a changed file reaches the browser on its own. If something still looks half-styled, reload once with **Ctrl+Shift+R**; if it persists, check **Help → About CPDM** to confirm the server is running the code you expect.
