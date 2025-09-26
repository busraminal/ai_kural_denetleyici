# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Optional

def _summarize_issues(result: Dict[str, Any]) -> str:
    """missing/wrong bulguları kısa listeye çevirir."""
    bad = []
    for f in result.get("findings", []):
        if f.get("status") in ("missing", "wrong"):
            rid = f.get("rule_id", "")
            ttl = f.get("title", "")
            det = f.get("detail", "")
            line = f"- {rid} → {f['status']} | {ttl}"
            if det:
                line += f" | {det}"
            bad.append(line)
    return "\n".join(bad) or "Eksik/hatalı yok."

def build_prompt(result: Dict[str, Any], asset_type: str) -> str:
    issues = _summarize_issues(result)
    verdict = result.get("verdict", "-")
    sums = result.get("summary_counts", {})
    return f"""
Sen tecrübeli bir gayrimenkul değerleme uzmanı gibi davranan bir yapay zekâsın.
Taşınmaz türü: {asset_type}
Karar (verdict): {verdict} | Özet: {sums}

Aşağıda, kuralların yakaladığı eksik/hatalı noktalar var.
Her bir madde için:
- olası etkisini (regülasyon/uyum, rapor kalitesi, değerleme güvenilirliği),
- kısa çözüm/aksiyon önerisini,
- varsa hangi bölümde/tabloda giderileceğini
resmî ve anlaşılır bir Türkçe ile yaz.

Bulgular:
{issues}

Çıktı formatı:
1) Genel değerlendirme (kısa paragraf)
2) Kritik maddeler listesi (madde madde)
3) Hızlı aksiyonlar (madde madde)
4) Notlar/varsayımlar (varsa)
""".strip()

def generate_commentary(result: Dict[str, Any], asset_type: str = "arsa",
                        model: str = "llama3") -> str:
    """
    Ollama ile doğal-dil yorumu üretir. Ollama hazır değilse
    anlaşılır bir fallback mesajı döner.
    """
    prompt = build_prompt(result, asset_type)
    try:
        # import’u try içinde tutuyoruz ki ollama kurulu değilse patlamasın
        from ollama import chat
        resp = chat(model=model, messages=[{"role": "user", "content": prompt}])
        content = (resp.get("message") or {}).get("content", "").strip()
        return content or "Ollama yanıtı boş döndü."
    except Exception as e:
        return (
            "⚠️ Ollama yorumu üretilemedi. Sebep: "
            f"{type(e).__name__}: {e}\n\n"
            "Yine de kuralların bulgularını üstteki raporlardan görebilirsiniz."
        )
