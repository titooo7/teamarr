# Teamarr — Spanish Localization Customizations

**Date:** 2026-07-04 (ported from the v2.6.1 fork of 2026-06-15; extended with changes 8–11 the same day)  
**Base version:** Teamarr v2.8.0, tag `94a7787d` (schema v76) — branch `dev-custom-2.8.0`  
**Commits:** ported `1a4d02c2`, `398de512`, `c26f2f0c`, `ba586924`, `5e443d1c` · new `f0057f40`, `b89fdca0`, `24d15169`, `2dc21525`, `2c214836`  
**Fork migration numbers:** **v77** (accent variants; was v75 on the v2.6.1 fork) and **v78** (Spanish language names). Schema version: **78**.

This document describes all customizations made to Teamarr for Spanish-language users. If a future Teamarr update overwrites these changes (e.g. `docker pull` of a new image), follow this guide to re-apply them.

> **Porting to a version NEWER than v2.8.0?** Use
> **`PORTING-TO-NEW-VERSIONS.md`** — the re-apply instructions below assume
> this same v2.8.0 code base. Expect the migration-number collision again:
> check the target's schema version and renumber v77 to the next free number.
>
> **Upgrading the production DB from the OLD v2.6.1 fork?** Its
> `schema_version=75` refers to the fork's old numbering and upstream's real
> v75/v76 never ran there — run
> `UPDATE settings SET schema_version = 74 WHERE id = 1;` (after backup)
> before first boot of this version. See `PORTING-TO-NEW-VERSIONS.md` Step 5.

---

## Summary of Changes

| # | Change | What it fixes |
|---|--------|---------------|
| 1 | Accent-insensitive keyword matching | Stream `en espanol` (no tilde) wasn't detected as Spanish |
| 2 | Language labels in Spanish | Channel names show `(Español)` instead of `(Spanish)` |
| 3 | Clean tvg-id slugs for accented labels | `Español` → slug `espanol` (not `espa-ol`) |
| 4 | Country name translations (matching) | `Brasil`→`Brazil`, `Catar`→`Qatar`, etc. for team matching |
| 5 | `ES:` prefix as Español match term | Channels prefixed `ES:` get the `(Español)` tag |
| 6 | Keyword behavior set to `separate` | Respects global "Separate" stream consolidation setting |
| 7 | Spanish country names in channel display | `Spain`→`España`, `Belgium`→`Bélgica`, etc. in channel names |
| 8 | Matching country dict derived from display dict + word boundaries | ~120 countries covered in BOTH directions (was ~40 for matching); `Costa de Marfil`, `Emiratos Árabes Unidos`, `Corea del Norte` etc. now match; `japon` can't mangle `japones` |
| 9 | Spanish language names as keyword match terms (v78 migration) | `EN ALEMÁN`, `en japones`, `en coreano`, `en francés` now detected |
| 10 | Youth/women suffix in display translation | `Spain U21`→`España U21`, `Mexico U-20`→`México U-20`, `Spain W`→`España W` |
| 11 | Spanish EPG output metadata | `Postponed: `→`Aplazado: ` prefix; XMLTV `lang="es"` (was hardcoded `"en"`) |

---

## Changes 8–11 (added 2026-07-04 on the v2.8.0 fork)

### 8. Derived country matching dict + word boundaries (`f0057f40`)

`COUNTRY_TRANSLATIONS` (ES/PT→EN, used before fuzzy matching) is no longer a
hand-written ~40-entry list — it is **derived by inverting
`ENGLISH_TO_SPANISH_COUNTRIES`** (identity mappings dropped) plus an
`_EXTRA_COUNTRY_VARIANTS` table (Spanish colloquial `holanda`, `arabia
saudita`; Portuguese forms `alemanha`, `japao`, `pais de gales`, …). The two
directions can never drift apart again. The dict is ordered longest-key-first
and `apply_city_translations()` now uses `\b`-bounded regex, so phrases beat
substrings (`irlanda del norte` before `irlanda`) and short names can't fire
inside words (`japon` in `japones`, `gales` in `legales`).
Files: `teamarr/utilities/constants.py`, `teamarr/consumers/matching/normalizer.py`,
tests in `tests/test_country_translations.py`.

