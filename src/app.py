# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List
import os
import sys
from pathlib import Path
import requests

# --- import yolları ---
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

# --- proje modülleri ---
from extract.pdf_reader import pick_first_pdf, read_pdf_lines
from extract.heading_extractor import load_headings_dict, detect_headings
from rules.rules_engine import run_rules
from report.report_writer import save_bundle            # JSON/Excel/MD(+CSV) tek seferde
from report.commentary_llm import generate_commentary   # Ollama yorumu (tek kaynak)

# ------------------------------
# Ayarlar
# ------------------------------
# Taşınmaz türü: "arsa" | "tarla" | "konut" | "bina" | "ticari_tesis" | "sera" | "turistik_tesis" | "akaryakit"
ASSET_TYPE = os.getenv("ASSET_TYPE", "arsa")
REPORT_BASENAME = f"ziraat_raporu_{ASSET_TYPE}"

# LLM kontrolü (aynı terminalde:  $env:ENABLE_LLM="1")
ENABLE_LLM = os.getenv("ENABLE_LLM", "0").strip().lower() in ("1", "true")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")  # hızlı varsayılan

def _warmup_ollama(model: str) -> None:
    """İlk çağrı gecikmesini azaltmak için 1 token'lık ısınma isteği."""
    if not ENABLE_LLM:
        return
    try:
        requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": "ok", "stream": False, "options": {"num_predict": 1}},
            timeout=5,
        )
    except Exception:
        # Sessiz geç; warmup başarısız olsa da akışı bozma
        pass

def main() -> None:
    print(f"ASSET_TYPE={ASSET_TYPE} | ENABLE_LLM={ENABLE_LLM} | OLLAMA_MODEL={OLLAMA_MODEL}")

    # (opsiyonel) LLM için warmup
    _warmup_ollama(OLLAMA_MODEL)

    # 1) PDF'i seç ve satırları oku
    pdf_path = pick_first_pdf("data/pdfs")
    print(f"Seçilen PDF: {pdf_path}")
    lines = read_pdf_lines(pdf_path)

    # 2) Sözlük ve kural dosyaları
    dict_path = "data/rules/headings_dict.yaml"
    rules_path = "data/rules/kurallar.yaml"

    for pth, msg in [(dict_path, "Başlık sözlüğü yok"), (rules_path, "Kural dosyası yok")]:
        if not Path(pth).exists():
            raise FileNotFoundError(f"{msg}: {Path(pth).resolve()}")

    # 3) Başlıkları tespit et
    hdict = load_headings_dict(dict_path)
    heads = detect_headings(lines, hdict, strict_threshold=0.70, suspect_low=0.50)

    print(f"\nTaşınmaz türü: {ASSET_TYPE}")
    print(f"Bulunan başlık/suspect sayısı: {len(heads)}")
    for h in heads[:30]:
        print(f"[p{h['page']}] {h['status'].upper()} "
              f"score={h['score']} canon={h['canonical'] or '-'}  →  {h['text']}")

    # 4) Kuralları çalıştır
    print("\n— KURAL MOTORU —")
    result = run_rules(lines, heads, rules_path, asset_type=ASSET_TYPE)

    print("VERDICT:", result.get("verdict"))
    print("ÖZET:", result.get("summary_counts"))
    for f in result.get("findings", [])[:20]:
        title = f.get("title", "")
        detail = f.get("detail", "")
        extra = f" — {detail}" if detail else ""
        print(f"- {f.get('rule_id')} → {f.get('status')} ({title}){extra}")

    # 5) (Opsiyonel) Ollama ile doğal dil yorumu
    commentary_text = ""
    if ENABLE_LLM:
        print("\n— YORUM (Ollama) —")
        try:
            # imza: generate_commentary(asset_type, result)
            commentary_text = generate_commentary(ASSET_TYPE, result)
            print(commentary_text or "(boş yanıt)")
        except Exception as e:
            print(f"[UYARI] Yorum üretilemedi: {type(e).__name__}: {e}")
    else:
        print("\n— YORUM (Ollama) — atlandı (ENABLE_LLM=0)")

    # 6) Çıktıları tek timestamp ile kaydet
    out_dir = "report"
    paths = save_bundle(
        result,
        rules_path=rules_path,
        out_dir=out_dir,
        base_name=REPORT_BASENAME,
        commentary_text=commentary_text or None,
        include_csv=True,
    )

    print("\nDosyalar hazır:")
    for k, v in paths.items():
        print(f"- {k.upper():<12}: {v}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[HATA] {type(e).__name__}: {e}")
        raise
