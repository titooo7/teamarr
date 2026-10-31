# Porting the fork's customizations to newer Teamarr versions

(Changes 1–14, catalogued in `CUSTOMIZATIONS.md`, are Spanish-language
localization. Change 15 — separate-mode failover backups — is this fork's
first customization that isn't localization; see its own section below.
Changes 16 and 18b are upstream bug fixes, carried until upstream ships
equivalent fixes; change 17 is a fixed fork behaviour tweak; change 18a is
DB-only, no code. All of 15–18 are covered by the Step 3/Step 6/Appendix
entries below.)

**Written:** 2026-07-04 · **Updated:** 2026-08-22/23 (change #15 added) ·
**Source fork:** v2.12.5
(`dev-custom-2.12.5` @ tag `v2.12.5`; run `git rev-list --count v2.12.5..HEAD`
for the exact current commit count) · **Validated
against:** upstream v2.12.5 (port from v2.12.4 completed 2026-08-18)

> ✅ **Port history:** v2.6.1 → v2.8.0 (2026-07-04, migrations renumbered to
> v77/v78) → v2.12.2 (2026-07-18, renumbered to **v84/v85**, moved into
> upstream's new `migrations/versioned.py` package) → v2.12.3 (2026-07-31,
> renumbered to **v85/v86** — upstream took migration number 84 for itself)
> → v2.12.4 (2026-08-07, **no renumbering needed** — upstream added zero new
> versioned migrations; still v85/v86, schema 86) → v2.12.5 (2026-08-18,
> **again no renumbering needed** — same reasoning, still v85/v86, schema 86).
>
> **For the NEXT port (v2.12.5 → newer), cherry-pick the FULL commit range**
> from this repo's current branch tip:
> ```bash
> git cherry-pick v2.12.5..dev-custom-2.12.5
> ```
> This is a change in approach from the v2.12.3 port guide (which said to
> cherry-pick a curated 17-commit subset and redo golden regeneration +
> renumber sweep fresh every time). **Cherry-pick everything instead** —
> it's simpler and was proven clean on two consecutive ports now: 20/21 fork
> commits applied with zero conflicts on the v2.12.4 port (one trivial
> conflict), and all 26 fork commits applied with **zero conflicts** on the
> v2.12.5 port, exactly matching the pre-flight recon's prediction. The
> golden-regeneration and renumber-sweep-fixup commits from past ports are
> now just inert history when they land on a target that doesn't need them
> (as neither v2.12.4 nor v2.12.5 did) — they cost nothing to carry forward.
> **Still redo Step 4's golden regeneration and Step 5's renumber-sweep grep
> fresh on the new target regardless** — never trust old golden files or old
> renumbering as final; only trust freshly-regenerated/freshly-grepped
> output. If the new target's migrations conflict with v85/v86 (upstream
> claims a number again), resolve renumbering with NEW commits on top of the
> full cherry-picked range, the same way the v2.12.3 port did — don't try to
> replay history that was numbered for a different target.
>
> **One cherry-pick gotcha found on the v2.12.5 port:** if the working tree
> has uncommitted local changes to a file a later commit in the range also
> touches (here: `CLAUDE.md`, restored from the untracked personal overlay
> before the cherry-pick started), `git cherry-pick` can abort mid-sequence
> with "local changes would be overwritten." Discard the dirty file first
> (it's safe if you already saved the overlay to `/tmp` per Step 1) —
> `git checkout -- CLAUDE.md` — then **`git cherry-pick --abort` and restart
> the whole range from scratch** rather than `--continue`; `--continue`
> after that kind of failure can silently commit an earlier pick as empty
> and skip its content (verify with `git log --oneline` against the
> expected commit count either way).

This guide re-applies the fork's customizations (catalogued in
`CUSTOMIZATIONS.md`) onto a **new upstream source tree**. It complements —
does not replace — `CUSTOMIZATIONS.md`, whose re-apply runbook assumes the
*same* version inside a running container.

---

## What was learned porting to v2.25.1 (2026-10-31) — READ THIS FIRST

v2.12.5 → v2.25.1 was 21 releases / 816 upstream commits, and it changes how
the next port should be done. Everything below the "Step" headings further
down was written for small minor-version hops and still applies in spirit.