### 9. Spanish language names as match terms — v78 migration (`b89fdca0`)

German/Japanese/Korean/Chinese keywords only had English + native terms, and
French had `Français` but not `Francés`, so streams tagged `EN ALEMÁN` /
`en japones` / `en coreano` matched nothing. The Spanish name (plus an
un-accented duplicate, so terms keep working under a stock upstream image) is
now in each keyword's match_terms. Seeds updated for fresh installs; **v78
data migration** back-fills existing DBs and matches rows by BOTH the stock
English label and the fork's Spanish label. Schema 77→78.
Files: `teamarr/database/schema.sql`, `teamarr/database/checkpoint_v43.py`,
`teamarr/database/connection.py` (`_migrate_v78_spanish_language_names`),
`docs/reference/architecture/migrations.md`, tests.

### 10. Youth/women national team suffixes in display (`24d15169`)

`_translate_country_for_display()` now recognizes a trailing `U<n>`/`U-<n>`/`W`
suffix, translates the country base, and re-appends the suffix
(`Spain U21`→`España U21`). Club names with such suffixes stay untouched
(base must be a known country). File: `teamarr/templates/variables/home_away.py`,
tests in `tests/test_country_display_translation.py`.

### 11. Spanish EPG output metadata (`2dc21525`)

`POSTPONED_LABEL` (prepended to postponed events' channel names/titles/
descriptions) is now `"Aplazado: "` (`teamarr/consumers/event_epg.py`), and
the XMLTV `lang` attribute on `<title>/<sub-title>/<desc>/<category>` is
`"es"` via the `XMLTV_LANG` constant (`teamarr/utilities/xmltv.py`) instead
of upstream's hardcoded `"en"`.

---

## Files Modified

### Core code (8 files)

| File | Change |
|------|--------|
| `teamarr/database/channels/keywords.py` | Added `_strip_accents()` helper; applied to both stream text and match terms in `check_exception_keyword()` and `_make_keyword_pattern()` |
| `teamarr/database/connection.py` | Added v77 migration `_migrate_v77_exception_keyword_accents()` + guard block |
| `teamarr/database/schema.sql` | Schema version 76→77; seed labels changed to Spanish; match terms include un-accented variants + `ES:` |
| `teamarr/database/checkpoint_v43.py` | Seed labels changed to Spanish; match terms updated to match schema.sql |
| `teamarr/consumers/lifecycle/types.py` | `slugify_keyword()` strips accents before slugifying |
| `teamarr/consumers/matching/normalizer.py` | `apply_city_translations()` now also applies `COUNTRY_TRANSLATIONS` |
| `teamarr/utilities/constants.py` | Added `COUNTRY_TRANSLATIONS` dict (~40 Spanish/Portuguese→English for matching) and `ENGLISH_TO_SPANISH_COUNTRIES` dict (~120 English→Spanish for display) |
| `teamarr/templates/variables/home_away.py` | Added `_translate_country_for_display()` helper; applied to `{home_team}`, `{away_team}`, `{home_team_short}`, `{away_team_short}` extractors |

### Docs (2 files)

| File | Change |
|------|--------|
| `docs/reference/architecture/migrations.md` | Schema version → 77, added v77 entry to version history |
| `CLAUDE.md` | Schema version reference → v77 |

### Tests (7 files)

| File | Change |
|------|--------|
| `tests/test_exception_keyword_accents.py` | **NEW** — 12 tests for accent-insensitive matching |
| `tests/test_migration_helpers.py` | Added `TestV77ExceptionKeywordAccents` class (5 tests) |
| `tests/test_exception_keyword_tvg_id.py` | Updated `test_special_chars` assertion for accent-stripping |
| `tests/test_live_status_prefix.py` | Updated `test_directo_removed_in_pipeline` for country translations |
| `tests/test_checkpoint_v43.py` | Schema version assertion 76→77 |
| `tests/test_milb_dedupe_v73.py` | Schema version assertions 76→77 |
| `tests/test_subscription_migration.py` | Schema version assertion 76→77 |

---

## Detailed Change Descriptions

