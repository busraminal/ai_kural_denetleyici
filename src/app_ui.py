# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os
from pathlib import Path
import hashlib
import shutil
import gradio as gr

# Proje modülleri
from extract.pdf_reader import read_pdf_lines
from extract.heading_extractor import load_headings_dict, detect_headings
from rules.rules_engine import run_rules
from report.commentary_llm import generate_commentary
from report.pdf_highlight import build_annotated_pdf  # yalnız sorunlu metinleri boyar

# -------------------------------------------------------------------
# Yol/ayarlar
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
RULES_DIR = DATA_DIR / "rules"
DICT_PATH = RULES_DIR / "headings_dict.yaml"
RULES_PATH = RULES_DIR / "kurallar.yaml"
REPORT_DIR = BASE_DIR / "report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

ASSET_TYPES = ["arsa", "tarla", "konut", "bina", "ticari_tesis", "sera", "turistik_tesis", "akaryakit"]

PROFILE_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "Ziraat – Tarla standardı": {"strict": 0.70, "suspect": 0.50},
    "Konut standardı":          {"strict": 0.72, "suspect": 0.52},
    "Ofis/İşyeri standardı":    {"strict": 0.68, "suspect": 0.48},
}

MODEL_HINTS: Dict[str, str] = {
    "qwen2.5:7b-instruct":        "Hızlı • 4–6GB VRAM • TR iyi",
    "qwen2.5:7b-instruct-q4_K_M": "Küçük bellek • Biraz daha yavaş",
    "mistral:7b-instruct":        "Dengeli • 6–8GB VRAM",
    "mistral:7b-instruct-q4_K_M": "Küçük bellek • Dengeli",
    "llama3:8b-instruct":         "Net cevap • 8–10GB VRAM",
    "llama3:8b-instruct-q4_K_M":  "Küçük bellek • Net cevap",
}

# --- ÖNEMLİ: Önbellek sürümü (değiştirince eski dosyalar kullanılmaz)
CACHE_VERSION = "hl_v2"
USE_CACHE_DEFAULT = False  # varsayılan: önbellek kullanma

def _ollama_models() -> List[str]:
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        r.raise_for_status()
        data = r.json() or {}
        names: List[str] = []
        for m in (data.get("models") or []):
            n = m.get("name") or m.get("model")
            if n:
                names.append(n)
        if not names:
            raise RuntimeError("model listesi boş")
    except Exception:
        names = ["qwen2.5:7b-instruct", "mistral:7b-instruct"]

    labeled = []
    for n in names:
        note = MODEL_HINTS.get(n, "")
        labeled.append(f"{n} · {note}" if note else n)
    return labeled

def _strip_model(label: str) -> str:
    return (label or "").split("·", 1)[0].strip()

def _sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def _cache_paths(pdf_hash: str, asset_type: str, model: Optional[str]) -> Tuple[Path, Path]:
    tag = model or "no-llm"
    cmt = REPORT_DIR / f"{CACHE_VERSION}_comment_{pdf_hash}_{asset_type}_{tag}.txt"
    pdf = REPORT_DIR / f"{CACHE_VERSION}_annotated_{pdf_hash}_{asset_type}_{tag}.pdf"
    return cmt, pdf

