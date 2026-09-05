---
name: semiauto-backlog-execution
description: SEMI-AUTONOMOUS backlog execution — take ONE product-backlog item (an id, or a small set of ids that form a single shippable unit) all the way to shipped, via a disciplined process with a human-in-the-loop FRONT HALF and an autonomous BACK HALF. The dividing line is the operator's answer to the LAST brainstorming question; from that answer onward the agent runs unattended — including WRITING THE SPEC, with no spec-approval gate. Everything before it that involves a judgment call keeps the operator in the loop. Always runs an upfront COMPREHENSIVE IMPACT ANALYSIS (Step 1.5) that traces the full production blast radius and folds every impacted surface (UI, config, schema, migrations, scheduled work, telemetry, callers, tests) into ONE atomic vertical-wedge unit so nothing needs follow-up work to be usable. Then autonomous — write the spec from the operator's answers, an independent technical-architect spec review, the plan, subagent-driven TDD, the verification gate, commit/ship per the project profile, backlog update, and a plain-language operator checklist. Carries an OPTIONAL project-defined domain-research hook (off by default; see .claude/backlog-helpers.yml). Favors a COMPLETE outcome over original-scope fidelity. Use when the user says "semiauto-backlog-execution", "semi-auto backlog", or asks to implement a backlog item but wants to stay in the loop through the brainstorming interview. For the FULLY autonomous path use pr-from-backlog; for a variant with the research hook removed entirely use no-research-backlog-execution. Do NOT use it merely to ADD or LIST backlog items — that is add-to-backlog / new-product-backlog.
---

# Semi-Auto Backlog Execution

Turn one backlog row (or a small cluster of rows that together form a single shippable unit) into shipped, deployed code — with a **human-in-the-loop front half** (an upfront comprehensive impact analysis and an interactive brainstorming *interview*) and an **autonomous back half** that starts the instant the operator answers the last brainstorming question (write the spec → review → plan → implement → ship), at the right amount of rigor for the task. The impact analysis (Step 1.5) is what makes each unit an **atomic vertical wedge** — a change that works end-to-end in production on its own, with every impacted surface folded in, rather than a slice that needs follow-up work before it's usable.

**Variants of this skill:**
- **`pr-from-backlog`** — the same process, fully autonomous: the agent resolves the design questions itself and reports every call it made.
- **`no-research-backlog-execution`** — the same process with the domain-research hook removed entirely.

## Step -1 — Read the project profile (do this first, every run)

Read `.claude/backlog-helpers.yml` at the repo root and hold it in context for the whole run. It is the single source of everything project-specific:

| Profile key | Governs |
|---|---|
| `backlog.*` | how to reach the store, what ids look like |
| `artifacts.*` | where specs and plans get written |
| `verification.*` | the Step-8.5 gate — the exact commands, and the safety-critical paths you hand-read |
| `impact_surfaces` | project-specific layers added to the Step-1.5 checklist |
| `deployment.*` | Step 9 — how shipped work reaches its running environment, and how to undo it |
| `observability.surfaces` | where the operator can see the feature working (Step 9, Final report, Step 12) |
| `research.*` | **the Step-3 hook** — off by default |
| `operator.*` | how plain the Step-12 checklist must be, and the reply phrases |
| `project.*` | branch, push policy, commit trailer |

**If a field is empty, use the documented default in the relevant step — never invent a command, a deploy procedure, or a research corpus.** If the profile file is missing entirely, say so once at the start, run with all defaults, and note it in the Final report.

Throughout, `<ID>` means an id in your project's format (see `backlog.id_prefix`).

## What "one unit" means here

A unit is **one coherent shippable thing**, identified by one or more ids from the `new-product-backlog` store. Multiple ids belong in the same unit only when they share a code path or a hard dependency (e.g. a root fix + the change that depends on it). When the caller gives you several ids, treat them as ONE unit and implement them together in dependency order.

If you were given a whole *batch* to run one-at-a-time, read **"Orchestrating a batch"** at the bottom first — each unit still runs through the steps below, but in its own isolated subagent.

## Backlog store & CLI (read once)