### 1. Accent-insensitive keyword matching

**Problem:** Python's `re` treats `ñ ≠ n`. A stream named `...EN espanol` (no tilde) failed to match the keyword term `Español` (with tilde), so no language was added to the channel name. The Portuguese stream worked by luck — the plain-ASCII English word `Portuguese` happened to be in its match terms.

**Fix:** Added `_strip_accents()` in `keywords.py` that decomposes text via `unicodedata.normalize('NFD', text)` and drops combining marks (category `Mn`). Applied to **both** the stream text and each match term before regex comparison, so `espanol` matches `Español`.

**Also includes:** v77 data migration that `UPDATE`s the Spanish/French/Portuguese keyword rows in the existing DB to include un-accented variants (`Espanol`, `Francais`, `Portugues`). Uses `UPDATE` (not `INSERT OR IGNORE`) because the seed can't modify existing rows.

### 2. Language labels in Spanish

**Problem:** Channel names showed `(Spanish)`, `(Portuguese)`, etc. — English labels.

**Fix:** Changed the `label` column in `consolidation_exception_keywords` table:

| Old (English) | New (Spanish) |
|---|---|
| Spanish | Español |
| French | Francés |
| German | Alemán |
| Portuguese | Portugués |
| Italian | Italiano |
| Japanese | Japonés |
| Korean | Coreano |
| Chinese | Chino |

**Important:** The `match_terms` are NOT changed — they still contain English/Spanish variants as they appear in stream names. Only the display `label` changed.

### 3. Clean tvg-id slugs for accented labels

**Problem:** With Spanish labels like `Español`, the `slugify_keyword()` function produced ugly tvg-ids: `Español` → `espa-ol` (the `ñ` was replaced with a hyphen).

**Fix:** Added accent-stripping to `slugify_keyword()` in `types.py` before the regex cleanup. Now `Español` → `espanol`, `Portugués` → `portugues`.

### 4. Country name translations (for team matching)

**Problem:** Streams with Spanish country names (`Brasil`, `Marruecos`, `Catar`) failed team matching against ESPN's English data. Many pairs score below the 60% fuzzy threshold (`Marruecos`↔`Morocco` = 50%), and two-team matchups require **both** teams to pass — so one low-scoring pair fails the whole match.

**Fix:** Added `COUNTRY_TRANSLATIONS` dict (~40 entries) to `constants.py`, wired into `apply_city_translations()` in `normalizer.py`. Spanish/Portuguese country names are translated to English **before** any matching happens. This is the reverse direction of change #7 (which translates English→Spanish for display).

Full translation table:

| Stream says | Translated to | | Stream says | Translated to |
|---|---|---|---|---|
| alemania / alemanha | germany | | japon | japan |
| belgica | belgium | | marruecos / marrocos | morocco |
| brasil | brazil | | noruega | norway |
| camerun | cameroon | | nueva zelanda | new zealand |
| catar | qatar | | paises bajos / holanda | netherlands |
| corea del sur | south korea | | polonia | poland |
| croacia | croatia | | republica checa | czech republic |
| dinamarca | denmark | | rumania | romania |
| egipto | egypt | | rusia | russia |
| escocia | scotland | | sudafrica | south africa |
| eslovaquia | slovakia | | suecia | sweden |
| eslovenia | slovenia | | suiza | switzerland |
| espana | spain | | tunez | tunisia |
| estados unidos | united states | | turquia | turkey |
| francia | france | | ucrania | ukraine |
| gales | wales | | | |
| grecia | greece | | | |
| inglaterra | england | | | |
| irlanda | ireland | | | |
| islandia | iceland | | | |
| italia | italy | | | |

### 5. `ES:` prefix as Español match term

**Problem:** Some Spanish-language channels use `ES:` as a prefix (e.g. `ES: DW EN ESPANOL UHD`) without containing "Español" or "Spanish" in the name.

**Fix:** Added `ES:` to the Español keyword's match_terms. The word-boundary regex `\bes:(?!\w)` avoids false positives — it won't match `ESPN:`, `MESSI:`, `NOTES:`, etc.

### 6. Keyword behavior set to `separate`

