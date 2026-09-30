"""Fresh ComfyUI next to the old one (comfyui_yeni_kur.bat).

- Downloads the latest official "ComfyUI Windows portable (NVIDIA)" release from GitHub (about 2 GB). The portable
  build carries its own python (python_embeded): no conda, and the old ComfyUI + its conda environment stay untouched.
- Unpacks it to P:\\Comfy\\ComfyUI_yeni (7-Zip if installed, otherwise Windows' own tar).
- Writes extra_model_paths.yaml so the Fooocus models (P:\\pinokio\\api\\fooocus\\app\\modelsM) are used where they are,
  without copying 475 GB.
- Adds ComfyUI-Manager (built in on new versions, otherwise cloned with git) and a start file on the desktop.
Running it again is safe: finished steps are skipped.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE = Path(os.environ.get("COMFY_BASE", r"P:\Comfy"))
TARGET = BASE / "ComfyUI_yeni"
FOOOCUS = Path(os.environ.get("FOOOCUS_MODELS", r"P:\pinokio\api\fooocus\app\modelsM"))
RELEASES = "https://api.github.com/repos/comfyanonymous/ComfyUI/releases/latest"
ASSET = re.compile(r"^ComfyUI_windows_portable_nvidia(_cu\d+)?\.7z$")
MANAGER_GIT = "https://github.com/ltdrdata/ComfyUI-Manager"
# ComfyUI's folder names for model kinds, and the Fooocus folder names that hold the same kind
KINDS = {
    "checkpoints": ["checkpoints"],
    "loras": ["loras", "lora"],
    "vae": ["vae"],
    "embeddings": ["embeddings"],
    "upscale_models": ["upscale_models", "upscale"],
    "controlnet": ["controlnet"],
    "clip_vision": ["clip_vision"],
    "clip": ["clip"],
    "unet": ["unet"],
    "diffusion_models": ["diffusion_models"],
    "text_encoders": ["text_encoders"],
}


def step(text: str) -> None:
    print(f"\n=== {text}", flush=True)


def pick_asset(release: dict) -> tuple[str, str, int]:
    """The plain NVIDIA build if there is one, else the first CUDA-specific one (all work on an RTX 4060)."""
    found = sorted((a for a in release.get("assets", []) if ASSET.match(a["name"])), key=lambda a: a["name"])
    if not found:
        raise SystemExit("GitHub'daki son surumde Windows portable (NVIDIA) dosyasi bulunamadi: " +
                         ", ".join(a["name"] for a in release.get("assets", [])))
    a = found[0]
    return a["name"], a["browser_download_url"], a.get("size", 0)


def download(url: str, dest: Path, size: int) -> None:
    if dest.exists() and size and dest.stat().st_size == size:
        print("zaten indirilmis:", dest)
        return
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "YerelAsistan"})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or size or 0)
        done, shown = 0, -1
        while chunk := r.read(4 * 1024 * 1024):
            f.write(chunk)
            done += len(chunk)
            percent = int(done * 100 / total) if total else 0
            if percent // 5 != shown:
                shown = percent // 5
                print(f"  %{percent}  ({done / 1024 ** 3:.2f} GB)", flush=True)
    part.replace(dest)


def unpack(archive: Path, into: Path) -> None:
    seven = next((p for p in (Path(r"C:\Program Files\7-Zip\7z.exe"), Path(r"C:\Program Files (x86)\7-Zip\7z.exe"))
                  if p.exists()), None)
    if seven:
        cmd = [str(seven), "x", "-y", f"-o{into}", str(archive)]
    else:
        cmd = ["tar", "-xf", str(archive), "-C", str(into)]  # Windows 11's tar (libarchive) reads .7z
    print(" ".join(cmd), flush=True)
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit(f"Arsiv acilamadi. Elle ac: {archive} dosyasina sag tikla > Tumunu ayikla > {into}\n"
                         "sonra bu araci yeniden calistir.")


def model_paths_yaml(fooocus: Path) -> str | None:
    if not fooocus.is_dir():
        return None
    subdirs = {d.name.lower(): d.name for d in fooocus.iterdir() if d.is_dir()}
    lines = ["# Yerel Asistan: Fooocus modelleri kopyalanmadan kullanilir", "fooocus:",
             f"    base_path: {fooocus.as_posix()}/"]
    for kind, names in KINDS.items():
        found = [subdirs[n] for n in names if n in subdirs]
        if found:
            lines.append(f"    {kind}: {found[0]}")
    return "\n".join(lines) + "\n" if len(lines) > 3 else None


def launcher(root: Path, manager_flag: bool) -> str:
    flags = "--windows-standalone-build --auto-launch" + (" --enable-manager" if manager_flag else "")
    return ("@echo off\r\n"
            "rem Yeni ComfyUI (Yerel Asistan araci comfyui_yeni_kur ile kuruldu)\r\n"
            f'cd /d "{root}"\r\n'
            f".\\python_embeded\\python.exe -s ComfyUI\\main.py {flags}\r\n"
            "pause\r\n")


def desktop() -> Path:
    try:
        import ctypes.wintypes

        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY (OneDrive too)
        if buf.value:
            return Path(buf.value)
    except Exception:
        pass
    return Path.home() / "Desktop"


def main() -> int:
    python = TARGET / "python_embeded" / "python.exe"
    if not python.exists():
        step("1/5 GitHub'da son ComfyUI surumu araniyor")
        req = urllib.request.Request(RELEASES, headers={"User-Agent": "YerelAsistan"})
        release = json.load(urllib.request.urlopen(req, timeout=60))
        name, url, size = pick_asset(release)
        print(f"surum {release.get('tag_name')}: {name} ({size / 1024 ** 3:.1f} GB)")
        free = shutil.disk_usage(BASE.anchor or BASE).free
        if free < 30 * 1024 ** 3:
            raise SystemExit(f"{BASE.anchor} surucusunde yeterli yer yok (en az 30 GB gerekir).")
        BASE.mkdir(parents=True, exist_ok=True)
        archive = BASE / name
        step("2/5 Indiriliyor")
        download(url, archive, size)
        step("3/5 Arsiv aciliyor (birkac dakika surebilir)")
        before = {d.name for d in BASE.iterdir() if d.is_dir()}
        unpack(archive, BASE)
        new = [d for d in BASE.iterdir() if d.is_dir() and d.name not in before and (d / "python_embeded").is_dir()]
        if len(new) != 1:
            raise SystemExit(f"Acilan klasor bulunamadi ({BASE} icine bak): {[d.name for d in new]}")
        new[0].rename(TARGET)
        archive.unlink()
    else:
        print("Yeni ComfyUI zaten kurulu:", TARGET)
    if not python.exists():
        raise SystemExit(f"Kurulum eksik: {python} yok.")

    step("4/5 Fooocus modelleri baglaniyor ve ComfyUI-Manager ekleniyor")
    comfy = TARGET / "ComfyUI"
    yaml = model_paths_yaml(FOOOCUS)
    if yaml:
        (comfy / "extra_model_paths.yaml").write_text(yaml, encoding="utf-8")
        print(yaml)
    else:
        print("Fooocus model klasoru bulunamadi:", FOOOCUS)
    cli_args = comfy / "comfy" / "cli_args.py"
    manager_flag = ((comfy / "manager_requirements.txt").exists() and cli_args.exists()
                    and "--enable-manager" in cli_args.read_text(encoding="utf-8", errors="replace"))
    if manager_flag:  # new ComfyUI: the manager is built in, only its packages are needed
        subprocess.run([str(python), "-s", "-m", "pip", "install", "-r", str(comfy / "manager_requirements.txt")])
    elif not (comfy / "custom_nodes" / "ComfyUI-Manager").exists():
        if shutil.which("git"):
            subprocess.run(["git", "clone", MANAGER_GIT, str(comfy / "custom_nodes" / "ComfyUI-Manager")])
        else:
            print("git yok: ComfyUI-Manager eklenmedi (ComfyUI yine de calisir).")

    step("5/5 Kontrol ve baslatma dosyasi")
    subprocess.run([str(python), "-s", "-c", "import torch; print('torch', torch.__version__, '- GPU:', "
                    "torch.cuda.is_available() and torch.cuda.get_device_name(0))"])
    start = launcher(TARGET, manager_flag)
    (BASE / "ComfyUI_yeni.bat").write_text(start, encoding="ascii", newline="")
    shortcut = desktop() / "ComfyUI (yeni).bat"
    try:
        shortcut.write_text(start, encoding="ascii", newline="")
        print("Masaustune eklendi:", shortcut)
    except OSError as e:
        print("Masaustune yazilamadi:", e)
    print(f"\nBITTI. Baslatmak icin: {BASE / 'ComfyUI_yeni.bat'} ya da masaustundeki 'ComfyUI (yeni)'.")
    print("Eski ComfyUI (P:\\Comfy\\ComfyUI.bat) ve conda ortamina dokunulmadi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
