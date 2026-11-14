# Demo script - T09 Multi-Market Privacy Decision Gate (G07)

Five slides, five minutes, all offline. Every number on a slide comes from a file in this repo.

## Slide 1 - the problem in one sentence

One ADAS collection, five markets, five different sets of duties. A consent checkbox is not a
cross-border transfer mechanism, and it is not a DPIA. The cost of being wrong lands on the people
filmed, because footage already in a training set cannot be un-collected.

## Slide 2 - what we built

Rule file with sources (configs/policy/privacy_policy_v1.yaml, version g07-1.1.0, 21 rules) plus a
rule engine with no eval() in it. Five steps: load with hash check, score every case, queue by risk,
human sign-off, batch decision plus audit checklist. Show out/poc/audit_checklist.md on screen.

## Slide 3 - baseline against PoC

Baseline A is the consent-only checklist the handout calls wrong: it releases CASE-02 (no transfer
mechanism), CASE-03 (raw faces in the cloud, no retention limit) and CASE-07 (no VN transfer impact
assessment). Critical-miss Rate 0.4286 against 0.0000 on the group gold set of 8 dev cases, and the
false-HOLD guardrail goes from FAIL to PASS. Baseline B holds everything: critical-miss 0.0000 but
the guardrail fails, which is why the primary metric is never read on its own.

## Slide 4 - the bug we shipped, and how it was caught

CASE-06 (Singapore) is the slide to spend time on. Policy v1.0.0 had no SG lawful-basis rule, so the
engine said GO because nothing fired, not because the file had evidence. The approver then escalated
it to HOLD, writing that no legitimate-interests assessment was on file. That was wrong: CASE-06.json
carries li_assessment_done: true. The queue never showed the field, because no rule read it, so the
human had no way to see it. Root cause: the fixture names one fact two ways, li_assessment_done in
CASE-06 and lia_done in CASE-10, and v1.0.0 read neither.

Measured cost of the mistake: false HOLD 1.0000 and guardrail FAIL on the version we were about to
submit, because the single GO case in the dev set was the one that got blocked. After v1.1.0 declared
the alias and added R-SG-02 and R-EU-04, false HOLD is 0.0000 and the guardrail passes. Both the
escalation and its correction are in out/poc/audit_log.jsonl, which is what an append-only log is for.

The transferable lesson: a human reviewer can only check what the system puts in front of them, so a
field no rule reads is invisible to the review step as well. Having a person in the loop does not
cover a hole in the rules.

## Slide 5 - what we will not claim

This gate finds missing evidence; it does not certify compliance with any law. 10 of 12 cases carry
needs_legal_review. No rule firing is not a clearance, and the checklist prints that sentence on
every case with no finding.

## Live demo commands (offline, seed 42)

    .\.venv\Scripts\python.exe -m tools.verify_manifests
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m src.main --track t09 --pipeline src.baselines.consent_only --output out/baseline --run-name baseline --offline --seed 42
    .\.venv\Scripts\python.exe -m src.main --config configs/lab.yaml --track t09 --output out/poc --run-name poc --offline --seed 42

Then open out/poc/contact_sheet.html in a browser and out/poc/audit_checklist.md in the editor.
