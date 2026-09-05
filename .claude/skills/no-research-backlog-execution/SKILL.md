---
name: no-research-backlog-execution
description: NO-RESEARCH variant of semiauto-backlog-execution — take ONE product-backlog item (an id, or a small set of ids that form a single shippable unit) all the way to shipped, with the same human-in-the-loop front half / autonomous back half split, but with the domain-research hook removed entirely — no corpus search, no commissioned research, no premise-verification fork, no domain-expert spec review. Use when the item is engineering-heavy or simple, or when any needed subject-matter grounding already happened before the item was added to the backlog. Everything else matches semiauto-backlog-execution exactly — Steps 0–1 (load, classify) run autonomously; Step 1.5 (comprehensive impact analysis, folding UI/config/schema/jobs/telemetry into one atomic vertical wedge) ALWAYS runs and surfaces any proposed deferral to the operator; the superpowers:brainstorming interview runs INTERACTIVELY; autonomous execution begins the moment the operator answers the last brainstorming question and runs unattended through spec-writing (no approval gate), the technical-architect spec review (always runs), the plan, subagent-driven TDD, the verification gate, commit/ship per the project profile, the backlog update, and the plain-language operator checklist. If mid-session the item turns out to hinge on a subject-matter question the codebase cannot settle, this skill STOPS rather than guessing. Use when the user says "no-research-backlog-execution", "no research backlog", "skip the research", or asks to implement a backlog item without subject-matter grounding. Do NOT use it merely to ADD or LIST backlog items — that is add-to-backlog / new-product-backlog.
---

# No-Research Backlog Execution

Turn one backlog row (or a small cluster of rows that together form a single shippable unit) into shipped, deployed code — with a **human-in-the-loop front half** (an upfront comprehensive impact analysis and an interactive brainstorming interview) and an **autonomous back half** that starts the instant the operator answers the last brainstorming question (write the spec → review → plan → implement → ship). The impact analysis (Step 1.5) is what makes each unit an **atomic vertical wedge** — a change that works end-to-end in production on its own, with every impacted surface folded in.

**This is the no-research counterpart of `semiauto-backlog-execution`.** It is identical to that skill **except that it never performs domain research**:

- **No research phase** — no corpus search, no commissioned research, no external grounding pass.
- **No premise-verification fork** — that step exists to check the backlog item's premise against research findings. With no research to check it against, it's gone.
- **No domain-expert spec review** — the brainstorming interview and the spec review both proceed on engineering judgment and codebase convention alone; only the technical-architect review runs.

Everything else — the front-half/back-half split, the Step-1.5 impact analysis, the interactive interview, the autonomous spec write with no approval gate, the technical-architect review, TDD implementation, the verification gate, shipping, and backlog bookkeeping — is unchanged.

**Use this when the item doesn't hinge on subject-matter judgment** — engineering-heavy or simple work, or an item whose domain question was already settled before it was added to the backlog (check `notes`/`artifacts` in Step 0). **If you discover mid-session that the item's correctness is a subject-matter question the codebase cannot settle — stop.** Tell the operator plainly, and either hand off to `semiauto-backlog-execution` (if that project has enabled its research hook) or ask the operator for the domain answer directly. Shipping a domain decision on a guess is the failure this guard exists to prevent.

## Step -1 — Read the project profile (do this first, every run)

Read `.claude/backlog-helpers.yml` at the repo root and hold it in context for the whole run. It is the single source of everything project-specific:

| Profile key | Governs |
|---|---|
| `backlog.*` | how to reach the store, what ids look like |
| `artifacts.*` | where specs and plans get written |
| `verification.*` | the Step-6.5 gate — the exact commands, and the safety-critical paths you hand-read |
| `impact_surfaces` | project-specific layers added to the Step-1.5 checklist |
| `deployment.*` | Step 7 — how shipped work reaches its running environment, and how to undo it |
| `observability.surfaces` | where the operator can see the feature working |
| `operator.*` | how plain the Step-10 checklist must be, and the reply phrases |
| `project.*` | branch, push policy, commit trailer |