**Problem:** The keyword `behavior='consolidate'` overrode the global "Stream Consolidation: Separate" setting, forcing all streams with the same keyword into one channel.

**Fix:** Changed all language keyword behaviors from `consolidate` to `separate` in the DB. Each stream now gets its own channel, consistent with the global setting.

**Note:** This is a DB-only change — the seed files (`schema.sql`, `checkpoint_v43.py`) still use `consolidate` as the default for fresh installs. Only the live DB was changed.

### 7. Spanish country names in channel name display

**Problem:** ESPN returns English country names (`Spain`, `Belgium`, `Saudi Arabia`), so channel names showed `18:00 CEST - Spain - Cape Verde` instead of Spanish names.

**Fix:** Added `ENGLISH_TO_SPANISH_COUNTRIES` dict (~120 countries) to `constants.py`. A `_translate_country_for_display()` helper in `home_away.py` applies it to the `{home_team}`, `{away_team}`, `{home_team_short}`, and `{away_team_short}` template variables. Now `Spain` → `España`, `Belgium` → `Bélgica`, `Saudi Arabia` → `Arabia Saudí`, etc.

**Key design decision:** Translation is **display-only** — applied at the template variable level, NOT at the ESPN provider or matching layer. This means:
- Matching, tvg-IDs, logs, and `{home_team_pascal}` keep the canonical English name
- Club names (`Real Madrid`, `Detroit Lions`) are untouched — only exact country-name matches translate
- The `{home_team_abbrev}` variable (e.g. `ESP`, `BRA`) is NOT translated

Example channel names after this change:

| Before | After |
|---|---|
| Spain - Cape Verde | España - Cabo Verde |
| Belgium - Egypt | Bélgica - Egipto |
| Saudi Arabia - Uruguay | Arabia Saudí - Uruguay |
| Brazil - Morocco | Brasil - Marruecos |

---

## How to Re-apply After a Teamarr Update

There are two approaches. **Approach A (local image)** is the recommended method — it bakes your modifications into a Docker image so they survive any container recreation. **Approach B (docker cp)** is the manual fallback.

---

### Approach A: Local Custom Image (RECOMMENDED)

Your modifications are built into a local Docker image tagged `teamarr:custom`. The `docker-compose.yml` is already set to use it. This means `docker compose down && up` preserves everything — no manual file copying needed.

#### One-time setup (already done)

```bash
cd /opt/teamarr
docker build -t teamarr:custom \
  --build-arg GIT_BRANCH=dev-custom \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
```

`docker-compose.yml` uses `image: teamarr:custom` (not the online image).

#### Try the official update

```bash
cd /opt/teamarr

# 1. Switch to official image
sed -i 's|image: teamarr:custom|image: ghcr.io/pharaoh-labs/teamarr:latest|' docker-compose.yml
docker compose down
docker pull ghcr.io/pharaoh-labs/teamarr:latest
docker compose up -d
```

The database (in `./data/`) survives — your keywords, settings, and channels stay intact. Try the official version.

#### Revert to your custom version

```bash
cd /opt/teamarr

# 1. Switch back to custom image
sed -i 's|image: ghcr.io/pharaoh-labs/teamarr:latest|image: teamarr:custom|' docker-compose.yml
docker compose down
docker compose up -d
```

If the official version changed keyword labels/behaviors in the DB, re-apply DB customizations (see Step 2 below). Otherwise you're done.

#### Full backup (in case of disaster)

```bash
# Save the Docker image (contains all code modifications)
docker save teamarr:custom -o /backup/teamarr-custom.tar

# Save the source code + DB + config
tar czf /backup/teamarr-backup.tar.gz -C /opt teamarr/
```

#### Full restore from backup

```bash
# Restore source code + DB
tar xzf /backup/teamarr-backup.tar.gz -C /opt/

# Restore Docker image
docker load -i /backup/teamarr-custom.tar

# Start
cd /opt/teamarr && docker compose up -d
```

---

### Approach B: Manual docker cp (FALLBACK)

If you can't build a local image, copy files manually after each container recreation.

### Step 1: Copy modified Python files into the container

