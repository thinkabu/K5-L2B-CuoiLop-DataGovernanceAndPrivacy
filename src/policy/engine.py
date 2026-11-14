"""Rule engine behind the T09 privacy gate (G07).

Design choices, all deliberate:

* **No eval().** Rules are structured data (`field` / `op` / `value`, nested in
  `all` / `any` / `none`), so a rule file can be reviewed by someone who does not
  read Python, and a malformed rule cannot execute arbitrary code.
* **Fail loudly.** An unknown operator, a rule without a `reason_code` or without a
  `source` raises at load time. A rule that silently does not fire is the failure
  mode this track is about, so there is no "skip what I do not understand" path.
* **Decisions carry provenance.** Every finding keeps the rule id, the reason code
  and the source reference, which is what the audit checklist prints.
* **Future law is a note, not a breach.** A rule whose `effective_date` is after the
  policy's `as_of` date is downgraded to NOTE (docs/tracks/T09.md section 8).

Precedence: HOLD > REWORK > GO. NOTE never changes the decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

PRECEDENCE = {"GO": 0, "REWORK": 1, "HOLD": 2}
NOTE = "NOTE"
REQUIRED_RULE_KEYS = ("id", "decision", "reason_code", "source")
CONDITION_KEYS = ("all", "any", "none")


# ----------------------------------------------------------------- field access
def get_field(case: dict, path: str) -> Any:
    """Dotted lookup, e.g. transfer.cross_border. A missing key yields None."""
    cur: Any = case
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _norm(v: Any) -> Any:
    """Treat an empty string like a missing value, so an empty mechanism matches null."""
    return None if isinstance(v, str) and v.strip() == "" else v


def _as_list(v: Any) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def _numeric(a: Any, b: Any, fn) -> bool:
    try:
        return bool(fn(float(a), float(b)))
    except (TypeError, ValueError):
        return False          # a null or non-numeric field cannot satisfy a numeric test


OPS = {
    "eq": lambda a, b: _norm(a) == _norm(b),
    "ne": lambda a, b: _norm(a) != _norm(b),
    "in": lambda a, b: _norm(a) in [_norm(x) for x in _as_list(b)],
    "not_in": lambda a, b: _norm(a) not in [_norm(x) for x in _as_list(b)],
    "is_null": lambda a, b: _norm(a) is None,
    "not_null": lambda a, b: _norm(a) is not None,
    "is_true": lambda a, b: a is True,
    "is_false": lambda a, b: a is False,
    "is_falsy": lambda a, b: not bool(a),          # False or missing
    "gt": lambda a, b: _numeric(a, b, lambda x, y: x > y),
    "gte": lambda a, b: _numeric(a, b, lambda x, y: x >= y),
    "lt": lambda a, b: _numeric(a, b, lambda x, y: x < y),
    "lte": lambda a, b: _numeric(a, b, lambda x, y: x <= y),
    "includes": lambda a, b: _norm(b) in [_norm(x) for x in _as_list(a)],
    "includes_any": lambda a, b: bool({_norm(x) for x in _as_list(a)} & {_norm(x) for x in _as_list(b)}),
    "excludes": lambda a, b: _norm(b) not in [_norm(x) for x in _as_list(a)],
    "nonempty": lambda a, b: bool(str(a).strip()) if a is not None else False,
}


# ----------------------------------------------------------------- data holders
@dataclass
class Finding:
    rule_id: str
    decision: str                 # HOLD / REWORK / NOTE (after effective-date handling)
    reason_code: str
    note: str = ""
    source: dict = dc_field(default_factory=dict)
    confidence: str = ""
    needs_legal_review: bool = False
    deferred_to: str | None = None   # set when a future effective_date downgraded it to NOTE

    @property
    def source_ref(self) -> str:
        s = self.source or {}
        bits = [str(s.get("doc", "")).strip(), str(s.get("ref", "")).strip()]
        return " - ".join([b for b in bits if b])


@dataclass
class CaseVerdict:
    case_id: str
    market: str
    decision: str
    reason_codes: list[str]
    rule_ids: list[str]
    findings: list[Finding]
    risk_score: float
    needs_legal_review: bool
    upcoming_obligations: list[str]
    normalisations: list[str] = dc_field(default_factory=list)

    def reason_codes_str(self) -> str:
        return ";".join(self.reason_codes)


# ----------------------------------------------------------------- policy loading
def _check_condition_shape(cond: Any, rule_id: str) -> None:
    if not isinstance(cond, dict):
        raise ValueError(f"rule {rule_id}: condition must be a mapping, got {type(cond).__name__}")
    group = [k for k in CONDITION_KEYS if k in cond]
    if group:
        for k in group:
            if not isinstance(cond[k], list):
                raise ValueError(f"rule {rule_id}: {k} must be a list of conditions")
            for sub in cond[k]:
                _check_condition_shape(sub, rule_id)
        return
    if "field" not in cond or "op" not in cond:
        raise ValueError(f"rule {rule_id}: condition needs field and op (or all/any/none), got {sorted(cond)}")
    if cond["op"] not in OPS:
        raise ValueError(f"rule {rule_id}: unknown operator {cond['op']!r}; allowed: {sorted(OPS)}")


def load_policy(path: str | Path) -> dict:
    """Load and validate a policy file. Raises ValueError on any malformed rule."""
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f) or {}
    if not policy.get("policy_version"):
        raise ValueError(f"{p}: policy_version is mandatory (a decision must name the policy it came from)")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError(f"{p}: rules must be a non-empty list")
    seen: set[str] = set()
    for raw in rules:
        if not isinstance(raw, dict):
            raise ValueError(f"{p}: every rule must be a mapping, got {type(raw).__name__}")
        missing = [k for k in REQUIRED_RULE_KEYS if not raw.get(k)]
        if missing:
            raise ValueError(f"{p}: rule {raw.get('id', 'unnamed')} is missing {missing} "
                             "(every rule must cite a source and a reason code)")
        rid = str(raw["id"])
        if rid in seen:
            raise ValueError(f"{p}: duplicate rule id {rid}")
        seen.add(rid)
        if raw["decision"] not in PRECEDENCE and raw["decision"] != NOTE:
            raise ValueError(f"rule {rid}: decision must be one of GO/REWORK/HOLD/NOTE, got {raw['decision']!r}")
        conds = [c for c in (raw.get("all"), raw.get("any"), raw.get("none")) if c is not None]
        if not conds:
            raise ValueError(f"rule {rid}: needs at least one of all/any/none")
        _check_condition_shape({k: v for k, v in raw.items() if k in CONDITION_KEYS}, rid)
    return policy


# ----------------------------------------------------------------- evaluation
def _eval_condition(cond: dict, case: dict) -> bool:
    if "all" in cond:
        return all(_eval_condition(c, case) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(c, case) for c in cond["any"])
    if "none" in cond:
        return not any(_eval_condition(c, case) for c in cond["none"])
    op = OPS.get(cond["op"])
    if op is None:                                     # unreachable after load_policy, kept as a guard
        raise ValueError(f"unknown operator {cond['op']!r}")
    return bool(op(get_field(case, cond["field"]), cond.get("value")))


def _market_matches(rule: dict, market: str) -> bool:
    markets = rule.get("markets") or ["*"]
    return "*" in markets or market in markets


def _to_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"bad date {v!r}: expected yyyy-mm-dd")


def apply_field_aliases(case: dict, policy: dict) -> tuple[dict, list[str]]:
    """Copy a known alias onto its canonical field name, and say what was copied.

    The fixture names the same fact two ways: CASE-06 carries li_assessment_done and CASE-10
    carries lia_done. A rule can only read one name, so the aliases are declared as data in the
    policy file (field_aliases) rather than hidden in code, and every copy is reported back so the
    audit trail shows that the gate renamed something before judging it. The canonical field wins
    when both are present: an explicit value is never overwritten by an alias.
    """
    aliases = policy.get("field_aliases") or {}
    if not aliases:
        return case, []
    out = dict(case)
    applied: list[str] = []
    for canonical, names in aliases.items():
        if _norm(out.get(canonical)) is not None:
            continue
        for name in _as_list(names):
            if _norm(out.get(name)) is not None:
                out[canonical] = out[name]
                applied.append(f"{name}->{canonical}")
                break
    return out, applied


def _ambiguity_finding(case: dict, policy: dict) -> Finding | None:
    notes = str(get_field(case, "ambiguity_notes") or "").strip()
    if not notes:
        return None
    amb = policy.get("ambiguity") or {}
    markers = [str(m).lower() for m in (amb.get("upcoming_law_markers") or [])]
    low = notes.lower()
    if any(m in low for m in markers):
        return Finding(rule_id="AMB-UPCOMING", decision=NOTE,
                       reason_code=amb.get("upcoming_reason_code", "UPCOMING_OBLIGATION"),
                       note=f"future-dated duty recorded, not scored as a present breach: {notes}",
                       source={"doc": "docs/tracks/T09.md", "ref": "section 8, effective_date handling"},
                       confidence="medium", needs_legal_review=True)
    return Finding(rule_id="AMB-01", decision=amb.get("decision", "HOLD"),
                   reason_code=amb.get("reason_code", "AMBIGUOUS_NEEDS_LEGAL"),
                   note=f"case file is ambiguous, legal must resolve it: {notes}",
                   source={"doc": "G07 protocol", "ref": "ambiguity escalates, it never defaults to GO"},
                   confidence="high", needs_legal_review=True)


def evaluate_case(case: dict, policy: dict, as_of: str | date | None = None) -> CaseVerdict:
    """Run every rule of the policy over one case and combine the findings."""
    case, normalisations = apply_field_aliases(case, policy)
    market = str(get_field(case, "market") or "").strip()
    asof = _to_date(as_of or policy.get("as_of") or policy.get("effective_date")) or date.today()
    weights = policy.get("severity_weight") or {"HOLD": 1.0, "REWORK": 0.5, NOTE: 0.1}
    findings: list[Finding] = []

    covered = policy.get("covered_markets")
    if covered and market not in covered:
        unc = policy.get("uncovered_market") or {}
        findings.append(Finding(rule_id="MKT-00", decision=unc.get("decision", "HOLD"),
                                reason_code=unc.get("reason_code", "AMBIGUOUS_NEEDS_LEGAL"),
                                note=unc.get("note", f"market {market or 'empty'} is outside this policy version"),
                                source={"doc": "G07 policy", "ref": "covered_markets"},
                                confidence="high", needs_legal_review=True))

    for rule in policy["rules"]:
        if not _market_matches(rule, market):
            continue
        cond = {k: v for k, v in rule.items() if k in CONDITION_KEYS}
        if not _eval_condition(cond, case):
            continue
        decision = rule["decision"]
        deferred = None
        eff = _to_date(rule.get("effective_date"))
        if eff and eff > asof and decision != NOTE:
            decision, deferred = NOTE, eff.isoformat()
        findings.append(Finding(rule_id=str(rule["id"]), decision=decision, reason_code=str(rule["reason_code"]),
                                note=str(rule.get("note", "")), source=rule.get("source") or {},
                                confidence=str(rule.get("confidence", "")),
                                needs_legal_review=bool(rule.get("needs_legal_review", False)),
                                deferred_to=deferred))

    amb = _ambiguity_finding(case, policy)
    if amb:
        findings.append(amb)

    blocking = [f for f in findings if f.decision != NOTE]
    decision = max([f.decision for f in blocking], key=lambda d: PRECEDENCE[d]) if blocking else "GO"
    score = sum(float(weights.get(f.decision, 0.1)) for f in findings)
    score += 0.25 * sum(1 for f in findings if f.needs_legal_review)
    score += 0.10 * sum(1 for f in findings if f.confidence == "low")

    seen: set[str] = set()
    codes = [f.reason_code for f in blocking if not (f.reason_code in seen or seen.add(f.reason_code))]
    if decision == "GO":
        codes = ["NO_GAP_FOUND"]
    return CaseVerdict(
        case_id=str(get_field(case, "case_id") or ""), market=market, decision=decision,
        reason_codes=codes, rule_ids=[f.rule_id for f in findings], findings=findings,
        risk_score=round(score, 4),
        needs_legal_review=any(f.needs_legal_review for f in findings),
        upcoming_obligations=[f"{f.rule_id}:{f.reason_code}@{f.deferred_to or 'n/a'}"
                              for f in findings if f.decision == NOTE],
        normalisations=normalisations,
    )
