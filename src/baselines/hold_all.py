"""Baseline B for T09 - the trivial gate that blocks everything.

Critical-miss Rate goes to 0 because nothing is ever released, and the false-HOLD
guardrail fails for the same reason. docs/tracks/T09.md asks for this number to be
reported next to the PoC, so the primary metric is not read on its own.

    python -m src.main --track t09 --pipeline src.baselines.hold_all \
        --output out/baseline_holdall --run-name baseline_holdall --offline --seed 42
"""
from __future__ import annotations

import pandas as pd

from ..common.context import RunContext
from ..common.decision import Decision, write_decision
from ..common.review import make_review_queue, write_review_queue
from ..metrics.tracks import get_track
from .consent_only import load_cases


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    rows = [{"case_id": c.get("case_id"), "decision": "HOLD", "reason_codes": "BASELINE_HOLD_ALL",
             "market": c.get("market"), "score": 1.0, "reason": "blocks every case"}
            for c in load_cases(ctx.input_dir)]
    out = pd.DataFrame(rows)
    ctx.stats["n_items"] = len(out)
    ctx.stats["policy"] = "baseline:hold_all"
    q = make_review_queue(out, "case_id", "score", int(ctx.param("budget", len(out))), reason_col="reason")
    write_review_queue(q, ctx.out("review_queue.csv"))
    out[spec.pred_columns + [c for c in out.columns if c not in spec.pred_columns]].to_csv(
        ctx.out(spec.pred_file), index=False)
    write_decision(
        Decision(status="HOLD", reason_code="BASELINE_ONLY", reason="Blocks everything; zero business value",
                 owner=ctx.config.get("owner", "baseline"), scope=f"{ctx.track}:hold_all",
                 evidence=[str(ctx.out(spec.pred_file))], metrics={"n_cases": len(out), "n_go": 0}),
        ctx.out("decision.json"), ctx.out("decision_log.csv"))
