"""Start the assistant and open it in the default browser."""

import threading
import webbrowser

import uvicorn

from app.config import ROOT, SETTINGS_DIR, VERSION

HOST = "127.0.0.1"  # only reachable from this computer
PORT = 8765

if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"Yerel Asistan sürüm {VERSION} başlatılıyor: {url}  (kapatmak için bu pencereyi kapat)")
    # 3.25: started by hand (baslat.bat) → nobody is signed in until a voice or passcode says who it is. Only the
    # automatic restarts below (after an update) bring the last person back (app/identity.py restore()); they do not
    # run this block.
    (SETTINGS_DIR / "oturum.json").unlink(missing_ok=True)
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
