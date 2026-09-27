"""Start the assistant and open it in the default browser."""

import threading
import webbrowser

import uvicorn

from app.config import ROOT, VERSION

HOST = "127.0.0.1"  # only reachable from this computer
PORT = 8765

if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"Yerel Asistan sürüm {VERSION} başlatılıyor: {url}  (kapatmak için bu pencereyi kapat)")
    threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    # reload: after an update (e.g. "Pull origin" in GitHub Desktop) the server restarts itself with the new code.
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        reload_dirs=[str(ROOT)],
        reload_includes=["*.py", "VERSION"],
    )
