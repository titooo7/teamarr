# Porting the Spanish-localization customizations to newer Teamarr versions

**Written:** 2026-07-04 · **Source fork:** v2.6.1 (`dev` @ `b4e63d8` + 5 custom
commits) · **Validated against:** upstream v2.8.0 (latest release, 2026-06-19)

> ✅ **The v2.6.1 → v2.8.0 port was COMPLETED on 2026-07-04** following this
> guide (this folder, branch `dev-custom-2.8.0`, migration renumbered to v77).
> Later the same day, changes 8–11 were added (see `CUSTOMIZATIONS.md`),
> including a second fork migration **v78**.
>
> For the NEXT port (v2.8.0 → newer), cherry-pick THIS repo's **10** commits:
> `1a4d02c2 398de512 c26f2f0c ba586924 5e443d1c f0057f40 b89fdca0 24d15169
> 2dc21525 2c214836`, and renumber **BOTH fork migrations** (v77 AND v78) to
> the next free numbers in the target. Everything else in the guide applies
> unchanged.

This guide re-applies the fork's 7 customizations (catalogued in
`CUSTOMIZATIONS.md`) onto a **new upstream source tree**. It complements —
does not replace — `CUSTOMIZATIONS.md`, whose re-apply runbook assumes the
*same* v2.6.1 version inside a running container.

---

## What was checked against v2.8.0 (as of 2026-07-04)

- **Nothing was upstreamed.** v2.8.0's `schema.sql` still seeds English
  labels (`Spanish`, `French`, …), `behavior='consolidate'`, and no
  unaccented match-term variants. All 7 customizations are still needed.
