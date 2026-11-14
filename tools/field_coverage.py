"""Every field in the case files must be read, aliased, or declared unused.

This is the check that would have caught the defect fixed in policy 1.1.0: CASE-06 carried
li_assessment_done and CASE-10 carried lia_done, the same fact under two names, and no rule read
either. A field nobody reads is invisible to the rules AND to the human reviewing the queue, so it
is a silent hole rather than a visible gap.

    python -m tools.field_coverage                 exit 0 when every field is accounted for
    python -m tools.field_coverage --policy X.yaml --cases DIR

Exit codes: 0 all fields accounted for, 1 unaccounted fields found, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

DEFAULT_POLICY = "configs/policy/privacy_policy_v1.yaml"
DEFAULT_CASES = "fixtures/t09_privacy_gate/cases"
ALWAYS_READ = {"case_id", "market", "ambiguity_notes"}   # read by the engine itself, not by a rule


def flatten(obj: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for key, value in obj.items():
        path = f"{prefix}{key}"
        out.add(path)
        if isinstance(value, dict):
            out = out.union(flatten(value, path + "."))
    return out


def fields_in_rules(node, acc: set[str]) -> set[str]:
    if isinstance(node, dict):
        if "field" in node:
            acc.add(str(node["field"]))
        for value in node.values():
            fields_in_rules(value, acc)
    elif isinstance(node, list):
        for value in node:
            fields_in_rules(value, acc)
    return acc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", default=DEFAULT_POLICY)
    ap.add_argument("--cases", default=DEFAULT_CASES)
    a = ap.parse_args(argv)

    policy_path, cases_dir = Path(a.policy), Path(a.cases)
    if not policy_path.is_file() or not cases_dir.is_dir():
        print(f"[field_coverage] need a policy file and a cases folder: {policy_path}, {cases_dir}", file=sys.stderr)
        return 2
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}

    present: dict[str, list[str]] = {}
    files = sorted(cases_dir.glob("CASE-*.json"))
    if not files:
        print(f"[field_coverage] no case files under {cases_dir}", file=sys.stderr)
        return 2
    for f in files:
        case = json.loads(f.read_text(encoding="utf-8"))
        for path in flatten(case):
            present.setdefault(path, []).append(case.get("case_id", f.stem))

    read = fields_in_rules(policy.get("rules", []), set()).union(ALWAYS_READ)
    aliases = policy.get("field_aliases") or {}
    alias_sources = {str(name) for names in aliases.values()
                     for name in (names if isinstance(names, list) else [names])}
    declared_unused = set((policy.get("fields_not_used") or {}).keys())

    def accounted(path: str) -> bool:
        if path in read or path in alias_sources or path in declared_unused:
            return True
        # a container counts as read when at least one of its leaves is read
        return any(r.startswith(path + ".") for r in read)

    gaps = {p: c for p, c in present.items() if not accounted(p)}
    print(f"[field_coverage] policy {policy.get('policy_version')} | {len(files)} cases | "
          f"{len(present)} field paths | {len(read)} read by rules | {len(alias_sources)} alias sources | "
          f"{len(declared_unused)} declared unused")
    if gaps:
        print("[field_coverage] NOT ACCOUNTED FOR - a rule must read it, or declare it in "
              "field_aliases or fields_not_used:")
        for path, cases in sorted(gaps.items()):
            print(f"  {path}  (in {', '.join(cases)})")
        return 1
    print("[field_coverage] OK: every field is read, aliased, or declared unused with a reason")
    return 0


if __name__ == "__main__":
    sys.exit(main())
