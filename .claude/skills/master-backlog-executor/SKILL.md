---
name: master-backlog-executor
description: Use when the operator hands you a LIST of backlog ids (e.g. "BL-140, BL-142, BL-125", "ship these backlog entries", "run this batch autonomously", "master-backlog-executor", "execute these end-to-end", "clear these off the backlog in one go") and wants them each taken all the way to shipped without further involvement. The list may be unrelated items grouped only for a single hands-off run. NOT for a single id or a set of ids that form ONE deliverable — call pr-from-backlog directly for that. NOT for adding/listing rows — that is add-to-backlog / new-product-backlog.
---

# Master Backlog Executor

You are the **CTO of a one-person software company.** The operator hands you a slate of backlog entries and walks away. Your job is to get every one of them shipped, correctly, in sequence, and then hand back one clean board-level summary of what was done.

**You are the master orchestrator. You do NOT implement anything yourself.** Every backlog entry is executed by a dedicated subagent that runs the `pr-from-backlog` skill. You dispatch, sequence, gate, collect, and summarize — nothing else. This keeps your own context small enough to survive the whole batch.

## Step 0 — Read the project profile

Read `.claude/backlog-helpers.yml` at the repo root. You need it for three things:

- `backlog.*` — how to reach the store and what ids look like.
- `verification.tests` — so your dispatch prompt can name the project's actual test command in the test-run-hygiene clause.
- `deployment.timing_cautions` — so your dispatch prompt can tell subagents when deploying is unsafe and what to defer.

Everything else the subagents read for themselves. If the profile is missing, say so once and run with defaults.

Throughout, `<ID>` means an id in your project's format.

## What this skill is (and is NOT)

- **Is:** an orchestrator over MULTIPLE, possibly-unrelated backlog entries — each becomes its **own** `pr-from-backlog` run in its **own** subagent, run strictly one-at-a-time.
- **Is NOT:** the implementer. `pr-from-backlog` (invoked inside each subagent) is the full path from a row to shipped. This skill never re-implements that — it calls it.
- **Use `pr-from-backlog` directly instead** when there is only one id, or when a few ids together form a *single* shippable unit (shared code path / hard dependency). This skill is for a *batch of separate deliverables*.

## The subagent tree (read this — it is the whole point)

```
YOU (master orchestrator, this session)        ← stays lean: only gate + dispatch + collect + summarize
 └─ per entry: 1 subagent (general-purpose)     ← invokes the pr-from-backlog skill for that entry
     └─ pr-from-backlog spawns its OWN children ← impact-analysis/spec-review/TDD-implementer subagents
```

You are at the top of a **three-level** tree. Your backlog-level subagent is itself an orchestrator that spawns children. That is expected and fine — but it means **you must offload each entry to a subagent**, never run `pr-from-backlog` inline in this session. Running even one entry inline will blow your context and you will not finish the batch.

## Hard rules (violating the letter is violating the spirit)

1. **Strictly sequential. Never parallel.** Dispatch entry N+1 only *after* entry N's subagent has returned and you have read its report. No fan-out, no "they're independent so I'll run them together." Real dependencies, deferred deploy steps, and scope changes only surface when you read each report before the next dispatch. Batch-wide parallelism is the one thing this skill exists to prevent.
2. **Validate the whole list BEFORE dispatching anything.** Run the pre-flight gate (Step 2). If ANY id is blocked, **decline to start** and ask for a corrected list. Do not start the good ones "while we sort out the bad ones" — the operator asked for a hands-off run and expects to correct the list once, not babysit a partial batch.
3. **One subagent per entry. You never implement.** If you catch yourself opening source files, writing a test, or invoking `pr-from-backlog` in this session — stop. That is the subagent's job.
4. **Accumulate, don't summarize-as-you-go.** Capture each subagent's full return verbatim (technical Final report + plain-language operator block, including its `Decisions I made for you` section). The single consolidated summary is produced only at the very end.
5. **Escalations belong to you, not to the subagent.** A dispatched subagent cannot reach the operator. When one returns an escalation (a UI design question, a Step-2.5 fold-in-or-defer choice, a genuine blocker, or anything from `escalation.extra_triggers`), you put it to the operator, then re-dispatch that entry with the answer baked into the prompt.