- **Upstream is at schema version 76.** The fork's custom migration took
  number **75**, which upstream has since used for its own migration —
  **the number collides and MUST be renumbered** (to **77** on v2.8.0;
  always verify against the target's `connection.py`, see Step 2).
- Re-verify these two points for any target newer than v2.8.0:
  - `https://raw.githubusercontent.com/Pharaoh-Labs/teamarr/<tag>/teamarr/database/schema.sql`
    → `schema_version INTEGER DEFAULT <N>` and the
    `consolidation_exception_keywords` seed block.

---

## The 5 custom commits to port

All fork code changes live in these commits on branch `dev`
(on top of upstream `b4e63d8`):

| Commit | Change | Files touched |
|---|---|---|
| `5d41c0b` | Accent-insensitive keyword matching + **v75 migration** | `teamarr/database/channels/keywords.py`, `teamarr/database/connection.py`, `teamarr/consumers/lifecycle/types.py`, `teamarr/database/schema.sql`, `docs/reference/architecture/migrations.md`, `CLAUDE.md`, tests |
| `4eaeb1f` | Spanish language labels in seeds | `teamarr/database/schema.sql`, `teamarr/database/checkpoint_v43.py` |
| `c0dc13e` | ES/PT→EN country translations (matching) | `teamarr/utilities/constants.py`, `teamarr/consumers/matching/normalizer.py`, tests |
| `299b7fc` | `ES:` prefix as Español match term | `teamarr/database/schema.sql`, `teamarr/database/checkpoint_v43.py`, `teamarr/database/connection.py` (v75 terms) |
| `47d81fd` | EN→ES country names in channel display | `teamarr/utilities/constants.py`, `teamarr/templates/variables/home_away.py`, tests |

Change #6 (keyword `behavior='separate'`) is **DB-only** — no commit; it's
re-applied via SQL (Step 6).

---

## Step 1 — Set up the target tree (per MyApps conventions)

```bash
cd /home/tito/MyApps

# Pristine reference copy (never modified)
git clone --branch v2.8.0 --depth 1 https://github.com/Pharaoh-Labs/teamarr.git \
    TEAMARR_v2.8.0_OFFICIAL_UNTOUCHED_SOURCE_CODE

# Working fork: copy THIS repo so the 5 custom commit objects come along
cp -r Teamarr_fork_v2.6.1 Teamarr_fork_v2.8.0
cd Teamarr_fork_v2.8.0
git stash -u          # stash uncommitted docker-compose.yml/CLAUDE.md/docs
git fetch origin --tags
git checkout -b dev-custom-2.8.0 v2.8.0
```

> The custom commit hashes only exist in the local fork repo — that's why we
> copy it rather than fresh-cloning. After checkout, restore the local-only
> files: `git stash pop` (or hand-copy `docker-compose.yml`, `CLAUDE.md`,
> `CUSTOMIZATIONS.md`, this file, `HANDOFF-*.md` from the v2.6.1 folder).

## Step 2 — Find the target's schema version and pick the new number

```bash
grep -n 'schema_version INTEGER DEFAULT' teamarr/database/schema.sql
grep -n 'current_version = ' teamarr/database/connection.py | tail -5
```

On v2.8.0 both show **76** → the fork migration becomes **v77**.
Rule: fork migration number = target's latest + 1. **Do not** "leave a gap"
(e.g. 900): Teamarr's `if current_version < N:` chain is strictly linear, and
jumping `schema_version` to 900 would make every future upstream migration
(77, 78, …) get skipped forever.

## Step 3 — Sanity-check the touched code still exists

```bash
grep -rn 'def check_exception_keyword\|def _make_keyword_pattern' teamarr/database/channels/keywords.py
grep -n  'def slugify_keyword' teamarr/consumers/lifecycle/types.py
grep -n  'def apply_city_translations' teamarr/consumers/matching/normalizer.py
grep -n  'def extract_home_team\|def extract_away_team' teamarr/templates/variables/home_away.py
grep -n  'EXCEPTION_KEYWORDS_SEED_V43' teamarr/database/checkpoint_v43.py
grep -n  'consolidation_exception_keywords' teamarr/database/schema.sql
```

If any anchor is missing (renamed/moved), fall back to manual re-application
using the per-change descriptions in `CUSTOMIZATIONS.md` §"Detailed Change
Descriptions" — the *intent* of each change is version-independent.

## Step 4 — Cherry-pick the 5 commits

```bash
git cherry-pick 5d41c0b 4eaeb1f c0dc13e 299b7fc 47d81fd
```

Expected conflicts and how to resolve:

| File | Likely conflict | Resolution |
|---|---|---|
| `teamarr/database/schema.sql` | `DEFAULT 75` vs upstream `DEFAULT 76` | Take **77** (the new number). Keep the Spanish seed block. |
| `teamarr/database/connection.py` | v75 guard block placement | Move the fork block **after upstream's last guard** (v76 on 2.8.0); renumber (Step 5). |
| `teamarr/utilities/constants.py` | Context drift around the two dicts | Both fork dicts are purely additive blocks — keep them plus upstream's changes. The v2.6.1 commits also carried ruff re-indent noise here; discard noise, keep only the dicts. |
| `teamarr/templates/variables/home_away.py` | Ruff line-joining noise from `47d81fd` | Keep only the import, `_translate_country_for_display()`, and the 4 wrapped `return` lines. |
| `tests/*` | Schema-version assertions | Take **77** everywhere (Step 5 list). |

Small files (`keywords.py`, `types.py`, `normalizer.py`,
`checkpoint_v43.py`) usually apply cleanly.

## Step 5 — Renumber the migration v75 → 77 (MANDATORY on ≥ v2.7)

Rename/update in one sweep (then grep to confirm nothing was missed):

1. `teamarr/database/connection.py`
   - `_migrate_v75_exception_keyword_accents` → `_migrate_v77_...`
   - guard block: `if current_version < 77:` / `_apply_migration(conn, 77, ...)`
     / `current_version = 77`, placed after upstream's v76 block.
2. `teamarr/database/schema.sql` — `schema_version INTEGER DEFAULT 77`.
3. `docs/reference/architecture/migrations.md` — current version 77; move the
   fork's entry to row 77 (leave upstream's real 75/76 rows intact).
4. Tests asserting the schema version (were 74→75 in the fork; now → 77):
   - `tests/test_migration_helpers.py` (`TestV75ExceptionKeywordAccents` —
     rename to `TestV77...`, update version literals)
   - `tests/test_checkpoint_v43.py`
   - `tests/test_milb_dedupe_v73.py`
   - `tests/test_subscription_migration.py`

```bash
grep -rn '75' teamarr/database/connection.py teamarr/database/schema.sql tests/ | grep -iv 'v43\|v73\|2\.7\|075' | grep -n 'schema\|migrat\|current_version\|v75\|_v7' # eyeball for leftovers
```

