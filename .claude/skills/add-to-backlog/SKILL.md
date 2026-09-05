---
name: add-to-backlog
description: Use when the operator wants to add a new item to the product backlog — triggers on "/add-to-backlog <description>", "add this to the backlog", "put X on the backlog", "log a new backlog item for X". Gathers just enough requirement via one-at-a-time clarifying questions, decides whether the ask is one atomic item or a phased split into several linked items, checks the existing backlog for duplicate/adjacent entries and resolves any overlap with the operator, captures priority and build-timing/dependencies, then writes the row(s) through the new-product-backlog CLI and commits.
---

# add-to-backlog

## Overview

A thin, operator-in-the-loop front end for the **`new-product-backlog`** store. It takes a **brief description of a user need** and turns it into **one — or a small set of linked — well-formed, non-duplicate backlog item(s)**, each an atomic vertical wedge, capturing priority, build-timing, and dependencies as **first-class schema fields**, then writes them through that skill's CLI and commits.

**This skill deliberately does NOT research or design the feature.** Every backlog *execution* skill (`semiauto-backlog-execution`, `no-research-backlog-execution`, `pr-from-backlog`) runs its own brainstorming to expand the requirement later. Your job here is only to capture enough that each item is unambiguous, correctly de-duplicated, and correctly **scoped** (small, atomic, self-contained). Do not over-interrogate.

**Invocation:** the operator calls this with a short description, e.g. `/add-to-backlog add a nightly error-rate alert email`. If no description was supplied, ask for it once before proceeding.

## Read the project profile first

Read `.claude/backlog-helpers.yml` at the repo root. From it you need:

- `backlog.cli_path`, `backlog.path`, `backlog.id_prefix` — how to reach the store and what ids look like.
- `project.primary_branch`, `project.push_policy`, `project.commit_trailer` — how Step 7 commits.

If the file is missing, say so once and fall back to the defaults documented below (auto-discovered CLI, `main`, ask before pushing). Never invent project-specific behavior that isn't in the profile.

Throughout this skill, `<ID>` means an id in your project's format — `BL-142`, `JIRA-871`, whatever `backlog.id_prefix` says.

## Backlog store & CLI (read once)

The backlog is a strict, schema-validated JSON file owned by the **`new-product-backlog`** skill. **It is mutated ONLY through that skill's Python CLI** — never hand-edit the JSON, never `sed` it, never write it with file tools. Every add/edit/discard flows through the CLI, which validates (schema + referential integrity) and writes atomically, so a bad command fails without corrupting the file.

Resolve the CLI and the file path once at the start, then reuse them:

```bash
# Use backlog.cli_path from the profile if set; otherwise auto-discover the
# installed new-product-backlog CLI (newest version if several).
BL="$(ls -d ~/.claude/plugins/cache/product-backlog-skill/product-backlog/*/skills/new-product-backlog/scripts/backlog.py 2>/dev/null | sort -V | tail -1)"
# Resolve THIS project's backlog file (git-root-aware), or use backlog.path.
BACKLOG="$(python3 "$BL" default-path)"
```

Every command below is `python3 "$BL" <cmd> "$BACKLOG" ...`. Key subcommands: `list` / `find` / `get` (read, print JSON), `add` (create, prints the new id), `edit` (change passed fields), `discard` (soft-delete → `status=discarded`, kept for history), `validate`. Add `--help` to any for flags. The schema fields you set are: `--name`, `--description`, `--status`, `--priority` (critical|high|medium|low), `--depends <ID>[,<ID>]`, `--dnbb YYYY-MM-DD` (a "don't build before" gate), `--notes`, `--artifact "label=url"` (repeatable).

## The procedure

Run these steps **in order**. Do not skip the scope-split check, the dedup check, or the priority/timing questions — capturing those is the entire reason this skill exists on top of the raw store.

### Step 1 — Clarify the requirement (one question at a time)

Ask a **small** number of free-text clarifying questions — **one at a time**, waiting for each answer before asking the next. Stop as soon as you can write a clear 2-3 line description and a short feature title. Typically 1-3 questions is enough; rarely more.

Aim the questions at what makes the item unambiguous and de-duplicable, e.g.:
- What problem does this solve / what's the trigger? (the "why")
- Which part of the system does it touch?
- Roughly what does "done" look like — is there an obvious acceptance signal?

Do **not** ask about implementation design or algorithms — that belongs to the execution skills. If the operator's one-line description is already clear enough to write a description, you may skip straight to Step 2 with zero questions.

### Step 2 — Scope the ask: one atomic item, or a phased split?

