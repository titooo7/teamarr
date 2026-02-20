# Teamarr

Dynamic EPG Generator for Sports Channels

> **This is a fork of [Pharaoh-Labs/teamarr](https://github.com/Pharaoh-Labs/teamarr) with additional features and enhancements.**

## What's Different in This Fork

### New Features

#### Linear EPG Discovery
Monitor linear TV channels from external XMLTV sources to automatically discover sports events and create channels. This feature:
- Fetches EPG data from XMLTV sources (supports GZIP compression)
- Performs fuzzy matching against official event listings
- Creates virtual streams that map to actual IPTV channels via tvg_id
- Enables event-based channels from 24/7 sports networks

**Configuration:**
- **TVG ID**: Use the tvg-id from your IPTV provider's M3U (NOT the Dispatcharr M3U)
- **XMLTV URL**: External EPG source URL
- **XMLTV Channel ID**: Optional, if different from TVG ID
- **Display Name**: Friendly name for the channel

Access via **Settings > Linear EPG Discovery** in the UI.

#### Additional Leagues
- **Euroleague Basketball** - European top-tier basketball competition
- **ACB (Liga Endesa)** - Spanish basketball league

### UI Enhancements
- **Edit & Clone buttons** for Linear EPG monitors
- **PUT endpoint** for updating existing Linear EPG monitors

### Bug Fixes & Improvements
- Fixed tvg_id type mismatch (int vs string normalization) in Linear EPG discovery
- Added TEAM_ALIASES support to Linear EPG fuzzy matcher
- Added team aliases: PAOK (PAOK Salonika), Celta (Celta Vigo), Stuttgart (VfB Stuttgart)

## Quick Start

```yaml
services:
  teamarr:
    image: ghcr.io/pharaoh-labs/teamarr:latest
    container_name: teamarr
    restart: unless-stopped
    ports:
      - 9195:9195
    volumes:
      - ./data:/app/data
    environment:
      - TZ=America/Detroit
```

```bash
docker compose up -d
```

## Upgrading from Legacy (1.x)

**There is no automatic migration path from legacy 1.x releases** due to significant architectural changes.

If you're upgrading from 1.x, you have two options:

1. **Start Fresh** - Archive your old database and begin with a clean setup. The app will detect your legacy database and guide you through the process, including downloading a backup of your data.

2. **Continue Using 1.x** - If you're not ready to migrate, use the archived image:
   ```yaml
   image: ghcr.io/pharaoh-labs/teamarr:1.4.9-archive
   ```
   Note: 1.x will continue to function but will not receive future updates.

## Image Tags

| Tag | Description |
|-----|-------------|
| `latest` | Stable release |
| `dev` | Development builds |
| `1.4.9-archive` | Final 1.x release (no longer maintained) |

## Documentation

**User Guide**: https://teamarr-v2.jesmann.com/

**Upstream Repository**: https://github.com/Pharaoh-Labs/teamarr

**Fork Repository**: https://github.com/titooo7/teamarr

Formal documentation coming soon.

## License

MIT
