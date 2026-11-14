# T09 handover — what to send, and what to do with it

Day 06 Data Lab · track **T09 Multi-Market Privacy Decision Gate** · group **G07**
Policy `g07-1.1.0` (`as_of: 2026-11-14`), sha256 `ef49790a9ef3c744…`, 21 rules.
First frozen as `g07-1.0.0` with 19 rules; 1.1.0 fixes a real defect an external reviewer found — see
section 8 and the changelog at the top of the rule file.

Everything below is written against the course starter repo
`VinUni-AI20k/K5-Day6-L2-DataGovernanceAndPrivacy` at commit `b0ce8bf`. Drop these files into a fresh
clone of that repo, keeping the paths exactly, and the lab runs.

## 1 · Files the group wrote (new — none of these exist in the template)

| Path | What it is |
|---|---|
| `configs/policy/privacy_policy_v1.yaml` | The rule file: 21 rules across VN / EU / US-CA / SG / IN, each with source, article reference, `version_date`, `confidence`, `needs_legal_review`. Also holds `field_aliases` and a changelog. This is the artefact a lawyer reads. |
| `src/policy/__init__.py` | Package marker for the engine. |
| `src/policy/engine.py` | The rule engine. Structured DSL (`field` / `op` / `value`, nested `all` / `any` / `none`), no `eval()`. Raises on a rule with no source, a duplicate id, an unknown operator, no condition, or a malformed date. A rule whose `effective_date` is in the future becomes a NOTE instead of a block. |
| `src/baselines/__init__.py` | Package marker for the baselines. |
| `src/baselines/consent_only.py` | Baseline A: "consent obtained means we are fine" — the checklist the handout calls wrong. |
| `src/baselines/hold_all.py` | Baseline B: blocks everything. Critical-miss 0, guardrail fails. Needed so the primary metric is never read on its own. |
| `tests/test_policy_engine.py` | 19 group tests: 13 on the success path, 6 on the failure path. One of them runs the coverage gate below, so a renamed or new fixture field breaks the build. |
| `tools/field_coverage.py` | The check that would have caught the 1.0.0 defect: every field present in the cases must be read by a rule, declared in `field_aliases`, or listed in `fields_not_used` with a reason. Exits 1 on a gap. Run it as `python -m tools.field_coverage`. |
| `.gitattributes` | `* text=auto eol=lf`. Without this, a Windows checkout breaks every fixture hash — see section 5. |
| `demo/README.md` | Five-slide demo script plus the live commands. |
| `HANDOVER.md` | This file. |

## 2 · Template files the group changed

| Path | Change |
|---|---|
| `configs/lab.yaml` | `group_id: G07`, owner, `track: t09`, `track_config: tracks/t09.yaml`, `input: fixtures/t09_privacy_gate`, and `params` with `policy_file` plus `budget: 12`. |
| `src/pipeline.py` | The whole group PoC: the five steps, plus a `SUPPORTED_TRACKS` guard so any other track still exits 3 (`tests/test_cli.py` checks that). |
| `reports/group_report.md` | Filled in, all 12 sections. |
| `reports/metric_contract.md` | Filled in, frozen 2026-11-14. |
| `reports/team_contributions.csv` | Six rows, one per role, matching section 10 of the report. Name and email columns are blank on purpose: each member fills in their own, exactly as `git config` has it. |

## 3 · Reports and generated evidence

| Path | Who made it | Note |
|---|---|---|
| `reports/group_report.md` | group | The graded report. Section 00 still needs the repo URL and the two tag commits. |
| `reports/metric_contract.md` | group | Primary metric, guardrail, splits, frozen threshold, and the limits of the internal self-check. |
| `reports/internal_gold_dev.csv` | group | Own labels for the 8 dev cases, each with a `basis_of_label` column. Not instructor ground truth. |
| `reports/metrics_baseline_internal.json` | script | Baseline A scored on the internal gold. |
| `reports/metrics_baseline_holdall_internal.json` | script | Baseline B (hold-all). |
| `reports/metrics_poc_engine_internal.json` | script | PoC with the human round removed (the ablation). |
| `reports/metrics_poc_reviewed_internal.json` | script | PoC as shipped, after the approver round. |
| `reports/table1_internal_baseline_vs_poc.md` | script | `src.compare` output: baseline against the shipped PoC. |
| `reports/table2_internal_baseline_vs_engine_only.md` | script | `src.compare` output: baseline against engine-only. |
| `reports/review_queue.csv` | pipeline + reviewer | The reviewed queue: 8 of 12 cases carry a decision, signed `Pham Huu Minh`. |
| `reports/decision_log.csv` | pipeline | Append-only decision log. |
| `reports/evidence_poc/decisions.csv` | pipeline | **The contract output.** `case_id, decision, reason_codes` plus rule ids, market, policy version. |
| `reports/evidence_poc/decisions_baseline.csv` | pipeline | Baseline A output, for side-by-side reading. |
| `reports/evidence_poc/findings.csv` | pipeline | One row per rule that fired: rule id, reason code, confidence, source doc and reference. |
| `reports/evidence_poc/audit_checklist.md` | pipeline | Per-case evidence with article references, and the three sign-off lines. |
| `reports/evidence_poc/audit_log.jsonl` | pipeline | Append-only: who decided what, when, from what to what, and why. |
| `reports/evidence_poc/review_queue_generated.csv` | pipeline | The queue as the engine produced it, before anyone touched it. |
| `reports/evidence_poc/review_queue_reviewed.csv` | reviewer | The file the approver filled in. Copy it to `out/poc/review_queue_reviewed.csv` to reproduce the reviewed run. |
| `reports/evidence_poc/decision.json` | pipeline | Batch decision: HOLD, `CASES_BLOCKED`, owner, policy version and sha256, evidence paths. |
| `reports/evidence_poc/run_info.json` | pipeline | Seed, git sha, config hash, runtime, machine, per-run stats. |

