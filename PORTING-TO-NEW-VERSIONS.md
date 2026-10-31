# Porting the fork's customizations to newer Teamarr versions

**Current state (2026-10-31):** fork based on upstream **v2.25.1**, branch
`dev-custom-2.25.1` (pushed to `titooo7/teamarr`), **schema 105**, fork
migrations **v104/v105**, LIVE in production. The fork's changes are catalogued in
`CUSTOMIZATIONS.md` (#1–#22; #13 is history, #16 was dropped because upstream
fixed it). This file is the **how-to for the next port**: Steps 1–9 below, then
a touch-point map of every change, then lessons from past ports.

**Port history:**

| Port | Date | Fork migrations | Notes |
|---|---|---|---|
| v2.6.1 → v2.8.0 | 2026-07-04 | v77/v78 | |
| → v2.12.2 | 2026-07-18 | v84/v85 | moved into upstream's `migrations/versioned.py` |
| → v2.12.3 | 2026-07-31 | v85/v86 | upstream took 84 |
| → v2.12.4 | 2026-08-07 | v85/v86 | no renumbering needed |
| → v2.12.5 | 2026-08-18 | v85/v86 | no renumbering needed |
| → **v2.25.1** | **2026-10-31** | **v104/v105** | 21 releases, 816 upstream commits; upstream took 85–103; net-diff method; prod reset 86 → 84; fixes #19/#20 found on deploy |

**Git facts the next port relies on:**
- Every fork branch (`dev-custom-2.8.0` … `dev-custom-2.12.5`, `dev-custom-2.25.1`)
  lives in this repo. Older fork folders were deleted on 2026-10-31; their
  history is here.
- Remotes: `origin` = Pharaoh-Labs/teamarr (upstream), `titooo7` = the private fork.
- Commit **only** with the noreply email
  `5730518+titooo7@users.noreply.github.com`, or GitHub rejects the push (GH007).
  Example: `git -c user.email=5730518+titooo7@users.noreply.github.com commit
  --author="titooo7 <5730518+titooo7@users.noreply.github.com>" …`.
  The old `dev-custom-2.12.x` branches carry the private email and must never
  be pushed as they are.
- Untracked on purpose: `CLAUDE.md` (personal overlay that replaces upstream's
  agent file), `docker-compose.override.yml` (Traefik labels), `HANDOFF-*.md`,
  `history/` (excluded via `.git/info/exclude`; holds the v2.12.5 overlay).

---

## Step 0 — Recon before touching anything (read-only)

```bash
cd /home/tito/MyApps/Teamarr_fork_v2.25.1
git fetch origin --tags
OLD=v2.25.1; NEW=vX.Y.Z; FORK=dev-custom-2.25.1
git rev-list --count $OLD..$NEW                       # size of the jump
# Which fork-touched files did upstream also change?
for f in $(git diff --name-only $OLD..$FORK | grep -vE '\.md$|goldens'); do
  git cat-file -e $NEW:$f 2>/dev/null && echo "$(git diff --shortstat $OLD $NEW -- $f) :: $f" || echo "GONE :: $f"
done
# Did upstream add migrations (fork numbers collide?) and what is the new DEFAULT?
git show $NEW:teamarr/database/schema.sql | grep -n 'schema_version INTEGER DEFAULT'
git diff $OLD $NEW -- teamarr/database/migrations/ teamarr/database/reconciliation.py | less
gh release list -R Pharaoh-Labs/teamarr -L 30          # read notes for breaking changes / first-run migrations
```

Read every upstream migration between the old and new schema numbers. List any
that touch the tables holding fork data: `consolidation_exception_keywords`,
`detection_keywords`, `templates`, `settings`, `managed_channel_streams`. Also
read `migrations/pre.py`: table rebuilds keyed on table state run regardless of
version. **Stop and decide** if any of them rewrites keyword labels or terms,
templates, or drops a table holding fork data.