**1. Don't cherry-pick the history on a big jump — 3-way-apply the net diff.**
Cherry-picking `v2.12.5..dev-custom-2.12.5` conflicted on the very first
commit (6 files). What worked: start `dev-custom-X.Y.Z` from the new tag, then
`git diff <old-tag> <old-fork-branch> -- <files> | git apply -3` per area
(localization, #17, #18b, tests), resolve the few `U` files by hand, and
re-implement anything whose host code was refactored (#15). In zsh, expand a
file list held in a variable with `${=F}` or `git diff` sees one bogus path.
Work with `--no-commit`-style staging if commits aren't authorized yet.

**2. Migrations: renumbered AND made additive.** Upstream used 85–103, so the
fork's v85/v86 became **v104/v105**. The old bodies did
`UPDATE … SET match_terms = <literal>` — re-run under new numbers they would
have wiped hand-added terms (prod has `MAX ES`, `Fanatiz`, `VIX` on Español).
They now append missing terms only (`_append_exception_keyword_terms`). Keep
them additive forever; the next renumber then costs nothing.

**3. Production needs `schema_version` set to 84 before the first boot.** Prod
says 86 (the fork's old numbers), so upstream's real v85/v86 (CFL → Bell Media)
would be skipped. Verified on a prod-DB copy: from 84 the chain runs 85→105 with
no errors; keyword rows, the `' - '` separator, template art URLs, row counts
and the #15 settings come out byte-identical. The only setting upstream changes
is v88: `global_channel_mode` manual → auto, 77 league starts → pinned blocks.
That layout was checked: v2.25.1 numbers prod's channels exactly as v2.12.5's own
code does today (prod's NBA 235–256 are merely stale; both versions put them at
290–311 on a full renumber).

**4. Default keyword seed moved out of `schema.sql` (#726).** It is now
`DEFAULT_EXCEPTION_KEYWORDS` in `teamarr/database/exception_keywords.py`
(plus the old `EXCEPTION_KEYWORDS_SEED_V43` in `checkpoint_v43.py`) — both
carry the Spanish labels. v93 marks those labels as seeded, so prod never gets
English duplicates. Upstream tests that name default labels
(`tests/test_exception_keyword_seed.py`, `test_exception_keyword_match_sources.py`)
were changed to the Spanish ones.

**5. Upstream reached the fork's code from the other side.** #16 is fixed
upstream (#716) — dropped. #17's double-swap guard exists upstream (#1119) —
took upstream's. Country translation: upstream made `translate_cities()`
(in `utilities/fuzzy_match.py`) the one city pass shared by stream AND provider
names (#797); the fork's country pass stays stream-side only, layered after it
in `apply_city_translations()`. Accent stripping: every keyword caller now goes
through `check_exception_keyword` → `_first_keyword_match` (incl. the new
EPG-programme-title path, #829), which is where `_strip_accents` is applied.

**6. #15 now lives in a stage after stream ordering.** `_stage_separate_fallbacks`
in `generation.py`, registered right after `_stage_stream_ordering`; the
backup offset is applied in phase 1 of `channel_steps.apply_stream_ordering` and
in `reorder_channel_streams`; phantom purge mirrors #1097 (catalog-unknown ids
only, windowed rows held back). `tests/epg/test_generation_contract.py` counts
13 cancellation checkpoints (upstream 12) because of the extra stage.

**7. Tests touched for fork behaviour (re-check each port):** schema-version
asserts (`== 105`); XMLTV goldens (`UPDATE_GOLDENS=1` — diff must be only
`lang="es"` plus the known #13 `Belgica/Espana` icon); day-first dates in
`tests/templates/test_starter_xmltv_goldens.py` and
`test_segment_start_context.py`; `tests/test_keyword_ordering_one_swap.py`
mirrored to keyword-first; lane/order-mode goldens pin
`KEYWORD_CHANNELS_FIRST=False` via an autouse fixture.

**8. Deploy reminders found this port:** `data/tsdb_seed.json` differs from
prod's (bind-mount gap — copy it explicitly); the image must be run once
against a prod-DB copy with Dispatcharr creds blanked **and** `--network none`
(blanking alone still let a login through in 2026-08).

## New in the fork (2026-08-22): separate-mode failover backups — a fourth port-check surface

Change #15 in `CUSTOMIZATIONS.md` (`teamarr/consumers/lifecycle/
separate_fallbacks.py`) is the fork's first feature that isn't Spanish
localization. It touches upstream code in exactly **four small spots**
(everything else is one new, fully fork-owned file) — check each of these
against the target on every future port, the same way you already diff
`normalizer.py`/`constants.py` for the localization changes:

1. **`teamarr/consumers/generation.py` — `_apply_stream_ordering`'s reorder
   loop.** It's the only site that rewrites stream priorities from ordering
   rules; the fork adds `BACKUP_PRIORITY_OFFSET` for `is_backup` rows there.
   If upstream restructures this loop (different variable names, moves the
   `update_stream_priority` call, splits the function), the offset-add needs
   to move with it or backups silently flatten back into the primary's
   priority band. Also re-check where `apply_separate_fallbacks()` is
   called — it must stay **after** `timer.mark("stream_ordering")`, never
   before (see the module's docstring for why).
2. **`teamarr/consumers/lifecycle/cleanup.py` — both `is_backup` guards.**
   `cleanup_deleted_streams` (the M3U-vanish path) must keep skipping
   `is_backup` rows when categorizing valid/missing/changed streams;
   `cleanup_disabled_groups` must keep computing its "does anything else
   feed this channel" `remaining` check over non-backup rows only. If
   upstream restructures either function's stream-categorization logic,
   re-locate and re-apply both guards — they're the highest-risk edits in
   the whole feature (a regression here means a backup silently starts
   affecting channel lifetime, which it must never do).
3. **`teamarr/database/channels/streams.py` — `add_stream_to_channel`'s
   `allowed_fields` list.** Must keep including `"is_backup"`, or every new
   backup row silently attaches with `is_backup=0` and immediately becomes
   indistinguishable from a real primary stream (breaking every guard above
   at once).
4. **Schema:** `settings.separate_fallback_enabled`,
   `settings.separate_fallback_count`, `managed_channel_streams.is_backup`
   are plain `ADD COLUMN`s in `schema.sql` — **no migration, no
   `schema_version` bump**, same "reconciliation-only" pattern as any other
   column addition (see `MIGRATIONS.md`: `reconcile_schema()` ALTERs in any
   column present in `schema.sql` but missing from the live DB,
   automatically, on next startup). Nothing to renumber here even if v85/v86
   need renumbering for an unrelated upstream collision — these three
   columns are independent of the versioned-migration chain entirely.

Also worth a quick diff-check (lower risk, but still fork-owned logic that
assumes today's shape of things): `check_exception_keyword()`'s return
shape (label + behavior) that `_eligible_groups()` depends on for the
per-keyword-wins-over-global-mode derivation, and `get_ordered_stream_ids()`
in `streams.py` — the fork deliberately does **not** touch its `ORDER BY`
clause (two upstream tests hand-roll `managed_channel_streams` rows without
the `is_backup` column and would break); if upstream itself changes that
`ORDER BY`, re-verify the priority-offset design still keeps the primary
first without needing to reference `is_backup` directly there.

---

## What was learned porting to v2.12.5 (2026-08-18)

- **`data/tsdb_seed.json` is a standing runbook defect — check it on
  EVERY port, not just when you notice the file changed upstream.**
  `docker-compose.yml` bind-mounts `./data:/app/data`, which **shadows** the
  copy the Dockerfile bakes into the image (`Dockerfile:38`), and
  `teamarr/database/seed.py` reads `<project root>/data/tsdb_seed.json` at
  runtime. Every deploy runbook to date (including this one, until now)
  rsyncs to `/opt/teamarr` with `--exclude data/`, which means **prod's seed
  file never gets updated by a normal deploy**, no matter how many releases
  pass. This port's cherry-picked tree got a fresh `data/tsdb_seed.json`
  from the `git checkout -b ... v2.12.5` step (WPBL added, +283/−244 vs the
  old file) — that refresh would have silently never reached production
  without an explicit extra copy step. **Add this to Step 6 of every future
  port unconditionally:** `ssh hetzner "cp .../tsdb_seed.json
  .../tsdb_seed.json.bak-<date>"` then `scp data/tsdb_seed.json
  hetzner:/opt/teamarr/data/tsdb_seed.json` — don't wait for a recon step to
  flag that the file changed; the shadowing bug means it's always at risk of
  going stale regardless of whether upstream touched it this release. A
  real fix would change the seed loader to prefer a newer bundled seed over
  a stale bind-mounted one (or version the seed file itself), but that's an
  upstream code change, not something to patch in the fork — documenting
  the gap here is the durable mitigation until then.
- **A feed-separation / team-stream-migration release note is a "check
  first, don't just deploy" flag, not a blocker.** v2.12.5's release notes
  document that with `feed_separation_enabled` AND `feed_detect_team_names`
  both on, team streams migrate from base channels into feed channels on
  the first EPG generation after upgrade — a real behavior change that
  could look alarming in a post-deploy diff if you weren't expecting it.
  The fix is cheap: read both flags from the prod `settings` table
  (`SELECT feed_separation_enabled, feed_detect_team_names FROM settings
  WHERE id=1`) as a pre-flight check before deploying. On this port,
  `feed_separation_enabled=0` on production, so the migration path never
  triggered — but the check is what tells you that, rather than assuming.
  Add an equivalent pre-flight settings check for any future release note
  that describes an automatic first-run data migration.
- **Cherry-picking the full range works, but sequence-state recovery from a
  failed pick needs care — see the cherry-pick gotcha in the callout above.**
  Restarting the whole range after `--abort` (rather than trying to salvage
  a partial sequence with `--continue`) is simpler to verify correct: just
  confirm the final commit count against `git rev-list --count`.
- **The recon-driven "expect zero/near-zero conflicts" prediction held
  exactly.** Doing the `gh api .../compare/OLD...NEW` diff before touching
  the tree (identifying exactly which fork-touched files upstream also
  changed, and confirming the hunks are disjoint by line number) continues
  to pay off — this port's recon named the only two files that could
  conflict (`constants.py`, `normalizer.py`) and both cherry-picked clean.
  Keep doing this recon step before every future port rather than starting
  the cherry-pick blind.

## What was learned porting to v2.12.4 (2026-08-07)

- **Don't assume a migration renumbering is needed — check first.** Every
  prior port (v2.8.0, v2.12.2, v2.12.3) needed the fork's migration numbers
  bumped because upstream had claimed them. This port didn't:
  `git log v2.12.3..v2.12.4 -- teamarr/database/migrations/versioned.py`
  came back empty, and `schema_version INTEGER DEFAULT` was still `84` on
  the target. **v85/v86 stayed valid untouched.** The check is the same
  either way (Step 2 below) — just don't assume the answer before running it.
- **Schema reconciliation can absorb a whole release's DB changes with zero
  fork involvement.** v2.12.4 added two new columns
  (`managed_channels.event_end_estimate`, `managed_channel_streams.feed_side`)
  purely via `CREATE TABLE` edits in `schema.sql` — no migration block at
  all, because `reconcile_schema()` (`teamarr/database/connection.py`)
  diffs the live DB against `schema.sql` on every startup and adds missing
  columns automatically, independent of `schema_version`. **This meant the
  usual "reset schema_version before first boot of the new image" step
  (present in every prior port's runbook) was not needed this time** — the
  production DB stayed at schema 86 across the whole port with zero
  manual intervention. Don't assume this holds for the next port either —
  it depends entirely on whether the new release's DB changes are plain
  columns (reconciliation-only) or need a data transform (needs a real
  migration, which DOES need the renumber-or-not check above).
- **Cherry-picking the full commit range from the previous fork branch, not
  a curated subset, is the simpler and more robust default.** See the port
  history note above. The only reason the v2.12.3 port used a curated
  17-commit list was to avoid replaying port-specific golden/renumber
  commits that were numbered for the v2.12.2→v2.12.3 gap specifically — but
  those commits are harmless no-ops to replay when the new target doesn't
  need renumbering, and when it does, fixing forward with new commits is no
  harder than it was before. Prefer the full range unless a specific
  conflict makes it not worth it.
- **A regression accepted on a previous port can become worth fixing on the
  next one.** Customization #13 (national-team art URLs resolving Spanish
  country names, from v2.12.3's #484 interacting with fork customization
  #7) was accepted as-is on 2026-07-31. It got fixed on this port via new
  customization #14 (`{home_team_en}`/`{away_team_en}`, fork-owned
  variables that never translate) — not because anything upstream changed,
  but because the port session was a natural moment to invest in a
  permanent fix (new variable names can never collide with anything
  upstream does) instead of carrying the regression forward indefinitely.
  Re-evaluate every "accepted for now" item in `CUSTOMIZATIONS.md` at each
  port — the cost/benefit can shift even when nothing about the regression
  itself changes.

## What was learned porting to v2.12.3 (2026-07-31, still applies)

- **Upstream can take a fork migration number for itself.** v2.12.3 added its
  own `_migrate_v84_filter_consolidation` (#484) — the exact number (84) the
  v2.12.2 fork's first customization migration occupied. **Always check
  whether upstream added new migrations in the target release BEFORE
  assuming the fork's existing numbers are still free** — a `git log
  --oneline v2.12.2..v2.12.3 -- teamarr/database/migrations/versioned.py`
  (or the GitHub compare view) on the target repo shows this immediately.
  When it happens, both fork migrations shift up by however many numbers
  upstream claimed (here: +1, so v84→v85 and v85→v86) — this is a normal,
  expected outcome of the port, not a sign something went wrong.
- **A fork variable can become collateral damage of an unrelated upstream
  refactor.** v2.12.3's #484 retired several `*_pascal`/`*_lower` template
  variables (including `home_team_pascal`/`away_team_pascal`) in favor of a
  general `|filter` chain, with a permanent legacy-alias fallback
  (`_LEGACY_ALIASES` in `templates/resolver.py`) so old templates keep
  rendering. The alias resolves the RETIRED name via the CURRENT value of its
  base variable (`{home_team_pascal}` → `{home_team|pascal}`) — so if a fork
  customization has changed what the base variable (`home_team`) resolves to
  (customization #7 translates it to Spanish for display), the retired
  variable's behavior silently changes too, even though nothing in the fork
  touched it. **When a port shows upstream deleting/aliasing a variable the
  fork's templates reference, check what base variable the new alias reads
  from and whether the fork has changed that base variable's meaning.** This
  is exactly why templates should be treated as part of the verification
  surface on every port, not just the Python diff — see customization #13 in
  `CUSTOMIZATIONS.md` (now fixed via #14) for the specific instance.
- **Golden regeneration can surface exactly this kind of interaction.**
  Regenerating `tests/templates/goldens/*.xml` with `UPDATE_GOLDENS=1` after
  the cherry-picks is not just a `lang="es"` formality — on the v2.12.3 port
  it also caught the `home_team_pascal` art-URL change. Always read the full
  golden diff, not just check it's non-empty, and treat any change beyond
  the expected `lang` swap as a signal to investigate before accepting it.
  (On the v2.12.4 port the diff was empty — also worth confirming rather
  than assuming.)

## What was learned porting to v2.12.2 (2026-07-18, still applies)

- **Nothing was upstreamed.** Upstream still seeds English labels, has zero
  i18n infrastructure, and (absent the fork) hardcodes `lang="en"` in XMLTV.
  All customizations are still needed. (A UI language toggle was considered
  and rejected: it would touch schema/settings/UI/every template variable and
  increase the per-release merge surface. Revisit only if upstream adds i18n
  hooks.)
- **Migrations live in `teamarr/database/migrations/`** (`versioned.py` for
  data migrations, `pre.py` for structural ones; conventions in
  `teamarr/database/MIGRATIONS.md`, enforced by
  `tests/migrations/test_migration_conventions.py`). Register new/renamed
  fork migration functions in `migrations/__init__.py` (imports + `__all__`).
- **Tests live in subdirectories** (`tests/migrations/`, `tests/matching/`,
  `tests/lifecycle/`, `tests/templates/`, …). Git rename detection follows
  most fork edits automatically; new fork test files must be `git mv`-ed into
  the right subdir if upstream reorganizes again.
- **XMLTV goldens need regeneration every port**, not just re-checking:
  `UPDATE_GOLDENS=1 pytest tests/templates/test_starter_xmltv_goldens.py`,
  then read the full diff.
- Re-verify for any target: check whether upstream added migrations
  (`git log <old-tag>..<new-tag> -- teamarr/database/migrations/versioned.py`
  on the target repo) and the current
  `schema_version INTEGER DEFAULT <N>` / `consolidation_exception_keywords`
  seed block in `teamarr/database/schema.sql`.

---

## Step 1 — Set up the target tree (per MyApps conventions)

```bash
cd /home/tito/MyApps

# Pristine reference copy (never modified)
git clone --branch vX.Y.Z --depth 1 https://github.com/Pharaoh-Labs/teamarr.git \
    TEAMARR_vX.Y.Z_OFFICIAL_UNTOUCHED_SOURCE_CODE

# Working fork: copy THIS repo so the custom commit objects come along
cp -r Teamarr_fork_v2.12.5 Teamarr_fork_vX.Y.Z
cd Teamarr_fork_vX.Y.Z
rm -rf .pytest_cache .ruff_cache .venv
cp CLAUDE.md /tmp/claude-fork-overlay.md   # save the personal overlay aside
git stash -u
git fetch origin --tags
git checkout -b dev-custom-X.Y.Z vX.Y.Z
git stash pop
```

> The custom commit hashes only exist in the local fork repo — that's why we
> copy it rather than fresh-cloning. `git stash pop` may conflict on
> `CLAUDE.md` (personal overlay vs upstream's file, if upstream changed it
> since the last port — it didn't between v2.12.4 and v2.12.5, so the pop was
> clean that time). If it conflicts, **take upstream's version**
> (`git show vX.Y.Z:CLAUDE.md > CLAUDE.md && git add CLAUDE.md`) — `git
> checkout --theirs` picks the STASH side in a stash-pop conflict, which is
> the OPPOSITE of what you want here; use `git show <tag>:<path>` instead to
> be sure. Either way, take upstream's tracked `CLAUDE.md` as the starting
> point and re-apply the (updated) personal overlay from
> `/tmp/claude-fork-overlay.md` at the end (Step 8).
> `CUSTOMIZATIONS.md`, `PORTING-TO-NEW-VERSIONS.md` and `docker-compose.yml`
> are **tracked** and arrive via cherry-pick; `HANDOFF-*.md` and
> `docker-compose.override.yml` are untracked/ignored personal files.

## Step 2 — Find the target's schema version and check whether renumbering is needed

```bash
grep -n 'schema_version INTEGER DEFAULT' teamarr/database/schema.sql
grep -n 'current_version < ' teamarr/database/migrations/versioned.py | tail -3
# Did upstream claim the fork's CURRENT migration numbers (v85/v86)?
git log <old-tag>..<new-tag> --oneline -- teamarr/database/migrations/versioned.py
```

**If that log is empty and `schema_version DEFAULT` matches what the fork
already expects (as of this writing: 84, fork uses 85/86) — no renumbering
is needed.** Skip straight to Step 3. This was the case for both the
v2.12.3→v2.12.4 port and the v2.12.4→v2.12.5 port; don't assume it will be
again.

**If upstream added migrations that consumed v85 and/or v86** — the fork's
numbers must move to the target's latest `DEFAULT` + 1 (and +2), regardless
of what the fork's numbers were on the previous version. **Do not** "leave a
gap" (e.g. jump to 900): the `if current_version < N:` chain is strictly
linear, and jumping `schema_version` ahead would make every future upstream
migration get skipped forever.

Also check whether the target added any new columns via plain `schema.sql`
edits (no migration block) — those are handled by `reconcile_schema()`
automatically and need **no** fork action at all beyond confirming they show
up after Step 3's cherry-pick (see the v2.12.4 lesson above).

## Step 3 — Sanity-check the touched code still exists

```bash
grep -rn 'def check_exception_keyword\|def _make_keyword_pattern' teamarr/database/channels/keywords.py
grep -n  'def slugify_keyword' teamarr/consumers/lifecycle/types.py
grep -n  'def apply_city_translations' teamarr/consumers/matching/normalizer.py
grep -n  'def extract_home_team\|def extract_away_team\|def extract_home_team_en\|def extract_away_team_en' teamarr/templates/variables/home_away.py
grep -n  'EXCEPTION_KEYWORDS_SEED_V43' teamarr/database/checkpoint_v43.py
grep -n  'consolidation_exception_keywords' teamarr/database/schema.sql
grep -n  'POSTPONED_LABEL' teamarr/consumers/event_epg.py
grep -n  '_apply_migration' teamarr/database/migrations/versioned.py | head -2

# Change #15 (separate-mode failover backups) — see the "New in the fork
# (2026-08-22)" section above for the full four-touch-point writeup
grep -n  'BACKUP_PRIORITY_OFFSET\|def apply_separate_fallbacks' teamarr/consumers/lifecycle/separate_fallbacks.py
grep -n  'apply_separate_fallbacks\|is_backup' teamarr/consumers/generation.py
grep -n  'is_backup' teamarr/consumers/lifecycle/cleanup.py
grep -n  '"is_backup"' teamarr/database/channels/streams.py

# Change #16 (EPG anchor guard on reverse-alias retry) — one-line fix, see CUSTOMIZATIONS.md §16
grep -n  'anchor_dt=ctx.anchor_dt' teamarr/consumers/matching/team_matcher.py

# Change #17 (keyword channels sort before plain, same event) — see CUSTOMIZATIONS.md §17
grep -n  'keyword_sort' teamarr/database/channel_numbers.py
grep -n  'def enforce\|keyword_number' teamarr/consumers/enforcement/ordering.py

# Change #18b (EPG star-rating date-misparse fix) — see CUSTOMIZATIONS.md §18.
# #18a is DB-only (Step 6 below) and touches no code, so nothing to grep for it.
grep -n  '_RATING_SUFFIX' teamarr/consumers/matching/epg_matcher.py
```

If any anchor is missing (renamed/moved), fall back to manual re-application
using `CUSTOMIZATIONS.md` §"Detailed Change Descriptions" — the *intent* of
each change is version-independent. Also check whether upstream retired or
re-aliased any template variable the fork's stored templates reference
(customization #13's history is exactly this pattern) — a variable
disappearing from the registry but still "working" via a legacy alias is
easy to miss.

## Step 4 — Cherry-pick the full commit range

```bash
git cherry-pick v2.12.5..dev-custom-2.12.5   # oldest first, resolve/continue as needed
```

(Substitute the actual previous fork tag/branch — `v2.12.5..dev-custom-2.12.5`
is this repo's range as of this writing; the next port cherry-picks from
whatever branch it copied in Step 1. If any commit in the range fails with a
"local changes would be overwritten" error because of a dirty tracked file
like `CLAUDE.md`, discard that file's local changes and **restart the whole
cherry-pick from scratch** — see the gotcha in the callout near the top of
this doc.)

Conflict resolutions that recur:

| File | Conflict | Resolution |
|---|---|---|
| `teamarr/database/schema.sql` | `DEFAULT` version, or a disjoint upstream column addition nearby | If renumbering (Step 2 said yes): take the **new fork number**. If not: usually auto-merges — the fork edits two small, stable regions (`schema_version` line, `consolidation_exception_keywords` seed block) that rarely overlap upstream's own edits. Keep the Spanish seed block either way. |
| `teamarr/database/migrations/versioned.py` | fork blocks vs new upstream migrations | Fork guard blocks go **after upstream's last block**; if renumbering, rename both the guard block AND the migration function's own name/docstring/log lines. Register the (renamed) functions in `migrations/__init__.py` (imports + `__all__`). |
| `CLAUDE.md` (tracked) | upstream rewrote it | Take upstream's, bump its "Schema version" table row to the fork number. |
| `docker-compose.yml` | upstream reworded a comment near a fork-owned env var line | Keep the fork's values (image, TZ, expose), take upstream's comment wording — this is the one conflict that recurred on the v2.12.4 port. |
| `docs/reference/architecture/migrations.md` | version history | Take upstream's; append the two fork rows; bump the "Current schema version" line if it changed. |
| `tests/**` version assertions | final schema number | Only relevant if renumbering happened — take the fork number everywhere (Step 5 grep — do this with a script). |
| `tests/templates/goldens/*.xml` | `lang` attribute, or nothing at all | Regenerate on the target regardless (`UPDATE_GOLDENS=1`), read the full diff (Step 4b) — don't assume "no conflict" means "no diff needed." |
| `teamarr/consumers/generation.py` | upstream restructures `_apply_stream_ordering`'s reorder loop, or moves where/when it's called relative to `timer.mark("stream_ordering")` | Re-apply the `BACKUP_PRIORITY_OFFSET` add and the `apply_separate_fallbacks()` call **immediately after** the stream-ordering phase, never before (see change #15's writeup for why the ordering matters) |
| `teamarr/consumers/lifecycle/cleanup.py` | upstream restructures `cleanup_deleted_streams`'s stream categorization or `cleanup_disabled_groups`'s `remaining` check | Re-apply both `is_backup`-skip guards at their new locations — these are the highest-risk edits in change #15; a regression here means a backup silently starts affecting channel lifetime |

Then regenerate the goldens fresh (don't just take the cherry-picked files):

```bash
UPDATE_GOLDENS=1 .venv/bin/python -m pytest tests/templates/test_starter_xmltv_goldens.py
git diff tests/templates/goldens/
```

**Read the whole diff.** By now (post-v2.12.3) every fork golden should
already carry `lang="es"`, so the expected result on a port where nothing
else changed is an **empty diff** (confirmed on the v2.12.4 port). Any diff
at all — even a small one — needs investigating before committing, not just
eyeballing that it's "small." That's exactly how the v2.12.3 port caught the
`home_team_pascal` art-URL shift.

⚠️ When staging conflict resolutions, use explicit `git add <files>` — a
blanket `git add -A` will sweep the untracked personal files
(`HANDOFF-*.md`, `docker-compose.override.yml`) into the commit.

## Step 5 — Renumber sweep (only if Step 2 found a collision)

If Step 2 found upstream had claimed v85 and/or v86, do a full grep sweep
after cherry-picking — a single sed pass over `_migrate_vNN_*` function names
is not sufficient, it misses test **class** names (`TestVNN...`) and prose
references in docstrings/comments that don't share the function's exact
token:

```bash
grep -rn 'migrate_vOLD\|TestVOLD' teamarr/ tests/
grep -rn 'schema_version.*== [0-9][0-9]' tests/   # eyeball every result, not just fork-added files
grep -n 'schema_version INTEGER DEFAULT' teamarr/database/schema.sql
```

Files that carry the final schema number: `schema.sql` (DEFAULT),
`docs/reference/architecture/migrations.md`, `CLAUDE.md` (tracked),
`tests/migrations/test_checkpoint_v43.py`,
`tests/migrations/test_subscription_migration.py`,
`tests/migrations/test_versioned_migrations.py` (×5),
`tests/test_media_server_settings.py`,
`tests/migrations/test_migration_helpers.py` (function names, class names,
AND docstrings/comments — check all three independently).

**If Step 2 found no collision (as on the v2.12.4 and v2.12.5 ports), skip
this step entirely** — but still run the same grep once as a sanity check;
it should come back empty (fork numbers unchanged, matching Step 2's
finding).

> **⚠️ Existing production DB warning — only applies when renumbering
> happened.** If the fork's migration numbers moved, the prod DB carries the
> PREVIOUS fork's numbering and has never run the upstream migrations that
> share those numbers in the new release. Before first boot of the new
> image: back up `data/teamarr.db`, then reset `schema_version` to the last
> upstream migration that actually ran on it. **If Step 2 found no
> collision, skip this entirely — no reset needed** (confirmed safe on the
> v2.12.4 port: prod DB stayed at schema 86 across the whole deploy with no
> manual reset, verified via `init_db` against a live prod-DB copy).
>
> Fork migrations are idempotent — re-running them is a safe no-op.
> When a reset IS needed: stop the OLD container before the reset and don't
> let it boot again afterwards (it would re-apply its own migrations and
> undo the reset). Sequence: `docker compose down` → backup → reset → deploy
> new image → `up -d`.
>
> (Historical resets: v2.8.0-fork DB (78) → 76 before v2.12.2's image;
> v2.12.2-fork DB (85) → 83 before v2.12.3's image. **v2.12.3→v2.12.4 and
> v2.12.4→v2.12.5: no reset, none needed.**)

## Step 6 — Re-apply the DB-only customizations

Seeds intentionally stay `consolidate`/stock-art-URLs; the live DB gets:

```sql
UPDATE consolidation_exception_keywords SET behavior='separate' WHERE behavior='consolidate';
```

Plus, as of the v2.12.4 port, customization #14's art-URL rewrite (see
`CUSTOMIZATIONS.md` §14 for the full SQL and which columns to check — the
column list can differ between DBs, always run the `SELECT` first).

Plus, as of 2026-08-23, the Español keyword's `match_terms` also carries
`MAX ES`, `Fanatiz`, and `VIX` terms (see `CUSTOMIZATIONS.md` §5's
addenda) — this is live-DB user data discovered from real stream names, not
something a fresh seed or a versioned migration carries, so it's easy to
lose on a port that only re-checks `behavior`. Confirm they're present:
`SELECT match_terms FROM consolidation_exception_keywords WHERE
label='Español'` should contain all three.

Plus, as of 2026-08-30 (change #18a — see `CUSTOMIZATIONS.md` §18), a
`detection_keywords` row makes `" - "` a matchup separator:

```sql
INSERT INTO detection_keywords (category, keyword, is_regex, target_value, enabled, priority, description)
VALUES ('separators', ' - ', 0, NULL, 1, 100,
        'Dash matchup separator: Movistar/European EPG titles (Real Madrid - Málaga)');
```

Same class of gap as the Español match-terms above: this is a live-DB row,
not a seed or a versioned migration, so **it will not survive a port that
only re-checks `behavior` or the seed tables** — confirm with
`SELECT * FROM detection_keywords WHERE category='separators'` (should
return exactly this one row on a fork DB; upstream ships none). **Requires
a container restart after insert** — `DetectionKeywordService._separators`
is a process-lifetime cache, unlike the exception keywords above (which are
re-read every generation run).

(Full label/match-term SQL for DBs that somehow reverted the #1–#9 seed
changes: `CUSTOMIZATIONS.md` §"Step 2: Apply DB-only changes".)

## Step 7 — Verify

```bash
# Fresh venv (the copied .venv is stale/removed)
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

.venv/bin/ruff check teamarr/ tests/
.venv/bin/python -m pytest tests/ -q        # target: 0 fork-caused failures
                                             # (2252 passed / 0 failed on
                                             # v2.12.5 — the pre-existing
                                             # test_date_format_learning.py
                                             # flake from v2.12.4 and earlier
                                             # is GONE, upstream fixed it in
                                             # v2.12.5 (#553); confirm any
                                             # NEW failure reproduces on the
                                             # PRISTINE clone before blaming
                                             # the fork)

# Migration chain on a COPY of the REAL prod DB (safer than the local
# data/teamarr.db, which tends to be stale — pull it read-only first):
#   scp hetzner:/opt/teamarr/data/teamarr.db /tmp/prod-copy.db
#   (only reset schema_version if Step 5 found a collision) → run init_db →
#   expect final = fork number, reconcile_schema logs any new plain columns,
#   Spanish labels + behavior='separate' + 'ES:' term intact.

# Feature spot checks (venv, this tree):
.venv/bin/python -c "
from teamarr.consumers.matching.normalizer import normalize_stream
print(normalize_stream('Brasil vs Marruecos EN espanol').normalized)   # brazil vs morocco …
print(normalize_stream('partido en japones').normalized)               # japones NOT mangled
from teamarr.templates.variables.home_away import _translate_country_for_display as t
print(t('Spain'), '|', t('Spain U21'), '|', t('Real Madrid'))          # España | España U21 | Real Madrid
from teamarr.consumers.lifecycle.types import slugify_keyword
print(slugify_keyword('Español'))                                      # espanol
from teamarr.database.channels.keywords import check_exception_keyword
from teamarr.database.exception_keywords import ExceptionKeyword
kw = ExceptionKeyword(id=1, label='Español', match_terms='ES:', behavior='separate', enabled=True)
print(check_exception_keyword('ES: DW EN VIVO', [kw]))                 # ('Español', 'separate')
print(check_exception_keyword('ESPN: game', [kw]))                     # (None, None)
"
# NOTE: check_exception_keyword returns a TUPLE (label, behavior) — test with
# result[0] is not None, never 'result is not None'.

# Build + smoke-test the custom image (Dockerfile builds from the local tree)
docker build -t teamarr:custom \
  --build-arg GIT_BRANCH=dev-custom-X.Y.Z \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
# Run it TWO ways against isolated data dirs (NOT the real data/teamarr.db):
#  1. fresh empty dir — confirms clean-install behavior (schema inits at the
#     fork's DEFAULT, seeds stay at their stock/untranslated defaults).
#  2. a copy of the patched real prod DB — confirms the live-DB path: 0
#     errors, no unexpected re-migration, DB-only customizations present.
```

Then the usual local Docker soak before any production deploy (production
only when tito explicitly asks — see `/home/tito/MyApps/CLAUDE.md`).

## Step 8 — Housekeeping

- Restore and update the new folder's personal `CLAUDE.md` overlay (from
  `/tmp/claude-fork-overlay.md`): version numbers, new cherry-pick range,
  migration-number status (moved or not, and why), verification-status
  paragraph, TODO section.
- Update `CUSTOMIZATIONS.md` header (base version, commit count, schema
  numbers) and THIS file (commit range, learned-lessons section, prod-DB
  reset status) — grep the whole doc for the OLD version string after
  editing, the same way Step 5 does for schema numbers.
- Write a `HANDOFF-<date>.md` for the port session.
- The superseded fork/pristine folder pair becomes scheduled-for-deletion per
  MyApps convention (tito deletes them himself; update
  `/home/tito/MyApps/CLAUDE.md` folder list).

---

## Appendix — the changes at a glance (intent, not diff)

| # | Change | Where (as of v2.12.5) | Verify by |
|---|--------|-------|-----------|
| 1 | Accent-insensitive keyword matching (`_strip_accents`, both sides) | `teamarr/database/channels/keywords.py` + migration v85 in `migrations/versioned.py` | `espanol` stream text matches `Español` term |
| 2 | Spanish keyword labels in seeds | `schema.sql`, `checkpoint_v43.py` | fresh DB shows `Español`, `Francés`, … |
| 3 | Accent-strip in `slugify_keyword()` | `teamarr/consumers/lifecycle/types.py` | `Español` → `espanol` |
| 4 | ES/PT→EN `COUNTRY_TRANSLATIONS` for matching (derived, `\b`-bounded) | `constants.py` + `normalizer.py` | `Brasil vs Marruecos` → `brazil vs morocco`; `japones` intact |
| 5 | `ES:` in Español match terms | seeds + migration terms | `ES: DW` tagged; `ESPN:` not |
| 6 | `behavior='separate'` (DB-only) | live DB SQL | keywords table shows `separate` |
| 7 | EN→ES `ENGLISH_TO_SPANISH_COUNTRIES` display translation | `constants.py` + `templates/variables/home_away.py` | `España - Cabo Verde`; tvg-id/logs English |
| 8 | Youth/women suffixes in display | `home_away.py` | `Spain U21` → `España U21` |
| 9 | Spanish language names as match terms | seeds + migration v86 | `EN ALEMAN` / `en coreano` detected |
| 10 | Spanish EPG metadata | `event_epg.py` (`Aplazado: `), `utilities/xmltv.py` (`lang="es"`) + regenerated goldens | XMLTV output carries `lang="es"` |
| 11 | `{game_date_short}` day-first (`22-Jul`) | `templates/variables/datetime.py` | channel names show day-first dates |
| 13 | National-team art URLs via `{home_team_pascal}` — **fixed by #14** | interaction between #7 and upstream #484's `_LEGACY_ALIASES` | see `CUSTOMIZATIONS.md` §13 for history |
| 14 | `{home_team_en}`/`{away_team_en}` untranslated variables (fixes #13) | `templates/variables/home_away.py` (code) + DB-only SQL (templates) | `{home_team_en}` stays `Spain` where `{home_team}` shows `España`; art URL SQL rewrite confirmed on prod-DB copy |
| 15 | Separate-mode failover backups (opt-in, off by default — not Spanish localization) | `teamarr/consumers/lifecycle/separate_fallbacks.py` (new file); hooks in `generation.py` + `cleanup.py` | enable via settings, generate, confirm `[SEPARATE_FALLBACK] converged N channel(s)` in logs and every channel's slot #0 stream == its `primary_stream_id` |
| 16 | EPG anchor guard bypassed on reverse-alias retry — **upstream bug fix**, not localization | `teamarr/consumers/matching/team_matcher.py`, `_try_reverse_alias_match()` | a highlights/encore/replay programme titled the same as a live event no longer binds to it; see `CUSTOMIZATIONS.md` §16 for the production incident |
| 17 | Keyword channels sort before the plain channel, same event only — fixed fork behaviour, not localization | `teamarr/database/channel_numbers.py` (`keyword_sort`) + `teamarr/consumers/enforcement/ordering.py` (detection comparison, `seen`-guard) | `(Español)`/`(Portugués)` channel numbered lower than the plain channel for the same event; never crosses to a different event's channels |
| 18a | `" - "` as a matchup separator (DB-only, no code) | `detection_keywords(category='separators')` — live-DB row, see Step 6 above | Movistar/European titles like `Real Madrid - Málaga` extract a team pair (`classify_stream` → `TEAM_VS_TEAM`, not `PLACEHOLDER`) |
| 18b | EPG guide star-rating (`★N.N/10`) misread as a date — **upstream bug fix**, not localization | `teamarr/consumers/matching/epg_matcher.py`, `_RATING_SUFFIX` / `_clean_epg_segment()` | a programme whose sub_title carries a fractional star rating no longer gets a false `extracted_date`; see `CUSTOMIZATIONS.md` §18 for the production incident |