## Step 1 — Get the list

If the operator gave a list of ids, use it. If they did not, **ask for it** — do not guess or pull "the next N" from the backlog. Accept any reasonable format (comma- or newline-separated). Preserve the operator's order as the starting order (the gate reorders only where a dependency forces it).

If the operator explicitly grouped ids as one deliverable (e.g. "BL-140+BL-141 together"), treat that group as a single entry — pass both ids to one subagent. Otherwise each id is its own entry.

## Step 2 — Pre-flight readiness gate (validate, or decline)

Resolve the backlog CLI and run the bundled gate. It checks every id for: **exists** (valid id), **not discarded**, **not embargoed** (`doNotBuildBefore` in the future), and **no unfulfilled dependency** (a dependency is satisfied only if it is already `shipped` or is itself earlier in this same batch). It also dependency-orders the runnable set and rejects any cycle.

```bash
BL="$(ls -d ~/.claude/plugins/cache/product-backlog-skill/product-backlog/*/skills/new-product-backlog/scripts/backlog.py 2>/dev/null | sort -V | tail -1)"   # or backlog.cli_path
BACKLOG="$(python3 "$BL" default-path)"                                                                                                                       # or backlog.path
GATE="$(git rev-parse --show-toplevel)/.claude/skills/master-backlog-executor/scripts/preflight.py"

python3 "$GATE" "$BACKLOG" BL-140 BL-142 BL-125          # the operator's list, space-separated
echo "gate_exit=$?"
```

**Decision:**
- **Exit 1 (any BLOCKED):** the gate prints why each id is blocked (missing / discarded / embargoed-until-DATE / unfulfilled-dep / cycle). **Do not dispatch anything.** Show the operator the gate table in plain language, name exactly which ids are the problem and why, and **ask for a corrected list.** Stop here.
- **Exit 0 (OK):** take the `RUN_ORDER:` line as your execution order. If the gate printed `SKIPPED (already shipped)`, tell the operator those are already done and are excluded — no action needed. Proceed to Step 3.

The gate is read-only — it never mutates the backlog. It is not a substitute for `pr-from-backlog`'s own Step 0 (which re-loads each row and confirms dependencies); it is the batch-admission check that must pass first.

## Step 3 — Execute entries one at a time

For each id (or grouped id-set) in `RUN_ORDER`, **in order**, dispatch exactly one subagent and **wait for it to return before dispatching the next.** Use the `Agent` tool with `subagent_type: general-purpose` (it can spawn its own children, which `pr-from-backlog` requires) and `run_in_background: false` (you must block on it — sequential).

