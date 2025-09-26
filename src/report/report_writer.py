# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json
import yaml
import pandas as pd

# ===============================
# Temel yardımcılar
# ===============================
def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _safe_stem(name: Optional[str]) -> str:
    """Dosya adı gövdesini güvenli hale getir."""
    if not name:
        return "report"
    s = Path(name).stem.replace(" ", "_")
    return s[:64] or "report"

def _ensure_dir(out_dir: str) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)

# ===============================
# YAML yükleme ve severity eşleme
# ===============================
def _load_rules(rules_path: str) -> Dict[str, Any]:
    with open(rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _severity_map(rules: Dict[str, Any]) -> Dict[str, str]:
    """
    rules.yaml içinden base-id -> severity eşlemesi üretir.
    'default_severity' yoksa 'major' varsayılır.
    """
    sev_of: Dict[str, str] = {}
    meta = (rules.get("metadata") or {})
    default = meta.get("default_severity", "major")

    def _ingest(arr: List[Dict[str, Any]]):
        for r in arr or []:
            rid = r.get("id")
            if not rid:
                continue
            sev_of[rid] = r.get("severity", default)

    _ingest(rules.get("common", []))
    by_type = rules.get("by_type") or {}
    for _, arr in by_type.items():
        _ingest(arr)
    return sev_of

def _attach_severity(findings: List[Dict[str, Any]], sev_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    rule_id alt-parçalı (RULE:Field) olabilir. Base id'yi ayıkla,
    bulguya severity ve base_rule_id alanlarını enjekte et.
    """
    out = []
    for f in findings or []:
        rid = f.get("rule_id", "")
        base = rid.split(":")[0] if ":" in rid else rid
        g = dict(f)
        g["base_rule_id"] = base
        g["severity"] = g.get("severity") or sev_map.get(base, "major")
        g.setdefault("title", "")
        g.setdefault("status", "")
        g.setdefault("detail", "")
        out.append(g)
    return out

# ===============================
# Tekil kaydetme fonksiyonları
# ===============================
def save_json(result: Dict[str, Any], out_dir: str,
              base_name: Optional[str] = None, ts: Optional[str] = None) -> str:
    _ensure_dir(out_dir)
    ts = ts or _timestamp()
    stem = _safe_stem(base_name)
    path = Path(out_dir) / f"{stem}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return str(path)

def save_csv(result: Dict[str, Any], rules_path: str, out_dir: str,
             base_name: Optional[str] = None, ts: Optional[str] = None) -> str:
    _ensure_dir(out_dir)
    ts = ts or _timestamp()
    stem = _safe_stem(base_name)
    path = Path(out_dir) / f"{stem}_{ts}.csv"

    rules = _load_rules(rules_path)
    sev_map = _severity_map(rules)
    findings = _attach_severity(result.get("findings", []), sev_map)

    df = pd.DataFrame(findings)
    if df.empty:
        df = pd.DataFrame(columns=["rule_id", "base_rule_id", "title", "status", "severity", "detail"])
    else:
        df = df[["rule_id", "base_rule_id", "title", "status", "severity", "detail"]]

    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)

def save_summary_markdown(result: Dict[str, Any], rules_path: str, out_dir: str,
                          base_name: Optional[str] = None, ts: Optional[str] = None) -> str:
    """
    Kuralların özetini (bulgular listesi dahil) Markdown olarak kaydeder.
    """
    _ensure_dir(out_dir)
    ts = ts or _timestamp()
    stem = _safe_stem(base_name)
    path = Path(out_dir) / f"{stem}_{ts}.md"

    rules = _load_rules(rules_path)
    sev_map = _severity_map(rules)
    findings = _attach_severity(result.get("findings", []), sev_map)

    sc = result.get("summary_counts", {}) or {}
    lines = []
    lines.append(f"# Rapor Özeti ({stem})\n")
    lines.append(f"- **Verdict:** {result.get('verdict')}")
    lines.append(
        f"- **present:** {sc.get('present', 0)}  |  **missing:** {sc.get('missing', 0)}  "
        f"|  **wrong:** {sc.get('wrong', 0)}  |  **optional_absent:** {sc.get('optional_absent', 0)}\n"
    )
    lines.append("## Bulgular")
    if not findings:
        lines.append("_Bulgu yok._")
    else:
        for f in findings:
            lines.append(
                f"- `{f['rule_id']}` **{f['status']}** [{f['severity']}] — {f['title']}"
                + (f" — _{f['detail']}_" if f.get("detail") else "")
            )

    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)

def save_commentary_markdown(commentary_text: str, out_dir: str,
                             base_name: Optional[str] = None, ts: Optional[str] = None) -> str:
    """
    Ollama vb. modelden gelen doğal dil yorumunu ayrı bir .md dosyasına kaydeder.
    """
    _ensure_dir(out_dir)
    ts = ts or _timestamp()
    stem = _safe_stem(base_name)
    path = Path(out_dir) / f"{stem}_{ts}_commentary.md"
    Path(path).write_text(commentary_text.strip() + "\n", encoding="utf-8")
    return str(path)

def save_excel(result: Dict[str, Any], rules_path: str, out_dir: str,
               base_name: Optional[str] = None, ts: Optional[str] = None,
               commentary_text: Optional[str] = None) -> str:
    """
    Excel: Overview + Findings + StatusCounts (+ Commentary, varsa)
    """
    _ensure_dir(out_dir)
    ts = ts or _timestamp()
    stem = _safe_stem(base_name)
    path = Path(out_dir) / f"{stem}_{ts}.xlsx"

    rules = _load_rules(rules_path)
    sev_map = _severity_map(rules)
    findings = _attach_severity(result.get("findings", []), sev_map)

    # Overview sheet
    sc = result.get("summary_counts", {}) or {}
    overview = pd.DataFrame([
        {"Key": "Verdict", "Value": result.get("verdict")},
        {"Key": "present", "Value": sc.get("present", 0)},
        {"Key": "missing", "Value": sc.get("missing", 0)},
        {"Key": "wrong", "Value": sc.get("wrong", 0)},
        {"Key": "optional_absent", "Value": sc.get("optional_absent", 0)},
    ])

    # Findings sheet
    df = pd.DataFrame(findings)
    if df.empty:
        df = pd.DataFrame(columns=["rule_id", "base_rule_id", "title", "status", "severity", "detail"])
    else:
        df = df[["rule_id", "base_rule_id", "title", "status", "severity", "detail"]]

    # StatusCounts sheet
    status_counts = (
        df.groupby(["status", "severity"], dropna=False).size().reset_index(name="count")
        if not df.empty else pd.DataFrame(columns=["status", "severity", "count"])
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        overview.to_excel(writer, index=False, sheet_name="Overview")
        df.to_excel(writer, index=False, sheet_name="Findings")
        status_counts.to_excel(writer, index=False, sheet_name="StatusCounts")

        if commentary_text:
            cdf = pd.DataFrame({"Commentary": commentary_text.splitlines()})
            cdf.to_excel(writer, index=False, sheet_name="Commentary")

    return str(path)

# ===============================
# Hepsini aynı timestamp ile kaydet (önerilen)
# ===============================
def save_bundle(
    result: Dict[str, Any],
    rules_path: str,
    out_dir: str,
    base_name: Optional[str] = None,
    commentary_text: Optional[str] = None,
    include_csv: bool = False,
) -> Dict[str, str]:
    """
    JSON / Excel / Summary MD (+ Commentary MD) çıktılarını **aynı timestamp** ile üretir.
    Geriye üretilen dosya yollarını döner.
    """
    ts = _timestamp()
    paths: Dict[str, str] = {}

    paths["json"] = save_json(result, out_dir=out_dir, base_name=base_name, ts=ts)
    paths["excel"] = save_excel(result, rules_path, out_dir=out_dir,
                                base_name=base_name, ts=ts, commentary_text=commentary_text)
    paths["summary_md"] = save_summary_markdown(result, rules_path, out_dir=out_dir,
                                                base_name=base_name, ts=ts)

    if commentary_text:
        paths["commentary_md"] = save_commentary_markdown(commentary_text, out_dir=out_dir,
                                                          base_name=base_name, ts=ts)

    if include_csv:
        paths["csv"] = save_csv(result, rules_path, out_dir=out_dir, base_name=base_name, ts=ts)

    return paths
