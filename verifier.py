import re
GUARANTEE = re.compile(r"guarantee|100 ?%|will (fully )?recover|assured|surely", re.I)

def verify(r: dict) -> dict:
    """Deterministic checks. Returns status + hard issues + advisory notes."""
    issues, notes = [], []
    plan = r.get("plan") or []
    if not plan: issues.append("Plan is empty.")
    for i in plan:
        if not i.get("action") or "priority" not in i: issues.append("Plan item missing required fields.")
        if not i.get("evidence_ids") and not i.get("unverified"):
            issues.append(f'"{i.get("action")}" has no evidence basis and is not marked unverified.')
        for e in i.get("evidence_ids", []):
            if e not in r.get("evidence_map", {}): issues.append(f"Invalid source reference {e}.")
        if i.get("kind") == "chemical" and not r.get("diagnosis_confirmed"):
            issues.append("Chemical recommendation without a confirmed diagnosis.")
    b = r.get("budget", {})
    if not b.get("within_budget", False): issues.append("Planned cost exceeds budget.")
    w = r.get("weather", {})
    if w.get("status") == "LIVE" and not w.get("retrieved_at"): issues.append("Live weather lacks retrieval timestamp.")
    if w.get("status") not in ("LIVE", "DEMO", "UNAVAILABLE"): issues.append("Unknown weather status.")
    text = " ".join([r.get("summary", "")] + [i.get("action", "") + i.get("reason", "") for i in plan])
    if GUARANTEE.search(text): issues.append("Text promises a guaranteed outcome.")
    if r.get("conflict_flag") and not r.get("conflicts"): issues.append("Conflicting evidence not disclosed.")
    if r.get("confidence", {}).get("level") == "low": notes.append("Low confidence: expert confirmation advised.")
    if issues: status = "VERIFICATION_FAILED"
    elif r.get("confidence", {}).get("level") == "low" or r.get("high_risk"): status = "EXPERT_REVIEW_RECOMMENDED"
    elif w.get("status") == "UNAVAILABLE": status = "DATA_UNAVAILABLE"
    else: status = "SUPPORTED_WITH_LIMITATIONS"
    return {"status": status, "issues": issues, "notes": notes}
