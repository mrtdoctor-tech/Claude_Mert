"""ComfyUI status report (comfyui_durum.bat): what is installed, before updating anything. Changes nothing.

Run with the ComfyUI conda environment's python. Prints: python/torch/CUDA/GPU, the packages HourGlow's hg_olcum.py
depends on (opencv, numpy), the ComfyUI version, custom nodes, the model files (by folder), extra_model_paths.yaml,
free disk space and the large model files in Pinokio apps (Fooocus...), which ComfyUI could share instead of copying.
"""

import os
import re
import shutil
import subprocess
import sys
from importlib import metadata

MODEL_EXT = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft")
SKIP_DIRS = {".git", "node_modules", "env", "venv", ".venv", "__pycache__", "cache", "site-packages", "bin"}


def gb(size: float) -> str:
    return f"{size / 1024 ** 3:.1f} GB"


def section(title: str) -> None:
    print(f"\n--- {title}")


def packages() -> None:
    section("Python ve paketler (ComfyUI ortami)")
    print("python", sys.version.split()[0], "-", sys.executable)
    for name in ("torch", "torchvision", "torchaudio", "xformers", "numpy", "opencv-python", "opencv-contrib-python",
                 "opencv-python-headless", "safetensors", "transformers", "comfyui-frontend-package", "av"):
        try:
            print(f"{name}: {metadata.version(name)}")
        except metadata.PackageNotFoundError:
            pass
    try:
        import torch

        print("CUDA:", torch.cuda.is_available(), "- torch CUDA", torch.version.cuda)
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            print("GPU:", p.name, "-", gb(p.total_memory))
    except Exception as e:  # a broken torch is exactly what the report should show
        print("torch acilamadi:", e)
    try:
        import cv2

        print("cv2 (hg_olcum icin):", cv2.__version__)
    except Exception as e:
        print("cv2 acilamadi:", e)


def comfy_version(comfy: str) -> None:
    section(f"ComfyUI: {comfy}")
    version_file = os.path.join(comfy, "comfyui_version.py")
    if os.path.exists(version_file):
        m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", open(version_file, encoding="utf-8").read())
        print("surum:", m.group(1) if m else "?")
    else:
        print("surum: comfyui_version.py yok (2025 oncesi eski bir surum)")
    if os.path.isdir(os.path.join(comfy, ".git")):
        try:
            out = subprocess.run(["git", "-C", comfy, "log", "-1", "--format=%cd %h", "--date=short"],
                                 capture_output=True, text=True, timeout=20)
            print("git: son degisiklik", out.stdout.strip() or out.stderr.strip())
            out = subprocess.run(["git", "-C", comfy, "status", "--short"], capture_output=True, text=True, timeout=20)
            changed = [l for l in out.stdout.splitlines() if l.strip()]
            print("elle degistirilmis dosya:", len(changed))
            for line in changed[:10]:
                print("  ", line)
        except FileNotFoundError:
            print("git: klasor git ile kurulmus ama git programi PATH'te yok")
        except Exception as e:
            print("git okunamadi:", e)
    else:
        print("git: yok (ZIP ile kurulmus)")
    nodes = os.path.join(comfy, "custom_nodes")
    section("Eklentiler (custom_nodes)")
    if os.path.isdir(nodes):
        found = sorted(n for n in os.listdir(nodes)
                       if os.path.isdir(os.path.join(nodes, n)) and not n.startswith((".", "__")))
        for n in found:
            print(" ", n, "(kapali)" if n.endswith(".disabled") else "")
        print("toplam:", len(found))
    for name in ("extra_model_paths.yaml",):
        path = os.path.join(comfy, name)
        if os.path.exists(path):
            section(name)
            print(open(path, encoding="utf-8", errors="replace").read().strip())


def model_files(root: str, limit: int = 400):
    count = 0
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith(MODEL_EXT):
                path = os.path.join(folder, f)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size >= 50 * 1024 ** 2:
                    yield path, size
                    count += 1
                    if count >= limit:
                        return


def models(comfy: str) -> None:
    section("Modeller (ComfyUI\\models, 50 MB ustu)")
    root = os.path.join(comfy, "models")
    total, by_folder = 0, {}
    for path, size in model_files(root):
        rel = os.path.relpath(path, root)
        by_folder.setdefault(rel.split(os.sep)[0], []).append((rel, size))
        total += size
    for folder in sorted(by_folder):
        print(f"[{folder}]")
        for rel, size in sorted(by_folder[folder]):
            print(f"  {gb(size):>8}  {rel}")
    print("toplam:", gb(total))


def pinokio(root: str) -> None:
    section(f"Pinokio uygulamalarindaki buyuk modeller ({root}, 500 MB ustu)")
    if not os.path.isdir(root):
        print("bulunamadi")
        return
    for app in sorted(os.listdir(root)):
        found = [(p, s) for p, s in model_files(os.path.join(root, app), 200) if s >= 500 * 1024 ** 2]
        if found:
            print(f"[{app}] {len(found)} dosya, {gb(sum(s for _, s in found))}")
            for p, s in sorted(found)[:25]:
                print(f"  {gb(s):>8}  {os.path.relpath(p, root)}")


def disks(paths) -> None:
    section("Bos disk alani")
    for p in paths:
        try:
            u = shutil.disk_usage(p)
            print(f"{p}  bos {gb(u.free)} / {gb(u.total)}")
        except OSError:
            pass


if __name__ == "__main__":
    comfy = sys.argv[1] if len(sys.argv) > 1 else r"P:\Comfy\ComfyUI"
    packages()
    comfy_version(comfy)
    models(comfy)
    pinokio(sys.argv[2] if len(sys.argv) > 2 else r"P:\pinokio\api")
    disks([os.path.splitdrive(comfy)[0] + os.sep or comfy, "C:\\"])