Before dedup, decide the **shape** of what you're logging. A single operator ask often describes work that should land as **several small, linked backlog items** rather than one large multi-phase entry. Every item you log must be an **atomic vertical wedge**: independently shippable, independently valuable, and self-contained — it includes every surface it needs (UI, config, schema, jobs, tests) to be usable in production on its own.

**Split into multiple items when ANY of these hold.** The operator will rarely say "these are two phases" outright — look for the predicates yourself:
- The ask **crosses a validation / risk boundary** — behind-a-flag → default-on, dry-run → acting for real, detect → enforce/auto-act, internal → customer-facing. The safe side is one item that ships and soaks first; the risky side is a **separate later item gated on it**.
- It **bundles parts that are each independently shippable and valuable** — e.g. "a conservative single-case v1" and "a general, configurable v2". Ship the tight version, log the expansion separately.
- A **soak / observation / validation period** should sit between two parts.
- A later part **materially depends** on shipping or learnings from an earlier part.

**Keep it as ONE item when** the parts are not independently valuable — where splitting would leave a fragment that does nothing usable on its own (a *horizontal* slice like "the schema", then "the code", then "the UI"). A vertical wedge already bundles all those surfaces; never split a single wedge along horizontal layers. One small self-contained change is also just one item.

**How to split (recipe):**
1. Make **v1 the tightest shippable wedge** that delivers a real positive outcome by itself. Push everything else out of v1.
2. Move the remaining discussed scope into **v2 (v3, …)**, each itself a full vertical wedge.
3. **Order them.** Each later item will `--depends` the item(s) it builds on (wired in Step 6, once the earlier ids exist).
4. If a **soak/observation period** gates a later item, plan its `--dnbb` per Step 5.

**Surface the proposed split to the operator in ONE message** — list each atomic item (short title + one-line scope) and its gate (depends-on / soak) — and get a single yes before writing. Don't re-interrogate per item.

Then run Step 3 (dedup) **for each** item in the plan.

### Step 3 — Check the existing backlog for duplicates / adjacent items

Query the store through the CLI (never open the JSON by hand). **For each** item produced by Step 2, scan **every** existing item — all statuses (`pending`, `shipped`, `discarded`, and any `new`) — for any item that is the same as, or adjacent to, the new ask. Match on feature name, description text, and the subsystem involved (not just exact wording).

```bash
python3 "$BL" list "$BACKLOG"                            # everything, as a JSON array
python3 "$BL" find "$BACKLOG" --name-contains "alert"    # targeted substring search
```

Then branch:

**A. Nothing similar found** → the item is unique. Go to Step 4.

**B. Found one or more related items** → **surface the finding to the operator** before doing anything else. For each match, state:
- the id and feature name,
- **its `status`** (pending / shipped / discarded), and
- a one-line note on how it relates to the new ask (duplicate vs adjacent).

Then resolve it with the operator using the sub-rules below. Ask **one question at a time**.

- **B1 — Adjacent (overlapping scope, not identical):** Ask whether the operator wants to **expand the scope of the existing item instead of adding a new one**.
  - If **yes** → do not create a new item. Instead, in Step 6 **edit the existing item**: append the added scope to its `notes` (read the current notes with `get`, append, write the combined string back with `edit --notes`), or, if it clarifies the item, refine its `--description`. Skip straight to Step 4 for priority/timing on the *combined* item, then Step 6.
  - If **no** → the operator wants a genuinely separate item. Ask how to keep the two non-overlapping so the new one is **truly unique** (e.g. a crisp boundary: "existing = detection, new = alerting"). If you are unsure whether the split is clean, ask for that clarification explicitly. Capture the agreed boundary — it goes into the new item's `notes` so the distinction is on record.

- **B2 — Truly a duplicate (same thing):** Tell the operator it duplicates that id and ask **which one to keep**.
  - If they keep the existing item → stop; do **not** add a new item. Report that the ask is already tracked (and its status). If they want anything added, treat it as a `notes` update to that item via Step 6.
  - If they keep the new one → in Step 6, add the new item **and supersede** the old one. The store supports a `discarded` status (kept for history, not deleted), which is exactly the supersede action: `discard <OLD-ID> --notes "Superseded by <NEW-ID>; not pursuing."`. Confirm the superseded id back to the operator before writing.

Do not proceed past Step 3 until every surfaced overlap has an operator decision.

### Step 4 — Capture priority (selector)

Ask the operator for the item's priority using a **single-select selector** (`AskUserQuestion`), header "Priority", with exactly these four options, in this order:

- **Critical**
- **High**
- **Medium**
- **Low**

Record the chosen value — it becomes the `--priority` field (lowercased: `critical`|`high`|`medium`|`low`).

