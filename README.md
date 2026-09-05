# backlog-helpers

A reusable set of **Claude Code skills that take a product-backlog item all the way to shipped** — impact analysis, spec, review, plan, TDD implementation, verification, ship, and a plain-language report for whoever has to live with the result.

These started life inside one specific project and were generalized. Everything project-specific now lives in **one file** — `.claude/backlog-helpers.yml` — so the skills themselves are drop-in and stay upgradable.

---

## The five skills

| Skill | What it does | When to reach for it |
|---|---|---|
| **`add-to-backlog`** | Turns a one-line ask into well-formed, de-duplicated backlog row(s). Decides atomic-vs-phased split, captures priority and build-timing as real schema fields, commits. | "Put X on the backlog" |
| **`semiauto-backlog-execution`** | One item → shipped. **Interactive front half** (you answer the design questions), **autonomous back half** (spec, review, plan, build, ship). Carries the optional research hook. | You want a say in the design |
| **`no-research-backlog-execution`** | Same as above with the domain-research hook removed entirely. | Engineering work; nothing to research |
| **`pr-from-backlog`** | One item → shipped, **fully hands-off**. Self-resolves every design question and reports each call in a required *Decisions I made for you* log. Escalates only for UI design, real blockers, destructive ops, and any new backlog row. | "Just do it" |
| **`master-backlog-executor`** | Orchestrates a **batch** of unrelated items. Pre-flight gate → one subagent per item, strictly sequential → one merged board-level summary. | "Ship these six, I'm going out" |

Two ideas run through all of them:

- **The vertical wedge.** Every unit must work end-to-end on its own. The impact analysis traces the full blast radius — config, UI, persistence, callers, scheduled work, telemetry, tests, docs — and folds every impacted surface into the *same* unit. A setting with no UI to set it, or a feature nobody can see working, is not done.
- **Scope discipline.** Deferring easy adjacent work is the default failure mode, not over-building. Fold it in and finish; defer only what is both very large and very complex.

---

## Prerequisites

1. **Claude Code.**
2. **The `product-backlog` plugin** — the skills read and write the backlog only through its `new-product-backlog` Python CLI, which owns id allocation, schema validation, referential integrity, and atomic writes. The skills auto-discover it at:
   `~/.claude/plugins/cache/product-backlog-skill/product-backlog/*/skills/new-product-backlog/scripts/backlog.py`
   If yours lives elsewhere, set `backlog.cli_path` in the profile.
3. **The `superpowers` plugin** — the execution skills call `brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`, `verification-before-completion`, and `finishing-a-development-branch`.
4. **`frontend-design`** (optional) — used when a unit reshapes a user-facing surface.

---

## Install into a project

```bash
# from your project root
git clone https://github.com/<you>/backlog-helpers /tmp/backlog-helpers
cp -R /tmp/backlog-helpers/.claude/skills/* .claude/skills/
cp -n /tmp/backlog-helpers/.claude/backlog-helpers.yml .claude/
```

Or clone this repo as the starting point for a brand-new project and build on top of it.

Then **fill in `.claude/backlog-helpers.yml`** — see the next section, which does it for you.

---

## Setting up a new project — paste this into Claude

Open a Claude Code session **in the new project's root** and paste the prompt below verbatim. It walks the repo, fills in the profile, and asks you only about the things it genuinely cannot discover.

````text
I've installed the backlog-helpers skills into this project. Set them up for it.

Read `.claude/backlog-helpers.yml` — that's the project profile the five backlog
skills (`add-to-backlog`, `semiauto-backlog-execution`,
`no-research-backlog-execution`, `pr-from-backlog`, `master-backlog-executor`)
read on every run. It's currently a template full of TODOs and empty fields.
Your job is to replace it with a filled-in profile that is TRUE for this repo.

Work in this order:

1. EXPLORE FIRST, ASK SECOND. Before asking me anything, investigate the repo
   and write down what you found:
   - Language, package manager, and build tooling (read the manifest:
     package.json / pyproject.toml / go.mod / Cargo.toml / Gemfile / etc.)
   - The real test, lint, format-check, typecheck and build commands. Prefer
     what CI actually runs (.github/workflows, .gitlab-ci.yml, Makefile,
     scripts in the manifest) over what a README claims. Verify at least the
     test command actually runs.
   - Where configuration and settings live, and how many environments there are.
   - Whether there's a UI, an admin surface, or a CLI where a human sets or
     sees things — and where its code lives. This is the surface that gets
     missed most often, so find it explicitly.
   - Where persistence and migrations live.
   - Any scheduled or background work (cron, workers, queues, timers).
   - How the project logs / reports / alerts — where a human would go to see
     that a new feature is actually working.
   - Whether docs/backlog/ and docs/superpowers/ already exist.
   - The default branch, and whether the repo looks trunk-based or PR-based.