`out/` is gitignored in the template, which is why these copies live under `reports/`.

## 4 · How to run it (Windows, offline, seed 42)

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.verify_manifests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.main --track t09 --pipeline src.baselines.consent_only --output out/baseline --run-name baseline --offline --seed 42
.\.venv\Scripts\python.exe -m src.main --config configs/lab.yaml --track t09 --output out/poc --run-name poc --offline --seed 42
```

To reproduce the reviewed run, copy `reports/evidence_poc/review_queue_reviewed.csv` to
`out/poc/review_queue_reviewed.csv` and run the last command again.

Expected, and checked on this machine (Windows 11 build 26300, Python 3.13.2, Intel i7-13620H):

- `tools.verify_manifests` gives `14 manifests, 0 failing`
- `python -m tools.field_coverage` exits 0 with every field accounted for
- `pytest -q` gives `66 passed, 39 skipped, 0 failed` (19 of those are the group's own)
- baseline run: exit 0, 12 cases, 4 GO, 0.0247 s
- PoC run: exit 0, 12 cases, engine HOLD 10 and GO 2; the review round keeps all 12 decisions, 0.1786 s
- two clean PoC runs produce byte-identical `decisions.csv` and `findings.csv`

## 5 · Three things that will bite on another machine

1. **Every fixture hash fails right after clone on Windows.** The cause is git, not the data: with
   `core.autocrlf=true` the checkout rewrites text files to CRLF while the manifests hash the LF bytes.
   The `.gitattributes` in this handover fixes new clones. On a clone that is already broken, run
   `git config core.autocrlf false` and re-checkout the working tree. Because `lab.yaml` sets
   `strict_provenance: true`, the pipeline otherwise stops at load with exit 2 — the guard doing its job.
2. **`python -m src.evaluate` dies with `UnicodeEncodeError` on a Windows console**, after it has already
   computed the metrics: the lab prints a character that cp1252 cannot encode. Set
   `PYTHONIOENCODING=utf-8` before running evaluate. Do not patch the lab file; the instructor runs the original.
3. **`tests/test_cli.py::test_template_pipeline_fails_clearly_not_silently` fails the moment a group
   implements `src/pipeline.py`**, because it runs the pipeline on t02 and demands exit 3. The guard in
   `src/pipeline.py` (`SUPPORTED_TRACKS = {"t09"}` raising `NotImplementedError`) keeps that test honest
   instead of being edited away.

## 6 · Official scoring is not in this repo

`fixtures/t09_privacy_gate/gt/` is instructor-only. `python -m src.evaluate --track t09 --pred out/poc/decisions.csv`
returns **exit code 2** with a missing-ground-truth message, which was checked rather than assumed. Every
number in the report that does not come from `run_info.json` comes from the group's own dev labels in
`reports/internal_gold_dev.csv`, written by the same person who wrote the rules — so they measure internal
consistency, not correctness. The report says this in section 04 and again in section 09.

## 7 · Still open

- **Names and commits for the six roles.** Section 00 and section 10 of the report, and
  `reports/team_contributions.csv`, carry one row per role with the name fields blank. Each member fills in
  their own name and email as `git config` has them, and makes at least one substantive commit to the module
  listed against their role — lab rule 6, and a whitespace-only commit does not count. The split follows file
  boundaries, so nobody has to touch anyone else's file:
  Lead/Integrator `configs/lab.yaml` plus the wiring in `src/pipeline.py`; Policy research
  `configs/policy/privacy_policy_v1.yaml`; Core algorithm `src/policy/engine.py`; Baseline and metric
  `src/baselines/` plus the evaluate and compare runs; QA `tests/test_policy_engine.py`; Human review and
  report `reports/` plus `demo/`. Then check it against `git shortlog -sne --all`.
- **Approver name.** `decision.json`, `audit_log.jsonl` and `audit_checklist.md` carry the person who actually
  signed this review round. If the group puts someone else in that seat, change `owner` in `configs/lab.yaml`
  and re-run the one PoC command so the audit trail names the right person.
- Section 00 of the report needs the repo URL and the `demo-180m` / `final-24h` tag commits.
- Nothing is committed yet; the first commit and the push belong to the submitter.
- Decide whether the report stays Vietnamese (matching the template and the Day 05 submission) or
  switches to English.
- The defect in policy v1.0.0 is fixed and shipped as v1.1.0, and it is written up as failure case 3 of the
  report rather than quietly patched. Short version: the fixture names one fact two ways
  (`li_assessment_done` in CASE-06, `lia_done` in CASE-10), v1.0.0 read neither, so CASE-06 passed because no
  rule fired and the approver then escalated it on a note that the case file contradicts. v1.1.0 declares the
  alias in the rule file, adds `R-SG-02` and `R-EU-04`, reports every rename into the audit log and into a
  `field_normalisations` column, and the review note is corrected in writing. Measured before shipping: no
  case changes decision, and all four eval-split decisions are untouched.
- Worth re-running whenever the fixture or the rule file changes: list every field present in the cases and
  compare it against every field the rules read. That check is what turns this class of bug from "someone
  noticed" into something the group catches itself.