> **⚠️ Existing production DB warning.** The prod DB already ran the fork's
> old v75, so it sits at `schema_version=75` — but it has **never run
> upstream's real v75/v76**. Booting stock-or-ported v2.8.0 against it would
> silently **skip upstream v75/v76**. Before first start of the new image:
>
> ```sql
> UPDATE settings SET schema_version = 74 WHERE id = 1;
> ```
>
> Then upstream 75, 76 and the fork's 77 (and 78) all run in order at the
> new image's first startup. The fork migrations are idempotent — re-running
> is a safe no-op. **Back up `data/teamarr.db` first.**
>
> **Ordering:** stop the OLD container before the reset and don't let it boot
> again afterwards — the old image would re-apply its own v75 migration and
> set `schema_version` back to 75, silently undoing the reset. Sequence:
> `docker compose down` → backup → reset → deploy new image → `up -d`.

## Step 6 — Re-apply the DB-only customization (behavior = separate)

Seeds intentionally stay `consolidate`; the live DB gets:

```sql
UPDATE consolidation_exception_keywords SET behavior='separate' WHERE behavior='consolidate';
```

(Full label/match-term SQL for DBs that somehow reverted: `CUSTOMIZATIONS.md`
§"Step 2: Apply DB-only changes".)

## Step 7 — Verify

```bash
# Unit tests (at minimum the touched ones)
pytest tests/test_exception_keyword_accents.py tests/test_migration_helpers.py \
       tests/test_exception_keyword_tvg_id.py tests/test_live_status_prefix.py \
       tests/test_checkpoint_v43.py tests/test_milb_dedupe_v73.py \
       tests/test_subscription_migration.py

# Build the custom image
docker build -t teamarr:custom \
  --build-arg GIT_BRANCH=dev-custom-2.8.0 \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) .

# Runtime spot checks (inside the running container)
docker exec teamarr python3 -c "
from teamarr.consumers.matching.normalizer import normalize_stream
print(normalize_stream('Brasil vs Marruecos EN espanol').normalized)  # → brazil vs morocco ...
from teamarr.templates.variables.home_away import _translate_country_for_display as t
print(t('Spain'), '|', t('Real Madrid'))                              # → España | Real Madrid
from teamarr.consumers.lifecycle.types import slugify_keyword
print(slugify_keyword('Español'))                                     # → espanol
import sqlite3; c = sqlite3.connect('/app/data/teamarr.db')
print('schema:', c.execute('SELECT schema_version FROM settings WHERE id=1').fetchone()[0])  # → 77
"
```

Then the usual local Docker soak before any production deploy (production
only when tito explicitly asks — see `/home/tito/MyApps/CLAUDE.md`).

## Step 8 — Housekeeping

- Update the new folder's `CLAUDE.md` (version numbers, new commit hashes of
  the cherry-picks, migration number 77).
- Update `CUSTOMIZATIONS.md` header (base version, commits, schema numbers).
- Write a `HANDOFF-<date>.md` for the port session.
- Old `Teamarr_fork_v2.6.1` / v2.6.1 pristine folders become
  scheduled-for-deletion per MyApps versioned-folder convention.

---

## Appendix — the 7 changes at a glance (intent, not diff)

| # | Change | Where | Verify by |
|---|--------|-------|-----------|
| 1 | Accent-insensitive keyword matching (`_strip_accents`, both sides) | `teamarr/database/channels/keywords.py` + migration (77) in `connection.py` | `espanol` stream text matches `Español` term |
| 2 | Spanish keyword labels in seeds | `schema.sql`, `checkpoint_v43.py` | fresh DB shows `Español`, `Francés`, … |
| 3 | Accent-strip in `slugify_keyword()` | `teamarr/consumers/lifecycle/types.py` | `Español` → `espanol` |
| 4 | ES/PT→EN `COUNTRY_TRANSLATIONS` for matching | `constants.py` + `normalizer.py` | `Brasil vs Marruecos` normalizes to `brazil vs morocco` |
| 5 | `ES:` in Español match terms | seeds + migration terms | `ES: DW EN ESPANOL` tagged `(Español)`; `ESPN:` not |
| 6 | `behavior='separate'` (DB-only) | live DB SQL | keywords table shows `separate` |
| 7 | EN→ES `ENGLISH_TO_SPANISH_COUNTRIES` display translation | `constants.py` + `templates/variables/home_away.py` | channel name `España - Cabo Verde`; tvg-id/logs stay English |
