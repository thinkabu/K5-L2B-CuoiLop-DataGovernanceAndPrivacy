"""G07 PoC pipeline for T09 - Multi-Market Privacy Decision Gate.

Five steps, run by: python -m src.main --config configs/lab.yaml --track t09 ...

    01 load      manifest hash check, 12 case files, versioned policy file (hash recorded)
    02 process   run the rule engine over every case -> decision + reason codes + findings
    03 rank      order cases by risk score into the review queue (budget = all 12 cases)
    04 review    apply reviewer decisions from review_queue_reviewed.csv, audit every change
    05 decide    batch GO/HOLD/REWORK with reason code + owner, write the audit checklist

Outputs in the run folder: decisions.csv (contract), findings.csv, review_queue.csv,
contact_sheet.html, audit_checklist.md, audit_log.jsonl, decision.json, decision_log.csv.

Never reads fixtures/t09_privacy_gate/gt/ - the GT guard in src.main enforces that.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, canonical_status, write_decision
from .common.io import sha256_file
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track
from .policy.engine import evaluate_case, load_policy

DEFAULT_POLICY = "configs/policy/privacy_policy_v1.yaml"
HUMAN_DECISIONS = {"approve", "reject", "edit", "escalate", "skip"}
SUPPORTED_TRACKS = {"t09"}


def _require_supported_track(ctx: RunContext) -> None:
    """G07 chose T09. Any other track must exit 3 (not implemented), not fail halfway
    through load() with a confusing input error - tests/test_cli.py checks this."""
    if ctx.track not in SUPPORTED_TRACKS:
        raise NotImplementedError(
            f"src.pipeline implements {sorted(SUPPORTED_TRACKS)} only, and track {ctx.track} is not one of them. "
            "G07 built the Multi-Market Privacy Decision Gate; see docs/tracks/T09.md")


# ---------------------------------------------------------------- 01 load
def _resolve_policy_path(ctx: RunContext) -> Path:
    """Accept a path relative to the fixture folder or to the repo root."""
    raw = str(ctx.param("policy_file", DEFAULT_POLICY))
    for cand in (ctx.input_dir / raw, Path(raw)):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"policy file not found: tried {ctx.input_dir / raw} and {Path(raw).resolve()}")


def load(ctx: RunContext) -> dict:
    _require_supported_track(ctx)
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")

    case_dir = ctx.input_dir / "cases"
    cases = []
    for p in sorted(case_dir.glob("CASE-*.json")):
        with open(p, "r", encoding="utf-8") as f:
            cases.append(json.load(f))
    if not cases:
        raise FileNotFoundError(f"no case files under {case_dir}")

    policy_path = _resolve_policy_path(ctx)
    policy = load_policy(policy_path)
    policy_sha = sha256_file(policy_path)
    ctx.stats["policy_version"] = policy.get("policy_version")
    ctx.stats["policy_file"] = str(policy_path)
    ctx.stats["policy_sha256"] = policy_sha
    ctx.stats["n_rules"] = len(policy.get("rules", []))
    ctx.audit.log(actor="pipeline", action="policy_loaded", item_id=str(policy_path),
                  after={"version": policy.get("policy_version"), "sha256": policy_sha,
                         "as_of": str(policy.get("as_of")), "n_rules": len(policy.get("rules", []))},
                  reason="every decision below is traceable to this rule file version")
    return {"manifest": pd.read_csv(manifest), "cases": cases, "policy": policy, "policy_path": policy_path}


# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    policy = data["policy"]
    rows, findings = [], []
    for case in data["cases"]:
        v = evaluate_case(case, policy)
        gaps = [f"{f.rule_id}:{f.reason_code}" for f in v.findings if f.decision != "NOTE"]
        if v.normalisations:
            # The gate renamed a field before judging the case, so the trail has to say so:
            # a reviewer reading the queue must be able to see what the engine actually read.
            ctx.audit.log(actor="pipeline", action="field_alias_applied", item_id=v.case_id,
                          after=v.normalisations, reason="declared in field_aliases of the policy file")
        rows.append({
            "case_id": v.case_id,
            "decision": v.decision,
            "reason_codes": v.reason_codes_str(),
            "market": v.market,
            "rule_ids": ";".join(v.rule_ids),
            "needs_legal_review": v.needs_legal_review,
            "upcoming_obligations": ";".join(v.upcoming_obligations),
            "field_normalisations": ";".join(v.normalisations),
            "evidence_gaps": ";".join(gaps),
            "policy_version": policy.get("policy_version"),
            "score": v.risk_score,
            "reason": v.reason_codes_str() if v.decision != "GO" else "no gap found",
        })
        for f in v.findings:
            findings.append({
                "case_id": v.case_id, "market": v.market, "rule_id": f.rule_id, "decision": f.decision,
                "reason_code": f.reason_code, "confidence": f.confidence,
                "needs_legal_review": f.needs_legal_review, "deferred_to": f.deferred_to or "",
                "source_doc": (f.source or {}).get("doc", ""), "source_ref": (f.source or {}).get("ref", ""),
                "source_url": (f.source or {}).get("url", ""), "note": f.note,
            })
    out = pd.DataFrame(rows).sort_values("case_id").reset_index(drop=True)
    pd.DataFrame(findings).to_csv(ctx.out("findings.csv"), index=False)
    ctx.stats["n_findings"] = len(findings)
    ctx.stats["decision_counts"] = out.decision.value_counts().to_dict()
    ctx.stats["policy"] = "poc:rule_engine"
    return out


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    """Highest risk first. The budget covers all 12 cases: the handout asks for a screen
    where the approver signs off on every case, not only on the worst few."""
    budget = int(ctx.param("budget", len(scored)))
    q = make_review_queue(scored, id_col="case_id", score_col="score", budget=budget,
                          reason_col="reason", action_col="decision", slice_col="market")
    write_review_queue(q, ctx.out("review_queue.csv"))
    render_contact_sheet(q, ctx.out("contact_sheet.html"), image_root=ctx.input_dir,
                         title=f"T09 privacy gate - {ctx.run_name} - approver sign-off")
    ctx.stats["budget"] = budget
    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Reviewer decisions win over the engine, and every change lands in the audit log."""
    final = scored.copy()
    for col in ("reviewer", "reviewer_decision", "review_note"):
        final[col] = ""
    final["engine_decision"] = final["decision"]

    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if not reviewed_path.exists():
        ctx.stats["n_reviewed"] = 0
        ctx.audit.log(actor="pipeline", action="review_skipped", item_id=str(reviewed_path),
                      reason="no reviewed queue present; engine decisions stand unreviewed")
        return final

    reviewed = load_review_decisions(reviewed_path, allowed=HUMAN_DECISIONS)
    ctx.stats["n_reviewed"] = len(reviewed)
    n_changed = 0
    known = set(final.case_id.astype(str))
    for r in reviewed.itertuples(index=False):
        case_id = str(r.item_id)
        if case_id not in known:
            raise ValueError(f"reviewed row {case_id} is not a case in this run")
        mask = final.case_id == case_id
        before = final.loc[mask, "decision"].iloc[0]
        decision = str(r.reviewer_decision)
        new, extra_code = before, ""
        if decision == "escalate":
            new, extra_code = "HOLD", "HUMAN_ESCALATION"
        elif decision in {"edit", "reject"}:
            if not str(r.override_value).strip():
                raise ValueError(f"{case_id}: reviewer_decision={decision} needs an override_value (GO/HOLD/REWORK)")
            new, extra_code = canonical_status(str(r.override_value)), "HUMAN_OVERRIDE"
        final.loc[mask, "reviewer"] = r.reviewer
        final.loc[mask, "reviewer_decision"] = decision
        final.loc[mask, "review_note"] = r.review_note
        if new != before:
            codes = [c for c in str(final.loc[mask, "reason_codes"].iloc[0]).split(";")
                     if c and c != "NO_GAP_FOUND"]
            if extra_code:
                codes.append(extra_code)
            final.loc[mask, "decision"] = new
            final.loc[mask, "reason_codes"] = ";".join(codes) if codes else (extra_code or "HUMAN_OVERRIDE")
            n_changed += 1
            ctx.audit.log(actor=r.reviewer, action=f"override:{decision}", item_id=case_id,
                          before=before, after=new, reason=r.review_note or "(no note given)")
        else:
            ctx.audit.log(actor=r.reviewer, action=f"review:{decision}", item_id=case_id,
                          before=before, after=new, reason=r.review_note or "(no note given)")
    ctx.stats["n_overridden"] = n_changed
    return final


