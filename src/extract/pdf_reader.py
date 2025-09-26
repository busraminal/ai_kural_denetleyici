# -*- coding: utf-8 -*-
from pathlib import Path
import sys

try:
    import fitz  # PyMuPDF
except Exception as e:
    print("PyMuPDF import HATASI:", e)
    print("Çözüm: pip install pymupdf")
    sys.exit(1)


def pick_first_pdf(dir_path: str) -> Path:
    d = Path(dir_path)
    if not d.exists():
        raise FileNotFoundError(f"Klasör yok: {d.resolve()}")
    pdfs = sorted([p for p in d.glob("*.pdf")])
    if not pdfs:
        raise FileNotFoundError(f"'{d.resolve()}' içinde PDF bulunamadı.")
    return pdfs[0]


def read_pdf_lines(pdf_path: Path):
    print("Çalışma dizini:", Path.cwd())
    print("Açılacak PDF:", pdf_path.resolve())
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF bulunamadı: {pdf_path}")

    doc = fitz.open(pdf_path)  # type: ignore[attr-defined]
    print("Sayfa sayısı:", doc.page_count)

    results = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        txt = (s.get("text") or "").strip()
                        if not txt:
                            continue
                        results.append({
                            "page": i + 1,
                            "text": txt,
                            "font": s.get("font"),
                            "size": s.get("size"),
                            "flags": s.get("flags"),
                            "bbox": s.get("bbox"),
                        })
    return results


if __name__ == "__main__":
    try:
        pdf_path = pick_first_pdf("data/pdfs")   # klasördeki ilk PDF’i seç
        lines = read_pdf_lines(pdf_path)
        print(f"Toplam satır: {len(lines)}")
        for l in lines[:20]:
            print(l)
    except Exception as e:
        print("HATA:", type(e).__name__, "-", e)
        sys.exit(1)