The `research.*` block is **ignored by this skill** — by design.

**If a field is empty, use the documented default in the relevant step — never invent a command or a deploy procedure.** If the profile file is missing entirely, say so once at the start, run with all defaults, and note it in the Final report.

Throughout, `<ID>` means an id in your project's format (see `backlog.id_prefix`).

## What "one unit" means here

A unit is **one coherent shippable thing**, identified by one or more ids from the `new-product-backlog` store. Multiple ids belong in the same unit only when they share a code path or a hard dependency. When given several ids, treat them as ONE unit and implement them together in dependency order.

If you were given a whole *batch* to run one-at-a-time, read **"Orchestrating a batch"** at the bottom first.

## Backlog store & CLI (read once)

The backlog is a strict, schema-validated JSON file owned by the **`new-product-backlog`** skill. **It is mutated ONLY through that skill's Python CLI** — never hand-edit the JSON. Resolve the CLI and the file once, then reuse them for every read/write this skill does directly:

```bash
BL="$(ls -d ~/.claude/plugins/cache/product-backlog-skill/product-backlog/*/skills/new-product-backlog/scripts/backlog.py 2>/dev/null | sort -V | tail -1)"   # or backlog.cli_path
BACKLOG="$(python3 "$BL" default-path)"                                                                                                                       # or backlog.path
```

The status vocabulary is `pending | shipped | discarded` (plus `new`); there are real `priority`, `dependencies`, `doNotBuildBefore`, `artifacts`, and `notes` fields. The batch-analysis backlog update at **Step 8** invokes the `new-product-backlog` *skill*; the direct row reads/edits in Steps 0 and 1.5 call the CLI as shown.

## Step 0 — Load the work

Read the target item(s) from the store via the CLI — `python3 "$BL" get "$BACKLOG" <ID>` (JSON). Extract: the `name`/`description`, `priority`, `dependencies`, `doNotBuildBefore`, `notes`, and any linked `artifacts` (an existing spec/plan/findings doc, source files, prior review notes). If an item links a spec or plan that already exists, you are *extending* the design, not starting cold — open it. **If `notes` or `artifacts` cite prior domain research**, that's exactly the "already settled" case this skill is for — note the citation so it can inform the spec, but don't re-run anything.

Confirm the dependencies are satisfied (shipped). If a hard dependency is still pending, stop and say so.

## Step 1 — Classify complexity (drives model choice in Step 6)

Judge whether this unit is **complex** (multi-component, intricate state, irreversible-ish, on a safety-critical path) or **simple** (a reword, a flag, a contained refactor, an additive event). Hold this in context — Step 6 uses it to pick Sonnet vs Opus per task.

**This skill assumes no subject-matter grounding is needed.** If, while loading the item or during the impact analysis, you find the item turns on a domain question that the codebase and its conventions cannot settle — and it has **not** already been settled — **stop.** Tell the operator this item needs grounding and this is the wrong skill for it. Don't guess at domain correctness.

## Step 1.5 — Comprehensive impact analysis (ALWAYS — this is the anti-regression gate)

Before you brainstorm anything, map the **full production blast radius** of this change. This step is why the unit ends up atomic. **The recurring failure it exists to kill:** shipping a change that is correct in isolation but *incomplete in production* — a new config knob with no UI to set it, a new field no report surfaces, a schema change with no migration, a changed default that silently breaks a distant caller — so the "done" unit still needs follow-up work before it's actually usable, and meanwhile an untraced surface regresses. Missing an impacted area is the more dangerous, more common error than a slightly larger unit.

**The goal is a vertical wedge:** ONE self-contained unit that delivers a working outcome end-to-end and depends on **no** later work to be useful in production.

