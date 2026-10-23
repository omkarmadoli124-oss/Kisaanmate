"""Bounded agent: max 3 follow-up questions, max 2 plan attempts, no tool use beyond fixed services."""
import logging
from . import services as S
from .verifier import verify, GUARANTEE

log = logging.getLogger("kisanmate")
MAX_ATTEMPTS = 2

def _questions(req):
    a, qs = req.answers, []
    if not req.profile.growth_stage and "growth_stage" not in a:
        qs.append({"key": "growth_stage", "text": "What is the crop growth stage?", "options": ["seedling", "vegetative", "flowering", "pod filling", "maturity"]})
    if "waterlogging" not in a:
        qs.append({"key": "waterlogging", "text": "Has water stood in the field recently?", "options": ["yes", "no", "unsure"]})
    if not req.problem.spread and "spread" not in a:
        qs.append({"key": "spread", "text": "Does the problem affect one plant, a few, or many?", "options": ["one", "few", "many"]})
    return qs[:3]

def _hypotheses(req, heavy_rain):
    a, txt = req.answers, (req.problem.symptoms + " " + " ".join(req.problem.selected)).lower()
    spread = a.get("spread") or req.problem.spread.lower()
    H = []
    def add(name, sup, miss):
        H.append({"name": name, "supporting": sup, "missing": miss, "status": "possible, not confirmed"})
    sup = []
    if a.get("waterlogging") == "yes": sup.append("You reported standing water.")
    if heavy_rain: sup.append("Heavy rain is in the forecast.")
    add("Waterlogging or poor drainage stress", sup, ["Check soil wetness and root colour"])
    sup = ["Yellowing mentioned."] if "yellow" in txt else []
    if "many" in spread: sup.append("Many plants affected, which can fit a nutrient or water problem.")
    add("Nutrient shortage (soil-test needed)", sup, ["Soil test result", "Which leaves yellow first"])
    sup = []
    if "few" in spread or "one" in spread: sup.append("Patchy spread can fit a pest or disease.")
    if any(k in txt for k in ("spot", "hole", "mosaic", "mottl")): sup.append("Spots or holes reported.")
    add("Pest or disease (not identified)", sup, ["Look at leaf undersides for insects", "Expert or KVK confirmation"])
    if any(k in txt for k in ("wilt", "root")):
        add("Root damage or root disease", ["Wilting or root damage reported."], ["Dig up a plant and inspect roots"])
    return H

def _plan(req, weather, heavy_rain, unknowns):
    p = []
    def item(action, reason, cost, ev, prio, est=False, unverified=False, kind="inspect"):
        p.append({"action": action, "reason": reason, "cost_inr": cost, "is_estimate": est, "evidence_ids": ev,
                  "priority": prio, "unverified": unverified, "kind": kind})
    item("Inspect 10 plants spread across the field: leaf undersides, stem base and roots.", "Distinguishes insects, disease and root or water problems before spending money.", 0, [], 1, unverified=True)
    if req.answers.get("waterlogging") == "yes" or heavy_rain:
        item("Clear drainage channels so water does not stand around the plants.", "Standing water can stress roots; rain is expected or was reported.", 0, ["e3"], 2)
    item("Get a soil test. The Soil Health Card scheme may offer this free; confirm locally.", "Shows whether nutrients are actually short.", 0, ["e1"], 3, est=True)
    item("Take photos and visit or call your local KVK for confirmation.", "Photos alone cannot confirm a diagnosis.", 0, ["e2"], 4)
    spent = sum(i["cost_inr"] for i in p)
    reserve = max(0.0, req.profile.budget_inr - spent)
    item("Keep your budget in reserve for a treatment that an expert confirms. Product price and dose need local confirmation.", "No treatment is advised until the cause is confirmed.", reserve, ["e2"], 5, est=True)
    return p

def _revise(r):
    """One revision pass: fix what the verifier flagged deterministically."""
    b = r["budget_in"]
    r["plan"] = [i for i in r["plan"] if i.get("kind") != "chemical"]
    for i in r["plan"]:
        if not i["evidence_ids"]: i["unverified"] = True
    over = sum(i["cost_inr"] or 0 for i in r["plan"]) - b
    for i in r["plan"]:
        if over > 0 and i["cost_inr"]:
            cut = min(i["cost_inr"], over); i["cost_inr"] -= cut; over -= cut
    r["summary"] = GUARANTEE.sub("[removed]", r.get("summary", ""))
    r["budget"] = S.calc_budget(r["plan"], b)

