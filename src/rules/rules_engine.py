# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, List, Any, Tuple
from pathlib import Path
import re
import yaml

# ---------- Yardımcılar ----------
def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _find_all(patt: str, text: str) -> List[re.Match]:
    try:
        return list(re.finditer(patt, text, flags=re.IGNORECASE | re.MULTILINE))
    except re.error:
        return []

def _has_any_literal(words: List[str], text: str) -> bool:
    """Kelime sınırıyla literal eşleşme."""
    return any(re.search(rf"\b{re.escape(w)}\b", text, flags=re.I) for w in words if w)

def _match_token(spec: str, text: str) -> bool:
    """
    Esnek alan adı eşleşmesi:
      - 're:...' → regex olarak ara
      - 'a|b|c'  → bu alternatiflerden herhangi biri (literal)
      - diğer    → literal kelime
    """
    if not spec:
        return False
    spec = spec.strip()
    if spec.startswith("re:"):
        patt = spec[3:].strip()
        if not patt:
            return False
        try:
            return re.search(patt, text, flags=re.I | re.M) is not None
        except re.error:
            return False
    if "|" in spec:
        alts = [s.strip() for s in spec.split("|") if s.strip()]
        return _has_any_literal(alts, text)
    return _has_any_literal([spec], text)

def _extract_date_hits(text: str) -> List[str]:
    # YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY vb.
    patt = r"(\d{4}-\d{2}-\d{2})|(\d{2}[./-]\d{2}[./-]\d{4})"
    return [m.group(0) for m in _find_all(patt, text)]

# ---------- Bölümleme (başlık → metin) ----------
def group_text_by_canonical(lines: List[Dict[str, Any]],
                            headings: List[Dict[str, Any]]) -> Dict[str, str]:
    # sayfa bazlı index listesi
    idx_by_page: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
    for i, row in enumerate(lines):
        idx_by_page.setdefault(row["page"], []).append((i, row))

    # başlıkların satır index’ini bul
    heads_idx: List[Tuple[int, str, str]] = []  # (index, canon, text)
    for h in headings:
        canon = (h.get("canonical") or "").strip()
        if not canon:
            continue
        page = h["page"]
        htext = (h.get("text") or "").strip()
        for idx, row in idx_by_page.get(page, []):
            if (row.get("text") or "").strip() == htext:
                heads_idx.append((idx, canon, htext))
                break

    heads_idx.sort(key=lambda x: x[0])

    sections: Dict[str, List[str]] = {}
    for k in range(len(heads_idx)):
        start_idx, canon, _ = heads_idx[k]
        end_idx = heads_idx[k + 1][0] if k + 1 < len(heads_idx) else len(lines)
        body = []
        for j in range(start_idx + 1, end_idx):
            t = (lines[j].get("text") or "").strip()
            if t:
                body.append(t)
        if body:
            sections.setdefault(canon, []).append("\n".join(body))
    return {k: "\n\n".join(v) for k, v in sections.items()}

