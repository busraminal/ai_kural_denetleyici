# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Iterable, cast
import os
import re
import fitz  # PyMuPDF

# --- yardımcılar -------------------------------------------------------------
_WS = re.compile(r"\s+")
_PUNCT_TAIL = re.compile(r"[ \t]*[:：;；,.…!?？!]+$")

def _norm(s: str) -> str:
    """Boşlukları sadeleştir, baş/sonu kırp."""
    return _WS.sub(" ", (s or "").strip())

def _tail_trim(s: str) -> str:
    """Sondaki yaygın noktalama işaretlerini temizle."""
    return _PUNCT_TAIL.sub("", s or "").strip()

def _variants(q: str) -> Iterable[str]:
    """Aramada denenecek metin varyantları (duyarsız eşleşme için)."""
    q = _norm(q)
    if not q:
        return []
    base = [q, q.upper(), q.lower(), _tail_trim(q)]
    seen: set[str] = set()
    out: list[str] = []
    for v in base:
        v = _norm(v)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# --- ana fonksiyon -----------------------------------------------------------
def build_annotated_pdf(original_pdf: str,
                        lines: List[Dict[str, Any]],
                        findings: List[Dict[str, Any]],
                        output_pdf: str) -> str:
    """
    PDF üzerinde *sorunlu* yerleri vurgular.
    - 'missing' boyanmaz (metin yoktur).
    - 'wrong' ve 'present' için hem 'title' hem de varsa 'detail' metni aranır.
    """
    doc = fitz.open(original_pdf)

    HIGHLIGHT_STATUSES = {"wrong", "present"}
    COLOR = (0.00, 0.60, 0.00)   # koyu yeşil
    OPACITY = 0.35

    for f in findings:
        status = f.get("status")
        if status not in HIGHLIGHT_STATUSES:
            continue

        # Aranacak cümle/kelimeler: title + detail (varsa)
        candidates: list[str] = []
        title = (f.get("title") or f.get("rule_id") or "").strip()
        detail = (f.get("detail") or "").strip()
        if title:
            candidates.append(title)
        if detail and detail.lower() != title.lower():
            candidates.append(detail)

        for raw in candidates:
            for q in _variants(raw):
                for p in doc:  # p: fitz.Page
                    page = cast(Any, p)  # Pylance uyarısını gider: dinamik metotlar
                    # hızlı kaba kontrol (performans)
                    text = page.get_text("text") or ""  # type: ignore[attr-defined]
                    if q.lower() not in text.lower():
                        continue

                    # PyMuPDF çoğu durumda duyarsız çalışır; yine de varyantları deniyoruz
                    rects = page.search_for(q)  # type: ignore[attr-defined]
                    # ek bir güvenlik: hiç bulamazsa trimlenmiş/upper varyant zaten _variants'ta var

                    for r in rects:
                        annot = page.add_highlight_annot(r)
                        annot.set_colors(stroke=COLOR, fill=COLOR)
                        annot.update(opacity=OPACITY)

    # Klasör yoksa oluştur
    out_dir = os.path.dirname(output_pdf)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    doc.save(output_pdf, deflate=True, garbage=4)
    doc.close()
    return output_pdf
