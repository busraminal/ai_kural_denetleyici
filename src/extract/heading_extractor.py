# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
import re
import numpy as np
import yaml

NUM_PATTERN = re.compile(r"^\s*\d+(\.\d+)*\s+")
WS = re.compile(r"\s+")

def _is_bold(font_name: Optional[str], flags: Optional[int]) -> bool:
    fn = (font_name or "").lower()
    if "bold" in fn:
        return True
    # flags sahada değişken; 0 dışı bir değer genelde vurgulu span demek
    return bool(flags and flags > 0)

def _keyword_match_score(text_lc: str, headings_dict: Dict[str, List[str]]) -> Tuple[str, float]:
    best_key = ""
    best = 0.0
    for key, variants in headings_dict.items():
        hit = 0
        for v in variants:
            v = v.lower()
            if v in text_lc:
                hit += 1
        if hit > 0:
            # kısa varyantlar için aşırı şişmeyi engelle
            score = min(1.0, 0.35 + 0.15 * hit)
            if score > best:
                best = score
                best_key = key
    return best_key, best

def load_headings_dict(yaml_path: str) -> Dict[str, List[str]]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # güvenlik: list olmayanları listeye çevir
    out: Dict[str, List[str]] = {}
    for k, v in data.items():
        if isinstance(v, list):
            out[k] = v
        elif isinstance(v, str):
            out[k] = [v]
    return out

def detect_headings(lines: List[Dict[str, Any]],
                    headings_dict: Dict[str, List[str]],
                    strict_threshold: float = 0.60,
                    suspect_low: float = 0.40) -> List[Dict[str, Any]]:
    """Satır listesinde muhtemel başlıkları skorlar ve döndürür."""
    if not lines:
        return []

    sizes = np.array([float(x.get("size", 0.0) or 0.0) for x in lines], dtype=float)
    med = float(np.median(sizes))
    p90 = float(np.percentile(sizes, 90))
    denom = max(1e-3, (p90 - med))

    results: List[Dict[str, Any]] = []
    for row in lines:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        # aşırı uzun paragrafları başlık dışı say
        if len(text) > 140:
            continue

        text_lc = text.lower()
        size = float(row.get("size", 0.0) or 0.0)
        size_norm = max(0.0, min(1.0, (size - med) / denom))
        bold = 1.0 if _is_bold(row.get("font"), row.get("flags")) else 0.0
        is_numbered = 1.0 if NUM_PATTERN.search(text) else 0.0
        canon_key, kw_score = _keyword_match_score(text_lc, headings_dict)

        # skor karışımı (heuristic)
        score = (
            0.35 * size_norm +
            0.25 * bold +
            0.25 * is_numbered +
            0.25 * kw_score
        )

        status = "other"
        if score >= strict_threshold:
            status = "heading"
        elif score >= suspect_low:
            status = "suspect"

        results.append({
            "page": row.get("page"),
            "text": text,
            "font": row.get("font"),
            "size": size,
            "score": round(float(score), 3),
            "status": status,
            "canonical": canon_key or None,
        })

    # yalnızca başlık/suspect olanları, yüksek skor önce
    results = [r for r in results if r["status"] in ("heading", "suspect")]
    results.sort(key=lambda r: (r["page"], -r["score"]))
    return results