**Trace every layer — don't reason from memory, follow the code.** For each symbol, config key, route, table, or function this unit touches, follow every **read and write** across the tree: grep/read the code, and spawn `Explore` / `general-purpose` subagents for breadth when the surface is wide (fan them out in parallel). Walk this checklist **explicitly** and record, for each line, one of `impacted → fold in` / `not impacted` / `already covered`:

- **Config & settings** — new/changed configuration? Trace the typed field/default, every environment's config file, validation, and any env-var plumbing.
- **UI / operator surfaces** — is there a screen, form, CLI flag, or read-only display where a human sets or sees this? **A setting a human is meant to control almost always has — or needs — a control surface. If one exists for the thing you're changing, updating it is IN-SCOPE, not a follow-up** (this is the canonical miss).
- **Data model / persistence / migration** — columns, rows, on-disk state. A new persisted field needs its write path, its read path, AND any migration/backfill for existing rows.
- **Callers & downstream consumers** — every place that reads the value or calls the function you changed. A changed default, shape, or units can break a distant consumer that isn't in the diff — that consumer is in-scope.
- **Scheduled / background work** — does a cron, queue worker, or scheduled job need new args, a new schedule, env, or a whole new job for this to actually run?
- **Observability** — will a human be able to *see it working*? Check `observability.surfaces` in the profile. If the feature isn't observable through an existing surface, **fold the telemetry into this unit**.
- **Tests** — the test surfaces every folded-in area needs.
- **Docs** — user-facing docs and the backlog row itself (below).
- **Everything in `impact_surfaces`** from the project profile — walk each entry by name and check its `where` path.

This checklist is the **floor, not the ceiling** — trace anything else the change reaches.

**Fold in by default; a deferral is an operator decision.** Apply **Scope discipline** (bottom of this skill): every impacted area needed to make the change complete gets **folded into THIS unit**. The ONLY carve-out is scope that is BOTH very large AND very complex. Any area you propose to defer is **SURFACED to the operator for their OK** — never dropped silently.

**Record the expanded scope in the backlog.** Append an `Impact-Expanded Scope` note to the item's `notes` via the CLI, with today's date. Read-modify-write so nothing is lost:

```bash
OLD="$(python3 "$BL" get "$BACKLOG" <ID> | python3 -c 'import json,sys;print(json.load(sys.stdin)["notes"])')"
python3 "$BL" edit "$BACKLOG" <ID> --notes "${OLD}
Impact-Expanded Scope (<currentDate>): folding in <UI / config / schema / jobs / telemetry / callers / tests …>."
```

**Carry it into brainstorming.** The impact-expanded scope is the authoritative brief for Step 3.

## Step 2 — Autonomy posture (semi-auto: interactive front half, autonomous back half)

There are **two phases**, split at the **end of the Step-3 brainstorming interview**:

> **The handover point is the operator's answer to the LAST brainstorming question.** The moment that answer lands, say so in one line (e.g. *"That's everything I need — going autonomous from here; I'll write the spec and ship it."*) and **stop asking**. Writing the spec is the first act of the autonomous half, not the last act of the interactive one — there is **no spec-approval gate**.

- **Front half — Steps 0 through the end of the Step-3 interview: human-in-the-loop where there is a judgment call.**
  - Steps 0–1 (load, classify) the agent does on its own.
  - **Step 1.5 (impact analysis):** the agent maps the full blast radius and folds impacted surfaces into scope autonomously, but **surfaces any DEFERRAL** to the operator for their OK.
  - **Step 3 (brainstorming INTERVIEW):** run the question-and-answer part **INTERACTIVELY** — ask the operator the design questions as normal, anchored on the codebase's own conventions and the backlog row's intent. You decide nothing silently while questions remain.
