"""Pictures in the chat (3.32): "Bu fişte ne yazıyor?", a screenshot pasted with Ctrl+V, a scanned PDF.

A picture added to a conversation is kept (as a JPEG of at most 1600 px) and shown in the chat as the person's message;
from then on it goes to the model with that message, so questions about it can be asked (gemma3 can see pictures).
Scanned PDFs, which have no text to read, are turned into text the same way: every page is shown to the model and
it writes down what is written there.
"""

import base64
import io
import logging

from . import llm

log = logging.getLogger("asistan.pictures")

KINDS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
MAX_SIDE = 1600
MAX_SCANNED_PAGES = 20
READ_PAGE = ("Bu, taranmış bir belgenin bir sayfası. Sayfadaki bütün yazıyı olduğu gibi, satır satır yaz: çevirme, özetleme, "
             "yorum ekleme. Tablo varsa satırlarını ' | ' ile ayır. Okunamayan yere [okunamadı] yaz. Sayfa boşsa yalnızca "
             "(boş sayfa) yaz.")


def prepare(data: bytes) -> tuple[bytes, int, int]:
    """(JPEG, width, height): turned upright (phone photos), at most MAX_SIDE, transparency on white."""
    from PIL import Image, ImageOps

    try:
        image = Image.open(io.BytesIO(data))
        image.seek(0)  # the first frame of a GIF
        image = ImageOps.exif_transpose(image)
    except Exception as e:
        raise ValueError(f"Resim açılamadı: {e}")
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        white = Image.new("RGB", image.size, "white")
        white.paste(image, mask=image.split()[-1])
        image = white
    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88)
    return out.getvalue(), image.width, image.height


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _pdf_pages(path: str) -> tuple[list[bytes], int]:
    import pypdfium2

    pdf = pypdfium2.PdfDocument(path)
    try:
        total = len(pdf)
        pages = []
        for index in range(min(total, MAX_SCANNED_PAGES)):
            page = pdf[index]
            width = page.get_width()
            scale = min(2.5, MAX_SIDE / max(width, page.get_height(), 1))  # ~150-180 dpi for A4
            image = page.render(scale=scale).to_pil()
            out = io.BytesIO()
            image.convert("RGB").save(out, format="JPEG", quality=90)
            pages.append(out.getvalue())
        return pages, total
    finally:
        pdf.close()


async def read_scanned_pdf(path: str, model: str) -> tuple[str, int]:
    """The text of a scanned PDF, written down by the model page by page. (text, number of pages)"""
    from starlette.concurrency import run_in_threadpool

    pages, total = await run_in_threadpool(_pdf_pages, path)
    parts = []
    for number, page in enumerate(pages, 1):
        try:
            text = await llm.chat_text(model, [{"role": "user", "content": READ_PAGE, "images": [b64(page)]}],
                                       num_predict=1500)
        except llm.OllamaError as e:
            raise ValueError(f"Sayfa {number} okunamadı: {e}")
        parts.append(f"[Sayfa {number}]\n{text.strip()}")
        log.info("Taranmış PDF: sayfa %d/%d okundu", number, len(pages))
    if total > len(pages):
        parts.append(f"[Belgenin {len(pages) + 1}-{total}. sayfaları okunmadı: en çok {MAX_SCANNED_PAGES} sayfa okunuyor.]")
    return "\n\n".join(parts), total
