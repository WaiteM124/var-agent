#!/usr/bin/env python3
"""Run the offline deterministic eval suite and gate against baseline.json.

No Azure credentials or LangChain are required. Exit codes:

* 0 — all cases ran and pass-rates meet ``evals/baseline.json``
* 1 — one or more regressions below baseline (or a case raised unexpectedly)
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.harness import (  # noqa: E402
    BASELINE_PATH,
    RESULTS_PATH,
    compare_to_baseline,
    load_case_files,
    run_case,
    summarise,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_PATH,
        help="Where to write results.json (default: evals/results.json)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="Baseline floors (default: evals/baseline.json)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite baseline.json from this run's pass-rates (use deliberately)",
    )
    args = parser.parse_args(argv)

    cases = load_case_files()
    if not cases:
        print("No eval cases found under evals/cases/", file=sys.stderr)
        return 1

    results: list[dict] = []
    for case in cases:
        try:
            results.append(run_case(case))
        except Exception as exc:  # noqa: BLE001 — surface per-case failures in results
            results.append(
                {
                    "id": case.get("id", "<unknown>"),
                    "label": case.get("label", "error"),
                    "kind": case.get("kind", "error"),
                    "pass": False,
                    "detail": {"error": str(exc), "traceback": traceback.format_exc()},
                }
            )

    summary = summarise(results)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "offline",
        "summary": summary,
        "cases": results,
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"evals: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']:.1%})")
    for label, rate in summary["by_label"].items():
        print(f"  {label}: {rate:.1%}")
    if summary["failed_ids"]:
        print("failed:", ", ".join(summary["failed_ids"]))
    print(f"wrote {args.results}")

    if args.update_baseline:
        baseline = {
            "version": 1,
            "min_pass_rate": 1.0,
            "by_label": {label: 1.0 for label in summary["by_label"]},
            "notes": "Offline floors. Do not lower to green CI without an ADR note.",
        }
        # Keep floors at 1.0 when the suite is fully green; otherwise mirror observed rates.
        if summary["pass_rate"] < 1.0:
            baseline["min_pass_rate"] = summary["pass_rate"]
            baseline["by_label"] = dict(summary["by_label"])
        args.baseline.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"updated baseline {args.baseline}")
        return 0 if summary["failed"] == 0 else 1

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    regressions = compare_to_baseline(summary, baseline)
    if regressions:
        print("baseline regressions:", file=sys.stderr)
        for line in regressions:
            print(f"  - {line}", file=sys.stderr)
        return 1
    if summary["failed"]:
        # Baseline floors met numerically but individual cases failed — still fail the gate.
        print("cases failed even though aggregate floors were met", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