- **Back half — from the operator's final brainstorming answer onward: fully AUTONOMOUS.** Write the spec from their answers (announce the path in one line; do NOT present it for approval and do NOT wait), run the Step-4 technical-architect review and **fold its findings silently**, write the plan, implement (subagent-driven TDD), run the verification gate, commit and ship, update + commit the backlog, print the operator checklist. Only stop in this half if you are genuinely blocked or hit an irreversible-and-unguessable decision.

**Exception — UI work.** If the scope includes a user-facing surface, the design questions are already interactive here (front half), so talk through layout and visuals with the operator and use the **`frontend-design`** skill. Once it and the rest of the questions are answered, everything from the spec write onward runs autonomously.

## Step 3 — Brainstorm the spec: INTERACTIVE interview, then autonomous spec write

Use **superpowers:brainstorming** to produce the spec. Run its **question-and-answer interview interactively, the way it is designed**: ask the operator clarifying questions one at a time and present approaches. This is the heart of the semi-auto front half. **Do NOT resolve the design questions silently while questions remain.**

**The interview is the ONLY interactive part of this step.** The moment the operator answers your last question, the front half is over: say so in one line, then **write the spec yourself and keep going** — no presenting it for review, no approval gate, no further questions.

**Brainstorm the impact-expanded scope, not the original slice.** Open the session by showing the operator the **Step-1.5 impact map** — what you traced, the surfaces you're folding in, and anything you propose to defer — so the interactive design covers the **whole vertical wedge**. The unit you spec here must be usable in production on its own, with no dependent follow-up; if brainstorming surfaces a further impacted surface, fold it in and re-map. The operator can veto or adjust the folded-in scope here.

**Decide collaboratively, anchored on the codebase's own conventions and the backlog row's intent** — this skill consults no external corpus, so there is no citation to nudge with. Present 2–3 realistic options per open question, name the trade-off in one line, and mark your recommendation. If a domain question comes up that you can't decide on convention alone, that's the Step-1 guard firing: stop rather than guessing. Surface the genuinely open engineering choices; don't manufacture questions where the convention is obvious.

**The operator may not be a software expert** (`operator.expertise`) — keep every question decidable by a non-expert: plain words, concrete options, the consequence of each spelled out.

### Step 3b — Write the spec (AUTONOMOUS — this is where hands-off execution begins)

As soon as the last question is answered, **write the spec to `artifacts.specs_dir` yourself and commit it** — that committed spec is the unit's durable design record. **Skip the brainstorming skill's `user-reviews-the-written-spec` gate**: do not paste the spec for approval and do not wait for a reply. Announce it in one line only — e.g. *"Spec written to `<path>` — going autonomous from here."* — and continue straight into Step 4.

Write the spec faithfully from what the operator actually decided in the interview. Anything they did NOT decide, you now resolve yourself, grounded in the codebase's conventions — **do not come back with another question** unless you are genuinely blocked or facing an irreversible-and-unguessable decision. From here the spec is **locked from the operator's side**.

## Step 4 — Technical-architect spec review *(always)*

Spawn an **Opus** subagent as an expert **Technical Architect (Software Engineering + DevOps)**. Have it independently review the spec for architecture, correctness, testability, failure modes, deploy/rollback safety, and fit with the existing codebase. This runs for **every** unit, including simple ones — it is the sole spec review in this variant, since there is no domain-expert pass. Give it the spec path **and** the source files it touches so it reviews against real code, not just prose. Fold its findings into the spec.

**Verify the substance, not the line numbers.** Architect findings are high-value, but its cited `file:line` references can be approximate. Before folding a finding in, confirm the underlying claim against the actual source (grep/read the symbol it names); adopt the substance, correct the locator.

## Step 5 — Write the plan (autonomous)

Write the implementation plan yourself with **superpowers:writing-plans**, into `artifacts.plans_dir`.

## Step 6 — Implement (superpowers:subagent-driven-development, autonomous)

Execute the plan with **superpowers:subagent-driven-development** in autonomous mode. Choose the model per task difficulty: **Sonnet for simpler tasks, Opus for complex ones** (intricate state, anything on a safety-critical path from the profile).