The backlog is a strict, schema-validated JSON file owned by the **`new-product-backlog`** skill. **It is mutated ONLY through that skill's Python CLI** — never hand-edit the JSON, never `sed` it, never write it with file tools. The CLI validates (schema + referential integrity) and writes atomically, so a bad command fails without corrupting the file. Resolve the CLI and the file once, then reuse them for every read (`get`/`list`/`find`) and write (`edit`/`discard`) this skill does directly:

```bash
BL="$(ls -d ~/.claude/plugins/cache/product-backlog-skill/product-backlog/*/skills/new-product-backlog/scripts/backlog.py 2>/dev/null | sort -V | tail -1)"   # or backlog.cli_path
BACKLOG="$(python3 "$BL" default-path)"                                                                                                                       # or backlog.path
```

The status vocabulary is `pending | shipped | discarded` (plus `new`); there are real `priority`, `dependencies`, `doNotBuildBefore`, `artifacts`, and `notes` fields, and an editable `description`. The batch-analysis backlog update at **Step 10** invokes the `new-product-backlog` *skill* (session analysis); the direct row reads/edits in Steps 0, 1.5, and 3.5 call the CLI as shown in each step.

## Step 0 — Load the work

Read the target item(s) from the store via the CLI — `python3 "$BL" get "$BACKLOG" <ID>` (JSON). Extract: the `name`/`description`, `priority`, `dependencies`, `doNotBuildBefore`, `notes`, and any linked `artifacts` (an existing spec/plan/findings doc, source files, prior review notes). If an item links a spec or plan that already exists, you are *extending* the design, not starting cold — open it.

Confirm the dependencies are satisfied (shipped). If a hard dependency is still pending, stop and say so — that unit can't be built today.

## Step 1 — Classify the task (drives everything below)

Make these judgments and **hold them in context**; several steps are gated on them:

- **Complexity:** `complex` (new core logic, multi-component, irreversible-ish, intricate state) or `simple` (a reword, a flag, a contained refactor, an additive event). Step 8 uses this to pick the implementer model per task.
- **Discipline — only meaningful when `research.enabled` is true:** `domain-heavy` (correctness is a subject-matter question, per the profile's `research.domain_definition`), `engineering-heavy` (correctness is a software question), or `hybrid`. When the research hook is off, everything is engineering — skip this judgment.

When the research hook is ON, the Step-3 research phase, the Step-3.5 premise fork, and the Step-5 domain-expert review **fire whenever the task is *domain-touching* — `domain-heavy` OR `hybrid` — AND `complex`.** A `hybrid` task has a real domain dimension; that dimension gets the **full** domain treatment even though the rest is engineering. Be honest: over-calling wastes a research cycle; **under-calling — labelling a domain-touching change "engineering" to skip the grounding — ships a domain change blind, the more dangerous error.**

## Step 1.5 — Comprehensive impact analysis (ALWAYS — this is the anti-regression gate)

Before you research or brainstorm anything, map the **full production blast radius** of this change. This step is why the unit ends up atomic. **The recurring failure it exists to kill:** shipping a change that is correct in isolation but *incomplete in production* — a new config knob with no UI to set it, a new field no report surfaces, a schema change with no migration, a changed default that silently breaks a distant caller — so the "done" unit still needs follow-up work before it's actually usable, and meanwhile an untraced surface regresses. Missing an impacted area is the more dangerous, more common error than a slightly larger unit.

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

**Fold in by default; a deferral is an operator decision.** Apply **Scope discipline** (bottom of this skill): every impacted area needed to make the change complete gets **folded into THIS unit** — enhance the spec, plan, implement, and ship it whole. The ONLY carve-out is scope that is BOTH very large AND very complex. And because deferring is exactly what recreates the "needs follow-up before it's usable" regression this step exists to prevent, **any area you propose to defer is SURFACED to the operator for their OK — never dropped silently.** Name the deferred boundary and why it's too big to fold in, and wait for their call before splitting it out.

**Record the expanded scope in the backlog.** Append an `Impact-Expanded Scope` note to the item's `notes` via the CLI, listing the surfaces you're folding in, with today's date. Read-modify-write so nothing is lost — `edit --notes` replaces the field:

```bash
OLD="$(python3 "$BL" get "$BACKLOG" <ID> | python3 -c 'import json,sys;print(json.load(sys.stdin)["notes"])')"
python3 "$BL" edit "$BACKLOG" <ID> --notes "${OLD}
Impact-Expanded Scope (<currentDate>): folding in <UI / config / schema / jobs / telemetry / callers / tests …>."
```

The item now describes the **whole wedge**, not the original slice — so the true scope is durable if the session closes.

**Carry it into brainstorming.** The impact-expanded scope is the authoritative brief for Step 4. This runs for **every** unit — simple ones included; a "just a flag" change is exactly where a missing UI/telemetry surface hides.

## Step 2 — Autonomy posture (semi-auto: interactive front half, autonomous back half)

There are **two phases**, split at the **end of the Step-4 brainstorming interview**:

> **The handover point is the operator's answer to the LAST brainstorming question.** The moment that answer lands, say so in one line (e.g. *"That's everything I need — going autonomous from here; I'll write the spec and ship it."*) and **stop asking**. Writing the spec is the first act of the autonomous half, not the last act of the interactive one — there is **no spec-approval gate**.

- **Front half — Steps 0 through the end of the Step-4 interview: human-in-the-loop where there is a judgment call.**
  - Steps 0–1 (load, classify) and Step 3 (research, when enabled) the agent does on its own — they gather knowledge and need no operator input.
  - **Step 1.5 (impact analysis):** the agent maps the full blast radius and folds impacted surfaces into scope autonomously (that's completeness, not a judgment call), but **surfaces any DEFERRAL** — an impacted area too large-and-complex to fold in — to the operator for their OK, because a silent deferral is what leaves a feature needing follow-up before it's usable.
  - **Step 3.5 (premise fork, only when the research hook is on):** if research refutes or reshapes the item, **surface the recommendation to the operator with citations and WAIT** — do not archive or scope-change autonomously.
  - **Step 4 (brainstorming INTERVIEW):** run the question-and-answer part **INTERACTIVELY** — ask the operator the design questions as normal. You decide nothing silently while questions remain.
- **Back half — from the operator's final brainstorming answer onward: fully AUTONOMOUS.** Write the spec from their answers (announce the path in one line; do NOT present it for approval and do NOT wait), run the Steps 5–6 spec reviews and **fold their findings silently**, write the plan, implement (subagent-driven TDD), run the verification gate, commit and ship, update + commit the backlog, print the operator checklist. Only stop in this half if you are genuinely blocked or hit an irreversible-and-unguessable decision.

**Exception — UI work.** If the scope includes a user-facing surface, the design questions are already interactive here (front half), so talk through layout and visuals with the operator and use the **`frontend-design`** skill. The UI design is part of the interactive interview; once it and the rest of the questions are answered, everything from the spec write onward runs autonomously.

## Step 3 — Domain research *(PROJECT HOOK — off by default)*

> ### 🔌 This is an extension point. Out of the box, this step does nothing.
>
> **Default behavior (`research.enabled: false`, which is the shipped default):** there is no domain research in this skill. Skip Step 3 and Step 3.5 entirely, treat every item as engineering, and design in Step 4 from the codebase's own conventions and the backlog row's intent. Say nothing about research in the Final report. **Do not** improvise a research procedure, invent a corpus, or run open-ended web research to fill the gap — an ungrounded "research" pass is worse than none, because it launders a guess as evidence.
>
> **To turn it on:** set `research.enabled: true` in `.claude/backlog-helpers.yml` and write the project's own procedure into `research.procedure`. A good procedure answers, literally and concretely:
> 1. **What counts as domain-touching here** (`research.domain_definition`) — the classifier Step 1 uses.
> 2. **Where the corpus lives** and how to search it — local files, a notebook, an internal wiki, a vendor's docs, a standards body.
> 3. **When existing material is sufficient** vs. when to commission fresh research, and which tool does that.
> 4. **Where new research output gets stored** (`artifacts.research_dir`) so the next run finds it.
> 5. **What a citation looks like** in this project, so downstream steps can quote one.
> 6. **Scoping rules** (`research.scopes`) — if the domain has separately-governed sub-areas whose doctrine must NOT be mixed, name them and require every query to be scoped to the one the item touches. Mixing them imports the wrong sub-area's doctrine as if it were evidence, which is the classic failure here.
>
> **When enabled, this step runs only for items that are domain-touching AND complex** (Step 1). Its output is a synthesized picture, recorded in context with citations, that Step 4 designs against and Step 5 reviews against.

## Step 3.5 — Premise verification fork *(only when `research.premise_fork` is true, and only for domain-touching + complex items)*

After the research is in hand, **stop and critically verify that the backlog entry's premise is still valid** in light of what the research actually says. This is a decisive gate — not a formality. Implementing a domain-wrong idea with good software craftsmanship still produces a wrong outcome.

**Semi-auto divergence — the operator decides on B/C, not you.** You do the full analysis, form a clear recommendation, **present it to the operator with citations, and WAIT for their call.** Only Outcome A continues without a check-in. Make the finding legible and recommend decisively — do not hedge.

**Three outcomes — diagnose exactly one:**

### Outcome A — Research confirms: proceed normally
The research supports the premise (possibly with refinements). Continue to Step 4. Note "premise verified" in your working context.

### Outcome B — Research refutes: recommend archiving, operator confirms
The research clearly contradicts the core premise. **Do not implement, and do not archive on your own.** Present the archive recommendation: what the item claimed, what the research found that contradicts it, the **specific citations**, and your recommendation. Give them the exact reply **`archive <ID>`**, and **wait**.

- If the operator **declines**, honor it and continue to Step 4 with their direction; note the override in the Final report.
- If the operator **confirms**, archive it — a status flip to `discarded` with the reason in `notes`; nothing is deleted:
  ```bash
  OLD="$(python3 "$BL" get "$BACKLOG" <ID> | python3 -c 'import json,sys;print(json.load(sys.stdin)["notes"])')"
  python3 "$BL" discard "$BACKLOG" <ID> --notes "${OLD}
  Research-Refuted (<currentDate>): <1–3 sentence plain-language reason>. Citations: <source>."
  git add <backlog.path> && git commit -m "chore(backlog): archive <ID> — premise refuted by research (YYYY-MM-DD)"
  ```
  Then **stop**. Skip Steps 4–12. Return a Final report explaining what was claimed, what the research found, the citations, and the archive commit hash; state "no code shipped." Print an operator block with a "Nothing to do" message.

### Outcome C — Research partially agrees: recommend a scope change, operator confirms
The research validates the *direction* but the original scope is too broad/narrow/mis-structured. Present the reshaped scope (what survives, what's dropped, what's substituted) with the citation, give them the exact reply **`accept scope <ID>`**, and **wait**. On confirmation: append a `Scope-Modified` note via `edit --notes` (read-modify-write), commit it, hold the change in context, and **continue to Step 4 with the modified scope as the authoritative brief**.

**Calibration.** The bar for Outcome B is *clear contradiction* — not "the research raises some doubts." Ambiguous or mixed research is Outcome C, not Outcome B.

## Step 4 — Brainstorm the spec: INTERACTIVE interview, then autonomous spec write

Use **superpowers:brainstorming** to produce the spec. Run its **question-and-answer interview interactively, the way it is designed**: ask the operator clarifying questions one at a time and present approaches. This is the heart of the semi-auto front half. **Do NOT resolve the design questions silently while questions remain.**

**The interview is the ONLY interactive part of this step.** The moment the operator answers your last question, the front half is over: say so in one line, then **write the spec yourself and keep going** — no presenting it for review, no approval gate, no further questions.

**Brainstorm the impact-expanded scope, not the original slice.** Open the session by showing the operator the **Step-1.5 impact map** — what you traced, the surfaces you're folding in, and anything you propose to defer — so the interactive design covers the **whole vertical wedge**. The unit you spec here must be usable in production on its own, with no dependent follow-up; if brainstorming surfaces a further impacted surface, fold it in and re-map. The operator can veto or adjust the folded-in scope here.

**Anchor every recommendation on something real.**
- **Engineering questions** (and all questions when the research hook is off): decide collaboratively, anchored on **the codebase's own conventions** and the backlog row's intent. Surface the genuinely open choices; don't manufacture questions where the convention is obvious.
- **Domain questions, research hook ON:** bring each one to the operator **with a clear, research-backed recommendation and the citation behind it, and nudge them toward the research-supported option.** Use `AskUserQuestion` where it fits, putting the research-supported option first and labelled `(Recommended)`. If the research is silent or mixed, say so plainly and offer your best engineering judgment instead — **never dress an ungrounded guess as research-backed, and never invent a citation.**
- **The operator may not be a domain or software expert** (`operator.expertise`). Make every question decidable by a non-expert: plain words, 2–3 realistic options, the trade-off in one line, your recommendation marked.

### Step 4b — Write the spec (AUTONOMOUS — this is where hands-off execution begins)

As soon as the last question is answered, **write the spec to `artifacts.specs_dir` yourself and commit it** — that committed spec is the unit's durable design record. **Skip the brainstorming skill's `user-reviews-the-written-spec` gate**: do not paste the spec for approval and do not wait for a reply. Announce it in one line only — e.g. *"Spec written to `<path>` — going autonomous from here."* — and continue straight into Step 5.

Write the spec faithfully from what the operator actually decided in the interview. Anything they did NOT decide, you now resolve yourself, grounded in the codebase's conventions (and the Step-3 research, if it ran) — **do not come back with another question** unless you are genuinely blocked or facing an irreversible-and-unguessable decision. From here the spec is **locked from the operator's side**.

## Step 5 — Domain-expert spec review *(only when `research.domain_expert_review` is true, and only for domain-touching + complex items)*

Spawn an **Opus** subagent as an independent **domain expert + critical reviewer**, briefed on the specific domain area (and, if `research.scopes` is set, scoped to the one sub-area this item touches — tell it the others exist, are separately governed, and are out of scope). Its knowledge source is the Step-3 grounding material; point it at the files and citations explicitly. Have it pressure-test the spec's *domain* correctness: is this what a competent practitioner would do, and what failure mode is missed? Fold its findings into the spec.

**Skip this step entirely when the research hook is off** — the technical-architect review below is then the sole spec review, and that is by design.

## Step 6 — Technical-architect spec review *(always)*

Spawn an **Opus** subagent as an expert **Technical Architect (Software Engineering + DevOps)**. Have it independently review the spec for architecture, correctness, testability, failure modes, deploy/rollback safety, and fit with the existing codebase. This runs for **every** unit, including simple ones — the engineering backstop. Give it the spec path **and** the source files it touches so it reviews against real code, not just prose. Fold its findings into the spec.

**Verify the substance, not the line numbers.** Architect findings are high-value, but its cited `file:line` references can be approximate. Before folding a finding in, confirm the underlying claim against the actual source (grep/read the symbol it names); adopt the substance, correct the locator. Don't reject a real finding because a line number drifted, and don't implement against a line number you haven't re-confirmed.

## Step 7 — Write the plan (autonomous)

Write the implementation plan yourself with **superpowers:writing-plans**, into `artifacts.plans_dir`.

## Step 8 — Implement (superpowers:subagent-driven-development, autonomous)

Execute the plan with **superpowers:subagent-driven-development** in autonomous mode. Choose the model per task difficulty: **Sonnet for simpler tasks, Opus for complex ones** (new core logic, intricate state, anything on a safety-critical path from the profile).

**Do NOT re-run the suite after each individual task.** `subagent-driven-development` already practices TDD, so each task lands verified; re-verifying per task burns orchestrator context for no new information. Take the implementer's per-task result at face value and move to the next task. Verification happens **once**, in Step 8.5, after every task in the plan is done.

## Step 8.5 — Pre-ship verification (ONCE, after ALL tasks are complete)

After the last task reports done — and before you commit in Step 9 — the orchestrator runs the full gate itself, one time (the `verification-before-completion` discipline):

- **Run every non-empty command in `verification`** — `tests`, `lint`, `format_check`, `typecheck`, `build`, then each entry in `extra`, in that order. Run them as CI would (whole-tree, not per-file — per-file dev checks miss tree-wide errors). **Read the actual output**, not just the exit code.
- **Hand-read the diff of every path in `verification.safety_critical_paths`** and check it against the spec's intended behavior.
- If `verification` is entirely empty, say so explicitly in the Final report — "no automated gate configured in the project profile; verified by <what you actually did>" — and at minimum run the project's obvious test command if one is discoverable from its manifest.

**Long-running suites:** never run a multi-minute suite as a blocking foreground call — a tool-call timeout can kill it mid-run and leave a frozen log. Launch it detached (`run_in_background: true`, or `nohup … > /tmp/<label>.log 2>&1 & disown`) and poll that run's own live log path. Never reuse a log path or PID from an earlier run.

If anything is red, dispatch a fix subagent, then re-run this step. Only proceed to Step 9 once you've seen it green with your own eyes.

## Step 9 — Commit, push, ship

1. **Commit**, following `project.push_policy`:
   - `auto` — commit and push to `project.primary_branch` without asking.
   - `ask` — commit, then ask the operator before pushing.
   - `branch` — work on a feature branch, push it, and open a PR (use **superpowers:finishing-a-development-branch**).

   Append `project.commit_trailer` if the profile sets one.

2. **Ship it, per `deployment.procedure` in the project profile.** Follow those instructions literally.
   - **Respect `deployment.timing_cautions`.** If the current moment falls inside a stated unsafe window, do what the caution says instead (usually: defer just the risky part and report it as pending).
   - **Confirm it landed** with `deployment.verify` if the profile provides a command.
   - **If `deployment.procedure` is empty**, "shipped" means **committed and pushed** — nothing more. Say exactly that in the Final report rather than implying a deployment happened.
   - **Never** improvise a deployment the profile doesn't describe, and never touch an environment the profile doesn't name.

3. **Rollout.** Follow `deployment.rollout_notes` if the profile sets a convention (a flag default, a staged rollout). **If it's empty, ship the feature ON** — a flag left off awaiting a soak is a flag someone has to remember to flip.

Whatever the ship outcome, the work is committed before you move on.

## Step 10 — Update the product backlog

Run the **new-product-backlog** skill. It analyzes this run (commits, spec/plan, what shipped) and proposes updates — moving the item(s) to `shipped` with the commit hash appended to `artifacts`, and filing only the follow-ups that were **deliberately deferred** as out-of-scope per Scope discipline. Most newly-found scope should have been **folded into this unit**, not deferred — don't manufacture follow-up rows for work you could have finished here.

## Step 11 — Accept + commit the backlog

Auto-accept the new-product-backlog skill's proposed changes (don't ask), then commit the backlog artifact, staged by explicit path, and push per `project.push_policy`.

## Final report

Close with a tight report:
- What shipped, and the commit hash(es).
- The verification result — which commands ran and what they said (test counts, clean/dirty).
- Ship status — what `deployment.procedure` did, or "committed and pushed; no deployment procedure configured."
- Any deviations from the spec, and why.
- New follow-ups filed, if any.
- **Where to look to confirm it's working** — name a concrete surface from `observability.surfaces` and say what "good" looks like. If you added telemetry to make it observable, say so.
- Confirmation that out-of-scope code paths were untouched.
- If Step 3.5 ran: the fork outcome. For **Outcome B** the report is a short refutation record with citations and the archive commit hash, stating "no code shipped." For **Outcome C**, include a `## Scope change` section — original scope, modified scope, the citation that drove it, the backlog commit hash.

When running as a dispatched subagent, this report **is** your return value to the orchestrator — make it the structured hand-back, not a human-facing chat message.

## Step 12 — Operator next-steps checklist (plain language)

The Final report above is for the developer/orchestrator — it's technical. Now print a **second, clearly separated block addressed to the human operator**. This is the part they act on after the session closes, so it must stand on its own.

Rules for this block (tune the register with `operator.expertise`; at `novice` these are strict):
- **Plain language. No jargon.** If a technical term is unavoidable, follow it with a short everyday-words parenthetical (e.g. "deploy (push the new code to the running system)", "flag (an on/off switch in the settings file)").
- **Be explicit about what needs the operator vs. what's automatic** — a non-expert can't infer it. Spell out whether the change is already live and, if it isn't, exactly what makes it live.
- **For every action, give the exact words to send back** (e.g. `reply "turn off <ID>"`), so the operator never has to phrase a technical request themselves.
- **Omit any heading that doesn't apply** — don't print empty "N/A" sections. If there's genuinely nothing to do, say so in one friendly line under **Do now**.
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

**Batch mode:** each unit's subagent still prints its own operator block, but the **orchestrator prints ONE consolidated operator checklist at the very end** of the batch. The operator should be able to read just that one checklist and know everything they need to do.

---

## Orchestrating a batch (one unit at a time)

When asked to run several units in sequence, the invoking session is the **orchestrator**. Because the front half is interactive, **the orchestrator itself conducts the human-in-the-loop front half for each unit with the operator — then dispatches everything from the spec write onward** to a subagent. A dispatched subagent cannot run an interactive interview, so the operator-facing work must happen in the orchestrator session, where the operator actually is.

1. **Resolve the unit list + dependency order** from the backlog (group ids into units; order so a unit never runs before the one it depends on).
2. **Run the front half per unit, in the orchestrator, with the operator — up to the last brainstorming answer.** For each: load (Steps 0–1), the **Step-1.5 impact analysis** (fold impacted surfaces in; surface any proposed deferral), research + the premise fork if the hook is on, then the **interactive brainstorming interview (Step 4)** over the impact-expanded scope, including any UI design. The orchestrator then **writes and commits the spec itself (Step 4b) with no approval gate**. Don't shortcut this just because you're in a batch.
3. **Dispatch each unit's AUTONOMOUS back half as its own subagent** (Agent tool), once its spec is committed:
   > Use the semiauto-backlog-execution skill's autonomous back half (Steps 5–12) to implement UNIT-N = <ID>[, <ID>] from the already-committed spec at `<spec path>`. Read `.claude/backlog-helpers.yml` first. The interactive front half is already complete — do NOT re-brainstorm, re-surface the premise fork, or ask the operator anything; run the spec reviews folding findings silently, then writing-plans onward, hands-off to shipped. <any locked scope change>. Return the structured final report.

   Each subagent gets a fresh, isolated context for the back half.
4. **Proceed unit-by-unit**, reading each report before dispatching the next; stop and surface anything a downstream unit must know. If a unit's scope changed, carry the modified scope forward into dependent units' dispatch prompts.
5. **Print ONE consolidated operator checklist** at the very end (per Step 12), merging every unit's operator block into a single plain-language list of what's done, what the operator must do now, what to watch for, and how to revert.

## Scope discipline — finish the whole job (fold new scope in)

The goal is a **complete outcome**, not strict fidelity to the original backlog wording. The upfront **Step 1.5 impact analysis** is the primary place this is enforced — it maps the blast radius *before* brainstorming so the whole wedge is in scope from the start. But scope also surfaces later: when you discover additional scope at any point — during the impact analysis, research, the spec reviews, implementation, or verification — **default to folding it into THIS unit**: enhance the spec and the plan, implement it, and ship the feature whole. Re-run the relevant spec review on the enhanced spec when the addition is substantial.

**Minimize new backlog rows.** Spinning newly-found, in-reach scope out into a future row is the **exception, not the default**. A feature that defers its own obvious completion — leaving an easy, related piece for "later" — is the failure mode this guards against.

**The ONLY carve-out: scope that is BOTH very large AND very complex.** If the additional scope is a major piece of work in its own right (a whole new subsystem, a research-heavy investigation) — genuinely too big to fold in without derailing this unit — then file it as a new Pending backlog row (Step 10 handles it) and note the boundary in the spec. If it is **not** that large and **not** that complex, fold it in and finish it here.

A hard dependency the row already names is always in-scope. **When unsure, lean toward folding in and finishing** — under this policy, deferring an easy related piece is the more common and more costly mistake than a slightly larger unit.