async def run(req) -> dict:
    trace = ["Checked farm profile and symptoms."]
    if not req.problem.symptoms and not req.problem.selected:
        return {"status": "NEEDS_MORE_INFORMATION", "questions": [], "message": "Describe a symptom or select at least one.", "trace": trace}
    qs = _questions(req)
    if qs:
        trace.append(f"Asked {len(qs)} follow-up question(s).")
        return {"status": "NEEDS_MORE_INFORMATION", "questions": qs, "trace": trace}
    weather = await S.fetch_weather(req.profile.district, req.profile.state)
    trace.append(f"Weather status: {weather['status']}.")
    if weather["status"] != "LIVE" and req.allow_demo_weather:
        weather = S.demo_weather(); trace.append("Used labelled DEMO weather by user choice.")
    days = weather.get("days", [])[:3]
    heavy = sum((d.get("rain_mm") or 0) for d in days) >= 40
    trace.append("Compared possible explanations with evidence.")
    H = _hypotheses(req, heavy)
    conflict = req.answers.get("waterlogging") == "no" and heavy
    conflicts = ["You reported no standing water, but heavy rain is forecast. Recheck drainage after rain."] if conflict else []
    r = {"hypotheses": H, "weather": weather, "evidence": list(S.EVIDENCE.values()), "evidence_map": S.EVIDENCE,
         "conflicts": conflicts, "conflict_flag": conflict, "budget_in": req.profile.budget_inr, "diagnosis_confirmed": False,
         "high_risk": True, "ai": {}, "attempts": 0,
         "avoid": ["Do not buy or spray any pesticide or fertiliser until the cause is confirmed.", "Do not spray just before heavy rain."],
         "reassess": "Re-inspect in 3 to 5 days, or sooner if the problem spreads.",
         "expert_when": "If spread continues, many plants are affected, or the cause is unclear after inspection, contact your local KVK.",
         "limitations": ["This is a set of possible explanations, not a verified diagnosis.", "Source links are pointers; their content was not fetched.",
                         "Costs are labelled estimates and need local confirmation."]}
    if weather["status"] != "LIVE":
        r["limitations"].append("Weather is " + ("DEMO data, not a real forecast." if weather["status"] == "DEMO" else "unavailable: " + weather.get("reason", "")))
    if S.flag_injection(req.problem.symptoms): r["limitations"].append("Instruction-like text in your description was ignored.")
    r["confidence"] = {"level": "low", "why": "Cause is unconfirmed; only symptoms and answers were available, no lab or expert evidence."}
    plan_unknowns = [h["name"] for h in H if h["missing"]]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        r["attempts"] = attempt
        if attempt == 1:
            r["plan"] = _plan(req, weather, heavy, plan_unknowns)
            r["budget"] = S.calc_budget(r["plan"], req.profile.budget_inr)
            r["summary"] = "DEMO summary (no AI used): Several causes are possible. Inspect first, test the soil, confirm with KVK before buying treatments."
            if S.ai_configured():
                try:
                    r["summary"] = await S.llm_summary({"plan": [i["action"] for i in r["plan"]], "hypotheses": [h["name"] for h in H], "avoid": r["avoid"]}, req.problem.symptoms, req.language)
                    r["ai"] = {"mode": "live", "provider": "OpenAI-compatible endpoint (user-configured)", "note": "Farm text and plan facts were sent to this provider. Images are never sent."}
                except Exception:
                    log.warning("AI call failed; using demo summary")
                    r["ai"] = {"mode": "demo", "note": "AI provider call failed; switched to deterministic DEMO summary."}
            else:
                r["ai"] = {"mode": "demo", "note": "No AI key configured: deterministic DEMO mode, not a live model."}
        v = verify(r)
        trace.append(f"Verification attempt {attempt}: {v['status']}.")
        if v["status"] != "VERIFICATION_FAILED": break
        if attempt < MAX_ATTEMPTS: _revise(r); trace.append("Revised plan once.")
    r.update(verification=v, status=v["status"] if v["status"] != "VERIFICATION_FAILED" else "EXPERT_REVIEW_RECOMMENDED", trace=trace)
    r.pop("evidence_map"); r.pop("budget_in")
    return r