**Do NOT re-run the suite after each individual task.** `subagent-driven-development` already practices TDD, so each task lands verified; re-verifying per task burns orchestrator context for no new information. Take the implementer's per-task result at face value and move to the next task. Verification happens **once**, in Step 6.5, after every task in the plan is done.

## Step 6.5 — Pre-ship verification (ONCE, after ALL tasks are complete)

After the last task reports done — and before you commit in Step 7 — the orchestrator runs the full gate itself, one time (the `verification-before-completion` discipline):

- **Run every non-empty command in `verification`** — `tests`, `lint`, `format_check`, `typecheck`, `build`, then each entry in `extra`, in that order. Run them as CI would (whole-tree, not per-file). **Read the actual output**, not just the exit code.
- **Hand-read the diff of every path in `verification.safety_critical_paths`** and check it against the spec's intended behavior.
- If `verification` is entirely empty, say so explicitly in the Final report rather than implying a gate ran, and at minimum run the project's obvious test command if one is discoverable from its manifest.

**Long-running suites:** never run a multi-minute suite as a blocking foreground call — a tool-call timeout can kill it mid-run and leave a frozen log. Launch it detached (`run_in_background: true`, or `nohup … > /tmp/<label>.log 2>&1 & disown`) and poll that run's own live log path. Never reuse a log path or PID from an earlier run.

If anything is red, dispatch a fix subagent, then re-run this step. Only proceed to Step 7 once you've seen it green with your own eyes.

## Step 7 — Commit, push, ship

1. **Commit**, following `project.push_policy`:
   - `auto` — commit and push to `project.primary_branch` without asking.
   - `ask` — commit, then ask the operator before pushing.
   - `branch` — work on a feature branch, push it, and open a PR (use **superpowers:finishing-a-development-branch**).

   Append `project.commit_trailer` if the profile sets one.

2. **Ship it, per `deployment.procedure` in the project profile.** Follow those instructions literally.
   - **Respect `deployment.timing_cautions`.** If the current moment falls inside a stated unsafe window, do what the caution says instead.
   - **Confirm it landed** with `deployment.verify` if the profile provides a command.
   - **If `deployment.procedure` is empty**, "shipped" means **committed and pushed** — nothing more. Say exactly that in the Final report rather than implying a deployment happened.
   - **Never** improvise a deployment the profile doesn't describe, and never touch an environment the profile doesn't name.

3. **Rollout.** Follow `deployment.rollout_notes` if the profile sets a convention. **If it's empty, ship the feature ON.**

Whatever the ship outcome, the work is committed before you move on.

## Step 8 — Update the product backlog

Run the **new-product-backlog** skill. It analyzes this run (commits, spec/plan, what shipped) and proposes updates — moving the item(s) to `shipped` with the commit hash appended to `artifacts`, and filing only the follow-ups that were **deliberately deferred** as out-of-scope per Scope discipline.

## Step 9 — Accept + commit the backlog

Auto-accept the new-product-backlog skill's proposed changes (don't ask), then commit the backlog artifact, staged by explicit path, and push per `project.push_policy`.

## Final report

Close with a tight report:
- What shipped, and the commit hash(es).
- The verification result — which commands ran and what they said.
- Ship status — what `deployment.procedure` did, or "committed and pushed; no deployment procedure configured."
- Any deviations from the spec, and why.
- New follow-ups filed, if any.
- **Where to look to confirm it's working** — name a concrete surface from `observability.surfaces` and say what "good" looks like. If you added telemetry to make it observable, say so.
- Confirmation that out-of-scope code paths were untouched.

When running as a dispatched subagent, this report **is** your return value to the orchestrator.

## Step 10 — Operator next-steps checklist (plain language)

The Final report above is for the developer/orchestrator — it's technical. Now print a **second, clearly separated block addressed to the human operator**.

