---
name: pr-from-backlog
description: FULLY AUTONOMOUS variant of semiauto-backlog-execution — take ONE product-backlog item (an id, or a small set of ids that form a single shippable unit) all the way to shipped without operator check-ins. Same disciplined process and the same rigor — an upfront COMPREHENSIVE IMPACT ANALYSIS (Step 1.5) that traces the full production blast radius and folds every impacted surface (UI, config, schema, migrations, scheduled work, telemetry, callers, tests) into ONE atomic vertical-wedge unit — but the agent DECIDES rather than asks — superpowers brainstorming runs in SELF-RESOLVING mode where the agent answers its own design questions from the codebase's conventions and writes the spec unattended, and every call it made lands in a required Decisions log. Then an independent technical-architect spec review, writing-plans, subagent-driven TDD, the verification gate, commit/ship per the project profile, the backlog update, and a plain-language operator next-steps checklist. The sanctioned interrupts are the ESCALATION TRIGGERS (Step 2) — frontend/UI visual design, a genuinely blocked or irreversible-and-unguessable decision, destructive operations, anything listed in the profile's escalation.extra_triggers, ANY new backlog row (fold-in vs. defer is always the operator's call — Step 2.5), and a real clarifying question where a wrong guess would waste the build. Interrupts are rare and always short, plain-language, and decision-shaped. Carries an OPTIONAL project-defined domain-research hook (off by default; see .claude/backlog-helpers.yml). Favors a COMPLETE outcome over original-scope fidelity. Use when the user says "pr-from-backlog", "pr from backlog", or asks to implement/ship a backlog item hands-off / without check-ins / "just do it". For the human-in-the-loop path use semiauto-backlog-execution instead. Do NOT use it merely to ADD or LIST backlog items — that is add-to-backlog / new-product-backlog.
---

# PR From Backlog — fully autonomous

Turn one backlog row (or a small cluster of rows that together form a single shippable unit) into shipped, deployed code — **hands-off, end to end** — at the right amount of rigor for the task. The impact analysis (Step 1.5) is what makes each unit an **atomic vertical wedge**: a change that works end-to-end in production on its own, with every impacted surface folded in, rather than a slice that needs follow-up work before it's usable.

**This is the fully-autonomous counterpart of `semiauto-backlog-execution`.** It is identical EXCEPT for *who decides*:

- **Step 1.5 (impact analysis):** the agent folds impacted surfaces in by default. **The one exception is deferral: any scope that would become a NEW backlog row is the operator's call** (Step 2.5) — the agent recommends, the operator picks.
- **Step 3.5 (premise fork, only when the research hook is on):** the agent **acts autonomously** on archive and scope-change outcomes — no operator confirmation.
- **Step 4 (brainstorming):** runs in **SELF-RESOLVING mode** — the agent answers its own design questions from the codebase's conventions (and the Step-3 research, if the hook is on), writes the spec, and self-approves it. **Exceptions:** frontend/UI *visual* design escalates, and so does a requirement that genuinely reads two ways.
- **Steps 5–12:** unchanged — already autonomous in the parent skill.

**Autonomy does not mean less rigor.** The impact analysis, the spec review(s), and the verification gate all still run in full. What changes is that the agent resolves the judgment calls itself, *with a recorded rationale*, and reports every one of them at the end so the operator can audit the decisions after the fact instead of during.

## Step -1 — Read the project profile (do this first, every run)

Read `.claude/backlog-helpers.yml` at the repo root and hold it in context for the whole run. It is the single source of everything project-specific:

| Profile key | Governs |
|---|---|
| `backlog.*` | how to reach the store, what ids look like |
| `artifacts.*` | where specs and plans get written |
| `verification.*` | the Step-8.5 gate — the exact commands, and the safety-critical paths you hand-read |
| `impact_surfaces` | project-specific layers added to the Step-1.5 checklist |
| `deployment.*` | Step 9 — how shipped work reaches its running environment, and how to undo it |
| `observability.surfaces` | where the operator can see the feature working |
| `research.*` | **the Step-3 hook** — off by default |
| `escalation.extra_triggers` | **additional reasons this skill must stop and ask** (Step 2) |
| `operator.*` | how plain the Step-12 checklist must be, and the reply phrases |
| `project.*` | branch, push policy, commit trailer |

**If a field is empty, use the documented default in the relevant step — never invent a command, a deploy procedure, or a research corpus.** Under full autonomy this rule is load-bearing: there is no operator to catch an improvised procedure. If the profile file is missing entirely, say so once at the start, run with all defaults, and note it prominently in the Final report.

Throughout, `<ID>` means an id in your project's format (see `backlog.id_prefix`).

## How to talk to the operator — read this once, applies everywhere

Every word the operator sees — a Step-2.5 fold-in-or-defer question, an escalation, a progress line, the Step-12 checklist — follows the same rules:

- **Short.** A question fits on a screen. If you need three paragraphs to set it up, you haven't finished thinking.
- **Plain.** No jargon. Not "blast radius", "vertical wedge", "typed field" — say "what else this touches", "finish it in one go", "setting". If a technical term is genuinely unavoidable, follow it with a few everyday words in brackets.
- **Decision-shaped.** Say what you'd do and why in one line, then let them pick. Don't present analysis and hope they infer the question.
- **No walls of text.** Detail belongs in the spec and the Final report, not in a question.

## What "one unit" means here

A unit is **one coherent shippable thing**, identified by one or more ids from the `new-product-backlog` store. Multiple ids belong in the same unit only when they share a code path or a hard dependency. When the caller gives you several ids, treat them as ONE unit and implement them together in dependency order.

If you were given a whole *batch* to run one-at-a-time, read **"Orchestrating a batch"** at the bottom first.

## Backlog store & CLI (read once)

The backlog is a strict, schema-validated JSON file owned by the **`new-product-backlog`** skill. **It is mutated ONLY through that skill's Python CLI** — never hand-edit the JSON. Resolve the CLI and the file once, then reuse them:

```bash
BL="$(ls -d ~/.claude/plugins/cache/product-backlog-skill/product-backlog/*/skills/new-product-backlog/scripts/backlog.py 2>/dev/null | sort -V | tail -1)"   # or backlog.cli_path
BACKLOG="$(python3 "$BL" default-path)"                                                                                                                       # or backlog.path
```

The status vocabulary is `pending | shipped | discarded` (plus `new`); there are real `priority`, `dependencies`, `doNotBuildBefore`, `artifacts`, and `notes` fields. The backlog update at **Step 10** invokes the `new-product-backlog` *skill*; the direct row reads/edits in Steps 0, 1.5, and 3.5 call the CLI as shown.

## Step 0 — Load the work

Read the target item(s) via `python3 "$BL" get "$BACKLOG" <ID>`. Extract: `name`/`description`, `priority`, `dependencies`, `doNotBuildBefore`, `notes`, and any linked `artifacts` (an existing spec/plan/findings doc, source files, prior review notes). If an item links a spec or plan that already exists, you are *extending* the design, not starting cold — open it.

Confirm the dependencies are satisfied (shipped). If a hard dependency is still pending, stop and say so.

## Step 1 — Classify the task

- **Complexity:** `complex` (new core logic, multi-component, irreversible-ish, intricate state) or `simple` (a reword, a flag, a contained refactor, an additive event). Step 8 uses this to pick the implementer model per task.
- **Discipline — only meaningful when `research.enabled` is true:** `domain-heavy`, `engineering-heavy`, or `hybrid`, per the profile's `research.domain_definition`. When the hook is off, everything is engineering.

When the research hook is ON, Steps 3, 3.5, and 5 fire whenever the task is **domain-touching (`domain-heavy` OR `hybrid`) AND `complex`.** **Autonomy raises the stakes on this call: there is no operator to catch a mis-classification, so when the discipline is arguable, classify it `hybrid` and do the grounding.**

## Step 1.5 — Comprehensive impact analysis (ALWAYS — this is the anti-regression gate)

Before you research or brainstorm anything, map the **full production blast radius** of this change. This step is why the unit ends up atomic. **The recurring failure it exists to kill:** shipping a change that is correct in isolation but *incomplete in production* — a new config knob with no UI to set it, a new field no report surfaces, a schema change with no migration, a changed default that silently breaks a distant caller — so the "done" unit still needs follow-up work before it's actually usable, and meanwhile an untraced surface regresses. Missing an impacted area is the more dangerous, more common error than a slightly larger unit.

**The goal is a vertical wedge:** ONE self-contained unit that delivers a working outcome end-to-end and depends on **no** later work to be useful in production.

**Trace every layer — don't reason from memory, follow the code.** For each symbol, config key, route, table, or function this unit touches, follow every **read and write** across the tree: grep/read the code, and spawn `Explore` / `general-purpose` subagents for breadth when the surface is wide (fan them out in parallel). Walk this checklist **explicitly** and record, for each line, one of `impacted → fold in` / `not impacted` / `already covered`:

- **Config & settings** — new/changed configuration? Trace the typed field/default, every environment's config file, validation, and any env-var plumbing.
- **UI / operator surfaces** — is there a screen, form, CLI flag, or read-only display where a human sets or sees this? **A setting a human is meant to control almost always has — or needs — a control surface. If one exists for the thing you're changing, updating it is IN-SCOPE, not a follow-up** (this is the canonical miss). Note: folding in a UI surface is what triggers the **frontend escalation** in Step 2 — the *visual design* of a new screen is the one thing you bring to the operator.
- **Data model / persistence / migration** — columns, rows, on-disk state. A new persisted field needs its write path, its read path, AND any migration/backfill for existing rows.
- **Callers & downstream consumers** — every place that reads the value or calls the function you changed. A changed default, shape, or units can break a distant consumer that isn't in the diff — that consumer is in-scope.
- **Scheduled / background work** — does a cron, queue worker, or scheduled job need new args, a new schedule, env, or a whole new job for this to actually run?
- **Observability** — will a human be able to *see it working*? Check `observability.surfaces`. If the feature isn't observable through an existing surface, **fold the telemetry into this unit**. Under full autonomy this matters more, not less: the telemetry is how the operator audits a decision they weren't asked about.
- **Tests** — the test surfaces every folded-in area needs.
- **Docs** — user-facing docs and the backlog row itself (below).
- **Everything in `impact_surfaces`** from the project profile — walk each entry by name and check its `where` path.

This checklist is the **floor, not the ceiling** — trace anything else the change reaches.

**Fold in by default; the operator decides deferrals.** Apply **Scope discipline** (bottom of this skill): every impacted area needed to make the change complete gets **folded into THIS unit**. The ONLY candidate for deferral is scope that is BOTH very large AND very complex (or that genuinely needs real-world evidence before it can be designed). **When you hit one, do not decide it and do not file the row — run Step 2.5 and let the operator pick.** Whatever they choose, a deferral still costs three things, all mandatory: (a) name the deferred boundary and the reason in the spec, (b) file it as a Pending backlog row at Step 10 with the embargo date and tracking mechanism they agreed to, and (c) report it in the Final report and the operator checklist. A deferral that isn't written down in all three places is a silent scope drop.

**Record the expanded scope in the backlog** (read-modify-write so nothing is lost):

```bash
OLD="$(python3 "$BL" get "$BACKLOG" <ID> | python3 -c 'import json,sys;print(json.load(sys.stdin)["notes"])')"
python3 "$BL" edit "$BACKLOG" <ID> --notes "${OLD}
Impact-Expanded Scope (<currentDate>): folding in <UI / config / schema / jobs / telemetry / callers / tests …>."
```

**Carry it into brainstorming.** The impact-expanded scope is the authoritative brief for Step 4. This runs for **every** unit — simple ones included; a "just a flag" change is exactly where a missing UI/telemetry surface hides.

## Step 2 — Autonomy posture (fully autonomous + the escalation triggers)

**Run Steps 0 through 12 hands-off.** Resolve every design question and scope call yourself, grounded in the codebase's own conventions (and the Step-3 research, if the hook is on). Do not ask the operator to choose, confirm, or approve; do not pause for a spec sign-off; do not pause before shipping.

**The sanctioned interrupts — the escalation triggers.** Stop and consult the operator when one of these fires:

1. **Frontend / UI visual design.** If the unit adds or reshapes a user-facing surface (a new screen or panel, a new form, a significant layout change), the **visual** design is an operator conversation — taste is not derivable from the codebase. Bring it to them and use the **`frontend-design`** skill. *Scope of this trigger:* only the visual/interaction design escalates. A UI change that is purely mechanical — adding a field to an existing form, surfacing a new value in an existing table, wiring an existing control to a new setting — follows the established patterns and does **not** escalate.
2. **Genuinely blocked, or an irreversible-and-unguessable decision.** Something outside the code decides the answer (a missing credential, an external service, a business fact only the operator holds), or the choice is irreversible AND the codebase gives you no basis to pick. "I'd like a second opinion" is not this. "Two options look about equal" is not this either — pick the one the conventions support, or the one that is cheaper to reverse, and **record the call in the Decisions log**.
3. **Destructive / irreversible operations** outside the normal flow — force-push, history rewrite, deleting operator data or persistent state, dropping a column, anything that cannot be undone by reverting a commit.
4. **Anything listed in `escalation.extra_triggers`** in the project profile. Treat each entry as a hard stop, worded by the operator themselves.
5. **Creating a new backlog row.** Any time — at any step — you conclude that some scope should become its own future item instead of shipping here, **that is the operator's call, never yours.** Stop and run **Step 2.5**. (One carve-out, mandated by this skill rather than discretionary: the ordinary **status flips** the `new-product-backlog` skill makes to rows this unit shipped. Everything else that would add a row asks first.)
6. **A real clarifying question.** If a wrong guess would send the build in the wrong direction — you're unsure what the operator actually wants from an ambiguously-worded row, the requirement reads two ways and the two readings produce materially different software, or something you found on the way changes what "done" should mean — **ask.** One short question, plain words, options laid out, then carry on autonomously. Autonomy is the default posture, not a vow of silence: it is far better to spend one question than to hand back a well-built wrong thing. This is **not** a licence to ask for reassurance, a second opinion, or approval of a call you can make yourself (see Red flags).

Everything else — including reshaping a unit's scope *within* this unit, and picking between two plausible implementations — **you decide.**

**How to ask, whenever you do interrupt.** Use `AskUserQuestion` with concrete options. Keep it short and jargon-free: the operator should be able to read it in a few seconds and pick, without scrolling and without decoding technical terms. One question at a time, name the trade-off in everyday words, mark your recommendation `(Recommended)` and say in one line why. Never dump the spec, the diff, or a wall of analysis into the question.

**The Decisions log (this is what replaces the operator's presence).** Maintain a running list, in your working context and then in the spec, of every judgment call you made that the semi-auto skill would have put to the operator. For each: the question, the options, the option you chose, and the **rationale or citation** behind it. This log is a **required section of the Final report**. Autonomy is only acceptable because the decisions are auditable after the fact — an unlogged decision is an unaccountable one.

## Step 2.5 — New scope? Ask before you file a backlog row *(applies at EVERY step)*

This is not a step you run once — it is a **rule that fires whenever, anywhere in Steps 0–12, you catch yourself thinking "that should be a separate backlog item."** Impact analysis, either spec review, implementation, verification, the Step-10 backlog pass — it doesn't matter where. **You never create the row on your own.**

**Why:** filing a row is a scheduling decision about the operator's time, not a technical one. Folding scope in makes today's unit bigger but finishes the job; splitting it out makes today's unit smaller but leaves work nobody may come back to. Only the operator knows which they want.

**The protocol:**

1. **Don't file anything yet.** No `add-to-backlog`, no CLI `add`, no "I'll note it and confirm later."
2. **Do your homework first**, so the question is a real choice and not a shrug: how big is the extra work, what breaks or stays incomplete if it waits, and — importantly — **is there a reason it is genuinely *better* done later?** (The common one: the change needs real-world evidence from the thing you're shipping today before its design can be settled sensibly.)
3. **Ask with `AskUserQuestion`** — one question, two options, plain words, short enough to read at a glance:
   - **Option A — Fold it in now:** what extra you'd build in this unit, and roughly how much bigger that makes it.
   - **Option B — Make it a separate item:** what ships today without it, and what stays missing until the new item is built.
   - Mark whichever you'd pick `(Recommended)` with a one-line reason.
4. **If Option B is better because it needs a soak first, say so IN the question** — the operator can't weigh that unless you hand them all three of these, in one or two plain sentences each:
   - **Why later is better** — what you'd learn from letting it run first, and what a decision made today would be guessing at.
   - **The embargo date** — a concrete `YYYY-MM-DD` for `add-to-backlog`'s `doNotBuildBefore`, plus the arithmetic behind it in everyday terms. Never propose an open-ended "sometime later."
   - **How the soak gets tracked** — the specific existing surface from `observability.surfaces` that will show whether it's working, and the number you'd look at when the embargo lifts. **If nothing currently emits that number, say so and fold the telemetry into THIS unit** — a soak you can't measure is not a soak.
5. **Act on the answer.** Fold in → enhance the spec/plan and build it here (re-run the relevant spec review if the addition is substantial). Separate item → file it at Step 10 via `add-to-backlog` with exactly the embargo date and tracking mechanism the operator agreed to, and record the deferred boundary in the spec.
6. **Log it either way** in the Decisions log and surface it in the Final report and the operator checklist — including that the operator, not you, made the call.

**Batch mode:** a dispatched subagent can't reach the operator. It returns the fold-in-or-defer question (with the homework already done) to the orchestrator, which asks, then re-dispatches with the answer baked in.

## Step 3 — Domain research *(PROJECT HOOK — off by default)*

> ### 🔌 This is an extension point. Out of the box, this step does nothing.
>
> **Default behavior (`research.enabled: false`, which is the shipped default):** there is no domain research in this skill. Skip Step 3 and Step 3.5 entirely, treat every item as engineering, and self-resolve in Step 4 from the codebase's own conventions and the backlog row's intent. **Do not** improvise a research procedure, invent a corpus, or run open-ended web research to fill the gap — under full autonomy an ungrounded "research" pass is especially dangerous, because it launders a guess as evidence with nobody in the loop to catch it. Where you have no grounding, say so plainly in the Decisions log.
>
> **To turn it on:** set `research.enabled: true` in `.claude/backlog-helpers.yml` and write the project's own procedure into `research.procedure`. A good procedure answers, literally and concretely: what counts as domain-touching here; where the corpus lives and how to search it; when existing material suffices vs. when to commission fresh research; where new output is stored (`artifacts.research_dir`); what a citation looks like; and any **scoping rules** (`research.scopes`) if the domain has separately-governed sub-areas whose doctrine must not be mixed.
>
> **Under full autonomy the research IS the operator.** In the semi-auto skill the research informs a recommendation the operator then rules on; here, when it is enabled, it is the *only* thing standing between a domain question and a coin flip. Skipping or thinning an enabled research procedure is a strictly worse error in this skill than in that one.

## Step 3.5 — Premise verification fork *(only when `research.premise_fork` is true, and only for domain-touching + complex items)*

After the research is in hand, **stop and critically verify that the backlog entry's premise is still valid** in light of what the research actually says. Implementing a domain-wrong idea with good software craftsmanship still produces a wrong outcome.

**Autonomous divergence — you decide, and you act.** Unlike `semiauto-backlog-execution`, you do **not** surface the outcome for confirmation. Diagnose, act, and report. Every fork you take goes in the **Decisions log** with its citations, and both the Final report and the operator checklist must surface it.

### Outcome A — Research confirms: proceed normally
Continue to Step 4; note "premise verified" in context.

### Outcome B — Research refutes: archive the item, ship no code
The research clearly contradicts the core premise. Archive it — a status flip to `discarded` with the reason in `notes`; nothing is deleted:
```bash
OLD="$(python3 "$BL" get "$BACKLOG" <ID> | python3 -c 'import json,sys;print(json.load(sys.stdin)["notes"])')"
python3 "$BL" discard "$BACKLOG" <ID> --notes "${OLD}
Research-Refuted (<currentDate>): <1–3 sentence plain-language reason>. Citations: <source>."
git add <backlog.path> && git commit -m "chore(backlog): archive <ID> — premise refuted by research (YYYY-MM-DD)"
```
Then **stop.** Skip Steps 4–11. Return a Final report with what was claimed, what the research found, the citations, and the archive commit hash; state "no code shipped." Then print the Step-12 operator block: a plain-language explanation, and the exact reply **`unarchive <ID>`** if they disagree and want it built anyway. **The archive is reversible by one operator reply — that is what makes it safe to do unattended.**

**Bar for B:** *clear contradiction* — not "the research raises some doubts." Ambiguous or mixed research is Outcome C. Do not archive on a weak signal just because archiving is cheap.

### Outcome C — Research partially agrees: reshape the scope and continue
Honor the research and reshape — no confirmation needed. *Unless* the reshape means spinning part of the original scope out into a **new backlog row** — that part goes through **Step 2.5** and the operator picks. Append a `Scope-Modified` note via `edit --notes` (read-modify-write), commit it, add it to the Decisions log, and **continue to Step 4 with the modified scope as the authoritative brief**.

## Step 4 — Brainstorm the spec, SELF-RESOLVING

Use **superpowers:brainstorming** to produce the spec, but run it in **self-resolving mode**: pose the design questions to yourself, answer them from the codebase's own conventions (and the Step-3 research, if the hook is on), and write the spec unattended. **Do not put the design questions to the operator** — that is `semiauto-backlog-execution`'s job, not this skill's.

**Brainstorm the impact-expanded scope, not the original slice.** The Step-1.5 impact map is the brief. The unit you spec here must be usable in production on its own, with no dependent follow-up; if brainstorming surfaces a further impacted surface, fold it in and re-map.

**Self-resolution protocol.** For each design question the brainstorming skill raises:

1. State the question and the realistic options (typically 2–3) in your working notes.
2. **Engineering question:** decide from the codebase's existing conventions and the backlog row's intent. Where the convention is obvious, just follow it — don't manufacture a decision record for it. Where two options are close, prefer the one that is cheaper to reverse.
3. **Domain question, research hook ON:** pick the option the research supports and **write the citation next to it**. If the research is silent or genuinely mixed, say so plainly in the log and choose on engineering judgment + reversibility — **never dress an ungrounded guess as research-backed, and never invent a citation.** A fabricated citation is worse than an honest "the research is silent here, I chose X because it's the cheaper mistake to undo."
4. **Every question you resolved goes in the Decisions log** (Step 2), which lands in the spec and in the Final report.

**Ask only when the answer would change the build.** Self-resolution is the default and covers nearly everything. But if brainstorming turns up a question where the row is genuinely ambiguous and the two readings produce materially different software, or where the answer depends on what the operator wants rather than on what's correct, **ask it** (Step 2 trigger 6) — one short plain-words question with the options, then resume self-resolving.

**The main escalation here: frontend visual design.** If the unit's scope includes a new or reshaped user-facing surface, stop here and design it **with the operator** — invoke the **`frontend-design`** skill. Then resume self-resolving for everything else and continue autonomously from Step 5. Mechanical UI work does not escalate.

Write the spec to `artifacts.specs_dir` — that committed spec is the unit's durable design record. **You self-approve it** (there is no operator spec gate in this skill); its Decisions-log section is what makes the self-approval auditable. Steps 5–6 then pressure-test it independently.

## Step 5 — Domain-expert spec review *(only when `research.domain_expert_review` is true, and only for domain-touching + complex items)*

Spawn an **Opus** subagent as an independent **domain expert + critical reviewer**, briefed on the specific domain area (and, if `research.scopes` is set, scoped to the one sub-area this item touches). Point it at the Step-3 grounding material explicitly. Have it pressure-test the spec's *domain* correctness. **Give it the Decisions log explicitly and ask it to challenge the calls you made** — in this skill it is the only independent check on a self-resolved design decision, so its job is bigger than in the semi-auto path. Fold its findings into the spec.

**Skip this step entirely when the research hook is off** — the technical-architect review below is then the sole spec review, and that is by design.

## Step 6 — Technical-architect spec review *(always)*

Spawn an **Opus** subagent as an expert **Technical Architect (Software Engineering + DevOps)**. Have it independently review the spec for architecture, correctness, testability, failure modes, deploy/rollback safety, and fit with the existing codebase. This runs for **every** unit, including simple ones — the engineering backstop. Give it the spec path **and** the source files it touches so it reviews against real code, not just prose. **Give it the Decisions log too, and ask it to challenge the engineering calls you self-resolved.** Fold its findings into the spec.

**Review findings that widen the scope: fold them in — and if one looks like a separate item, run Step 2.5.** Both reviews are prime places where "that should really be its own ticket" shows up. Default to folding the finding into this unit. The moment you'd rather defer it, stop and put the fold-in-or-defer choice to the operator; do not file the row yourself.

**Verify the substance, not the line numbers.** Architect findings are high-value, but its cited `file:line` references can be approximate. Before folding a finding in, confirm the underlying claim against the actual source; adopt the substance, correct the locator.

## Step 7 — Write the plan

Write the implementation plan yourself with **superpowers:writing-plans**, into `artifacts.plans_dir`.

## Step 8 — Implement (superpowers:subagent-driven-development)

Execute the plan with **superpowers:subagent-driven-development** in autonomous mode. Choose the model per task difficulty: **Sonnet for simpler tasks, Opus for complex ones** (new core logic, intricate state, anything on a safety-critical path from the profile).

**Do NOT re-run the suite after each individual task.** `subagent-driven-development` already practices TDD, so each task lands verified. Verification happens **once**, in Step 8.5, after every task in the plan is done.

## Step 8.5 — Pre-ship verification (ONCE, after ALL tasks are complete)

After the last task reports done — and before you commit in Step 9 — the orchestrator runs the full gate itself, one time (the `verification-before-completion` discipline; with no operator watching, this gate is non-negotiable):

- **Run every non-empty command in `verification`** — `tests`, `lint`, `format_check`, `typecheck`, `build`, then each entry in `extra`, in that order. Run them as CI would (whole-tree, not per-file). **Read the actual output**, not just the exit code.
- **Hand-read the diff of every path in `verification.safety_critical_paths`** and check it against the spec's intended behavior.
- If `verification` is entirely empty, say so explicitly in the Final report rather than implying a gate ran, and at minimum run the project's obvious test command if one is discoverable from its manifest.

**Long-running suites:** never run a multi-minute suite as a blocking foreground call — a tool-call timeout can kill it mid-run and leave a frozen log. Launch it detached (`run_in_background: true`, or `nohup … > /tmp/<label>.log 2>&1 & disown`) and poll that run's own live log path. Never reuse a log path or PID from an earlier run, and never wait passively past ~3x the suite's normal runtime without verifying the process is still alive.

If anything is red, dispatch a fix subagent, then re-run this step. Only proceed to Step 9 once you've seen it green with your own eyes.

## Step 9 — Commit, push, ship

1. **Commit**, following `project.push_policy`:
   - `auto` — commit and push to `project.primary_branch` without asking.
   - `ask` — commit; push is the one thing you may pause on even in this skill, unless the operator pre-authorized it.
   - `branch` — work on a feature branch, push it, and open a PR (use **superpowers:finishing-a-development-branch**).

   Append `project.commit_trailer` if the profile sets one.

2. **Ship it, per `deployment.procedure` in the project profile — no ask.** Follow those instructions literally.
   - **Respect `deployment.timing_cautions`.** If the current moment falls inside a stated unsafe window, defer just the risky part, report it explicitly as `deploy_pending: <what>@<commit>`, and say so in both reports. The code is still committed either way.
   - **Confirm it landed** with `deployment.verify` if the profile provides a command.
   - **If `deployment.procedure` is empty**, "shipped" means **committed and pushed** — nothing more. Say exactly that in the Final report.
   - **Never** improvise a deployment the profile doesn't describe, and never touch an environment the profile doesn't name. Under full autonomy, an unnamed environment is an escalation (Step 2 trigger 2), not a guess.

3. **Rollout.** Follow `deployment.rollout_notes` if set. **If it's empty, ship the feature ON.**

Whatever the ship outcome, the work is committed before you move on.

## Step 10 — Update the product backlog

Run the **new-product-backlog** skill. It analyzes this run and proposes updates — moving the item(s) to `shipped` with the commit hash appended to `artifacts`, and filing the follow-ups the **operator agreed to defer** at Step 2.5. Most newly-found scope should have been **folded into this unit**. But every deferral the operator approved **must** land here as a row: the backlog is the only place a deferral survives the session.

**No new row the operator hasn't approved.** Status flips on rows this unit shipped are automatic — fine. **Any other new row needs a Step-2.5 answer first.** If the `new-product-backlog` skill proposes a follow-up row you never put to the operator, don't auto-accept it: either fold that work into this unit, or ask now. When you file an approved deferral, use `add-to-backlog` with **exactly** the `doNotBuildBefore` embargo date and the tracking mechanism the operator agreed to — not your own revised version of them.

## Step 11 — Accept + commit the backlog

Auto-accept the new-product-backlog skill's remaining proposed changes (don't ask), then commit the backlog artifact, staged by explicit path, and push per `project.push_policy`.

## Final report

Close with a tight report: what shipped, the commit hash(es), the verification result (which commands ran and what they said), ship status (what the deployment procedure did, or "committed and pushed; no deployment procedure configured"), any deviations from the spec and why, and confirmation that out-of-scope code paths were untouched. Then:

- **`## Decisions I made for you` — REQUIRED, and it is the report's most important section in this skill.** List every judgment call from the Step-2 Decisions log: the question, the options, the option chosen, and the rationale or citation. Include the Step-3.5 fork outcome if it ran, every self-resolved brainstorming question, and every Step-1.5 deferral. **The operator was not consulted on any of these — this list is how they audit that.** If a call was made without grounding, say so explicitly rather than implying grounding you don't have.
- **Where to look to confirm it's working** — name a concrete surface from `observability.surfaces` and what "good" looks like. If you added telemetry to make it observable, say so.
- Report any **escalation trigger** that fired (which one, what you asked, what the operator said) — or state "no escalations; fully autonomous end to end."
- **`## Decisions YOU made`** — every Step-2.5 fold-in-or-defer question you put to the operator, what they chose, and what you did with it. For each deferral they approved: the new row id, the embargo date now on `doNotBuildBefore`, and the surface that tracks it. State explicitly that **no backlog row was created without their say-so** — or, if none came up, "no new backlog rows proposed."
- If Step 3.5 produced **Outcome B**, the report is a short refutation record with citations and the archive commit hash; state "no code shipped." If **Outcome C**, include a `## Scope change` section — original scope, modified scope, the citation that drove it, the backlog commit hash.

When running as a dispatched subagent, this report **is** your return value to the orchestrator.

## Step 12 — Operator next-steps checklist (plain language)

The Final report above is for the developer/orchestrator — it's technical. Now print a **second, clearly separated block addressed to the human operator**. In this skill it carries extra weight: the operator **was not in the loop**, so this block is their first and only look at what was decided on their behalf.

Rules for this block (tune the register with `operator.expertise`; at `novice` these are strict):
- **Plain language. No jargon.** If a technical term is unavoidable, follow it with a short everyday-words parenthetical.
- **Be explicit about what needs the operator vs. what's automatic.** Spell out whether the change is already live and, if not, exactly what makes it live.
- **For every action, give the exact words to send back.**
- **Omit any heading that doesn't apply.**
- **Standard reply phrases — use these EXACT verbs every time**, plus anything in `operator.extra_reply_phrases`:
  - **`turn off <ID>`** → switch the feature back off / undo it.
  - **`redo <ID> as <X>`** → the operator disagrees with a decision this skill made on their behalf; re-open it with their direction.
  - **`unarchive <ID>`** → put back a backlog item this skill archived at Step 3.5 and build it anyway.
- **The `🤔 Decisions I made without asking` heading is REQUIRED whenever any judgment call was self-resolved.** State each in one plain sentence ("I picked X over Y because Z"), and remind them they can override any of it with `redo <ID> as <your choice>`. Skip the heading only when the unit genuinely had no judgment calls (a pure mechanical change).
- Use these headings, in this order:

```
## ✅ Done for you (nothing to do)
- <plain one-liners: what shipped, that the automated checks passed, whether it's live and when it starts being used>

## 🤔 Decisions I made without asking
- <each judgment call in one plain sentence + why + the exact `redo <ID> as <X>` reply to override it>

## 👉 Do now
- <concrete action + the exact reply to send>  — OR  "Nothing right now — you're all set."

## 🔔 Watch for later
- <anything that needs an eye kept on it: where to look, what "good" looks like, and by when; plus any work the operator chose to defer at Step 2.5 — the new item's id, the date it becomes eligible, and what to look at in the meantime>

## 🛟 If something looks wrong
- <the revert path in plain words (from deployment.revert) + the exact reply that triggers it>
```

**Batch mode:** each unit's subagent still prints its own operator block, but the **orchestrator prints ONE consolidated operator checklist at the very end** of the batch — merging every **Do now** item, **every decision made without asking across all units**, everything to watch for, and a single **If something looks wrong** line.

---

## Orchestrating a batch (one unit at a time)

When asked to run several units in sequence, the invoking session is the **orchestrator**. Because this skill is fully autonomous, **each unit runs end-to-end (Steps 0–12) in its own dispatched subagent** — there is no interactive front half to keep in the orchestrator session.

1. **Resolve the unit list + dependency order** from the backlog.
2. **Dispatch each unit as its own subagent** (Agent tool):
   > Use the `pr-from-backlog` skill to take UNIT-N = <ID>[, <ID>] from the product backlog all the way to shipped, fully autonomously (Steps 0–12). Read `.claude/backlog-helpers.yml` first. <any locked upstream scope change from an earlier unit>. Return the structured final report, including the Decisions-I-made section.
3. **Escalations come back up to the orchestrator.** If a unit's subagent hits an escalation trigger, it stops and returns that ask — the orchestrator surfaces it to the operator, gets the answer, and re-dispatches the unit with the answer baked into the prompt. Subagents cannot talk to the operator directly.
4. **Proceed unit-by-unit**, reading each report before dispatching the next. If a subagent returned **Outcome B** (archived), drop that unit and any unit that depended on it (or re-scope it, and say so). If **Outcome C**, carry the modified scope forward into dependent units' dispatch prompts.
5. **Print ONE consolidated operator checklist** at the very end (per Step 12), including a single combined **Decisions I made without asking** list across all units.

## Scope discipline — finish the whole job (fold new scope in)

The goal is a **complete outcome**, not strict fidelity to the original backlog wording. The upfront **Step 1.5 impact analysis** is the primary place this is enforced. But scope also surfaces later — during research, the spec reviews, implementation, or verification — and there you **default to folding it into THIS unit**: enhance the spec and the plan, implement it, and ship the feature whole. Re-run the relevant spec review on the enhanced spec when the addition is substantial.

**Minimize new backlog rows.** Spinning newly-found, in-reach scope out into a future row is the **exception, not the default**.

**The ONLY carve-out: scope that is BOTH very large AND very complex** (or that genuinely needs real-world evidence before it can be designed). If the additional scope is a major piece of work in its own right — genuinely too big to fold in without derailing this unit — then **run Step 2.5 and let the operator choose**; if they say defer, file it as a new Pending row at Step 10 and note the boundary in the spec. If it is **not** that large and **not** that complex, fold it in and finish it here — no question needed.

A hard dependency the row already names is always in-scope. **When unsure, lean toward folding in and finishing.**

## Red flags — you are about to break the autonomy contract

Autonomy fails in two opposite directions. Both of these mean stop and re-read Step 2:

**Asking when you should decide** (this skill collapsing into `semiauto-backlog-execution`):
- "Let me just confirm the approach before I write the spec" → No. Self-resolve it and log the decision.
- "The evidence is ambiguous, so I'll ask the operator" → No. Ambiguity is a logged engineering call, not an escalation.
- "Archiving feels drastic, I should check first" → No. The archive is one `unarchive <ID>` reply away from undone. Act, then report.
- "Two options look about equal" → Pick the one the conventions support, or the cheaper one to reverse. Log it.
- "Does this look right so far?" / "Shall I go ahead?" → No. Progress updates and approval requests are not questions. Ask only when an answer changes what you build.

*The test:* would a different answer change the code you write, or the scope you ship? If yes, ask (short, plain, with options). If no, decide and log it.

**Deciding when you should ask** (the dangerous direction):
- Filing a new backlog row — for deferred scope, a review finding, a "nice follow-up" — without running **Step 2.5** → **escalate.** Fold-in vs. defer is always the operator's call.
- Guessing at a requirement that genuinely reads two ways, where the two readings build different things → **ask.** Building the wrong reading well is the expensive outcome.
- Designing a new screen's look and layout yourself → **escalate** (`frontend-design`).
- Anything matching `escalation.extra_triggers` in the profile → **escalate.** Those are the operator's own hard stops.
- Improvising a deployment step the profile doesn't describe, or touching an environment it doesn't name → **escalate.**
- Force-push, history rewrite, deleting persistent state or data → **escalate.**
- A decision that is irreversible AND has no basis in the codebase → **escalate.**

**And the failure mode unique to full autonomy:**
- Shipping without the **Decisions I made for you** section, or with a decision listed but no rationale → the work is unauditable. The operator's only window into a session they weren't part of is that list. It is not optional garnish; it is the price of not asking.