```bash
# From the /opt/teamarr directory (where your local code lives)
docker cp teamarr/database/channels/keywords.py     teamarr:/app/teamarr/database/channels/keywords.py
docker cp teamarr/database/connection.py            teamarr:/app/teamarr/database/connection.py
docker cp teamarr/database/schema.sql               teamarr:/app/teamarr/database/schema.sql
docker cp teamarr/database/checkpoint_v43.py        teamarr:/app/teamarr/database/checkpoint_v43.py
docker cp teamarr/consumers/lifecycle/types.py      teamarr:/app/teamarr/consumers/lifecycle/types.py
docker cp teamarr/consumers/matching/normalizer.py  teamarr:/app/teamarr/consumers/matching/normalizer.py
docker cp teamarr/utilities/constants.py            teamarr:/app/teamarr/utilities/constants.py
docker cp teamarr/templates/variables/home_away.py  teamarr:/app/teamarr/templates/variables/home_away.py
docker cp teamarr/consumers/event_epg.py            teamarr:/app/teamarr/consumers/event_epg.py
docker cp teamarr/utilities/xmltv.py                teamarr:/app/teamarr/utilities/xmltv.py
```

### Step 2: Apply DB-only changes

After copying files and restarting, run these SQL updates inside the container to fix the live database (the seed `INSERT OR IGNORE` won't modify existing rows):

```bash
docker exec teamarr python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/teamarr.db')

# 1. Rename labels to Spanish
label_updates = {
    'Spanish': 'Español', 'French': 'Francés', 'German': 'Alemán',
    'Portuguese': 'Portugués', 'Italian': 'Italiano', 'Japanese': 'Japonés',
    'Korean': 'Coreano', 'Chinese': 'Chino',
}
for old, new in label_updates.items():
    conn.execute('UPDATE consolidation_exception_keywords SET label=? WHERE label=?', (new, old))

# 2. Update match terms (Spanish label, with un-accented variants + ES:)
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Spanish, En Español, En Espanol, (ESP), Español, Espanol, ES:' WHERE label='Español'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='French, En Français, En Francais, (FRA), Français, Francais, Francés, Frances' WHERE label='Francés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Portuguese, (POR), Português, Portugues' WHERE label='Portugués'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='German, (GER), Deutsch, Alemán, Aleman' WHERE label='Alemán'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Japanese, (JPN), 日本語, Japonés, Japones' WHERE label='Japonés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Korean, (KOR), 한국어, Coreano' WHERE label='Coreano'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Chinese, (CHN), (CHI), 中文, Chino' WHERE label='Chino'\")

# 3. Set all keyword behaviors to 'separate'
conn.execute(\"UPDATE consolidation_exception_keywords SET behavior='separate' WHERE behavior='consolidate'\")

conn.commit()

# Verify
rows = conn.execute('SELECT label, behavior FROM consolidation_exception_keywords ORDER BY label').fetchall()
for r in rows: print(f'  {r[0]:14} behavior={r[1]}')
conn.close()
"
```

### Step 3: Restart the container

```bash
docker restart teamarr
```

### Step 4: Verify

```bash
# Check schema version (should be 78+)
docker exec teamarr python3 -c "
import sqlite3; c=sqlite3.connect('/app/data/teamarr.db')
print('Schema version:', c.execute('SELECT schema_version FROM settings WHERE id=1').fetchone()[0])
print('Keywords:', c.execute('SELECT count(*) FROM consolidation_exception_keywords').fetchone()[0])
for r in c.execute('SELECT label, match_terms, behavior FROM consolidation_exception_keywords ORDER BY label').fetchall():
    print(f'  {r[0]:14} | {r[1][:50]:50} | {r[2]}')
"

# Check accent-insensitive matching works
docker exec teamarr python3 -c "
from teamarr.consumers.matching.normalizer import normalize_stream
print(normalize_stream('Brasil vs Marruecos EN espanol').normalized)
# Should print: brazil vs morocco EN espanol
"

# Check country display translation works
docker exec teamarr python3 -c "
from teamarr.templates.variables.home_away import _translate_country_for_display
print(_translate_country_for_display('Spain'))
# Should print: España
print(_translate_country_for_display('Real Madrid'))
# Should print: Real Madrid (clubs unchanged)
"
```

---

## Docker Deployment Notes

- **Single remote:** `origin` → `Pharaoh-Labs/teamarr`
- **Container name:** `teamarr`
- **DB path (host):** `/opt/teamarr/data/teamarr.db`
- **DB path (container):** `/app/data/teamarr.db`
- **Local code:** `/opt/teamarr/` (dev branch, 5 unpushed commits)
- **DB is read-only from host** while container is running — always run DB updates via `docker exec`
- `docker-compose.yml` has local-only Traefik/saltbox changes (not committed)

### All files copied into the container

These 10 files need to be re-copied after any image update:

```
teamarr/database/channels/keywords.py
teamarr/database/connection.py
teamarr/database/schema.sql
teamarr/database/checkpoint_v43.py
teamarr/consumers/lifecycle/types.py
teamarr/consumers/matching/normalizer.py
teamarr/utilities/constants.py
teamarr/templates/variables/home_away.py
teamarr/consumers/event_epg.py
teamarr/utilities/xmltv.py
```

### Quick re-apply script

Save this as `/opt/teamarr/reapply-customizations.sh`:

```bash
#!/bin/bash
set -e
cd /opt/teamarr

echo "=== Copying modified files into container ==="
docker cp teamarr/database/channels/keywords.py     teamarr:/app/teamarr/database/channels/keywords.py
docker cp teamarr/database/connection.py            teamarr:/app/teamarr/database/connection.py
docker cp teamarr/database/schema.sql               teamarr:/app/teamarr/database/schema.sql
docker cp teamarr/database/checkpoint_v43.py        teamarr:/app/teamarr/database/checkpoint_v43.py
docker cp teamarr/consumers/lifecycle/types.py      teamarr:/app/teamarr/consumers/lifecycle/types.py
docker cp teamarr/consumers/matching/normalizer.py  teamarr:/app/teamarr/consumers/matching/normalizer.py
docker cp teamarr/utilities/constants.py            teamarr:/app/teamarr/utilities/constants.py
docker cp teamarr/templates/variables/home_away.py  teamarr:/app/teamarr/templates/variables/home_away.py
docker cp teamarr/consumers/event_epg.py            teamarr:/app/teamarr/consumers/event_epg.py
docker cp teamarr/utilities/xmltv.py                teamarr:/app/teamarr/utilities/xmltv.py

echo "=== Restarting container ==="
docker restart teamarr
sleep 8

echo "=== Applying DB customizations ==="
docker exec teamarr python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/teamarr.db')

# Rename labels to Spanish (only if they still have English names)
for old, new in {'Spanish':'Español','French':'Francés','German':'Alemán',
                 'Portuguese':'Portugués','Italian':'Italiano','Japanese':'Japonés',
                 'Korean':'Coreano','Chinese':'Chino'}.items():
    conn.execute('UPDATE consolidation_exception_keywords SET label=? WHERE label=?', (new, old))

# Update match terms
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Spanish, En Español, En Espanol, (ESP), Español, Espanol, ES:' WHERE label='Español'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='French, En Français, En Francais, (FRA), Français, Francais, Francés, Frances' WHERE label='Francés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Portuguese, (POR), Português, Portugues' WHERE label='Portugués'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='German, (GER), Deutsch, Alemán, Aleman' WHERE label='Alemán'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Japanese, (JPN), 日本語, Japonés, Japones' WHERE label='Japonés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Korean, (KOR), 한국어, Coreano' WHERE label='Coreano'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Chinese, (CHN), (CHI), 中文, Chino' WHERE label='Chino'\")

# Set behavior to separate
conn.execute(\"UPDATE consolidation_exception_keywords SET behavior='separate' WHERE behavior='consolidate'\")
conn.commit()

rows = conn.execute('SELECT label, behavior FROM consolidation_exception_keywords ORDER BY label').fetchall()
for r in rows: print(f'  {r[0]:14} behavior={r[1]}')
conn.close()
"

echo "=== Done ==="
docker ps --filter name=teamarr --format '{{.Status}}'
```

Then: `chmod +x /opt/teamarr/reapply-customizations.sh && ./reapply-customizations.sh`
