"""Reads pip's --dry-run plan (asistani_ai_assistanta_tasi.bat) and says whether HourGlow's packages would change.

A package in "Would install" is either new to the environment (harmless: nothing used it before) or already installed
and about to be replaced by another version (risky for the HourGlow scripts). Only the second kind stops the move.
Exit code 1 = stop.
"""

import re
import sys
from importlib import metadata

SENSITIVE = {"numpy", "torch", "torchaudio", "torchvision", "numba", "llvmlite", "scipy", "librosa", "soundfile",
             "tiktoken", "openai-whisper", "transformers", "tokenizers", "huggingface-hub", "protobuf"}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main(plan_path: str) -> int:
    planned = {}
    for line in open(plan_path, encoding="utf-8", errors="replace"):
        if line.startswith("Would install"):
            for item in line.split()[2:]:
                name, _, version = item.rpartition("-")
                planned[_norm(name)] = version
    installed = {_norm(d.metadata["Name"]): d.version for d in metadata.distributions() if d.metadata["Name"]}
    new = sorted(n for n in planned if n not in installed)
    changed = sorted(n for n in planned if n in installed)
    print("Yeni eklenecek (ortamda hic yoktu, zararsiz):", ", ".join(new) or "-")
    print("Surumu degisecek (zaten kurulu):", ", ".join(f"{n} {installed[n]} -> {planned[n]}" for n in changed) or "-")
    risky = [n for n in changed if n in SENSITIVE or n.startswith("nvidia-")]  # nvidia-*: torch's CUDA libraries
    if risky:
        print("HourGlow icin hassas olan ve degisecek:", ", ".join(risky))
        return 1
    print("HourGlow'un hassas paketlerinden hicbiri degismiyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
