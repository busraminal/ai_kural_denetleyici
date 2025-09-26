# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List
import os, json, socket, requests

HTTP_URL  = "http://127.0.0.1:11434/api/generate"
HTTP_TAGS = "http://127.0.0.1:11434/api/tags"
HTTP_TIMEOUT = 25  # agresif timeout
SESSION = requests.Session()  # bağlantı tekrar kullanılsın

# HIZ ODAKLI OLLAMA SEÇENEKLERİ
OL_OPTIONS = {
    "temperature": 0.2,
    "num_ctx": 1024,     # kısa bağlam
    "num_predict": 120,  # çıktı üst limiti
    "top_p": 0.9,
    "repeat_penalty": 1.05,
    # "num_gpu": -1,     # GPU varsa otomatik; istersen sabitle
    # "num_thread": 0,   # 0=otomatik; CPU’da çekirdek sayısına göre
}

def _ollama_python_available() -> bool:
    try:
        import ollama  # type: ignore
        return True
    except Exception:
        return False

def _ollama_http_alive(host="127.0.0.1", port=11434, timeout=0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _http_tags_ok() -> bool:
    try:
        r = SESSION.get(HTTP_TAGS, timeout=2.5)
        return r.ok
    except Exception:
        return False

def _model_list() -> List[str]:
    try:
        r = SESSION.get(HTTP_TAGS, timeout=2.5)
        r.raise_for_status()
        data = r.json() or {}
        return [m.get("name") or m.get("model") for m in (data.get("models") or []) if m]
    except Exception:
        return []

def _pick_model() -> str:
    m = os.getenv("OLLAMA_MODEL", "").strip()
    return m or "qwen2.5:7b-instruct-q4_K_M"

def _llm_enabled() -> bool:
    return os.getenv("ENABLE_LLM", "0").strip().lower() in ("1", "true")

def _build_prompt(asset_type: str, verdict: str, summary: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
    # en hızlı: sadece eksik+wrong ilk 6 öğe
    focused = [f for f in findings if f.get("status") in ("missing", "wrong")][:6]
    lines = [
        f"Alan: Ziraat değerleme | Tür: {asset_type}",
        f"Durum: {verdict} | Özet: {summary}",
        "Öne çıkan maddeler:",
    ]
    for f in focused:
        rid = f.get("rule_id",""); title = f.get("title","")
        lines.append(f"- {rid}: {title}")
    lines.append(
        "\nGörev: 4–5 madde yaz. Her madde 1 satır, direkt aksiyon; toplam 80–120 kelime. "
        "Tekrar yok, resmi üslup, Türkçe."
    )
    return "\n".join(lines)

def _call_ollama_python(prompt: str, model: str) -> str:
    import ollama  # type: ignore
    resp = ollama.generate(model=model, prompt=prompt, stream=False, options=OL_OPTIONS)
    return (resp.get("response") or "").strip()

def _call_ollama_http(prompt: str, model: str) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False, "options": OL_OPTIONS}
    r = SESSION.post(HTTP_URL, json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json() or {}
    return (data.get("response") or "").strip()

def generate_commentary(asset_type: str, result: Dict[str, Any]) -> str:
    if not _llm_enabled():
        print("— YORUM (Ollama) — devre dışı")
        return ""

    model = _pick_model()
    prompt = _build_prompt(
        asset_type,
        result.get("verdict",""),
        result.get("summary_counts",{}) or {},
        result.get("findings",[]) or [],
    )

    # model yüklü değilse uyar ama yine dene
    avail = _model_list()
    if avail and model not in avail:
        print(f"[YORUM] Model bulunamadı: {model}. Yüklü: {avail}")

    if _ollama_python_available():
        try:
            return _call_ollama_python(prompt, model)
        except Exception as e:
            print(f"[YORUM] SDK hata: {type(e).__name__}: {e}")

    if _ollama_http_alive() or _http_tags_ok():
        try:
            return _call_ollama_http(prompt, model)
        except Exception as e:
            print(f"[YORUM] HTTP hata: {type(e).__name__}: {e}")

    print("— YORUM üretilemedi.")
    return ""
