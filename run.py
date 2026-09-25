"""Start the assistant and open it in the default browser."""

import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"  # only reachable from this computer
PORT = 8765

if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"Asistan başlatılıyor: {url}  (kapatmak için bu pencereyi kapat)")
    threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT)