# ---------- Rule-type değerlendiriciler ----------
def eval_required_fields(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    out = []
    for fld in rule.get("fields", []):
        ok = _match_token(fld, text)
        out.append({
            "rule_id": rule["id"] + f":{fld}",
            "status": "present" if ok else "missing",
            "title": f"{rule['title']} → {fld}",
        })
    return out

def eval_nonempty_text(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    ok = bool(text.strip())
    return [{"rule_id": rule["id"], "status": "present" if ok else "missing", "title": rule["title"]}]

def eval_coexist(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    fields = rule.get("fields", [])
    ok = all(_match_token(f, text) for f in fields)
    return [{"rule_id": rule["id"], "status": "present" if ok else "missing", "title": rule["title"]}]

def eval_table_columns(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    cols = rule.get("columns_required", []) or rule.get("constraints", {}).get("columns_required", [])
    out = []
    for c in cols:
        ok = _match_token(c, text)
        out.append({
            "rule_id": rule["id"] + f":{c}",
            "status": "present" if ok else "missing",
            "title": f"{rule['title']} → kolon {c}",
        })
    return out

def eval_list_min_count(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    # emsal için satır ipucu
    hint = rule.get("row_hint_regex", r"(Emsal|Karşılaştırılabilir)")
    hits = _find_all(hint, text)
    cnt = len(hits)
    need = int(rule.get("min", rule.get("min_count", 0)))
    st = "present" if cnt >= need else "wrong"
    return [{"rule_id": rule["id"], "status": st, "title": rule["title"], "detail": f"adet={cnt}, min={need}"}]

def eval_enum(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    allowed = rule.get("allowed", [])
    ok = any(_match_token(a, text) for a in allowed)
    return [{"rule_id": rule["id"], "status": "present" if ok else "missing", "title": rule["title"]}]

def eval_flags(rule: Dict[str, Any], text: str, optional=False) -> List[Dict[str, Any]]:
    flags = rule.get("flags", [])
    out = []
    for fl in flags:
        ok = _match_token(fl, text)
        status = "present" if ok else ("optional_absent" if optional else "missing")
        out.append({"rule_id": rule["id"] + f":{fl}", "status": status, "title": f"{rule['title']} → {fl}"})
    return out

def eval_date_triplet(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    hits = _extract_date_hits(text)
    # talep/keşif/rapor kelimelerine yakın tarih var mı?
    need_labels = ["talep", "keşif", "kesif", "rapor"]
    found = {lab: False for lab in ["talep", "kesif", "rapor"]}
    for lab in need_labels:
        if _find_all(rf"\b{lab}\b", text):
            if hits:
                # kaba yakınlık: aynı paragrafta tarih geçiyorsa say
                found["kesif" if lab in ("keşif", "kesif") else lab] = True
    ok = all(found.values())
    return [{
        "rule_id": rule["id"],
        "status": "present" if ok else "missing",
        "title": rule["title"],
        "detail": f"bulunan: {found}, tarih_sayısı: {len(hits)}",
    }]

def eval_attachments(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    req = (rule.get("attachments") or {}).get("required", [])
    opt = (rule.get("attachments") or {}).get("optional", [])
    out = []
    for a in req:
        ok = _match_token(a, text)
        out.append({"rule_id": rule["id"] + f":{a}", "status": "present" if ok else "missing", "title": f"Ek zorunlu: {a}"})
    for a in opt:
        ok = _match_token(a, text)
        out.append({"rule_id": rule["id"] + f":{a}",
                    "status": "present" if ok else "optional_absent",
                    "title": f"Ek opsiyonel: {a}"})
    return out

def eval_quality_rules(rule: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    out = []
    for r in rule.get("rules", []):
        kind = r.get("kind")
        if kind == "forbid_terms":
            terms = r.get("terms", [])
            bad = [t for t in terms if _match_token(t, text)]
            out.append({"rule_id": rule["id"] + ":forbid_terms",
                        "status": "wrong" if bad else "present",
                        "title": "Yasaklı ifade", "detail": ", ".join(bad)})
        elif kind == "date_format":
            ok = bool(_extract_date_hits(text))  # şimdilik varlık kontrolü
            out.append({"rule_id": rule["id"] + ":date", "status": "present" if ok else "missing",
                        "title": "Tarih formatı (kaba)"})
        else:
            out.append({"rule_id": rule["id"] + f":{kind}", "status": "present",
                        "title": f"TODO desteklenecek: {kind}"})
    return out

# Basit “alan → muhtemel bölüm” eşlemesi (kapsayıcı arama için)
FIELD_SECTION_HINT = {
    "Tarihler": ["kimlik", "yontem"],
    "Kimlik": ["kimlik"],
    "Konum": ["konum", "kimlik"],
    "TapuKaydi": ["tapu"],
    "MalikHisse": ["kimlik", "tapu"],
    "AdaParsel": ["kimlik", "tapu"],
    "ImarDurumu": ["imar"],
    "ImarLejant": ["imar"],
    "RuhsatProje": ["ruhsat"],
    "YasalMevcutKarsilastirma": ["nihai", "kanaat", "yontem"],
    "YontemGerekcesi": ["yontem", "kanaat"],
    "Emsaller": ["emsal", "yontem"],
    "EmsalTablo": ["emsal"],
    "GelirYontemi": ["yontem"],
    "MaliyetYontemi": ["yontem"],
    "SigortaDegeriHesap": ["sigorta", "nihai"],
    "NihaiDeger": ["nihai"],
    "SatisElverislilik": ["kanaat"],
    "DepremKentsel": ["risk"],
    "OzelKisitlar": ["risk"],
    "YikimKarari": ["risk"],
    "Ekler": ["ekler"],
    "Kalite": ["kimlik", "tapu", "yontem", "imar", "nihai"],
    # tür-özel bazı alanlar
    "ImarCap": ["imar"],
    "ParselOzellikleri": ["kimlik", "imar"],
    "KadastroPaftasi": ["tapu", "konum"],
    "SulamaDurumu": ["tarla_ozel", "kimlik"],
    "ToprakSinifi": ["tarla_ozel"],
    "ParselButunlugu": ["kimlik"],
    "YapiRuhsati": ["ruhsat"],
    "Iskan": ["ruhsat"],
    "OnayliProje": ["ruhsat"],
    "Alanlar": ["kimlik", "ruhsat"],
    "BinaBelgeleri": ["ruhsat"],
    "InsaatYiliSinifi": ["kimlik", "ruhsat"],
}

def _concat_sections(text_by_section: Dict[str, str], field_name: str) -> str:
    desired = FIELD_SECTION_HINT.get(field_name, [])
    if not desired:
        return "\n\n".join(text_by_section.values())
    return "\n\n".join([text_by_section.get(w, "") for w in desired if w in text_by_section])

# ---------- Rule yürütücü ----------
def run_rules(lines: List[Dict[str, Any]],
              headings: List[Dict[str, Any]],
              rules_path: str,
              asset_type: str = "arsa") -> Dict[str, Any]:
    rules = load_yaml(rules_path)

    # PDF metnini bölümlere ayır
    text_by_section = group_text_by_canonical(lines, headings)

    # çalışacak kural setini topla
    queue: List[Dict[str, Any]] = []
    queue.extend(rules.get("common", []))
    by_type = (rules.get("by_type") or {}).get(asset_type, [])
    queue.extend(by_type)

    findings: List[Dict[str, Any]] = []

    for r in queue:
        r = dict(r)  # kopya
        r.setdefault("id", r.get("title", "RULE").upper().replace(" ", "_"))
        rtype = r.get("type")
        field = r.get("field")
        text = _concat_sections(text_by_section, field) if field else "\n\n".join(text_by_section.values())

        if rtype == "required_fields":
            findings.extend(eval_required_fields(r, text))
        elif rtype == "nonempty_text":
            findings.extend(eval_nonempty_text(r, text))
        elif rtype == "coexist":
            findings.extend(eval_coexist(r, text))
        elif rtype in ("table_columns", "takidat_table"):
            findings.extend(eval_table_columns(r, text))
        elif rtype in ("list_min_count",):
            findings.extend(eval_list_min_count(r, text))
        elif rtype == "enum":
            findings.extend(eval_enum(r, text))
        elif rtype == "flags":
            findings.extend(eval_flags(r, text, optional=False))
        elif rtype == "flags_optional":
            findings.extend(eval_flags(r, text, optional=True))
        elif rtype == "date_triplet":
            findings.extend(eval_date_triplet(r, text))
        elif rtype == "attachments_check":
            findings.extend(eval_attachments(r, text))
        elif rtype == "quality_rules":
            findings.extend(eval_quality_rules(r, text))
        # Basit/kısmi destek (TODO ayrıntılandırılabilir)
        elif rtype in ("separate_calc", "doc_triplet_match", "compare_required",
                       "area_pair", "boolean_required", "composite_presence"):
            findings.append({
                "rule_id": r["id"],
                "status": "present" if text.strip() else "missing",
                "title": r["title"],
                "detail": f"TYPE={rtype} (kısmi kontrol)",
            })
        else:
            findings.append({
                "rule_id": r["id"],
                "status": "present",
                "title": f"{r['title']} (desteklenmeyen type: {rtype})",
            })

    # özet
    summary = {"present": 0, "missing": 0, "wrong": 0, "optional_absent": 0}
    for f in findings:
        st = f["status"]
        if st in summary:
            summary[st] += 1

    verdict = "OK"
    if summary["missing"] > 0 or summary["wrong"] > 0:
        verdict = "EKSİK"

    return {"verdict": verdict, "summary_counts": summary, "findings": findings}
