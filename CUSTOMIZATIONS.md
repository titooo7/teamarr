# Teamarr — Fork Customizations

**Date:** 2026-10-31 port from the v2.12.5 fork (feature set unchanged except change #16, **dropped** — upstream shipped the same fix as #716). Previous history below is kept as written for the v2.12.x forks.  
**Base version:** Teamarr v2.25.1, tag `v2.25.1` (`82883cbf`, schema v103 upstream) — branch `dev-custom-2.25.1`  
**How it was ported:** NOT a commit-by-commit cherry-pick (816 upstream commits since v2.12.5 made that conflict on nearly every fork commit). The net fork diff (`git diff v2.12.5 dev-custom-2.12.5`) was 3-way-applied per file and four conflicts resolved by hand; #15 was re-implemented on upstream's new `generation_pipeline/`; the fork migrations were rewritten. See `PORTING-TO-NEW-VERSIONS.md` → "What was learned porting to v2.25.1".  
**Fork migration numbers:** **v104** (accent variants) and **v105** (Spanish language names) — renumbered from v85/v86 because upstream v2.25.1 uses 85–103 (v85/v86/v87 = CFL→Bell Media). Both are now **additive** (append missing terms only, never overwrite). Schema version: **105**. **Production DB needs `schema_version` reset to 84 before first boot** (it says 86 from the fork's old numbering, which would skip upstream's real v85/v86).

This document describes all customizations made to this Teamarr fork: changes 1–14 are Spanish-language localization; change 15 is an opt-in failover feature (separate-mode backups); change 16 was an upstream bug fix, **dropped on the v2.25.1 port** because upstream fixed it; change 17 is a channel-ordering tweak; changes 18, 19 and 20 are matching/provider bug fixes (18a is DB-only). Each change's own section explains the why; the per-section history notes are kept as written at the time.

> **Porting to a newer version?** Use **`PORTING-TO-NEW-VERSIONS.md`** (Steps
> 0–9 plus a touch-point map that says where every change lives *today*).
> The "Files Modified" table and the "How to Re-apply After a Teamarr Update"
> runbook further down were written for v2.12.5 and keep older paths; where
> they disagree with the touch-point map, the map wins. The main moves on
> v2.25.1:
> - the keyword seeds left `schema.sql` for `exception_keywords.py`;
> - the fork migrations are v104/v105;
> - #15 is wired through `generation_pipeline/`.

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
| 9 | Spanish language names as keyword match terms (v86 migration) | `EN ALEMÁN`, `en japones`, `en coreano`, `en francés` now detected |
| 10 | Youth/women suffix in display translation | `Spain U21`→`España U21`, `Mexico U-20`→`México U-20`, `Spain W`→`España W` |
| 11 | Spanish EPG output metadata | `Postponed: `→`Aplazado: ` prefix; XMLTV `lang="es"` (was hardcoded `"en"`) |
| 12 | `{game_date_short}` day-first format | Shows `22-Jul` (Spanish day-month order) instead of `Jul 22` |
| 13 | **FIXED via #14** (was: accepted regression, v2.12.3 upstream #484) | National-team art/thumbnail URLs built from `{home_team_pascal}`/`{away_team_pascal}` resolved with the Spanish country name and fell back to generic art — see detailed section below |
| 14 | `{home_team_en}`/`{away_team_en}` untranslated variables | Fixes #13: art/logo URLs can reference the English team name even though `{home_team}`/`{away_team}` are translated for display |
| 15 | Separate-mode failover backups (`separate_fallbacks.py`) | "Separate" consolidation mode channels can each carry up to N same-exception-keyword-group sibling streams as Dispatcharr failover backups, behind their own stream (opt-in; not Spanish-localization) |
| 16 | **DROPPED on the v2.25.1 port — upstream fixed it (#716).** EPG anchor guard bypassed on reverse-alias retry — upstream bug fix | A highlights/encore/replay programme could bind to a same-titled live event any distance away, producing a Dispatcharr channel with zero streams (production incident, 2026-08-23) |
| 17 | Keyword channels sort before the plain channel, same event only | `(Español)`/`(Portugués)` channels now get lower numbers than the plain channel for the same game (fixed fork behaviour, not Spanish-localization) |
| 18 | Dash matchup separator + EPG star-rating strip — **two bug fixes** | Movistar/European EPG titles ("Real Madrid - Málaga") never extracted a team pair; separately, a "★N.N/10" guide rating was misread as a date and silently killed an otherwise-correct match |
| 19 | Dash-written EPG matchups not split between the teams (v2.25.1) | Upstream #728 split "DIRECTO Jornada 9: Chelsea - Manchester United" at the team dash, so no Movistar/DAZN programme matched |
| 20 | A failed ESPN fetch is never cached as an empty day (v2.25.1) | An ESPN 403 burst got cached as "no games": LaLiga/Premier League vanished for the day, past days for 30 days |

---

## Changes 8–14 (8–11 added 2026-07-04 on the v2.8.0 fork; 12 added 2026-07-22; 13 accepted 2026-07-31, fixed 2026-08-07 via 14)

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
tests in `tests/matching/test_country_translations.py`.

### 9. Spanish language names as match terms — v86 migration (`6809c0a3`)

German/Japanese/Korean/Chinese keywords only had English + native terms, and
French had `Français` but not `Francés`, so streams tagged `EN ALEMÁN` /
`en japones` / `en coreano` matched nothing. The Spanish name (plus an
un-accented duplicate, so terms keep working under a stock upstream image) is
now in each keyword's match_terms. Seeds updated for fresh installs; **v86
data migration** back-fills existing DBs and matches rows by BOTH the stock
English label and the fork's Spanish label. Schema 85→86 (was 84→85 on the
v2.12.2 fork; renumbered because upstream v2.12.3 took migration 84 for
itself — see the port header above).
Files: `teamarr/database/schema.sql`, `teamarr/database/checkpoint_v43.py`,
`teamarr/database/migrations/versioned.py` (`_migrate_v86_spanish_language_names`),
`teamarr/database/migrations/__init__.py`,
`docs/reference/architecture/migrations.md`, tests.

### 10. Youth/women national team suffixes in display (`24d15169`)

`_translate_country_for_display()` now recognizes a trailing `U<n>`/`U-<n>`/`W`
suffix, translates the country base, and re-appends the suffix
(`Spain U21`→`España U21`). Club names with such suffixes stay untouched
(base must be a known country). File: `teamarr/templates/variables/home_away.py`,
tests in `tests/templates/test_country_display_translation.py`.

### 11. Spanish EPG output metadata (`2dc21525`)

`POSTPONED_LABEL` (prepended to postponed events' channel names/titles/
descriptions) is now `"Aplazado: "` (`teamarr/consumers/event_epg.py`), and
the XMLTV `lang` attribute on `<title>/<sub-title>/<desc>/<category>` is
`"es"` via the `XMLTV_LANG` constant (`teamarr/utilities/xmltv.py`) instead
of upstream's hardcoded `"en"`.

### 12. `{game_date_short}` day-first format (`f223464e`, added 2026-07-22)

The short-date template variable renders `22-Jul` (strftime `%-d-%b`,
day-month order as used in Spanish) instead of upstream's `Jul 22`
(`%b %-d`). Applies to `.next`/`.last` suffixes too. Month abbreviations
stay English (`Jul`, `Dec`) — Python's C locale, same as upstream.
Files: `teamarr/templates/variables/datetime.py` (format + description),
`teamarr/templates/sample_data.py` (UI sample values),
`docs/guide/epg/variables.md` (example). No seeds/goldens/tests reference
the format, so the change is self-contained.

### 13. National-team art URLs — regression, now FIXED (see #14)

**Not a fork change** — a behavior change in upstream v2.12.3 that interacted
badly with change #7 above. Accepted as-is on the v2.12.3 port (2026-07-31);
**fixed on the v2.12.4 port (2026-08-07) via change #14 below.**

Upstream #484 retired `{home_team_pascal}`/`{away_team_pascal}` as standalone
template variables (along with 8 other `_pascal`/`_lower` variants) in favor
of a general `|filter` system. They still render — forever, via a permanent
`_LEGACY_ALIASES` table in `teamarr/templates/resolver.py` — but now as
`{home_team|pascal}`, i.e. "take the `home_team` variable's current value,
then PascalCase it." Previously `home_team_pascal` was its OWN extractor
(`_to_pascal_case(game_ctx.event.home_team.name)`, now deleted) that read the
raw ESPN team name directly, bypassing whatever change #7 does to the
`home_team` variable.

Because change #7 makes `{home_team}` resolve to the **Spanish** display name
for national teams, `{home_team_pascal}` — now just
`{home_team|pascal}` — inherits that translation. A template like
`{league_id}/{home_team_pascal}/{away_team_pascal}/logo.png` for a
Spain-vs-Morocco match used to build `world-cup/Spain/Morocco/logo.png`
(matching the external art service's naming); it built
`world-cup/Espana/Marruecos/logo.png` instead, which the art service doesn't
recognize, so the channel fell back to generic `fallback=true` art.

**Scope:** national-team channels only (club names like `Real Madrid` are
never translated by change #7, so club art was unaffected). Upstream's v84
data migration (`_migrate_v84_filter_consolidation`) physically rewrote every
stored template's `_pascal`/`_lower` tokens to the new `|filter` form on
first boot of v2.12.3, so the old raw-English behavior couldn't be recovered
by editing a template alone — it needed a code change.

**Decision history:** accepted as-is 2026-07-31 (World Cup had just ended,
few national-team fixtures expected for months). Fixed 2026-08-07, on the
v2.12.4 port, via change #14 — see that section for the approach and why it
was chosen over re-registering `home_team_pascal` directly.

### 14. `{home_team_en}`/`{away_team_en}` untranslated variables — fixes #13

**Added:** 2026-08-07, v2.12.4 port. **Code:** commit on `dev-custom-2.12.4`
(see git log). **Files:** `teamarr/templates/variables/home_away.py` (new
`extract_home_team_en`/`extract_away_team_en`, registered right after the
existing `extract_home_team`/`extract_away_team`), plus
`tests/templates/test_home_away_en_variables.py` (new).

**What it does:** two fork-owned template variables, `{home_team_en}` and
`{away_team_en}`, that extract the same positional team name as
`{home_team}`/`{away_team}` but **skip** `_translate_country_for_display()`
— they always resolve the raw ESPN English name. `.next`/`.last` suffixes
work automatically (`SuffixRules.ALL`, same as every other home/away
variable).

**Why new names instead of fixing `{home_team_pascal}` directly:** the
alternative (re-registering `home_team_pascal`/`away_team_pascal` as
fork-owned variables and dropping them from upstream's
`_V84_RETIRED_TRANSFORMS`) was rejected — it requires editing inside
upstream's own migration-internals block every port and depends on the
"variable registry beats `_LEGACY_ALIASES`" precedence continuing to hold.
`{home_team_en}`/`{away_team_en}` are new names upstream has never used and
never will retire, so they can't collide and need no interaction with
upstream's alias machinery — a permanent escape hatch, not a per-port patch.

**Template side is DB-only** (same pattern as change #6): fresh installs and
the starter `default_templates.py` specs are **not** touched — they keep
building art URLs from `{home_team|pascal}` (still Spanish-affected). Only
the **live DB's stored templates** get rewritten, via SQL, to reference
`{home_team_en|pascal}`/`{away_team_en|pascal}` instead. This avoids adding a
third fork migration (another number for upstream to potentially steal on a
future release) and avoids a recurring conflict in `default_templates.py`,
which upstream churns.

**Columns to check/rewrite** (superset of where `{home_team|pascal}`/
`{away_team|pascal}` can appear — checked against the real prod DB on the
2026-08-07 port; only `program_art_url`, `event_channel_logo_url`,
`pregame_fallback`, `postgame_fallback` had hits, but re-run the `SELECT`
every time since which templates are customized can differ between DBs):

```sql
-- Inspect first — see which rows/columns actually need it on THIS db:
SELECT id, name, program_art_url, event_channel_logo_url,
       pregame_fallback, postgame_fallback
  FROM templates
 WHERE program_art_url        LIKE '%_team|pascal%'
    OR event_channel_logo_url LIKE '%_team|pascal%'
    OR pregame_fallback       LIKE '%_team|pascal%'
    OR postgame_fallback      LIKE '%_team|pascal%';

-- Apply (safe to re-run — WHERE clause makes it a no-op once done):
UPDATE templates SET
  program_art_url        = replace(replace(program_art_url,
                              '{home_team|pascal}', '{home_team_en|pascal}'),
                              '{away_team|pascal}', '{away_team_en|pascal}'),
  event_channel_logo_url = replace(replace(event_channel_logo_url,
                              '{home_team|pascal}', '{home_team_en|pascal}'),
                              '{away_team|pascal}', '{away_team_en|pascal}'),
  pregame_fallback        = replace(replace(pregame_fallback,
                              '{home_team|pascal}', '{home_team_en|pascal}'),
                              '{away_team|pascal}', '{away_team_en|pascal}'),
  postgame_fallback       = replace(replace(postgame_fallback,
                              '{home_team|pascal}', '{home_team_en|pascal}'),
                              '{away_team|pascal}', '{away_team_en|pascal}')
WHERE program_art_url        LIKE '%_team|pascal%'
   OR event_channel_logo_url LIKE '%_team|pascal%'
   OR pregame_fallback       LIKE '%_team|pascal%'
   OR postgame_fallback      LIKE '%_team|pascal%';
```

The `pregame_fallback`/`postgame_fallback` columns are JSON blobs (per-period
overrides) whose `art_url` key can carry the same tokens — the textual
`replace()` is JSON-safe here for the same reason upstream's own v84
migration's textual rewrite was: the tokens contain no quotes or backslashes.
Only the `art_url` key ever holds these tokens in practice — `title`/
`subtitle`/`description` correctly use the (Spanish-translated)
`{home_team}`/`{away_team}` and must NOT be touched.

**Verification done (2026-08-07 port, applied live to production 2026-08-07,
re-confirmed intact 2026-08-18 on the v2.12.5 port):** applied against a
scp'd copy of the real production `teamarr.db` — 6 template rows
(`program_art_url`/`event_channel_logo_url`: ids 1, 3, 5, 13, 14, 16) plus 2
rows' `pregame_fallback`/`postgame_fallback` blobs, all rewritten correctly,
all other `_V84_TEMPLATE_COLUMNS` columns confirmed clean (no hits).
Container booted against the patched DB copy: healthy, 0 errors, no
re-migration. **Live in production** since 2026-08-07; the 2026-08-18
v2.12.5 deploy re-checked it idempotently (0 remaining `_team|pascal` hits)
before the rsync/build, no re-apply needed.

**Not yet applied to:** this repo's own local `data/teamarr.db` (a separate
dev copy — only needed if testing art URLs locally).

---

## Change 15: Separate-mode failover backups

**Added:** 2026-08-22. **Not Spanish localization** — the fork's first
feature of a different kind (opt-in behavior change, off by default).

**Problem:** "Separate" consolidation mode
(`settings.global_consolidation_mode='separate'`, or a per-keyword
`behavior='separate'` — this fork runs both) gives each matched stream its
own Dispatcharr channel holding exactly **one** stream. If that stream dies,
the channel is dead: there is nothing to fail over to, unlike "Consolidate"
mode where multiple streams for the same event already live on one channel
in failover order.

**What it does:** an opt-in pass, `apply_separate_fallbacks()`, gives each
separate-mode channel up to N (default 3, 0–10) **same-exception-keyword-
group** sibling streams as Dispatcharr failover backups — attached behind
the channel's own stream, which always stays at slot #0. The fallback pool
never crosses exception-keyword groups: a `(Español)` channel only falls
back to other `(Español)` streams, a plain channel only to other plain
streams — the broadcast language never changes on failover. This isn't just
a preference: `KeywordEnforcer` re-derives each stream row's expected
keyword from its name and moves any row whose keyword no longer matches the
channel's, so same-keyword-only backups make that a structural no-op;
cross-group backups would be ripped off every channel on every run.

**Files (all new, one file holds all the logic):**

- `teamarr/consumers/lifecycle/separate_fallbacks.py` — the pass itself
  (`apply_separate_fallbacks`, `_eligible_groups`, `_desired_backups`,
  `_converge_channel`, `_teardown_all`). Exports `BACKUP_PRIORITY_OFFSET`
  (`1_000_000_000` — above the max stream-ordering rule priority), used to
  keep the primary at slot #0 without any extra pinning logic: a backup's
  priority is always `<source stream's rule priority> + BACKUP_PRIORITY_OFFSET`.
- Wired into `teamarr/consumers/generation.py` **after**
  `timer.mark("stream_ordering")`, not before — `_apply_stream_ordering`
  only pushes to Dispatcharr when `reordered_count > 0 or has_windowed`, so
  a fan-out that ran first would insert rows that never reach Dispatcharr
  that run. `_apply_stream_ordering`'s reorder loop is also offset-aware now
  (adds `BACKUP_PRIORITY_OFFSET` for `is_backup` rows) — the only site that
  rewrites priorities from ordering rules, so without this it would flatten
  backups back into the primary's band.
- Two guards in `teamarr/consumers/lifecycle/cleanup.py` — the highest-risk
  edits, since a backup must **never** affect channel lifetime:
  `cleanup_deleted_streams` (the M3U-vanish path) skips `is_backup` rows
  entirely when categorizing valid/missing/changed streams, so a channel
  whose own stream left the M3U still dies even with healthy backups
  present; `cleanup_disabled_groups` computes its "does anything else still
  feed this channel" check over non-backup rows only, so a backup sourced
  from a still-enabled group can't keep alive a channel whose own stream
  came from the disabled group (backups sourced from the disabled group are
  still detached, same as any other stream).
- Settings: `separate_fallback_enabled` (bool, default off) and
  `separate_fallback_count` (int, default 3, clamped 0–10) on
  `ChannelNumberingSettings` (`teamarr/database/settings/types.py`), writer
  validation in `teamarr/database/settings/update.py`, API models/route in
  `teamarr/api/routes/settings/{models.py,channel_numbering.py}`.
- Frontend: `separate_fallback_enabled`/`separate_fallback_count` added to
  `ChannelNumberingSettings`/`...Update` in `frontend/src/api/settings.ts`; a
  `Switch` + numeric `Input` control in
  `frontend/src/pages/channels/ChannelConsolidation.tsx`, rendered
  **unconditionally** (not gated on the Consolidate/Separate radio) since a
  per-keyword `behavior='separate'` can make the feature active even while
  the default mode reads "Consolidate".
- **Bug fix found while building this:**
  `frontend/src/components/ExceptionKeywordsCard.tsx` used to hide the
  entire Exception Keywords table whenever
  `global_consolidation_mode !== 'consolidate'` — which is **always true**
  in this fork's real settings (`global_consolidation_mode='separate'`).
  Per-keyword `behavior` is honored in both modes
  (`teamarr/consumers/lifecycle/creator.py:256`), so that gate was hiding a
  fully-functional, actively-used table. The gate (and the now-unused
  `useChannelNumberingSettings` import) was removed.

**Schema (no migration — see "Schema version note" in `CLAUDE.md` and
`PORTING-TO-NEW-VERSIONS.md`):** three plain `ADD COLUMN`s in
`teamarr/database/schema.sql`, picked up automatically by
`reconcile_schema()` on next startup — `settings.separate_fallback_enabled`,
`settings.separate_fallback_count`, `managed_channel_streams.is_backup`. No
`schema_version` bump; stays **86**.

**One incidental schema-adjacent finding:** `managed_channel_history.
change_source` is `CHECK`-constrained to a fixed value list that has no
`'separate_fallback'` member. Adding one would need a real column-rewrite
migration (SQLite can't `ALTER` an existing `CHECK` via reconciliation),
which this feature deliberately avoids — so `_converge_channel()` logs
history rows with `change_source='lifecycle'` (an existing allowed value)
and puts the real origin in the `notes` text (`"[separate_fallback] ..."`)
instead.

**Tests:** `tests/lifecycle/test_separate_fallbacks.py` (mutual attach, cap
+ determinism, keyword/feed isolation, primary-always-at-slot-0,
idempotence, cap-shrink/sibling-deletion convergence, toggle-off teardown,
window-intersection, Dispatcharr-failure rollback), `tests/lifecycle/
test_separate_fallback_lifecycle.py` (the two cleanup.py lifecycle guards,
plus a `KeywordEnforcer` no-op regression test), `tests/
test_separate_fallback_ordering.py` (the offset-aware reorder loop doesn't
oscillate across runs).

**Verification done (2026-08-22):** full suite 2279/2279 passing (2252
baseline + 27 new), `ruff check` clean, `schema_version` confirmed still 86
via `tests/migrations/`. A frontend `tsc --noEmit` pass came back clean at
this point, but that check is weaker than the production build — see the
next paragraph.

**Docker smoke test done (2026-08-22/23):** real container build + startup
against a **copy** of the local dev `data/teamarr.db` (original untouched;
copy discarded after). Findings:

- The production frontend build (`npx tsc -b`, run by the Dockerfile) is
  **stricter** than plain `tsc --noEmit` and caught a real bug the earlier
  check missed: `frontend/src/pages/channels/ChannelNumbering.tsx` had a
  hardcoded pre-fetch default `ChannelNumberingSettings` object missing the
  two new fields, failing the build outright. Fixed (see the "Files
  Modified" table); rebuilt clean.
- Startup reconciliation added the 3 new columns automatically — confirmed
  **no migration file, `schema_version` stayed 86** — matching the
  "reconciliation-only" design.
- Settings API (`GET`/`PUT /api/v1/settings/channel-numbering`) correctly
  serves and updates both new fields.
- A live generation run through the real pipeline: `[SEPARATE_FALLBACK]
  converged 30 channel(s): +90/-0 backups` — exactly 30 channels × cap 3,
  zero errors. Direct DB check confirmed the priority math: primary stream
  at its rule priority (`99`), all 3 backups at `1000000099`
  (`99 + BACKUP_PRIORITY_OFFSET`) — primary always sorts first.
- Toggle-off (teardown) ran cleanly with no errors, including against
  channels that had since been soft-deleted by the normal event-expiry
  cleanup (a pre-existing, unrelated pipeline stage — the test DB's events
  were already in the past relative to the test date) — confirmed
  `_teardown_all` degrades gracefully rather than erroring on that state.
- **Safety note:** the copied DB carried real production Dispatcharr
  credentials (`teve.sumzin.xyz`). Teamarr authenticates to Dispatcharr
  automatically at container startup, before any test-specific config
  changes can run — so one login/connect call reached the real server
  before it was disabled in the copy. No channel, stream, or generation
  data was read or written (every Dispatcharr call attempted after that
  point failed with "not configured", confirming it was disabled before any
  generation ran). For a repeat of this test, blank the Dispatcharr
  credentials in the DB copy **before** first starting the container, not
  after.

---

## Change 16: EPG anchor guard bypassed on reverse-alias retry (upstream bug fix)

> **v2.25.1 port (2026-10-31): dropped.** Upstream v2.25.1 passes
> `anchor_dt=ctx.anchor_dt` in `_try_reverse_alias_match()` itself (comment
> cites #716), so neither the code change nor
> `tests/matching/test_epg_anchor_reverse_alias.py` is carried any more. The
> section below is kept as history.

**Added:** 2026-08-23. **Not localization, not a fork feature** — this is a
fix for a defect in stock upstream `teamarr/consumers/matching/team_matcher.py`
(confirmed byte-identical to `v2.12.5` and to upstream's `dev` branch as of
2026-08-23 — `git fetch origin --tags` found no newer tag, and
`git log v2.12.5..origin/dev -- teamarr/consumers/matching/team_matcher.py`
shows only an unrelated commit, `b19311f2`, that doesn't touch this code
path). Carry this patch until upstream ships an equivalent fix, then drop it;
worth reporting to Pharaoh-Labs/teamarr.

**Problem — production incident, 2026-08-23:** two channels for
"15:00, 23-Aug | Brighton & Hove Albion - Aston Villa" were created in
Dispatcharr with **zero streams** (the only 2 empty channels out of 81 active
managed channels at the time). Traced via prod logs to a 15-minute
**highlights** programme, `'PL: Brighton v Aston Villa Hls'` at
`2026-08-24T03:30:00+00:00`, binding to the live 13:00 UTC kickoff — 870
minutes away:

```
[CLASSIFY] 'PL: Brighton v Aston Villa Hls' -> team_vs_team (teams=Brighton/Aston Villa Hls)
[FAILED] stream_id=71118 reason=no_event_found teams=Brighton/Aston Villa Hls
[REVERSE_ALIAS] team1=Brighton → [('brighton and hove albion', None)], team2=Aston Villa Hls → []
[MATCHED] stream_id=71118 method=fuzzy event=401879297 league=eng.1 confidence=100%
[REVERSE_ALIAS_MATCH] stream_id=71118 'Brighton/Aston Villa Hls' → 'brighton and hove albion/…'
[EPG_MATCH] tvg=skysport1.nz prog='PL: Brighton v Aston Villa Hls' @2026-08-24T03:30:00+00:00
            -> event=401879297 'AVL @ BHA' @2026-08-23T13:00:00+00:00 (Δ=870m)
```

`ANCHOR_MATCH_TOLERANCE_SECONDS = 90 * 60` (`team_matcher.py:61`) exists
specifically to reject this — its own comment calls it *"the definitive,
category-independent guard against encore binding."* It is enforced in
`_match_against_events` and `_match_against_multi_league_events`, both gated
on `ctx.anchor_dt is not None`. `_try_reverse_alias_match()` rebuilds a
`MatchContext` for its retry but **omitted `anchor_dt`**, so it defaulted to
`None` and the anchor gate ran as a no-op on this path — any distance would
match. Both entry-path `MatchContext` constructions (`match_single_league`,
`match_multi_league`) pass `anchor_dt` correctly; the retry at
`_try_reverse_alias_match` was the only leak. Not an isolated case: in one
10 MB prod log, 43 of 113 `[EPG_MATCH]` pairs exceeded the 90-minute
tolerance (most harmlessly discarded because the caller keeps only the
programme nearest each event — the damage lands only where no closer
programme exists on that guide channel).

A second, independent contributor to the same incident was a **settings**
mismatch, not a bug: `channel_pre_buffer_minutes=720` (12h) created channels
before `epg_stream_pre_buffer_minutes=600` (10h) let any EPG-matched stream
attach, so every event briefly had a clickable empty channel regardless of
this fix. Corrected via **Channels → Lifecycle → Pre-Event Buffer**, 12 → 9
hours (`channel_pre_buffer_minutes` 720 → 540), applied directly on
production and the local dev DB on 2026-08-23 — settings-only, no code, no
migration, not part of this change.

**What it does:** one-line fix — `_try_reverse_alias_match()`'s retry
`MatchContext` (`team_matcher.py:1927-1939`) now passes
`anchor_dt=ctx.anchor_dt` through, same as both entry paths already do.
Surgical: on the non-EPG (stream-name) path `ctx.anchor_dt` is already
`None`, so behavior there is unchanged; only EPG-anchored reverse-alias
matching is affected, which is exactly the case the guard was written for.

**Files:**
- `teamarr/consumers/matching/team_matcher.py` — the fix, `:1927-1939`.
- `tests/matching/test_epg_anchor_reverse_alias.py` — **NEW**. The
  reverse-alias path had **zero** test coverage before this
  (`grep -rln "REVERSE_ALIAS" tests/` found nothing). Reproduces the
  production incident directly against `TeamMatcher._try_reverse_alias_match()`
  with the real team names, stream title, event, and timestamps: (1) the
  far-anchor highlights case → asserted `None` (fails without the fix,
  confirmed by temporarily reverting it and re-running); (2) a near-anchor
  live broadcast (5 min before kickoff) → still matches, guarding against
  over-correction; (3) the non-anchored stream-name path → unaffected.

**Verification done (2026-08-23):** full suite **2282/2282 passing** (2279
baseline + 3 new), `ruff check teamarr/ tests/` clean. Confirmed the new test
fails on the exact production Δ=870m case with the fix reverted (`git stash`
on `team_matcher.py` alone), and passes with it applied. Also manually
replayed the second real prod occurrence for the same fixture (`NZ: SKY
SPORT 6`, Δ=525m, a stale-guide live-titled repeat) — correctly rejected by
the fixed code. **Deployed to production 2026-08-23** (`GIT_SHA=f2b7ea2c`) —
code-only fix, no DB/schema change, no migration. (This section previously
said "not yet deployed"; corrected 2026-08-24 after the container's startup
log confirmed it had been running since 2026-08-23T12:48:59Z — see
`CLAUDE.md` item 16 and the change #17 TODO entry for the full note.)

---

## Change 17: Keyword channels sort before the plain channel for the same event

> **v2.25.1 port (2026-10-31):** upstream independently added the same
> once-per-pass swap guard to `KeywordOrderingEnforcer` (#1119, `used_ids`), so
> the fork's own `seen` guard was dropped in favour of upstream's; only the
> inverted comparison remains fork code there. The `sort_key()` direction is now
> behind a module flag, `channel_numbers.KEYWORD_CHANNELS_FIRST = True`, so the
> upstream lane/order-mode tests (`tests/lifecycle/test_numbering_lanes.py`,
> `tests/lifecycle/test_channel_order_mode.py`) pin the stock direction with an
> autouse fixture and keep upstream's expected numbers byte-identical; the fork
> direction is covered by `tests/lifecycle/test_keyword_first_ordering.py` and
> the mirrored `tests/test_keyword_ordering_one_swap.py`.

**Added:** 2026-08-24. Fork-owned prioritization tweak, not localization.
tito's channel list carries several channels per game — the plain one plus
one or more exception-keyword variants (`(Español)`, `(Portugués)`, …) — and
wanted the ones he actually watches, the keyword variants, to lead.

**Constraint:** this is a **same-event tie-break only**. Every ordering rule
above it — priority teams, sport priority, league priority, event start
time, event id — is untouched, so it can never move a channel relative to a
*different* event's channels.

**What it does:** two enforcement points both said "plain channel first";
both were inverted so they agree instead of fighting each other:

1. **The global sort tie-break** —
   `teamarr/database/channel_numbers.py`, `get_all_channels_sorted()`'s
   `sort_key()`. The `keyword_sort` element (the *last* item of the sort
   tuple, so purely a same-event tie-break) used to be `(0, "")` for the
   plain channel / `(1, keyword)` for a keyword channel; now it's
   `(0, keyword)` / `(1, "")` — keyword channels first, sorted
   alphabetically among themselves (`Español` before `Portugués`), plain
   channel last. This wins on every normal `compact`-mode run (the default),
   since the whole numbering grid is rebuilt from this sort each run.
2. **`KeywordOrderingEnforcer`** —
   `teamarr/consumers/enforcement/ordering.py`. This is the corrective pass
   that matters in `gap`/`strict` stability mode, where existing channel
   numbers are locked and only re-graded on the daily reset — without
   inverting this too, a locked-in "wrong" pair would never get fixed
   between resets. Its detection query used to fire on
   `keyword_number < main_number`; now it fires on
   `keyword_number > main_number`, and does the same symmetric swap (which
   didn't need to change — swapping two numbers is direction-agnostic).
   Added a `seen` guard so a channel already swapped once in a pass is
   skipped on any later pair — protects against a pre-existing hazard in
   this self-join query, not new behavior: with tito's **separate** mode
   (several plain + several keyword channels per event) it can return
   several pairs sharing a channel, all built from one stale snapshot of
   `channel_number`; without the guard a channel could be swapped twice
   using an outdated number in the same pass. Anything the guard skips is
   still caught by the authoritative reassignment pass moments later, or
   re-detected next run.

**No settings toggle** — fixed fork behaviour, smallest diff, easiest to
carry across future upstream ports. **No schema/DB change** — schema stays
**86**.

**When it takes effect:** immediately on the next generation run in
`channel_stability_mode = compact` (the default). In `gap`/`strict` mode,
existing channels are locked and keep their numbers until the daily reset
(`channel_daily_reset_time`, default `04:00`) or an armed re-grid ("Re-grid
now" on the Channel Numbering settings page).

**Files:**
- `teamarr/database/channel_numbers.py` — `keyword_sort` inverted in
  `sort_key()`; docstring/comments updated.
- `teamarr/consumers/enforcement/ordering.py` — detection comparison
  inverted (`<` → `>`); `seen`-guard added against the pre-existing
  double-swap hazard; docstrings/log text updated to match the new
  direction.
- `teamarr/consumers/event_group_processor/processor.py` — step comment
  updated (no logic change).
- `tests/lifecycle/test_keyword_first_ordering.py` — **NEW**. Same-event
  keyword-before-plain (single and multi-keyword), the fork's separate-mode
  shape (multiple plain + multiple keyword channels for one event stays a
  contiguous keyword-first block), and three explicit "never crosses
  events" guards (by event time, league priority, priority team).
- `tests/test_keyword_ordering_safe_update.py` — fixture numbers flipped so
  the pair still trips the (now inverted) detection condition; the test's
  actual subject (Dispatcharr-rejects-the-swap → DB left unchanged) is
  unaffected.
- `tests/lifecycle/test_channel_stability.py` —
  `test_gap_sticky_keyword_variants_stay_contiguous` and
  `test_gap_reset_keyword_variant_contiguous_with_gap_between_events`
  asserted the old main-before-keyword ordering directly; flipped to match.

**Verification done (2026-08-24):** full suite **2288/2288 passing**
(2282 baseline + 6 new/modified), `ruff check teamarr/ tests/` clean.
**Deployed to production 2026-08-24** (`GIT_SHA=8d75ee59`) — code-only
change, no DB/schema change, no migration (schema stayed 86). Container
healthy, zero `ERROR` log lines across startup + a full production EPG
generation run (611 programmes/events, 126.5s). Verified against real prod
data: `Málaga - Deportivo (Español)` moved from #887 to #880, ahead of the
plain channel now at #882. See `CLAUDE.md`'s TODO for the full deploy log.

---

## Change 18: Dash matchup separator + EPG star-rating strip

**Added:** 2026-08-30. Two independent fixes, deployed together because the
second was only discovered while verifying the first. Neither is
localization; both are matching-pipeline bug fixes.

**Trigger:** tito reported that the production channel `17:00, 30-Aug |
Real Madrid - Málaga (Español)` carried only its ESPN+ stream, even though
the EPG showed a matching Movistar LaLiga programme
(`DIRECTO Jornada 3: Real Madrid - Málaga T26/27 · LALIGA EA SPORTS`,
tvg `M+ LaLiga HD`, stream `ES: MOVISTAR LALIGA ᴴᴰ`, group 73
`ES| M+ LALIGA VIP`).

### 18a. `" - "` as a matchup separator (DB-only, no code change)

Stock Teamarr deliberately excludes `" - "` from `GAME_SEPARATORS`
(`teamarr/utilities/constants.py:509-520` — hyphens appear inside team names
and schedule labels; see the comment at `classifier.py:1826-1830`). Verified
against production code + data: the real programme title classified as
`PLACEHOLDER` (with its real sub_title) — no team pair was ever extracted, so
the match was never attempted. `detection_keywords(category='separators')`
is upstream's own sanctioned per-install extension point for exactly this
case, so no code change was needed:

```sql
INSERT INTO detection_keywords (category, keyword, is_regex, target_value, enabled, priority, description)
VALUES ('separators', ' - ', 0, NULL, 1, 100,
        'Dash matchup separator: Movistar/European EPG titles (Real Madrid - Málaga)');
```

**Requires a container restart** — unlike the exception keywords (re-read
every generation run via `_check_exception_keyword`), separators are cached
for the process lifetime in `DetectionKeywordService._separators` (a
`ClassVar`), and `invalidate_cache()` has no callers anywhere in the codebase
that would refresh it mid-run.

**Blast radius, measured against 5,614 distinct production stream names**
(classified with and without the separator): 1,349 reclassify, all in the
permissive direction (`TEAM_ONLY`/`PLACEHOLDER` → `TEAM_VS_TEAM`); **zero**
currently-matching streams regressed.

### 18b. EPG guide star-rating misread as a date (code fix)

Deploying 18a alone was **not sufficient** — tracing the actual match logs
after deployment showed the newly-extracted team pair (`Real Madrid` /
`Málaga T26/27 · LALIGA EA SPORTS | 2026 | TP | ★6.6/10`) scored a perfect
100/100 against the real event, then was rejected anyway:

```
[FAILED] stream_id=89352 reason=date_mismatch teams=Real Madrid/Málaga T26/27 · LALIGA EA SPORTS | 2026 | TP | ★6.6/10
[NEAR_MISS] stream_id=89352 best='Real Madrid vs Málaga' (esp.1 2026-08-30) scores Real Madrid=100 / Málaga...=100 (need 60) alias1=none alias2=none date_gated=1
```

Root cause: the guide's `sub_title` carries a star rating (`2026 | TP |
★6.6/10`). The `"N.N/10"` shape collides with `normalizer.py`'s bare MM/DD
date pattern (`DATE_PATTERNS`, `\b(\d{1,2})[/\-](\d{1,2})\b`,
`teamarr/consumers/matching/normalizer.py:283`) — `★6.6/10` contains `6/10`,
read as **June 10**. Because built-in date extraction is `trusted`, the
`#474` trusted-date gate (`team_matcher.py:1178-1184`) silently rejects the
match as an 81-day mismatch against the real 30-Aug broadcast — even though
the anchor gate (Δ=10m) and team scoring both passed cleanly.

**Not a new bug** — pre-existing in stock upstream, present regardless of
18a. It went unnoticed because whole-number ratings dodge it by accident:
`★6.0/10` contains `0/10`, an invalid date (month/day 0), so extraction
silently no-ops. Any fractional rating (`★X.1` through `★X.9`, i.e. almost
all of them) hits it. Confirmed live: today's parallel Celta–Athletic game
(`★6.0/10`) matched fine via the *description fallback* — but 18a's team
extraction success routes it away from that fallback
(`matcher.py`'s `_try_description_match` skips whenever `team1`/`team2` are
already populated), so 18a alone would have silently traded one broken path
for another on ratings that used to dodge the bug by luck.

**Fix:** strip the `"★N.N/10"` token in `_clean_epg_segment()`
(`teamarr/consumers/matching/epg_matcher.py`) — the function that already
exists for exactly this purpose (it strips superscript "Live"/"New" feed
decoration before the text reaches the classifier). Deliberately **not**
fixed in the shared `DATE_PATTERNS` regex: the rating is purely an EPG-guide
artifact, never a real date in a stream or programme title, so the narrower
fix has no blast radius outside EPG matching.

```python
_RATING_SUFFIX = re.compile(r"[★☆]\s*\d(?:\.\d)?\s*/\s*10\b")

def _clean_epg_segment(text: str) -> str:
    text = _RATING_SUFFIX.sub(" ", text)
    return re.sub(r"\s+", " ", _EPG_DECORATION.sub(" ", text)).strip()
```

**Files:**
- `teamarr/consumers/matching/epg_matcher.py` — `_RATING_SUFFIX` constant +
  the strip call in `_clean_epg_segment()`.
- `tests/epg/test_epg_matcher_logic.py` — **3 new tests**: the rating is
  stripped from `build_match_input()` output; the stripped rating produces
  no false `extracted_date` for both the fractional (★6.6) and whole-number
  (★6.0) cases; a genuine embedded date elsewhere in the string still
  extracts (no over-matching).

**Verification done (2026-08-30):**
- Full suite **2291/2291 passing** (2288 baseline + 3 new),
  `ruff check teamarr/ tests/` clean.
- 18a (separator) deployed alone first, full production EPG generation run:
  the target stream still didn't attach (18b's bug, then undiscovered,
  blocked it) — matched-stream counts per group nonetheless rose from a
  280-total baseline with **zero groups regressing**.
- 18b (rating strip) deployed on top, second full production EPG generation
  run: channel 4005 (`17:00, 30-Aug | Real Madrid - Málaga (Español)`) now
  carries `ES: MOVISTAR LALIGA ᴴᴰ` (`match_method='epg'`) plus two
  same-exception-keyword-group siblings pulled in as failover backups by
  customization #15. Matched-stream totals rose again, **280 → 409 across
  both deploys, zero groups regressed either time** — a strictly monotonic
  improvement. Zero `ERROR` log lines across both startups + both full
  generation runs.
- **Deployed to production 2026-08-30**: 18a via direct SQL insert
  (`docker compose down` → `data/teamarr.db` backed up to
  `data/teamarr.db.bak-pre-dash-separator-20260830`, checksum-verified
  byte-identical before the insert → row inserted → `up -d`); 18b via
  `rsync` of the two changed files (`epg_matcher.py` backed up server-side
  to `epg_matcher.py.bak-pre-rating-fix-20260830` first) →
  `docker compose down` → `docker build -t teamarr:custom .` → `up -d`.
  Both code-only/data-only — **no schema/DB migration, schema stayed 86**.
  Commit `4cde9ccc` (18b; 18a has no commit, it is data-only).
- **Known drift, unrelated to this change:** `/opt/teamarr`'s local git
  checkout is stuck at a stale `dev-custom-2.12.2` HEAD
  (`61ba6ece`) from before this fork's git history was properly tracked
  server-side — prior deploys have always been plain `rsync`, never `git
  pull`, on that directory. The *file content* deployed is correct
  (verified directly: `docker run --rm teamarr:custom cat
  .../epg_matcher.py` shows the fix), but the app's reported version
  string (`GIT_BRANCH`/`GIT_SHA` build args, sourced from that stale git
  state) is misleading. Not fixed as part of this change — flagged in
  `CLAUDE.md`'s TODO for a future session to decide how to reconcile
  `/opt/teamarr`'s git state with reality.

---

## Changes 19–20: found on the v2.25.1 production deploy (2026-10-31)

Both are fixes to upstream behaviour that only showed up against real
production data. The first generation after the deploy matched far fewer
streams (programmes 1,049 → 102), and both causes had to be fixed before the
deploy counted as healthy.

### 19. Dash-written EPG matchups must not be split between the teams (`29f85753`)

Upstream #728 added a plain `-` to `_INLINE_SEP` (`teamarr/consumers/matching/epg_matcher.py`),
the pattern that splits a sub_title-less programme title into
"category | matchup". Movistar/DAZN write the matchup itself with a dash
(`DIRECTO Jornada 9: Chelsea - Manchester United T26/27`). The split landed
between the two teams (`… Chelsea | Manchester United T26/27`), so no pair was
extracted and every such programme failed. This is the same shape #18a's
`' - '` separator row exists for.

**Fix:** `_split_inline_matchup()` splits at the first inline separator only
when the text after it still holds a matchup separator (built-in
`GAME_SEPARATORS` or another inline dash). Upstream's own cases still split:
`MLB Baseball - Mets at Mariners`, `NBA : Game 1 : Knicks at Spurs`,
`Premier League — Arsenal vs Chelsea`. Test:
`test_build_input_dash_matchup_is_not_split_between_teams` in
`tests/epg/test_epg_matcher_logic.py`.

### 20. A failed ESPN fetch is never cached as an empty day (`32a91846`)

At startup, v2.25.1's cache refresh and the first generation together sent
ESPN enough requests to be throttled with HTTP 403. This was the first run
after upgrading, and v2.25.1 renamed the event cache (`events_v2`), so
everything was fetched cold. The ESPN client returns `None` on an HTTP error.
The provider turned that into `[]`, and `SportsDataService.get_events` cached
it like a real empty day:
- 394 `events_v2` and 564 `events_raw` entries were empty;
- LaLiga and Premier League showed no games today and tomorrow;
- the past five days were cached empty for 30 days.

**Fix:**
- `ESPNProvider.get_events` (scoreboard, MMA and tournament paths) raises
  `ESPNFetchError` (`teamarr/providers/espn/client.py`) when the request failed.
  A genuine empty scoreboard is still `[]`.
- `_fetch_provider_span` records failed buckets, and `get_events` returns
  what it has without caching that user-day.
- The raw bucket was already left uncached on an exception.

The poisoned rows already in production were deleted (with the container
stopped). Test: `tests/services/test_failed_fetch_not_cached.py`. After the
fix, a cold run logs `[EVENTS] … bucket … failed` warnings instead of caching,
and the next run refetches them: 0 × 403 once warm.

**Worth reporting upstream:** both #19 and #20 are upstream issues.

---

## Files Modified


> **Path note (v2.25.1):** this table describes the v2.12.5 layout. For current
> locations, including changes #19/#20, see the touch-point map in
> `PORTING-TO-NEW-VERSIONS.md`.

### Core code (8 files)

| File | Change |
|------|--------|
| `teamarr/database/channels/keywords.py` | Added `_strip_accents()` helper; applied to both stream text and match terms in `check_exception_keyword()` and `_make_keyword_pattern()` |
| `teamarr/database/migrations/versioned.py` | Added v85 migration `_migrate_v85_exception_keyword_accents()` and v86 `_migrate_v86_spanish_language_names()` + guard blocks, placed after upstream's own v84 block |
| `teamarr/database/migrations/__init__.py` | Export the two fork migration functions |
| `teamarr/database/schema.sql` | Schema version 84→86; seed labels changed to Spanish; match terms include un-accented variants + `ES:` |
| `teamarr/database/checkpoint_v43.py` | Seed labels changed to Spanish; match terms updated to match schema.sql |
| `teamarr/consumers/lifecycle/types.py` | `slugify_keyword()` strips accents before slugifying |
| `teamarr/consumers/matching/normalizer.py` | `apply_city_translations()` now also applies `COUNTRY_TRANSLATIONS` |
| `teamarr/utilities/constants.py` | Added `COUNTRY_TRANSLATIONS` dict (~40 Spanish/Portuguese→English for matching) and `ENGLISH_TO_SPANISH_COUNTRIES` dict (~120 English→Spanish for display) |
| `teamarr/templates/variables/home_away.py` | Added `_translate_country_for_display()` helper; applied to `{home_team}`, `{away_team}`, `{home_team_short}`, `{away_team_short}` extractors. **v2.12.4:** added untranslated `{home_team_en}`/`{away_team_en}` (change #14) |
| `teamarr/templates/variables/datetime.py` | `game_date_short` format `%b %-d` → `%-d-%b` (`22-Jul`) |
| `teamarr/templates/sample_data.py` | `game_date_short` UI samples → `22-Dec` style |
| `teamarr/consumers/lifecycle/separate_fallbacks.py` | **NEW** (change #15) — the whole failover-backup pass, self-contained |
| `teamarr/consumers/generation.py` | Wired `apply_separate_fallbacks()` in after the stream-ordering phase; offset-aware reorder loop; `GenerationResult.separate_fallbacks` field |
| `teamarr/consumers/lifecycle/cleanup.py` | Two `is_backup` lifecycle guards (`cleanup_deleted_streams`, `cleanup_disabled_groups`) |
| `teamarr/database/channels/types.py` | `ManagedChannelStream.is_backup` field |
| `teamarr/database/channels/streams.py` | `is_backup` added to `add_stream_to_channel()`'s `allowed_fields` |
| `teamarr/database/settings/types.py` | `ChannelNumberingSettings.separate_fallback_enabled`/`separate_fallback_count` |
| `teamarr/database/settings/update.py` | `update_channel_numbering_settings()` accepts + clamps (0–10) the two new fields |
| `teamarr/api/routes/settings/models.py` | `ChannelNumberingSettingsModel`/`...Update` carry the two new fields |
| `teamarr/api/routes/settings/channel_numbering.py` | Range validation (0–10) for `separate_fallback_count` |
| `frontend/src/api/settings.ts` | `ChannelNumberingSettings`/`...Update` TS interfaces carry the two new fields |
| `frontend/src/pages/channels/ChannelConsolidation.tsx` | New unconditional Switch + Input control |
| `frontend/src/components/ExceptionKeywordsCard.tsx` | Removed the `global_consolidation_mode !== 'consolidate'` gate (bug fix, see change #15) |
| `frontend/src/pages/channels/ChannelNumbering.tsx` | Added the two new fields to a hardcoded pre-fetch default `ChannelNumberingSettings` object (`tsc -b`, the production build's stricter project check, fails without this — a plain `tsc --noEmit` run missed it; caught by the Docker smoke test) |
| `teamarr/consumers/matching/team_matcher.py` | **Bug fix** (change #16) — `_try_reverse_alias_match()`'s retry `MatchContext` now carries `anchor_dt=ctx.anchor_dt` through, so the EPG anchor-distance guard isn't a no-op on the reverse-alias path |
| `teamarr/database/channel_numbers.py` | **Change #17** — `keyword_sort` inverted in `get_all_channels_sorted()`'s `sort_key()` so keyword channels sort before the plain channel for the same event |
| `teamarr/consumers/enforcement/ordering.py` | **Change #17** — `KeywordOrderingEnforcer`'s detection comparison inverted; added a `seen` guard against double-swapping a channel from a stale number in one pass |
| `teamarr/consumers/event_group_processor/processor.py` | **Change #17** — step comment updated to match the new ordering direction (no logic change) |

### Docs (2 files)

| File | Change |
|------|--------|
| `docs/reference/architecture/migrations.md` | Schema version → 86, added v85/v86 entries to version history |
| `docs/guide/epg/variables.md` | `game_date_short` example → `22-Dec` |
| `CLAUDE.md` | Schema version reference → v86 (upstream's tracked agent file; the fork's personal CLAUDE.md overlay is uncommitted) |

### Tests (7 files)

| File | Change |
|------|--------|
| `tests/matching/test_exception_keyword_accents.py` | **NEW** — tests for accent-insensitive matching (incl. v86 Spanish-name terms) |
| `tests/matching/test_country_translations.py` | **NEW** — country matching/derived-dict tests |
| `tests/templates/test_country_display_translation.py` | **NEW** — youth/women suffix display tests |
| `tests/templates/test_home_away_en_variables.py` | **NEW** (v2.12.4) — `{home_team_en}`/`{away_team_en}` diverge from `{home_team}`/`{away_team}` for national teams, agree for clubs, empty-safe with no game context |
| `tests/migrations/test_migration_helpers.py` | Added `TestV85ExceptionKeywordAccents` + `TestV86SpanishLanguageNames` classes |
| `tests/lifecycle/test_exception_keyword_tvg_id.py` | Updated `test_special_chars` assertion for accent-stripping |
| `tests/matching/test_live_status_prefix.py` | Updated `test_directo_removed_in_pipeline` for country translations |
| `tests/migrations/test_checkpoint_v43.py` | Final schema version assertion → 86 |
| `tests/migrations/test_subscription_migration.py` | Final schema version assertion → 86 |
| `tests/migrations/test_versioned_migrations.py` | Final schema version assertions → 86 (×5) |
| `tests/test_media_server_settings.py` | Final schema version assertion → 86 |
| `tests/templates/goldens/*.xml` | Regenerated (`UPDATE_GOLDENS=1`) for `lang="es"` — upstream goldens assume `lang="en"`; `international_event.xml` also carries the accepted #13 regression (icon URLs use the Spanish country name) |
| `tests/lifecycle/test_separate_fallbacks.py` | **NEW** (change #15) — mutual attach, cap+determinism, keyword/feed isolation, primary-always-at-slot-0, idempotence, convergence, teardown, window-intersection, rollback |
| `tests/lifecycle/test_separate_fallback_lifecycle.py` | **NEW** (change #15) — the two `cleanup.py` lifecycle guards + `KeywordEnforcer` no-op |
| `tests/test_separate_fallback_ordering.py` | **NEW** (change #15) — offset-aware reorder loop, no oscillation across runs |
| `tests/fakes.py` | `FakeStream.is_backup` field added (default `False`) |
| `tests/matching/test_epg_anchor_reverse_alias.py` | **NEW** (change #16) — reproduces the production incident directly against `TeamMatcher._try_reverse_alias_match()`: a far-anchor highlights match is rejected, a near-anchor live match still succeeds, the non-anchored stream-name path is unaffected |
| `tests/lifecycle/test_keyword_first_ordering.py` | **NEW** (change #17) — same-event keyword-before-plain (single + multi-keyword), separate-mode contiguous block, and explicit "never crosses events" guards (time, league priority, priority team) |
| `tests/test_keyword_ordering_safe_update.py` | **Change #17** — fixture numbers flipped to trip the inverted detection condition; subject under test unaffected |
| `tests/lifecycle/test_channel_stability.py` | **Change #17** — two tests that asserted main-before-keyword directly, flipped to keyword-before-main |

---

## Detailed Change Descriptions

### 1. Accent-insensitive keyword matching

**Problem:** Python's `re` treats `ñ ≠ n`. A stream named `...EN espanol` (no tilde) failed to match the keyword term `Español` (with tilde), so no language was added to the channel name. The Portuguese stream worked by luck — the plain-ASCII English word `Portuguese` happened to be in its match terms.

**Fix:** Added `_strip_accents()` in `keywords.py` that decomposes text via `unicodedata.normalize('NFD', text)` and drops combining marks (category `Mn`). Applied to **both** the stream text and each match term before regex comparison, so `espanol` matches `Español`.

**Also includes:** v85 data migration that `UPDATE`s the Spanish/French/Portuguese keyword rows in the existing DB to include un-accented variants (`Espanol`, `Francais`, `Portugues`). Uses `UPDATE` (not `INSERT OR IGNORE`) because the seed can't modify existing rows.

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

**Addendum (2026-08-23):** `ES:` only matches a colon-suffixed prefix, so an
HBO Max Spain feed like `Fútbol: RCD Espanyol vs Real Madrid @ Aug 22 20:30
PM :MAX ES 31` slipped through with no Español match (bare "ES", no colon)
and landed on a plain, unsuffixed channel instead of merging under
`(Español)`. Added `MAX ES` as its own term — narrower and safer than a bare
`ES` (which would catch any standalone "ES" token anywhere in a stream name,
an unverifiable risk against the full real catalog); confirmed `\bmax es\b`
doesn't match plain `HBO MAX`. DB-only, same as this change's original `ES:`
addition — applied directly to the live DB (both production and local dev)
via `UPDATE consolidation_exception_keywords SET match_terms = match_terms
|| ', MAX ES' WHERE label='Español'`; also folded into the canonical
re-apply scripts below so a fresh port doesn't lose it.

**Addendum (2026-08-23, same day):** also added `Fanatiz` and `VIX` —
tito's own Spanish-language streaming-service source names (Fanatiz:
LATAM sports; VIX: TelevisaUnivision's Spanish-language service) that don't
contain "Español"/"Spanish" anywhere in their stream names either. Verified
word-boundary-safe against `MATRIX`, `REVIX`, `PHOENIX`, `AVIX`,
`Fanatical` (none false-positive). Same DB-only apply pattern as `MAX ES`,
same live DBs, same re-apply scripts.

### 6. Keyword behavior set to `separate`

**Problem:** The keyword `behavior='consolidate'` overrode the global "Stream Consolidation: Separate" setting, forcing all streams with the same keyword into one channel.

**Fix:** Changed all language keyword behaviors from `consolidate` to `separate` in the DB. Each stream now gets its own channel, consistent with the global setting.

**Note:** This is a DB-only change — the seed files (`schema.sql`, `checkpoint_v43.py`) still use `consolidate` as the default for fresh installs. Only the live DB was changed.

### 7. Spanish country names in channel name display

**Problem:** ESPN returns English country names (`Spain`, `Belgium`, `Saudi Arabia`), so channel names showed `18:00 CEST - Spain - Cape Verde` instead of Spanish names.

**Fix:** Added `ENGLISH_TO_SPANISH_COUNTRIES` dict (~120 countries) to `constants.py`. A `_translate_country_for_display()` helper in `home_away.py` applies it to the `{home_team}`, `{away_team}`, `{home_team_short}`, and `{away_team_short}` template variables. Now `Spain` → `España`, `Belgium` → `Bélgica`, `Saudi Arabia` → `Arabia Saudí`, etc.

**Key design decision:** Translation is **display-only** — applied at the template variable level, NOT at the ESPN provider or matching layer. This means:
- Matching, tvg-IDs, and logs keep the canonical English name
- **As of v2.12.3, `{home_team_pascal}` no longer keeps the English name** —
  see accepted regression #13 below
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


> **Path note (v2.25.1):** written for in-container patching on v2.12.5. The
> DB-only SQL below (Step 2) is still correct and is the reference for #5/#6/#14/#18a.
> The Python file list in Step 1 is not current: use git and the touch-point map
> in `PORTING-TO-NEW-VERSIONS.md`.

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
docker cp teamarr/database/migrations/versioned.py  teamarr:/app/teamarr/database/migrations/versioned.py
docker cp teamarr/database/migrations/__init__.py   teamarr:/app/teamarr/database/migrations/__init__.py
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
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Spanish, En Español, En Espanol, (ESP), Español, Espanol, ES:, MAX ES, Fanatiz, VIX' WHERE label='Español'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='French, En Français, En Francais, (FRA), Français, Francais, Francés, Frances' WHERE label='Francés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Portuguese, (POR), Português, Portugues' WHERE label='Portugués'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='German, (GER), Deutsch, Alemán, Aleman' WHERE label='Alemán'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Japanese, (JPN), 日本語, Japonés, Japones' WHERE label='Japonés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Korean, (KOR), 한국어, Coreano' WHERE label='Coreano'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Chinese, (CHN), (CHI), 中文, Chino' WHERE label='Chino'\")

# 3. Set all keyword behaviors to 'separate'
conn.execute(\"UPDATE consolidation_exception_keywords SET behavior='separate' WHERE behavior='consolidate'\")

# 4. (v2.12.4+, change #14) Point art/logo URLs at the untranslated
#    {home_team_en}/{away_team_en} variables instead of {home_team}/{away_team}
#    — see change #14 above for the full runbook, why it's needed, and which
#    columns to check. This block covers the 4 columns found on the real
#    prod DB as of the 2026-08-07 port; re-run the SELECT in #14 first if
#    porting further to confirm the column list still matches.
conn.execute(\"UPDATE templates SET program_art_url = replace(replace(program_art_url, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE program_art_url LIKE '%_team|pascal%'\")
conn.execute(\"UPDATE templates SET event_channel_logo_url = replace(replace(event_channel_logo_url, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE event_channel_logo_url LIKE '%_team|pascal%'\")
conn.execute(\"UPDATE templates SET pregame_fallback = replace(replace(pregame_fallback, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE pregame_fallback LIKE '%_team|pascal%'\")
conn.execute(\"UPDATE templates SET postgame_fallback = replace(replace(postgame_fallback, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE postgame_fallback LIKE '%_team|pascal%'\")

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
# Check schema version (should be 86+)
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

These 11 files need to be re-copied after any image update:

```
teamarr/database/channels/keywords.py
teamarr/database/migrations/versioned.py
teamarr/database/migrations/__init__.py
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
docker cp teamarr/database/migrations/versioned.py  teamarr:/app/teamarr/database/migrations/versioned.py
docker cp teamarr/database/migrations/__init__.py   teamarr:/app/teamarr/database/migrations/__init__.py
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
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Spanish, En Español, En Espanol, (ESP), Español, Espanol, ES:, MAX ES, Fanatiz, VIX' WHERE label='Español'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='French, En Français, En Francais, (FRA), Français, Francais, Francés, Frances' WHERE label='Francés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Portuguese, (POR), Português, Portugues' WHERE label='Portugués'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='German, (GER), Deutsch, Alemán, Aleman' WHERE label='Alemán'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Japanese, (JPN), 日本語, Japonés, Japones' WHERE label='Japonés'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Korean, (KOR), 한국어, Coreano' WHERE label='Coreano'\")
conn.execute(\"UPDATE consolidation_exception_keywords SET match_terms='Chinese, (CHN), (CHI), 中文, Chino' WHERE label='Chino'\")

# Set behavior to separate
conn.execute(\"UPDATE consolidation_exception_keywords SET behavior='separate' WHERE behavior='consolidate'\")

# (v2.12.4+, change #14) Untranslated art/logo URLs — see change #14 for the runbook
conn.execute(\"UPDATE templates SET program_art_url = replace(replace(program_art_url, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE program_art_url LIKE '%_team|pascal%'\")
conn.execute(\"UPDATE templates SET event_channel_logo_url = replace(replace(event_channel_logo_url, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE event_channel_logo_url LIKE '%_team|pascal%'\")
conn.execute(\"UPDATE templates SET pregame_fallback = replace(replace(pregame_fallback, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE pregame_fallback LIKE '%_team|pascal%'\")
conn.execute(\"UPDATE templates SET postgame_fallback = replace(replace(postgame_fallback, '{home_team|pascal}', '{home_team_en|pascal}'), '{away_team|pascal}', '{away_team_en|pascal}') WHERE postgame_fallback LIKE '%_team|pascal%'\")
conn.commit()

rows = conn.execute('SELECT label, behavior FROM consolidation_exception_keywords ORDER BY label').fetchall()
for r in rows: print(f'  {r[0]:14} behavior={r[1]}')
conn.close()
"

echo "=== Done ==="
docker ps --filter name=teamarr --format '{{.Status}}'
```

Then: `chmod +x /opt/teamarr/reapply-customizations.sh && ./reapply-customizations.sh`