# ---------------------------------------------------------------- 05 decide
def _write_audit_checklist(ctx: RunContext, final: pd.DataFrame, data: dict) -> Path:
    policy = data["policy"]
    fpath = ctx.out("findings.csv")
    findings = pd.read_csv(fpath) if fpath.exists() else pd.DataFrame(columns=["case_id"])
    sha = str(ctx.stats.get("policy_sha256", ""))[:16]
    lines = [
        "# T09 privacy gate - audit checklist",
        "",
        f"- run: {ctx.run_name} / track: {ctx.track} / seed: {ctx.seed} / offline: {ctx.offline}",
        f"- policy: {policy.get('policy_version')} (as_of {policy.get('as_of')}), sha256 {sha}",
        f"- policy file: {ctx.stats.get('policy_file')}",
        f"- input: {ctx.input_dir}, cases: {len(final)}",
        f"- approver on file: {ctx.config.get('owner')}",
        "",
        "Teaching artefact. The gate is a review aid; the DPO or counsel owns the final call.",
        "",
        "| case | market | engine | final | reviewer | reason codes |",
        "|---|---|---|---|---|---|",
    ]
    for r in final.itertuples(index=False):
        lines.append(f"| {r.case_id} | {r.market} | {r.engine_decision} | {r.decision} | "
                     f"{r.reviewer or '-'} | {r.reason_codes} |")
    lines += ["", "## Per-case evidence", ""]
    for r in final.itertuples(index=False):
        lines.append(f"### {r.case_id} - {r.market} - {r.decision}")
        sub = findings[findings.case_id == r.case_id] if len(findings) else pd.DataFrame()
        if not len(sub):
            lines.append("- no rule fired: no gap found against policy "
                         f"{policy.get('policy_version')} (an absent finding is not a legal clearance)")
        for f in sub.itertuples(index=False):
            tag = "NOTE, not in force yet" if f.decision == "NOTE" else f.decision
            legal = ", needs legal review" if bool(f.needs_legal_review) else ""
            defer = f", binds from {f.deferred_to}" if str(f.deferred_to) not in ("", "nan") else ""
            lines.append(f"- {f.rule_id} [{tag}] {f.reason_code}{defer}{legal}")
            lines.append(f"  - source: {f.source_doc} - {f.source_ref}")
            if str(f.note) not in ("", "nan"):
                lines.append(f"  - {f.note}")
        if str(getattr(r, "field_normalisations", "")) not in ("", "nan"):
            lines.append(f"- field renamed before judging, per the policy aliases: {r.field_normalisations}")
        if r.reviewer:
            lines.append(f"- reviewer {r.reviewer}: {r.reviewer_decision} - {r.review_note or 'no note'}")
        lines.append("")
    lines += [
        "## Sign-off",
        "",
        f"- [ ] {ctx.config.get('owner')} has read every HOLD above and agrees with the reason codes",
        "- [ ] every rule marked needs_legal_review has been checked against the original instrument",
        "- [ ] cases flagged UPCOMING_OBLIGATION are in the compliance roadmap, with their dates",
        "",
    ]
    path = ctx.out("audit_checklist.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    counts = final.decision.value_counts().to_dict()
    n_hold, n_rework = int(counts.get("HOLD", 0)), int(counts.get("REWORK", 0))
    if n_hold:
        status, code = "HOLD", "CASES_BLOCKED"
        reason = f"{n_hold} of {len(final)} cases are blocked pending legal sign-off"
    elif n_rework:
        status, code = "REWORK", "CASES_NEED_REWORK"
        reason = f"{n_rework} of {len(final)} cases need fixes before collection starts"
    else:
        status, code = "GO", "ALL_CASES_CLEAR"
        reason = f"all {len(final)} cases pass policy {ctx.stats.get('policy_version')}"
    return Decision(
        status=status, reason_code=code, reason=reason,
        owner=ctx.config.get("owner", "TODO-owner"), scope=f"{ctx.track}:{ctx.run_name}",
        evidence=[str(ctx.out("decisions.csv")), str(ctx.out("findings.csv")),
                  str(ctx.out("audit_checklist.md")), str(ctx.stats.get("policy_file", ""))],
        metrics={"n_cases": len(final), "decision_counts": counts,
                 "n_needs_legal_review": int(final.needs_legal_review.sum()),
                 "n_reviewed": ctx.stats.get("n_reviewed", 0),
                 "n_overridden": ctx.stats.get("n_overridden", 0),
                 "policy_version": ctx.stats.get("policy_version"),
                 "policy_sha256": ctx.stats.get("policy_sha256")})


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    final[spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]].to_csv(
        ctx.out(spec.pred_file), index=False)
    _write_audit_checklist(ctx, final, data)
    write_decision(decide(ctx, final), ctx.out("decision.json"), ctx.out("decision_log.csv"))