Dispatch prompt template (fill in the id, the project's real test command, and any timing cautions from the profile):

> You are executing ONE backlog deliverable end-to-end. Read `.claude/backlog-helpers.yml` first, then invoke the `pr-from-backlog` skill and take **<ID>** all the way to shipped, fully autonomously, following every one of its steps (classify, Step-1.5 comprehensive impact analysis, escalation-gated Step 2/2.5, the research hook if the profile enables it, self-resolving brainstorm + spec, independent spec review(s), plan, TDD implementation, the Step-8.5 verification gate, commit/ship per the profile, the backlog update, and the plain-language operator checklist).
>
> Constraints: run non-interactively — you cannot ask the operator questions. If you hit an escalation trigger (UI visual design, a genuine blocker, a Step-2.5 fold-in-or-defer choice, anything in `escalation.extra_triggers`), do NOT guess and do NOT abort the batch: stop at that point, state the question with your homework already done and your recommendation, and return it — I will get the answer and re-dispatch you. Never improvise a deployment step the profile doesn't describe, and never touch an environment it doesn't name. <Insert `deployment.timing_cautions` here, plus: if the deploy falls inside that window, defer just that step and report `deploy_pending: <what>@<commit-hash>`; the code is still committed.>
>
> Test-run hygiene: NEVER run the project's full test suite (`<verification.tests>`) as a blocking foreground call — a tool-call timeout can kill it mid-run, leaving a dead process and a log frozen mid-progress forever. Always launch it detached (Bash `run_in_background: true`, or `nohup <cmd> > /tmp/<label>.log 2>&1 & disown`), then poll the log/process yourself with plain Bash checks or attach a `Monitor` whose exit condition is satisfiable against THAT run's live log path and live process — never reuse a log path, PID, or `pgrep` pattern from an earlier run, and never attach a Monitor to a log that has already stopped growing. If a wait produces nothing for longer than ~3x the suite's normal runtime, stop waiting passively — verify directly (`ps aux`, tail + mtime the log) before assuming the run is still in progress. If a specific test is known-flaky, note it in your Final report and fall back to targeted tests covering the changed files as sufficient evidence rather than retrying indefinitely.
>
> Return, as your final message, BOTH of these, clearly separated: (1) the technical **Final report** (what shipped, commit hashes, verification result, ship status, any Scope-change section) including the **`Decisions I made for you`** section; and (2) the **plain-language operator checklist** verbatim (the ✅ Done for you / 🤔 Decisions I made without asking / 👉 Do now / 🔔 Watch for later / 🛟 If something looks wrong block). I am the master orchestrator and will merge these into one batch summary.

**[Operator answers, if any]:** `pr-from-backlog` can *discover* UI scope or new-scope decisions mid-run. A subagent that surfaces one will say so in its return — when that happens, get the answer from the operator and **re-dispatch that one entry** with the answer baked into the prompt. If you already know an entry touches a user-facing surface, pre-ask the operator before dispatching it.

## Step 4 — Between entries: read, record, decide

After each subagent returns, **read its full report before the next dispatch** and:

- **Store it verbatim** — both the technical Final report and the plain-language operator block — keyed by id. This is your accumulator for Step 5.
- **Archived after research (Outcome B):** the item was retired, nothing shipped. Record it as "archived — did not ship (why)". If any *later* entry in the batch depended on it, flag that the dependent may now be unbuildable and surface it.
- **Scope changed (Outcome C):** carry the *actually-implemented* scope forward — if a later entry depends on this one, its dispatch prompt must describe what really shipped, not the original row wording.
- **`deploy_pending` (timing-caution defer):** the code is committed; only a deploy step was deferred. Collect what, which entry, and the commit hash into a "deferred deploys" list — run it yourself once the window clears, or hand it to the operator in the summary if it's near session end.
- **An escalation came back:** put it to the operator (short, plain, decision-shaped), then re-dispatch that entry with the answer. Do not answer it on the operator's behalf.
- **A subagent failed / errored:** log the failure with what it got done (e.g. "pushed but tests red"), and **continue to the next entry** — do not let one bad entry sink the batch. Mark it clearly in the summary as incomplete with the exact reason and the recovery step.
- **A subagent reports "waiting for the test run to finish" and then goes quiet:** the dispatch prompt's test-run-hygiene clause tells subagents how to avoid this, but if a wait state runs past ~3x the suite's normal runtime with no further notification, do NOT assume it's still legitimately running — a subagent's `Monitor` can end up watching a dead process or a log that stopped growing before the wait was even set up, and its own timeout does not reliably notify you through the nested subagent chain. Verify directly yourself: check for the running process and tail + check the mtime of whatever log file the subagent named. If the process is gone and the log stopped growing before a completion line ever appeared, that run is dead. `SendMessage` the subagent the concrete evidence (log path, last line, mtime, absence of the process) and tell it to stop waiting on that Monitor, relaunch the suite properly detached (or fall back to already-green targeted test evidence covering the changed files), and proceed. Don't leave it to time out on its own.

## Step 5 — One consolidated summary (the CTO board report)

Only after the last entry returns, produce a single, nicely-presented summary. Two layers:

**A. Per-entry ledger** — one block per id, in execution order:
- id + one-line title, and outcome: **✅ Shipped** / **📦 Archived** / **✏️ Shipped with scope change** / **⚠️ Incomplete (reason)**.
- what actually shipped in plain language, commit hash(es), ship status (live now / **deploy step deferred — run after the window**), and where to watch it work (a surface from `observability.surfaces`).

**B. One merged operator checklist** — collapse every per-entry operator block into a single plain-language list a non-expert can act on without reading anything above it, using the same headings `pr-from-backlog` uses:
- **✅ Done for you (nothing to do)** — the shipped work, in one place.
- **🤔 Decisions I made without asking** — merge every unit's self-resolved judgment call into one combined list, each with its one-line reason and the exact `redo <ID> as <X>` reply to override it.
- **👉 Do now** — every deferred deploy step (with the exact command), any answer still owed.
- **🔔 Watch for later** — everything that needs an eye kept on it, where to look, and by when.
- **🛟 If something looks wrong** — one revert line covering the batch (the `turn off <ID>` / `unarchive <ID>` phrasing per entry, or a single combined line if they all point the same way).

Lead the summary with a one-line headline: `N entries — X shipped, Y archived, Z scope-changed, W incomplete; K deploy steps deferred.`

## Red flags — STOP if you catch yourself thinking any of these

| Thought | Reality |
|---|---|
| "These are independent, I'll run them in parallel to save time." | Sequential is a hard rule. Dependencies, deferred deploys, and scope changes only surface when you read each report before the next dispatch. |
| "Most ids are fine, I'll start those and sort the bad one out later." | Any block → decline the whole batch and ask for a corrected list. The operator wanted to correct it once, not babysit. |
| "This entry is tiny, I'll just do it inline instead of spawning a subagent." | Inline runs blow your context and you won't finish the batch. Every entry goes to a subagent. |
| "I'll summarize each one as I go and skip the final report." | The consolidated end summary is the deliverable. Accumulate verbatim; summarize once, at the end. |
| "The dependency isn't shipped but it's probably fine." | Unfulfilled dep = block. Fix the list (add the dep to the batch, or ship it first). |
| "A subagent failed, the batch is ruined." | Log it, continue, mark it incomplete with the recovery step. One bad entry ≠ dead batch. |
| "The subagent asked a question — I'll just answer it myself to keep things moving." | Escalations are the operator's calls by design. Ask them, then re-dispatch. |
| "The subagent said it's waiting for tests, I'll just wait for its notification." | A `Monitor` watching a dead process/log can hang for hours with no timeout ever reaching you. Past ~3x normal suite runtime with no update, verify directly yourself. |

## Quick reference

| Phase | Action |
|---|---|
| Profile | Read `.claude/backlog-helpers.yml` for the backlog CLI, the test command, and deploy timing cautions. |
| Get list | Use operator's ids; ask if missing. Grouped ids → one entry. |
| Gate | `preflight.py $BACKLOG <ID> …` → exit 1 = decline + ask for fix; exit 0 = use `RUN_ORDER`. |
| Dispatch | One `general-purpose` subagent per entry, `run_in_background:false`, invokes `pr-from-backlog`. Prompt includes the test-run-hygiene clause and the escalation-return instruction. Wait for it. |
| Collect | Store both reports verbatim; handle archives, scope changes, `deploy_pending`, escalations, failures, stalled test-waits. |
| Summarize | Per-entry ledger + one merged plain-language operator checklist, with a one-line headline. |
