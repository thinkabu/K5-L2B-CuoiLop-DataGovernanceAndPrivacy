Baseline: `baseline` (git b0ce8bf, seed 42) · PoC: `poc_engine` (git b0ce8bf, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Critical-miss Rate** (risky cases given GO / risky cases) | all | 0.4286 | 0.0000 | -0.4286 | -100.0% | lower | 8 |
| High-risk HOLD Recall (risky cases not GO / risky cases) | all | 0.5714 | 1.0000 | 0.4286 | +75.0% | higher | None |
| False HOLD rate (GO cases blocked / GO cases) | all | 1.0000 | 0.0000 | -1.0000 | -100.0% | lower | None |
| Exact decision accuracy (fraction) | all | 0.5000 | 1.0000 | 0.5000 | +100.0% | higher | 8 |
| Guardrail: False HOLD rate <= 0.5 (1 = pass, 0 = fail (constrained primary)) | all | 0.0000 | 1.0000 | 1.0000 | baseline=0 | higher | None |
| Reason-code match (risky) (risky cases with ≥1 correct reason code) | all | 0.0000 | 1.0000 | 1.0000 | baseline=0 | higher | None |
| Runtime / 100 items (s) | all | 0.2058 | 0.8775 | | | lower | |
