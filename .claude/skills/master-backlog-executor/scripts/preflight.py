#!/usr/bin/env python3
"""Pre-flight readiness gate for master-backlog-executor.

Given the product-backlog JSON and a list of backlog ids the operator wants
executed in one batch, classify each id and decide whether the batch may start.

Id format is whatever the store uses (BL-140, JIRA-871, ...); this script never
parses ids, it only looks them up.

A batch is DECLINED (exit 1) if ANY id is BLOCKED:
  - MISSING    : id not in the backlog (invalid id / typo)
  - DISCARDED  : status == discarded (retired item — nothing to build)
  - EMBARGOED  : doNotBuildBefore is a date in the future (soak/do-not-build-before gate)
  - UNFULFILLED: depends on an id that is not shipped AND not earlier in THIS batch

An id that is already `shipped` is not a block — it is SKIPPED (surfaced,
excluded from the run) so the operator knows it was already done.

READY ids are emitted in dependency-first order (in-batch dependencies run
before their dependents). A dependency cycle among the batch is a BLOCK.

Usage:
    preflight.py <backlog.json> <ID> <ID> <ID> ...

Read-only. Never mutates the backlog. Exit 0 = batch may start, 1 = decline.
"""

from __future__ import annotations

import json
import sys
from datetime import date


def load_items(path: str) -> dict[str, dict]:
    with open(path) as fh:
        doc = json.load(fh)
    items = doc["items"] if isinstance(doc, dict) else doc
    return {it["id"]: it for it in items}


def topo_order(ready: list[str], by_id: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Order `ready` so an id's in-batch dependencies come first.

    Returns (ordered, cycle_ids). cycle_ids is non-empty if a cycle blocks ordering.
    """
    ready_set = set(ready)
    ordered: list[str] = []
    placed: set[str] = set()
    # Deterministic: iterate in the caller's order, repeatedly placing any id
    # whose in-batch deps are all already placed.
    remaining = list(ready)
    progress = True
    while remaining and progress:
        progress = False
        still: list[str] = []
        for bid in remaining:
            deps_in_batch = [d for d in by_id[bid].get("dependencies", []) if d in ready_set]
            if all(d in placed for d in deps_in_batch):
                ordered.append(bid)
                placed.add(bid)
                progress = True
            else:
                still.append(bid)
        remaining = still
    return ordered, remaining  # `remaining` non-empty => cycle among these ids


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: preflight.py <backlog.json> <ID> <ID> ...", file=sys.stderr)
        return 2

    path = argv[1]
    batch = argv[2:]
    by_id = load_items(path)
    today = date.today().isoformat()
    batch_set = set(batch)

    verdicts: dict[str, tuple[str, str]] = {}  # id -> (state, reason)
    for bid in batch:
        it = by_id.get(bid)
        if it is None:
            verdicts[bid] = ("BLOCKED", "MISSING — no such id in the backlog (typo?)")
            continue
        status = it.get("status")
        if status == "discarded":
            verdicts[bid] = ("BLOCKED", "DISCARDED — item is retired, nothing to build")
            continue
        if status == "shipped":
            verdicts[bid] = ("SKIP", "already shipped — excluded from the run")
            continue
        dnbb = it.get("doNotBuildBefore")
        if dnbb and dnbb > today:
            verdicts[bid] = ("BLOCKED", f"EMBARGOED — doNotBuildBefore {dnbb} (today {today})")
            continue
        # Dependencies: satisfied if shipped, or present earlier-eligible in THIS batch.
        unmet = []
        for dep in it.get("dependencies", []):
            dep_item = by_id.get(dep)
            dep_shipped = dep_item is not None and dep_item.get("status") == "shipped"
            dep_in_batch = (
                dep in batch_set
                and verdicts.get(dep, ("", ""))[0] != "BLOCKED"
                and (dep_item is None or dep_item.get("status") != "discarded")
            )
            if not (dep_shipped or dep_in_batch):
                why = "missing" if dep_item is None else dep_item.get("status")
                unmet.append(f"{dep}({why})")
        if unmet:
            verdicts[bid] = ("BLOCKED", "UNFULFILLED dep(s): " + ", ".join(unmet))
            continue
        verdicts[bid] = ("READY", "")

    ready = [b for b in batch if verdicts[b][0] == "READY"]
    ordered, cycle = topo_order(ready, by_id)
    for c in cycle:
        verdicts[c] = ("BLOCKED", "DEPENDENCY CYCLE among the batch — cannot order")
    ready = ordered

    blocked = [b for b in batch if verdicts[b][0] == "BLOCKED"]
    skipped = [b for b in batch if verdicts[b][0] == "SKIP"]

    # Human-readable table
    print("Pre-flight readiness gate")
    print("=" * 60)
    for bid in batch:
        state, reason = verdicts[bid]
        icon = {"READY": "✅", "SKIP": "⏭️ ", "BLOCKED": "⛔"}[state]
        line = f"{icon} {bid:<8} {state}"
        if reason:
            line += f" — {reason}"
        print(line)
    print("=" * 60)

    if blocked:
        print(f"DECLINE: {len(blocked)} blocked id(s): {' '.join(blocked)}")
        print("Fix the list above and re-run the gate before starting the batch.")
        return 1

    print(f"RUN_ORDER: {' '.join(ready)}")
    if skipped:
        print(f"SKIPPED (already shipped): {' '.join(skipped)}")
    print(f"OK: {len(ready)} ready to execute, {len(skipped)} skipped, 0 blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
