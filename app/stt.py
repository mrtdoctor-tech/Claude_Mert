"""Offline speech-to-text with faster-whisper (the model is downloaded once, on first use).

With an NVIDIA graphics card it runs on the GPU (many times faster), provided the CUDA libraries
(cuBLAS, cuDNN; installed by baslat.bat / kurulum.bat from requirements-gpu.txt) can be loaded.
Otherwise, or if the GPU fails at any point, it quietly uses the CPU.
"""

import logging
import os
import threading

log = logging.getLogger("asistan.stt")

# Windows file names of the CUDA libraries faster-whisper (CTranslate2 4.5+) needs on the GPU.
CUDA_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll")

_lock = threading.Lock()
_model = None
_model_key = None  # (model name, "gpu" | "cpu")
_gpu_failed = False  # after one GPU error, stay on the CPU until the app restarts
_dlls_added = False


def _add_nvidia_dlls():
    """Make the DLLs from the pip packages nvidia-cublas-cu12 / nvidia-cudnn-cu12 findable."""
    global _dlls_added
    if _dlls_added or os.name != "nt":
        return
    _dlls_added = True
    try:
        import nvidia
    except ImportError:
        return
    for root in getattr(nvidia, "__path__", []):
        for package in ("cublas", "cudnn"):
            bin_dir = os.path.join(root, package, "bin")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


def _gpu_usable() -> bool:
    if _gpu_failed:
        return False
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() < 1:
            return False
    except Exception:
        return False
    if os.name == "nt":
        # A missing CUDA DLL can crash the whole process later, so check they all load first.
        import ctypes

        _add_nvidia_dlls()
        for dll in CUDA_DLLS:
            try:
                ctypes.WinDLL(dll)
            except OSError:
                log.info("Ses tanıma işlemcide çalışacak: %s bulunamadı", dll)
                return False
    return True


def load(model_name: str, device: str = "auto"):
    """Load (or reuse) the model. device: "auto" = GPU when possible, "cpu" = always CPU."""
    global _model, _model_key, _gpu_failed
    with _lock:
        use_gpu = device != "cpu" and _gpu_usable()
        key = (model_name, "gpu" if use_gpu else "cpu")
        if _model is None or _model_key != key:
            from faster_whisper import WhisperModel

            _model = None
            if use_gpu:
                try:
                    _model = WhisperModel(model_name, device="cuda", compute_type="float16")
                except Exception:
                    log.exception("Ses tanıma ekran kartında başlatılamadı, işlemciye geçiliyor")
                    _gpu_failed = True
                    key = (model_name, "cpu")
            if _model is None:
                _model = WhisperModel(model_name, device="cpu", compute_type="int8")
            _model_key = key
            log.info("Ses tanıma modeli hazır: %s (%s)", *key)
        return _model


def current_device() -> str | None:
    """ "gpu" / "cpu" once a model is loaded, else None."""
    return _model_key[1] if _model_key else None


def _run(model, path: str, language: str | None) -> str:
    segments, _ = model.transcribe(path, language=language or None, vad_filter=True, beam_size=1)
    return " ".join(s.text.strip() for s in segments).strip()


def transcribe(path: str, model_name: str, language: str | None, device: str = "auto") -> tuple[str, str]:
    """Returns (text, "gpu" | "cpu")."""
    global _gpu_failed
    model = load(model_name, device)
    try:
        with _lock:
            return _run(model, path, language), current_device()
    except Exception:
        if current_device() != "gpu":
            raise
        log.exception("Ses tanıma ekran kartında başarısız oldu, işlemciye geçiliyor")
        _gpu_failed = True
    model = load(model_name, "cpu")
    with _lock:
        return _run(model, path, language), current_device()
