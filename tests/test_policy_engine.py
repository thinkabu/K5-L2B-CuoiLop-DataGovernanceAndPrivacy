"""Tests the G07 group owns: the rule engine behind T09.

Two halves, as the rubric asks. The success half proves the engine reaches the
decision we claim, on the real fixture cases. The failure half proves that a bad
rule file stops the run instead of quietly scoring nothing, which is the failure
mode that would make every number in the report meaningless.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.policy.engine import evaluate_case, get_field, load_policy

POLICY_PATH = Path("configs/policy/privacy_policy_v1.yaml")
CASES_DIR = Path("fixtures/t09_privacy_gate/cases")


@pytest.fixture(scope="module")
def policy():
    return load_policy(POLICY_PATH)


def case(**over):
    """A minimal clean case; each test breaks exactly one thing."""
    base = {
        "case_id": "CASE-TEST", "market": "EU", "purpose": "ADAS model training",
        "data_types": ["exterior_video"], "lawful_basis": "legitimate_interest",
        "consent": {"obtained": False, "granular": False, "withdrawable": False, "record_available": False},
        "notice_given": True,
        "storage": {"raw_retained": False, "location": "on_device", "encryption_at_rest": True},
        "transfer": {"cross_border": False, "destination": None, "mechanism": None,
                     "transfer_impact_assessment": False},
        "retention_days": 90, "dpia_done": True, "minors_possible": False,
        "anonymization": "blur_on_edge_before_upload", "ambiguity_notes": "",
        # Policy 1.1.0 onward: an EU or SG legitimate-interest case is only clean once the
        # balancing test is on file, so the baseline case carries it.
        "lia_done": True,
    }
    base.update(over)
    return base


def write_policy(tmp_path: Path, lines: list) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ------------------------------------------------------------------ success path
def test_clean_eu_case_passes_the_gate(policy):
    v = evaluate_case(case(), policy)
    assert v.decision == "GO"
    assert v.reason_codes == ["NO_GAP_FOUND"]


def test_every_fixture_case_gets_a_decision_and_a_reason(policy):
    files = sorted(CASES_DIR.glob("CASE-*.json"))
    assert len(files) == 12, "fixture should hold 12 cases"
    for f in files:
        v = evaluate_case(json.loads(f.read_text(encoding="utf-8")), policy)
        assert v.decision in {"GO", "HOLD", "REWORK"}
        assert v.reason_codes, f"{v.case_id} has a decision but no reason code"
        if v.decision != "GO":
            assert v.rule_ids, f"{v.case_id} is blocked by no named rule"


def test_cross_border_without_a_mechanism_is_held(policy):
    v = evaluate_case(case(transfer={"cross_border": True, "destination": "non-adequate third country",
                                     "mechanism": None, "transfer_impact_assessment": False}), policy)
    assert v.decision == "HOLD"
    assert "XBORDER_NO_MECHANISM" in v.reason_codes
    assert "R-XB-01" in v.rule_ids


def test_hold_beats_rework_in_precedence(policy):
    """Unbounded retention alone is REWORK; add a missing DPIA and the case must HOLD."""
    rework_only = evaluate_case(case(retention_days=None), policy)
    assert rework_only.decision == "REWORK"
    both = evaluate_case(case(retention_days=None, dpia_done=False), policy)
    assert both.decision == "HOLD"
    assert {"RETENTION_UNBOUNDED", "DPIA_MISSING"}.issubset(set(both.reason_codes))


def test_future_obligation_is_a_note_not_a_breach(policy):
    """R-IN-01 binds on 2027-05-13, so an Indian case today carries a note, not a block."""
    consented = {"obtained": True, "granular": True, "withdrawable": True, "record_available": True}
    v = evaluate_case(case(market="IN", lawful_basis="consent", consent=consented), policy)
    assert v.decision == "GO"
    assert any("DPDP_CORE_OBLIGATIONS" in u for u in v.upcoming_obligations)
    later = evaluate_case(case(market="IN", lawful_basis="consent", consent=consented), policy,
                          as_of="2027-06-01")
    assert later.decision == "HOLD", "once the date passes the same rule must block"


def test_ambiguity_escalates_but_a_future_date_note_does_not(policy):
    legal = evaluate_case(case(ambiguity_notes="Vendor contract unclear whether vendor is processor."), policy)
    assert legal.decision == "HOLD"
    assert "AMBIGUOUS_NEEDS_LEGAL" in legal.reason_codes
    upcoming = evaluate_case(case(ambiguity_notes="DPDP Act 2023: core obligations apply from 13/05/2027."), policy)
    assert upcoming.decision == "GO"
    assert any("UPCOMING_OBLIGATION" in u for u in upcoming.upcoming_obligations)


def test_legitimate_interest_without_an_assessment_is_held(policy):
    """The gap an external reviewer found in policy 1.0.0: nothing read the assessment field."""
    eu = evaluate_case(case(lia_done=False), policy)
    assert eu.decision == "HOLD"
    assert "LIA_MISSING" in eu.reason_codes
    assert "R-EU-04" in eu.rule_ids
    sg = evaluate_case(case(market="SG", lia_done=False), policy)
    assert sg.decision == "HOLD"
    assert "R-SG-02" in sg.rule_ids
    missing_entirely = case()
    del missing_entirely["lia_done"]
    assert evaluate_case(missing_entirely, policy).decision == "HOLD", \
        "an absent field must not read as an assessment that was done"


def test_the_other_spelling_of_the_assessment_field_is_accepted(policy):
    """CASE-06 writes li_assessment_done, CASE-10 writes lia_done. Same fact, so same outcome."""
    other = case(market="SG")
    del other["lia_done"]
    other["li_assessment_done"] = True
    v = evaluate_case(other, policy)
    assert v.decision == "GO"
    assert v.normalisations == ["li_assessment_done->lia_done"]
    assert "R-SG-02" not in v.rule_ids


def test_the_canonical_field_wins_over_an_alias(policy):
    """An explicit lia_done: false must not be overwritten by a stale alias saying true."""
    both = case(market="SG", lia_done=False)
    both["li_assessment_done"] = True
    v = evaluate_case(both, policy)
    assert v.decision == "HOLD"
    assert "LIA_MISSING" in v.reason_codes
    assert v.normalisations == []


def test_market_outside_the_policy_is_escalated_not_released(policy):
    v = evaluate_case(case(market="BR"), policy)
    assert v.decision == "HOLD"
    assert "MKT-00" in v.rule_ids


def test_every_case_field_is_accounted_for():
    """The coverage gate from tools/field_coverage.py, run as part of the suite.

    Policy 1.0.0 shipped with a field no rule read, which is how CASE-06 passed for the wrong
    reason. Keeping the gate in pytest means a new fixture field, or a renamed one, breaks the
    build instead of quietly widening that hole again.
    """
    from tools.field_coverage import main as coverage_main
    assert coverage_main([]) == 0


def test_get_field_reads_nested_paths_and_tolerates_gaps():
    c = case()
    assert get_field(c, "transfer.cross_border") is False
    assert get_field(c, "storage.location") == "on_device"
    assert get_field(c, "transfer.nothing_here") is None
    assert get_field(c, "retention_days.deeper") is None


def test_missing_retention_does_not_crash_a_numeric_rule(policy):
    """R-RET-02 compares retention_days with 365: a null must not raise, and must not fire it."""
    v = evaluate_case(case(retention_days=None), policy)
    assert "R-RET-02" not in v.rule_ids
    assert "R-RET-01" in v.rule_ids


# ------------------------------------------------------------------ failure path
def test_rule_without_a_source_is_rejected(tmp_path):
    p = write_policy(tmp_path, [
        "policy_version: test-0.1",
        "rules:",
        "  - id: R-NO-SRC",
        "    decision: HOLD",
        "    reason_code: NO_LAWFUL_BASIS",
        "    all:",
        "      - {field: lawful_basis, op: eq, value: unknown}",
    ])
    with pytest.raises(ValueError, match="source"):
        load_policy(p)


def test_unknown_operator_is_rejected(tmp_path):
    p = write_policy(tmp_path, [
        "policy_version: test-0.1",
        "rules:",
        "  - id: R-BAD-OP",
        "    decision: HOLD",
        "    reason_code: NO_LAWFUL_BASIS",
        "    source: {doc: test, ref: test}",
        "    all:",
        "      - {field: lawful_basis, op: sounds_like, value: unknown}",
    ])
    with pytest.raises(ValueError, match="unknown operator"):
        load_policy(p)


def test_duplicate_rule_id_is_rejected(tmp_path):
    rule = ["  - id: R-DUP", "    decision: HOLD", "    reason_code: MINORS",
            "    source: {doc: test, ref: test}", "    all:",
            "      - {field: minors_possible, op: is_true}"]
    p = write_policy(tmp_path, ["policy_version: test-0.1", "rules:"] + rule + rule)
    with pytest.raises(ValueError, match="duplicate rule id"):
        load_policy(p)


def test_policy_without_a_version_is_rejected(tmp_path):
    p = write_policy(tmp_path, [
        "rules:",
        "  - id: R-X",
        "    decision: HOLD",
        "    reason_code: MINORS",
        "    source: {doc: test, ref: test}",
        "    all:",
        "      - {field: minors_possible, op: is_true}",
    ])
    with pytest.raises(ValueError, match="policy_version"):
        load_policy(p)


def test_rule_without_any_condition_is_rejected(tmp_path):
    p = write_policy(tmp_path, [
        "policy_version: test-0.1",
        "rules:",
        "  - id: R-EMPTY",
        "    decision: HOLD",
        "    reason_code: MINORS",
        "    source: {doc: test, ref: test}",
    ])
    with pytest.raises(ValueError, match="all/any/none"):
        load_policy(p)


def test_bad_effective_date_is_rejected_at_evaluation(tmp_path):
    p = write_policy(tmp_path, [
        "policy_version: test-0.1",
        "rules:",
        "  - id: R-BAD-DATE",
        "    decision: HOLD",
        "    reason_code: MINORS",
        "    effective_date: 13-05-2027",
        "    source: {doc: test, ref: test}",
        "    all:",
        "      - {field: minors_possible, op: is_true}",
    ])
    pol = load_policy(p)
    with pytest.raises(ValueError, match="expected yyyy-mm-dd"):
        evaluate_case(case(minors_possible=True), pol)