**For a phased split (Step 2):** ask priority **once for the whole set**, not per item. Later phases usually **inherit** the same priority — their timing is controlled by the dependency/soak gate, not by demoting the priority — unless the operator says a later phase is genuinely lower.

### Step 5 — Capture build timing / dependencies

Ask whether this should be **built immediately** or **wait**. Cover, in one question (free-text is fine, or a selector with an "Other" escape):
- build now, or
- wait until a **specific date**, or
- wait for a **specific event/condition** (e.g. "after the next release", "once the migration lands"), or
- **depends on other backlog items** — capture the specific id(s).

Map the answer onto the schema in Step 6:
- **specific date** → `--dnbb YYYY-MM-DD` (the "don't build before" gate).
- **depends on an item** → `--depends <ID>[,<ID>]` (must reference existing ids; the validator rejects phantom ids and cycles).
- **event/condition** (no calendar date, no tracked id) → a plain sentence in `--notes`, since there is no structured field for it.
- **build now** → nothing extra; leave `dnbb` unset and `depends` empty.

**Phased-split items (from Step 2) — wire the gate between phases:**
- Each later phase **depends on** its earlier phase → `--depends <EARLIER-ID>` (applied in Step 6, since the earlier id doesn't exist until you create it). `--depends` is the **hard** gate: the later phase literally cannot start until the earlier one is done.
- When a **soak / observation period** gates a later phase, also set `--dnbb` as a **calendar reminder on top of** the depends link:
  - The soak is usually measured from when the earlier phase **ships**, which isn't known at add time. If the operator gives an absolute target date, use it. Otherwise set a **conservative estimate = today + rough-time-to-ship-the-earlier-phase + soak-window**, and record the true relative rule in `--notes` (e.g. "soak ~8 weeks after <ID> ships; push `--dnbb` out if it ships later").
  - **Never** invent a false-precision date and drop the relative rule — the `--depends` link plus the note are what actually protect the gate; `--dnbb` is only a reminder.
  - Leave `--dnbb` **unset on the first phase** unless it has its own independent calendar reason.

### Step 6 — Write the item(s) through the CLI

Do the actual mutation with **`new-product-backlog` CLI calls** (never hand-edit the JSON). The CLI owns id allocation, timestamps, validation, and the atomic write — you only supply the fields. Priority / dependencies / build-gate are **real fields**, so put each where it belongs rather than stuffing them into notes. `notes` holds only free-text that has no field of its own (an event-based build trigger, the uniqueness-boundary from Step 3B, a supersede line, the relative soak rule).

- **New unique item** (new items are `pending` — nothing is built yet at add time):
  ```bash
  NEW_ID="$(python3 "$BL" add "$BACKLOG" \
    --name "<title>" --description "<2-3 line description>" \
    --status pending --priority <critical|high|medium|low> \
    [--depends <ID>[,<ID>]] [--dnbb YYYY-MM-DD] \
    [--notes "<event-based timing and/or uniqueness-boundary note>"])"
  ```
  `add` prints (and here captures) the new id; it also self-initializes the file/dir if the backlog doesn't exist yet.

- **Phased split (multiple linked items)** → create them **in dependency order**, capturing each id and feeding it into the next item's `--depends`. The validator rejects a `--depends` on a non-existent id, so earlier phases MUST be created first:
  ```bash
  V1="$(python3 "$BL" add "$BACKLOG" \
    --name "<feature> v1 — <tight wedge>" \
    --description "<v1: the minimal, self-contained, independently-valuable slice>" \
    --status pending --priority <p> \
    --notes "Tight first wedge; its soak/success unlocks <feature> v2.")"

  V2="$(python3 "$BL" add "$BACKLOG" \
    --name "<feature> v2 — <expansion>" \
    --description "<v2: builds on v1; also a full vertical wedge>" \
    --status pending --priority <p> \
    --depends "$V1" --dnbb <YYYY-MM-DD> \
    --notes "Soak-gated: build after $V1 soaks ~<window>; --dnbb is an estimate from today — slip it if v1 ships later.")"
  ```
  If `add` prints more than the bare id, extract the id before reusing it in `--depends`.

- **Scope expansion (Step 3 B1-yes)** → edit the existing item; append the widened scope to its notes (read-modify-write so nothing is lost), and re-set priority/timing on the combined item if they changed:
  ```bash
  OLD="$(python3 "$BL" get "$BACKLOG" <ID> | python3 -c 'import json,sys;print(json.load(sys.stdin)["notes"])')"
  python3 "$BL" edit "$BACKLOG" <ID> --notes "${OLD}
  Scope expanded (<currentDate>): <what was added>." [--priority ...] [--depends ...] [--dnbb ...]
  ```

- **Duplicate, keep new (Step 3 B2)** → add the new item as above **and** supersede the old one:
  ```bash
  python3 "$BL" discard "$BACKLOG" <OLD-ID> --notes "Superseded by ${NEW_ID}; not pursuing."
  ```

There is **no interactive confirm gate** to answer — the CLI validates and writes in one shot. If a command fails validation (bad `--depends`, would-be cycle), it exits non-zero and writes nothing; fix the argument and re-run.

### Step 7 — Commit (and push, per the profile)

Stage **only** the backlog JSON by explicit path, commit, and then follow `project.push_policy`:

```bash
git add <backlog.path>
git commit -m "chore(backlog): add <ID> <short title>"
# push_policy: auto   -> git push origin <project.primary_branch>
# push_policy: ask    -> ask the operator, then push
# push_policy: branch -> you should already be on a working branch; push it and open a PR
```

For a **phased split**, use one commit that names each id and the wiring, e.g.:
```
chore(backlog): add BL-126 <feat> v1 + BL-127 v2 (depends BL-126, soak-gated 2026-09-24)
```

Never `git add .` / `git add -A` — other dirty files in the tree are not this skill's concern. Append `project.commit_trailer` if the profile sets one.

### Step 8 — Report

One-line summary: the new id(s) (or the updated/superseded id), the priority, and the build-timing/wiring — for a split, name each id and its gate (`v2 depends <v1-id>, soak-gated <date>`) — plus the commit hash. Don't restate the whole flow.

## Quick reference

| Step | Action | Operator interaction |
|------|--------|----------------------|
| 1 | Clarify requirement | 1-3 free-text questions, one at a time; skip if already clear |
| 2 | Scope: one atomic item or phased split? | Split on risk-boundary / independently-valuable parts / soak between parts; keep tight v1, push rest to v2+; surface the split in ONE message for a yes |
| 3 | Dedup / adjacency scan via CLI `list`/`find` (all statuses), per item | Surface matches (id + status + relation); resolve expand-vs-split-vs-duplicate |
| 4 | Priority | `AskUserQuestion` selector: Critical / High / Medium / Low → `--priority`; ask once for a split set |
| 5 | Build timing | now / date (`--dnbb`) / event (notes) / depends-on (`--depends`); later phase → `--depends` earlier + `--dnbb` soak estimate |
| 6 | Write item(s) | `new-product-backlog` CLI (`add`/`edit`/`discard`); split → create in dependency order, feed each id into the next `--depends` |
| 7 | Commit (+ push per profile) | Stage the backlog file by explicit path; one commit naming all ids |
| 8 | Report | One line: id(s), priority, timing/wiring, commit |

## Common mistakes

- **Logging a multi-phase ask as one big item.** When parts cross a risk boundary, are each independently valuable, or are separated by a soak, split into atomic vertical wedges wired with `--depends` + `--dnbb`. Burying the phasing in `--notes` on one blob hides the gate and makes each phase un-schedulable — that's the exact thing this skill exists to prevent.
- **Over-splitting into horizontal fragments.** Don't slice one wedge into "schema" / "code" / "UI" items that individually ship nothing usable. Split only where each piece is independently shippable AND independently valuable; each split item must itself be a complete vertical wedge (all its surfaces included).
- **Setting `--dnbb` to a false-precision date on a soak-gated phase.** The soak is relative to the earlier phase *shipping*, which is unknown at add time. Use an operator-given date or a conservative today+estimate, and always keep the `--depends` link and the relative rule in `--notes` — they are the real gate.
- **Skipping the dedup check because the ask "sounds new."** Always scan the whole store first — adjacent items are easy to miss and expensive to untangle later. Run it for *each* item in a split.
- **Over-interrogating in Step 1.** This skill captures a requirement, it does not design the feature. The execution skills expand it. Ask the minimum.
- **Hand-editing the JSON.** Never open the backlog file with file tools, `sed`, or hand-written JSON. Every change goes through the `new-product-backlog` CLI, which is the sole writer and the only thing that keeps the file always-valid.
- **Stuffing priority/deps/timing into `notes`.** The schema has real `priority`, `dependencies`, and `doNotBuildBefore` fields — use them. Reserve `notes` for free-text with no field of its own (event-based timing, uniqueness boundary, supersede line, relative soak rule).
- **Inventing a dependency.** Only pass `--depends <ID>` when that id actually exists and the blocking relationship is real; the validator rejects phantom ids and cycles. For a split, create earlier phases first so the id exists before you reference it.
- **Physically deleting a duplicate.** Don't `rm` it — supersede via `discard` (status flips to `discarded`, the item is kept for history).