2. THEN ASK ME, in one batch, only what you could not determine:
   - How code actually gets deployed to wherever it runs, step by concrete step
     (or "it doesn't — pushing is shipping").
   - How to verify a deploy landed, and how to undo one.
   - Any times or conditions when deploying is unsafe.
   - Which paths are safety-critical — where a bug is expensive or hard to undo.
   - Whether I want pushes to happen automatically, after asking, or via PRs.
   - Whether this project has a real subject-matter domain where correctness is
     an expert question rather than a software question. Default is NO — only
     say yes if there's a genuine body of outside knowledge that should ground
     design decisions.
   - Anything a fully-autonomous run must never do without asking me first.

3. WRITE THE PROFILE. Fill in every field you can justify. Leave a field empty
   rather than guessing — the skills have documented fallbacks for empty
   fields, but they will faithfully execute a wrong command you invented.
   Keep the explanatory comments in the file.

4. FILL IN `impact_surfaces` CAREFULLY. This is the part that pays off most.
   One entry per layer of this codebase that a change might touch, each with a
   concrete `where` path and a one-line note on what's easy to miss there.
   Base it on what you found in step 1, not on a generic checklist.

5. IF I SAID YES TO A DOMAIN in step 2, set `research.enabled: true` and write
   `research.procedure` as literal, concrete instructions: where the corpus
   lives, how to search it, when to commission new research and with what tool,
   where new output gets stored, and what a citation looks like here. If the
   domain has separately-governed sub-areas whose doctrine must not be mixed,
   list them in `research.scopes`. If I said no, leave the whole block off —
   `no-research-backlog-execution` is then the natural default skill.

6. CREATE the `artifacts.specs_dir` and `artifacts.plans_dir` directories with
   a `.gitkeep`, and initialize the backlog store if it doesn't exist yet
   (the new-product-backlog CLI self-initializes on first `add`).

7. SANITY-CHECK IT. Run every verification command you wrote down and show me
   the output. A profile with a command that doesn't run is worse than an empty
   one.

8. REPORT BACK: a short summary of the profile you wrote, every field you left
   empty and why, and which of the five skills I should reach for first.

Do not modify the SKILL.md files themselves — everything project-specific
belongs in the profile.
````

---

## The profile, in brief

`.claude/backlog-helpers.yml` is the only file you edit per project.

| Block | What it controls |
|---|---|
| `project` | Branch, push policy (`auto` / `ask` / `branch`), commit trailer |
| `backlog` | Where the store is, how to reach the CLI, what ids look like |
| `artifacts` | Where specs and plans get written |
| `verification` | **The pre-ship gate** — the exact commands, plus safety-critical paths the agent hand-reads |
| `impact_surfaces` | Project-specific layers added to the impact-analysis checklist |
| `deployment` | **The only place deployment is described** — procedure, verify, timing cautions, revert, rollout convention |
| `observability` | Where a human sees a shipped feature working |
| `research` | **The optional domain-research hook** — off by default |
| `escalation` | Extra hard stops for fully-autonomous runs |
| `operator` | How plain the closing checklist must be, and the reply phrases |

**Empty fields are safe.** Every step documents its fallback — an empty `deployment.procedure` means "committed and pushed is shipped", and the skill says exactly that in its report rather than pretending a deploy happened. What is *not* safe is a field with a command that doesn't work: the skills will run it faithfully.

---

## The two extension points

### 1. Domain research (off by default)

The original versions of these skills consulted a practitioner corpus before designing anything domain-touching. That was specific to one project's subject matter, so it was removed — and replaced with a **marked hook**.

Out of the box, no skill does any domain research; they design from the codebase's own conventions and the backlog row's intent. `no-research-backlog-execution` doesn't even have the hook.

Turn it on only if your project has a real domain where correctness is a subject-matter question. Set `research.enabled: true` and write `research.procedure` as literal instructions. Two optional add-ons come with it:

- `premise_fork: true` — after research, check that the backlog item's core claim survives what the research says, and archive or reshape it if it doesn't.
- `domain_expert_review: true` — add a second, domain-expert spec review alongside the technical-architect one.

The hook lives in **Step 3** of `semiauto-backlog-execution` and `pr-from-backlog`, marked with a 🔌.

### 2. Deployment

There is no built-in deployment. Whatever your project does — CI on push, a script, a container roll, nothing at all — goes in `deployment.procedure` as concrete instructions to an agent, and the skills follow it literally. They will never improvise a deploy step or touch an environment the profile doesn't name.

---

## Which skill do I use?

```
Adding work to the backlog?              → add-to-backlog
One item, want a say in the design?      → semiauto-backlog-execution
One item, no domain questions at all?    → no-research-backlog-execution
One item, hands-off?                     → pr-from-backlog
A batch of unrelated items, hands-off?   → master-backlog-executor
```

`master-backlog-executor` calls `pr-from-backlog` under the hood, one subagent per item, strictly sequential, and merges every report into one summary at the end.

---

## Repo layout

```
README.md
.claude/
  backlog-helpers.yml                    # the project profile TEMPLATE
  skills/
    add-to-backlog/SKILL.md
    semiauto-backlog-execution/SKILL.md
    no-research-backlog-execution/SKILL.md
    pr-from-backlog/SKILL.md
    master-backlog-executor/
      SKILL.md
      scripts/preflight.py               # read-only batch-admission gate
```
