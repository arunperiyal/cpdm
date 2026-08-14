"""CPDM launcher: `python app.py` starts the workspace and opens a browser.

The application itself lives in ``src/cpdm``; this file only puts ``src`` on the
import path and runs the app factory.
"""

import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from cpdm import create_app  # noqa: E402  (import needs the path set above)

HOST = os.environ.get("CPDM_HOST", "127.0.0.1")
PORT = int(os.environ.get("CPDM_PORT", "5000"))
DEBUG = os.environ.get("CPDM_DEBUG", "").lower() in ("1", "true", "yes")

app = create_app()


def open_browser():
    webbrowser.open_new(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    print(f"Launching CPDM Web Workspace on http://{HOST}:{PORT} ...")
    if not DEBUG:
        threading.Timer(1.2, open_browser).start()
    app.run(host=HOST, port=PORT, debug=DEBUG)