Also check whether upstream fixed something the fork carries. #16 disappeared
that way (#716), and #17's double-swap guard became upstream's own (#1119).
Changes that are upstream bug fixes (#18b, #19, #20) are the likeliest to go
the same way.

## Step 1 — Set up the target tree

```bash
cd /home/tito/MyApps
git clone --branch vX.Y.Z --depth 1 https://github.com/Pharaoh-Labs/teamarr.git \
    TEAMARR_vX.Y.Z_OFFICIAL_UNTOUCHED_SOURCE_CODE          # pristine, never modified
cp -r Teamarr_fork_v2.25.1 Teamarr_fork_vX.Y.Z            # copy THIS repo: keeps every fork branch
cd Teamarr_fork_vX.Y.Z
rm -rf .pytest_cache .ruff_cache .venv frontend/node_modules frontend/dist
cp CLAUDE.md /tmp/claude-fork-overlay.md                  # personal overlay, restored in Step 9
git stash -u && git checkout -b dev-custom-X.Y.Z vX.Y.Z && git stash pop
# CLAUDE.md conflicts on pop when upstream changed it: take upstream's tracked file
git show vX.Y.Z:CLAUDE.md > CLAUDE.md && git reset -q CLAUDE.md && git stash drop
```

## Step 2 — Apply the fork, one area at a time (3-way merge of the net diff)

**Default method since v2.25.1:** apply the fork's *net* diff, not its commit
history. Cherry-picking `v2.12.5..dev-custom-2.12.5` conflicted on its first
commit. The net diff produced four small conflicts in total. A cherry-pick of
`v2.25.1..dev-custom-2.25.1` (5 clean commits) is reasonable only for a small
hop where recon shows disjoint hunks.

```bash
OLD=v2.25.1; FORK=dev-custom-2.25.1
# zsh: expand a list held in a variable with ${=F}
F="teamarr/database/channels/keywords.py teamarr/consumers/lifecycle/types.py ..."   # one area
git diff $OLD $FORK -- ${=F} | git apply -3
git status --short | grep '^U'                            # resolve these by hand
```

Areas, in order:
1. **localization** (#1–#14): `keywords.py`, `lifecycle/types.py`,
   `normalizer.py`, `constants.py`, `home_away.py`, `event_epg.py`, `xmltv.py`,
   `datetime.py`, `sample_data.py`, `exception_keywords.py`, `checkpoint_v43.py`
   and their tests.
2. **ordering** (#17).
3. **EPG matching fixes** (#18b, #19): `epg_matcher.py` and its tests.
4. **ESPN failed-fetch fix** (#20): `providers/espn/{client,provider,tournament}.py`,
   `services/sports_data.py` and its test.
5. **#15**: `separate_fallbacks.py` plus its hooks. Re-implement rather than
   force-merge if upstream refactored the host code again (see the map below).
6. **migrations** (Step 3).
7. **docs**: `CUSTOMIZATIONS.md`, this file, `docs/reference/architecture/migrations.md`.

**Conflict rule of thumb:** take upstream's structure and re-insert the fork's
*intent*, as described in `CUSTOMIZATIONS.md`. Mark fork code in upstream files
with `(fork)` / `Fork customization #N` comments, as the existing code does.
Commit (noreply email) after each area so a bad merge is easy to back out, or
stage only when commits aren't authorized yet.

## Step 3 — Migrations: renumber and keep them additive

- If upstream's chain now reaches or passes the fork's numbers, move the fork's
  two blocks to **upstream's new last number +1 and +2**. Never leave a gap: the
  `if current_version < N` chain is linear, so a jump would skip every future
  upstream migration. Rename the functions (`_migrate_vNNN_…`), log lines and
  docstrings, update `migrations/__init__.py` (imports + `__all__`), the
  `schema.sql` DEFAULT, `docs/reference/architecture/migrations.md`, and every
  test that asserts the final number. Find them with
  `grep -rn 'schema_version.*== [0-9]' tests/` and
  `grep -rn "== 105" tests/`.
- The bodies must stay **additive** (`_append_exception_keyword_terms`: append
  missing terms only, case-insensitive). Re-running them under a new number
  must never remove a term someone added by hand in production.
- **Production DB reset rule:** when the fork's numbers moved, prod's
  `schema_version` still holds the OLD fork number, which can hide upstream
  migrations that share those numbers. Before the first boot of the new image,
  set it to the **last upstream migration number that prod really ran**, which
  is the old fork's first number minus 1. For the next port from v2.25.1 that is
  103, if upstream claims 104/105. Do it with the container stopped and after
  the backup. Fork migrations are additive, so re-running them is harmless.

## Step 4 — DB-only customizations (they live only in the production DB)

None of these are in seeds or migrations, so a port can silently lose them.
Check each one on the prod-DB copy after the migration test (Step 6):

| What | Check |
|---|---|
| #6 every keyword `behavior='separate'` | `SELECT label, behavior FROM consolidation_exception_keywords` |
| Español extra terms `ES:, MAX ES, Fanatiz, VIX` (#5 addenda) | `SELECT match_terms FROM consolidation_exception_keywords WHERE label='Español'` |
| #14 art-URL templates use `{home_team_en|pascal}` | `CUSTOMIZATIONS.md` §14 `SELECT` → 0 rows still using `_team|pascal` |
| #18a `' - '` matchup separator row | `SELECT * FROM detection_keywords WHERE category='separators'` (needs a restart after any insert) |
| #15 settings `separate_fallback_enabled=1`, `count=3` | `SELECT separate_fallback_enabled, separate_fallback_count FROM settings` |

## Step 5 — Tests that encode fork behaviour (adapt, never weaken)

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest tests/ -q -p no:cacheprovider && .venv/bin/ruff check teamarr/ tests/
```

Expected fork-related failures and the right fix:
- **schema-version asserts:** bump to the new fork number.
- **XMLTV goldens:** `UPDATE_GOLDENS=1 .venv/bin/pytest tests/templates/test_starter_xmltv_goldens.py`.
  Read the diff. After normalising `lang="es"`→`"en"`, `Belgica/Espana`→`Belgium/Spain`
  and day-first dates, it must be empty.
- **Day-first dates in literal expectations:** e.g.
  `tests/templates/test_starter_xmltv_goldens.py` idle texts and
  `test_segment_start_context.py`. Also check whether upstream added new
  `%b %-d` sites in `templates/variables/datetime.py` that belong to
  `{game_date_short}`.
- **Default keyword labels in upstream tests:** use the Spanish ones
  (`tests/test_exception_keyword_seed.py`, `test_exception_keyword_match_sources.py`).
- **Keyword-first ordering (#17):** upstream lane and order-mode goldens pin the
  stock direction with an autouse fixture (`KEYWORD_CHANNELS_FIRST=False`).
  Any NEW upstream test module that numbers keyword channels needs the same
  fixture. First confirm the only difference is the same-event swap: flip the
  flag and run it.
- **New generation stage (#15):** `tests/epg/test_generation_contract.py`
  counts one extra stage and cancellation checkpoint.

Before blaming the fork for any other failure, reproduce it on the pristine
clone.

## Step 6 — Verify against a copy of the production DB

1. Copy prod's DB read-only: `scp hetzner:/opt/teamarr/data/teamarr.db <scratch>/prod.db`.
   Keep it in the scratch dir and **delete it afterwards**: it contains the
   Dispatcharr credentials.
2. Snapshot the fork-carrying rows: keyword rows, separators, templates
   1/3/5/13/14/16, settings, row counts. Apply the Step 3 reset if needed, run
   `init_db(<copy>)`, then diff the snapshot. **Pass** means no change except
   ones a named upstream migration explains.
3. If upstream migrates settings (as v88 did for manual numbering), compare
   channel numbers. Run `reassign_all_channels` with the OLD fork code and the
   NEW code on separate copies; the results must agree.
4. Run the feature spot checks:
   - `apply_city_translations('Brasil vs Marruecos EN espanol')` → `brazil vs morocco …`
   - `japones` stays unmangled
   - `España U21`
   - `slugify_keyword('Español')` → `espanol`
   - `check_exception_keyword` on `ES: DW` / `ESPN:` / `EN ALEMÁN`; it returns a
     TUPLE, so test `result[0]`
   - `_clean_epg_segment('… ★6.6/10')`
   - `build_match_input` on `DIRECTO Jornada 9: Chelsea - Manchester United T26/27`
     (no pipe)
5. Build the image and smoke-test two ways: a fresh empty data dir, and the
   prod copy run with **`--network none`**. Blanking the Dispatcharr
   credentials alone still let a login through in 2026-08.
6. Run a fresh independent verifier pass before deploying.

## Step 7 — Deploy (only when tito asks)

```bash
ssh hetzner 'cd /opt/teamarr && docker compose down && D=$(date +%Y%m%d) &&
  cp -p data/teamarr.db data/teamarr.db.bak-pre-vXYZ-$D && sha256sum data/teamarr.db*$D data/teamarr.db &&
  docker tag teamarr:custom teamarr:custom-<old>-rollback &&
  tar --exclude=./data --exclude=./.git -czf /opt/teamarr-code-<old>-rollback-$D.tgz .'
# schema reset if Step 3 says so:  sqlite3 data/teamarr.db "UPDATE settings SET schema_version=<N> WHERE id=1"
rsync -az --delete --exclude=/data/ --exclude=.venv/ --exclude=.pytest_cache/ --exclude=.ruff_cache/ \
  --exclude=__pycache__/ --exclude=/teamarr.db --exclude=.git/ --exclude=frontend/node_modules/ \
  --exclude=frontend/dist/ --exclude=/.claude/ --exclude=/CLAUDE.md --exclude=/docker-compose.override.yml \
  ./ hetzner:/opt/teamarr/                                # dry-run with -n first and read the deletions
scp data/tsdb_seed.json hetzner:/opt/teamarr/data/        # ALWAYS (bind mount shadows the image copy); back up the old one first
ssh hetzner 'cd /opt/teamarr && docker build -t teamarr:custom --build-arg GIT_BRANCH=dev-custom-X.Y.Z --build-arg GIT_SHA=<sha> . && docker compose up -d'
```

Then:
1. Check the migrations in `docker logs teamarr`.
2. **Wait for the startup cache refresh to finish** before generating: poll
   `docker exec teamarr curl -s localhost:9195/api/v1/cache/status` until
   `refresh_in_progress` is false. Startup refresh plus a generation together
   got the server throttled by ESPN (HTTP 403).
3. Generate: `docker exec teamarr curl -s -X POST -H "Content-Type: application/json" -d "{}" localhost:9195/api/v1/epg/generate`.
4. **Judge the result against a baseline captured before `down`:**
   - active channels, keyword channels, and attached primary/backup streams by
     `match_method`;
   - `lang="es"` count in `data/teamarr.xml`;
   - distinct matched streams in `epg_matched_streams` for the run.

   Don't use `streams_matched`, which changed meaning in v2.25.1. A big drop
   means stop and investigate (v2.25.1: 1,049 → 102 programmes, which turned
   out to be #19 and #20).
5. Watch for empty event-cache rows written during 403 bursts:
   `SELECT COUNT(*) FROM service_cache WHERE cache_key LIKE 'events_v2:%' AND data_json='[]' AND created_at > '<deploy time>'`.
   #20 prevents new ones; delete rows already poisoned with the container stopped.

**Rollback:** `down`; restore the DB backup (a newer-schema DB is not usable by
the old code); restore the code tarball; retag the rollback image as
`teamarr:custom`; `up -d`.

## Step 8 — Things production can still surprise you with

These come from real deploys. Anything a prod-DB copy can't show needs live
data:
- Guides change shape. #19 broke only with live Movistar/DAZN titles.
- ESPN throttling and caching (#20).
- Settings migrations that rearrange numbering (v88).
- Re-check every "accepted for now" item in `CUSTOMIZATIONS.md` on each port;
  #13 was accepted once and fixed a port later.

## Step 9 — Housekeeping

- Restore the personal `CLAUDE.md` overlay with a status block and deploy record.
- Update `CUSTOMIZATIONS.md` (header, new or dropped changes) and THIS file
  (history row, touch-point map, lessons section). Grep both for the old version
  string.
- Update `/home/tito/MyApps/CLAUDE.md` (the folder list) and memory.
- Push the new branch to `titooo7` (noreply email).
- The old fork folder and its untouched copy can be deleted once tito agrees.
  Their history stays in this repo.

---

## Touch-point map (as of v2.25.1)

Exact locations move between releases. Re-find them with the grep in the last
column.

| # | Change | Where | Re-find with |
|---|---|---|---|
| 1 | Accent-insensitive keyword matching | `database/channels/keywords.py`: `_strip_accents`, used in `_make_keyword_pattern` and `_first_keyword_match` (stream name, EPG programme title, event text) | `grep -n _strip_accents` |
| 2/5/9 | Spanish default keywords (labels, `ES:`, un-accented and Spanish-name terms) | `database/exception_keywords.py` `DEFAULT_EXCEPTION_KEYWORDS` (the seed moved out of `schema.sql` in #726) + `database/checkpoint_v43.py` `EXCEPTION_KEYWORDS_SEED_V43`; keep both in step | `grep -n "Español" teamarr/database/*.py` |
| 3 | Accent-strip in tvg-id slugs | `consumers/lifecycle/types.py` `slugify_keyword` | `grep -n "def slugify_keyword"` |
| 4/8 | ES/PT→EN country translation, stream side only, after upstream's shared `translate_cities` (#797) | `consumers/matching/normalizer.py` `apply_city_translations`; dicts in `utilities/constants.py` | `grep -n COUNTRY_TRANSLATIONS` |
| 6 | `behavior='separate'` | DB only | Step 4 |
| 7/10 | EN→ES country display incl. U21/W | `templates/variables/home_away.py` `_translate_country_for_display` | `grep -n _translate_country_for_display` |
| 11 | `Aplazado: ` and XMLTV `lang="es"` | `consumers/event_epg.py` `POSTPONED_LABEL`, `utilities/xmltv.py` `XMLTV_LANG` | `grep -n "POSTPONED_LABEL =\|XMLTV_LANG ="` |
| 12 | `{game_date_short}` day-first | `templates/variables/datetime.py` (`%-d-%b`), `templates/sample_data.py` | `grep -n "%-d-%b\|%b %-d"` |
| 14 | `{home_team_en}`/`{away_team_en}` | `templates/variables/home_away.py` + DB templates (Step 4) | `grep -n extract_home_team_en` |
| 15 | Separate-mode failover backups | new `consumers/lifecycle/separate_fallbacks.py`; stage `_stage_separate_fallbacks` registered right after `_stage_stream_ordering` in `consumers/generation.py`; backup offset in phase 1 of `generation_pipeline/channel_steps.py` `apply_stream_ordering`, in `database/channels/streams.py` `reorder_channel_streams`, and in the stream-explainer `expected_priority` in `api/routes/channels.py`; two guards in `consumers/lifecycle/cleanup.py` (`cleanup_deleted_streams`, `cleanup_disabled_groups`); `is_backup` in `add_stream_to_channel` allowed fields; settings in `database/settings/types.py`/`update.py`, `api/routes/settings/`; UI in `frontend/src/pages/channels/ChannelConsolidation.tsx`, `ChannelNumbering.tsx`, `api/settings.ts`; `ExceptionKeywordsCard.tsx` gate removed; 3 plain columns in `schema.sql` (reconciliation, no migration) | `grep -rn "is_backup\|BACKUP_PRIORITY_OFFSET\|separate_fallback" teamarr frontend/src` |
| 17 | Keyword channels before the plain channel (same event) | `database/channel_numbers.py` `KEYWORD_CHANNELS_FIRST` + `sort_key`; `consumers/enforcement/ordering.py` comparison `k > m` (the swap guard is upstream's #1119) | `grep -n "KEYWORD_CHANNELS_FIRST\|AS INTEGER) > CAST"` |
| 18a | `' - '` matchup separator | DB only (`detection_keywords`) | Step 4 |
| 18b | Strip EPG `★N.N/10` rating before date extraction | `consumers/matching/epg_matcher.py` `_RATING_SUFFIX` in `_clean_epg_segment` | `grep -n _RATING_SUFFIX` |
| 19 | Don't split dash-written matchups between the teams | `consumers/matching/epg_matcher.py` `_split_inline_matchup` (upstream #728 added `-` to `_INLINE_SEP`) | `grep -n _split_inline_matchup` |
| 20 | Never cache a failed ESPN fetch as an empty day | `providers/espn/client.py` `ESPNFetchError`; raised in `provider.py` (scoreboard + MMA) and `tournament.py`; `services/sports_data.py` `failed_buckets` skip-cache | `grep -rn "ESPNFetchError\|failed_buckets"` |
| 21 | Dash with a racing series on its left = race, not matchup | `consumers/matching/classifier.py` `_classify_racing_event` (`elif sep.strip() == "-"` branch) | `grep -n 'sep.strip() == "-"'` |
| 22 | EPG racing programme's broadcast instant counts as timed evidence | `consumers/matching/racing_matcher.py` `_match_to_event` (`timed_evidence`, `ctx.anchor_dt`) | `grep -n "timed_evidence"` |
| mig | Fork migrations v104/v105 (additive) | `database/migrations/versioned.py` (`_append_exception_keyword_terms`, `_migrate_v104_…`, `_migrate_v105_…`, blocks after upstream's last), `migrations/__init__.py`, `schema.sql` DEFAULT, `docs/reference/architecture/migrations.md` | `grep -rn "_migrate_v10[45]"` |
| — | #16 EPG anchor on reverse-alias retry | **dropped**: upstream #716 | — |

---

# History — lessons from earlier ports (kept for context)

## What was learned porting to v2.25.1 (2026-10-31)

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

**8. The deploy surfaced two more upstream issues → fork changes #19 and #20**
(see `CUSTOMIZATIONS.md`). The prod-copy migration test could not catch them:
both need live ESPN/Dispatcharr data. **Judge a deploy by distinct matched
streams and programme counts, not `streams_matched`.** The old figure (409) was
a sum over 46 per-source sub-runs. The new pipeline records one consolidated
run (upstream v90 #645), and the channel-source group is split per Dispatcharr
group (#542). Comparable numbers on 2026-10-31:
- v2.12.5: 332 distinct streams, 1,049 `lang="es"` programmes, 116 channels;
- v2.25.1 after the fixes: 312 distinct streams, 1,170 programmes, 128 channels.

The ~20 streams it no longer matches are stale stream names that refer to
last weekend's games. v2.25.1's date/fixture gates reject them correctly.
**Don't trigger a generation while the startup cache refresh is still
running** (poll `GET /api/v1/cache/status` until `refresh_in_progress` is
false). Together they got the server throttled by ESPN. The generate endpoint
now needs a JSON body: `-H "Content-Type: application/json" -d "{}"`.

**9. Deploy reminders found this port:** `data/tsdb_seed.json` differs from
prod's (bind-mount gap — copy it explicitly); the image must be run once
against a prod-DB copy with Dispatcharr creds blanked **and** `--network none`
(blanking alone still let a login through in 2026-08).


---

## #15 touch points as they were on v2.12.5 (historical; current map above)


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