Rules for this block (tune the register with `operator.expertise`; at `novice` these are strict):
- **Plain language. No jargon.** If a technical term is unavoidable, follow it with a short everyday-words parenthetical.
- **Be explicit about what needs the operator vs. what's automatic.** Spell out whether the change is already live and, if not, exactly what makes it live.
- **For every action, give the exact words to send back** (e.g. `reply "turn off <ID>"`).
- **Omit any heading that doesn't apply.**
- **Standard reply phrases — use these EXACT verbs every time**, plus anything in `operator.extra_reply_phrases`:
  - **`turn off <ID>`** → switch the feature back off / undo it.
  - **`redo <ID> as <X>`** → the operator disagrees with a decision made on their behalf; re-open it with their direction.
- Use these headings, in this order:

```
## ✅ Done for you (nothing to do)
- <plain one-liners: what shipped, that the automated checks passed, whether it's live and when it starts being used>

## 👉 Do now
- <concrete action + the exact reply to send>  — OR  "Nothing right now — you're all set."

## 🔔 Watch for later
- <anything that needs an eye kept on it: where to look, what "good" looks like, and by when>

## 🛟 If something looks wrong
- <the revert path in plain words (from deployment.revert) + the exact reply that triggers it>
```

**Batch mode:** each unit's subagent still prints its own operator block, but the **orchestrator prints ONE consolidated operator checklist at the very end** of the batch.

---

## Orchestrating a batch (one unit at a time)

When asked to run several units in sequence, the invoking session is the **orchestrator**. Because the front half is interactive, **the orchestrator itself conducts the front half for each unit with the operator — then dispatches everything from the spec write onward** to a subagent.

1. **Resolve the unit list + dependency order** from the backlog.
2. **Run the front half per unit, in the orchestrator, with the operator — up to the last brainstorming answer.** For each: load (Steps 0–1), the **Step-1.5 impact analysis** (fold impacted surfaces in; surface any proposed deferral), then the **interactive brainstorming interview (Step 3)** over the impact-expanded scope, including any UI design. The orchestrator then **writes and commits the spec itself (Step 3b) with no approval gate**. Don't shortcut this just because you're in a batch.
3. **Dispatch each unit's AUTONOMOUS back half as its own subagent** (Agent tool), once its spec is committed:
   > Use the no-research-backlog-execution skill's autonomous back half (Steps 4–10) to implement UNIT-N = <ID>[, <ID>] from the already-committed spec at `<spec path>`. Read `.claude/backlog-helpers.yml` first. The interactive front half is already complete — do NOT re-brainstorm or ask the operator anything; run the Step-4 technical-architect review folding findings silently, then writing-plans onward, hands-off to shipped. Return the structured final report.

   Each subagent gets a fresh, isolated context.
4. **Proceed unit-by-unit**, reading each report before dispatching the next; stop and surface anything a downstream unit must know.
5. **Print ONE consolidated operator checklist** at the very end, merging every unit's operator block into a single plain-language list.

## Scope discipline — finish the whole job (fold new scope in)

The goal is a **complete outcome**, not strict fidelity to the original backlog wording. The upfront **Step 1.5 impact analysis** is the primary place this is enforced. But scope also surfaces later: when you discover additional scope at any point, **default to folding it into THIS unit**: enhance the spec and the plan, implement it, and ship the feature whole. Re-run the Step-4 technical-architect review on the enhanced spec if the addition is substantial.

**Minimize new backlog rows.** Spinning newly-found, in-reach scope out into a future row is the **exception, not the default**.

**The ONLY carve-out: scope that is BOTH very large AND very complex.** If the additional scope is a major piece of work in its own right — genuinely too big to fold in without derailing this unit — then file it as a new Pending backlog row (Step 8 handles it) and note the boundary in the spec. If it is **not** that large and **not** that complex, fold it in and finish it here.

A hard dependency the row already names is always in-scope. **When unsure, lean toward folding in and finishing.**