# -------------------------------------------------------------------
# Ana boru hattı
# -------------------------------------------------------------------
def pipeline(
    pdf_file,                  # gr.File
    asset_type: str,           # Dropdown
    profile_name: str,         # Profil/preset
    enable_llm: bool,          # Checkbox
    model_choice_label: str,   # Dropdown (kurulu modeller)
    model_override: str,       # Textbox (elle model adı)
    use_cache: bool,           # Önbellek kullanılsın mı?
    progress: gr.Progress = gr.Progress(track_tqdm=True),
) -> Tuple[str, str | None]:

    if not pdf_file:
        return "Lütfen PDF yükleyin.", None
    if not asset_type:
        return "Lütfen taşınmaz türünü seçin.", None

    in_path = Path(pdf_file.name)
    if in_path.suffix.lower() != ".pdf":
        return "Yüklenen dosya PDF değil. Lütfen .pdf yükleyin.", None

    progress(0.02, desc="Dosya hazırlanıyor…")
    target = PDF_DIR / in_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(in_path, target)
    pdf_hash = _sha1_file(target)

    model_to_use = ""
    if enable_llm:
        if model_override and model_override.strip():
            model_to_use = model_override.strip()
        elif model_choice_label and model_choice_label.strip():
            model_to_use = _strip_model(model_choice_label)
        else:
            model_to_use = "qwen2.5:7b-instruct"

    cmt_path, ann_pdf_path = _cache_paths(pdf_hash, asset_type, model_to_use if enable_llm else None)
    if use_cache and cmt_path.exists() and ann_pdf_path.exists():
        progress(0.10, desc="Önbellekten getiriliyor…")
        return cmt_path.read_text(encoding="utf-8"), str(ann_pdf_path)

    progress(0.20, desc="PDF okunuyor…")
    lines = read_pdf_lines(target)

    progress(0.40, desc="Başlıklar tespit ediliyor…")
    hdict = load_headings_dict(str(DICT_PATH))
    t_cfg = PROFILE_THRESHOLDS.get(profile_name, {"strict": 0.70, "suspect": 0.50})
    heads = detect_headings(
        lines,
        hdict,
        strict_threshold=float(t_cfg["strict"]),
        suspect_low=float(t_cfg["suspect"]),
    )

    progress(0.60, desc="Kurallar çalıştırılıyor…")
    result = run_rules(lines, heads, str(RULES_PATH), asset_type=asset_type)

    commentary = ""
    if enable_llm:
        progress(0.75, desc="Yorum (cevap modeli) üretiliyor…")
        prev_model = os.getenv("OLLAMA_MODEL", "")
        prev_llm = os.getenv("ENABLE_LLM", "0")
        try:
            os.environ["OLLAMA_MODEL"] = model_to_use
            os.environ["ENABLE_LLM"] = "1"
            commentary = generate_commentary(asset_type, result) or ""
        finally:
            os.environ["OLLAMA_MODEL"] = prev_model
            os.environ["ENABLE_LLM"] = prev_llm
    else:
        commentary = "LLM yorumu devre dışı."

    progress(0.88, desc="PDF üzeri vurgular ekleniyor…")
    ann_pdf_path_str = build_annotated_pdf(
        original_pdf=str(target),
        lines=lines,
        findings=result.get("findings", []) or [],
        output_pdf=str(ann_pdf_path),
    )

    try:
        cmt_path.write_text(commentary or "", encoding="utf-8")
    except Exception:
        pass

    progress(1.0, desc="Hazır.")
    return (commentary or "Yorum üretilmedi."), ann_pdf_path_str

# -------------------------------------------------------------------
# UI
# -------------------------------------------------------------------
AVAILABLE_MODELS = _ollama_models()
DEFAULT_MODEL_LABEL = next(iter(AVAILABLE_MODELS), "qwen2.5:7b-instruct")

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## Ziraat Rapor Denetleyici — Yerel Arayüz")

    with gr.Row():
        with gr.Column(scale=1):
            pdf = gr.File(label="PDF yükle", file_types=[".pdf"])
            asset = gr.Dropdown(ASSET_TYPES, value="tarla", label="Taşınmaz türü")
            profile = gr.Dropdown(
                list(PROFILE_THRESHOLDS.keys()),
                value="Ziraat – Tarla standardı",
                label="Profil (eşik/kurallar)"
            )
            enable_llm = gr.Checkbox(label="Cevap (LLM) yorumu üret", value=True)
            model_choice = gr.Dropdown(
                choices=AVAILABLE_MODELS,
                value=DEFAULT_MODEL_LABEL,
                label="Cevap modeli (kurulu modeller)",
            )
            model_override = gr.Textbox(
                label="Model adı (elle - opsiyonel)",
                placeholder="örn. qwen2.5:7b-instruct-q4_K_M"
            )
            use_cache = gr.Checkbox(label="Önbelleği kullan (ileri düzey)", value=USE_CACHE_DEFAULT)
            run_btn = gr.Button("ÇALIŞTIR", variant="primary")

        with gr.Column(scale=2):
            summary = gr.Textbox(
                label="Yorum",
                lines=14,
                interactive=False,
                show_copy_button=True,
                placeholder="İşlem sonuçları burada görünecek."
            )
            pdf_out = gr.File(label="PDF indir (vurgulu)", file_types=[".pdf"])

    run_btn.click(
        pipeline,
        inputs=[pdf, asset, profile, enable_llm, model_choice, model_override, use_cache],
        outputs=[summary, pdf_out]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", inbrowser=True)

