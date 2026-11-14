"""Baseline A for T09 - the checklist the handout calls out as wrong.

Policy: "consent obtained means we are fine". One field, one branch, no market
awareness, no transfer check, no retention check. docs/tracks/T09.md section 4
prescribes exactly this baseline so the report can show what it misses.

    python -m src.main --track t09 --pipeline src.baselines.consent_only \
        --output out/baseline --run-name baseline --offline --seed 42
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..common.context import RunContext
from ..common.decision import Decision, write_decision
from ..common.manifest import verify_manifest
from ..common.review import make_review_queue, write_review_queue
from ..metrics.tracks import get_track


def load_cases(input_dir: Path) -> list[dict]:
    cases = []
    for p in sorted((input_dir / "cases").glob("CASE-*.json")):
        with open(p, "r", encoding="utf-8") as f:
            cases.append(json.load(f))
    if not cases:
        raise FileNotFoundError(f"no case files under {input_dir / 'cases'}")
    return cases


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems and ctx.config.get("strict_provenance", True):
        raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")

    rows = []
    for case in load_cases(ctx.input_dir):
        consented = bool((case.get("consent") or {}).get("obtained"))
        rows.append({
            "case_id": case.get("case_id"),
            "decision": "GO" if consented else "HOLD",
            "reason_codes": "BASELINE_CONSENT_OK" if consented else "BASELINE_NO_CONSENT",
            "market": case.get("market"),
            "score": 0.0 if consented else 1.0,
            "reason": "consent-only checklist",
        })
    out = pd.DataFrame(rows)
    ctx.stats["n_items"] = len(out)
    ctx.stats["n_go"] = int((out.decision == "GO").sum())
    ctx.stats["policy"] = "baseline:consent_only"

    budget = int(ctx.param("budget", len(out)))
    q = make_review_queue(out, "case_id", "score", budget, reason_col="reason")
    write_review_queue(q, ctx.out("review_queue.csv"))
    out[spec.pred_columns + [c for c in out.columns if c not in spec.pred_columns]].to_csv(
        ctx.out(spec.pred_file), index=False)
    if ctx.audit:
        ctx.audit.log(actor="baseline", action="decisions_written", item_id=spec.pred_file,
                      after={"n": len(out), "go": ctx.stats["n_go"]}, reason="consent-only baseline")
    write_decision(
        Decision(status="HOLD", reason_code="BASELINE_ONLY",
                 reason="Consent-only checklist: kept for comparison, never a release gate",
                 owner=ctx.config.get("owner", "baseline"), scope=f"{ctx.track}:baseline",
                 evidence=[str(ctx.out(spec.pred_file))],
                 metrics={"n_cases": len(out), "n_go": ctx.stats["n_go"]}),
        ctx.out("decision.json"), ctx.out("decision_log.csv"))
