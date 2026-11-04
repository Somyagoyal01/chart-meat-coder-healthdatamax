"""PDF -> text. Uses the PDF text layer; falls back to OCR (Tesseract) for scanned pages."""
from __future__ import annotations
import io
import pymupdf

MIN_CHARS = 30  # a page with less text than this is treated as a scan


def _ocr_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:  # OCR is optional
        return ""
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def extract_pages(path: str) -> list[dict]:
    """Return [{'page': n, 'text': str, 'method': 'text'|'ocr'}]."""
    out = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            method = "text"
            if len(text.strip()) < MIN_CHARS:
                text, method = _ocr_page(page), "ocr"
            out.append({"page": i, "text": text, "method": method})
    return out


def extract_text(path: str) -> tuple[str, list[str]]:
    pages = extract_pages(path)
    return "\n".join(p["text"] for p in pages), [p["method"] for p in pages]
