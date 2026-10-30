name: Update CBM Mila Data

on:
  schedule:
    # Regular checks outside the main match window.
    - cron: "12 * * * *"
    # Match days: Thursday, Friday and Saturday, 13:05–21:45 Algeria time (UTC+1).
    - cron: "5,25,45 12-20 * * 4,5,6"
    # Midweek postponed/rescheduled match window: Tuesday and Wednesday afternoons.
    - cron: "10,40 13-18 * * 2,3"
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Test a scrape without changing repository files or sending notifications"
        required: false
        default: "false"
        type: choice
        options:
          - "false"
          - "true"
      always_report:
        description: "Send a Telegram report even when no data changed (manual runs only)"
        required: false
        default: "true"
        type: choice
        options:
          - "true"
          - "false"
      accept_regression:
        description: "Allow a one-time decrease in played matches for an official league correction"
        required: false
        default: "false"
        type: choice
        options:
          - "false"
          - "true"

# Contents permission publishes the data; Pages permission requests a fresh public-site build.
permissions:
  contents: write
  pages: write

# Never run two scrapes against the same branch at the same time.
concurrency:
  group: cbm-mila-update-data
  cancel-in-progress: false

jobs:
  scrape-and-publish:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: "requirements.txt"

      - name: Install pinned Python dependencies
        run: python -m pip install -r requirements.txt

      - name: Check Python syntax
        run: python -m py_compile scraper.py scripts/validate_data.py scripts/notify_failure.py

      - name: Restore HTTP conditional-request cache
        uses: actions/cache/restore@v4
        with:
          path: .cache
          key: cbm-http-cache-${{ runner.os }}-seed
          restore-keys: |
            cbm-http-cache-${{ runner.os }}-

      - name: Snapshot the current published dataset
        run: cp data/data.json "$RUNNER_TEMP/cbm-data-before.json"

      - name: Record HTTP cache state before scraping
        run: |
          if [ -f .cache/http_cache.json ]; then
            sha256sum .cache/http_cache.json | awk '{print $1}' > "$RUNNER_TEMP/cbm-http-cache-before.sha256"
          else
            echo "none" > "$RUNNER_TEMP/cbm-http-cache-before.sha256"
          fi

      - name: Fetch, validate and queue notifications
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          ADMIN_KEY: ${{ secrets.ADMIN_KEY }}
          REGISTRY_URL: ${{ secrets.REGISTRY_URL }}
          VAPID_PRIVATE_KEY: ${{ secrets.VAPID_PRIVATE_KEY }}
          DRY_RUN: ${{ inputs.dry_run || 'false' }}
          ACCEPT_REGRESSION: ${{ inputs.accept_regression || 'false' }}
          NO_NEWS_EVERY_HOURS: ${{ vars.NO_NEWS_EVERY_HOURS || '6' }}
          FORCE_REPORT: ${{ github.event_name == 'workflow_dispatch' && inputs.always_report == 'true' }}
        run: python scraper.py --verbose --defer-notifications

      - name: Validate the final dataset against its previous version
        env:
          ACCEPT_REGRESSION: ${{ inputs.accept_regression || 'false' }}
        run: |
          set -euo pipefail
          args=()
          if [[ "${ACCEPT_REGRESSION,,}" == "true" || "${ACCEPT_REGRESSION}" == "1" ]]; then
            args+=(--accept-regression)
          fi
          python scripts/validate_data.py --previous "$RUNNER_TEMP/cbm-data-before.json" "${args[@]}"

      - name: Detect changes to the HTTP cache
        id: cache-diff
        run: |
          before="$(cat "$RUNNER_TEMP/cbm-http-cache-before.sha256" 2>/dev/null || echo none)"
          if [ -f .cache/http_cache.json ]; then
            after="$(sha256sum .cache/http_cache.json | awk '{print $1}')"
          else
            after="none"
          fi
          if [ "$after" != "none" ] && [ "$before" != "$after" ]; then
            echo "changed=true" >> "$GITHUB_OUTPUT"
          else
            echo "changed=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Save the HTTP cache when it changed
        if: success() && steps.cache-diff.outputs.changed == 'true' && inputs.dry_run != 'true'
        uses: actions/cache/save@v4
        continue-on-error: true
        with:
          path: .cache
          key: cbm-http-cache-${{ runner.os }}-${{ hashFiles('.cache/http_cache.json') }}

      - name: Commit and push dataset changes safely
        id: commit-data
        if: inputs.dry_run != 'true'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          ADMIN_KEY: ${{ secrets.ADMIN_KEY }}
          REGISTRY_URL: ${{ secrets.REGISTRY_URL }}
          VAPID_PRIVATE_KEY: ${{ secrets.VAPID_PRIVATE_KEY }}
          ACCEPT_REGRESSION: ${{ inputs.accept_regression || 'false' }}
          NO_NEWS_EVERY_HOURS: ${{ vars.NO_NEWS_EVERY_HOURS || '6' }}
          FORCE_REPORT: ${{ github.event_name == 'workflow_dispatch' && inputs.always_report == 'true' }}
        shell: bash
        run: |
          set -Eeuo pipefail
          git config user.name "cbm-bot"
          git config user.email "cbm-bot@users.noreply.github.com"
          data_changed=false

          stage_data() {
            git add -- data/data.json data/status.json
          }

          validate_data() {
            local baseline="$1"
            local args=()
            if [[ "${ACCEPT_REGRESSION,,}" == "true" || "${ACCEPT_REGRESSION}" == "1" ]]; then
              args+=(--accept-regression)
            fi
            python scripts/validate_data.py --previous "$baseline" "${args[@]}"
          }

          stage_data
          if ! git diff --cached --quiet -- data/data.json; then
            data_changed=true
          fi
          if git diff --cached --quiet; then
            echo "data_changed=false" >> "$GITHUB_OUTPUT"
            echo "No dataset/status changes to commit. Any previously queued notifications will still be checked."
            exit 0
          fi

          git commit -m "chore(data): auto-update match & standings data"
          pushed=0

          for attempt in 1 2 3; do
            echo "Push attempt ${attempt}/3"
            if git push origin "HEAD:${GITHUB_REF_NAME}"; then
              echo "Dataset commit pushed successfully."
              pushed=1
              break
            fi

            echo "Push did not succeed; fetching the latest branch before retrying."
            if ! git fetch origin "${GITHUB_REF_NAME}"; then
              sleep 4
              continue
            fi

            git show "origin/${GITHUB_REF_NAME}:data/data.json" > "$RUNNER_TEMP/cbm-data-rebase-baseline.json"
            if git rebase "origin/${GITHUB_REF_NAME}"; then
              # Do not publish a successful rebase until its combined data passes validation.
              validate_data "$RUNNER_TEMP/cbm-data-rebase-baseline.json"
              sleep 3
              continue
            fi

            # A JSON conflict is safer to resolve by scraping again from the latest published baseline.
            git rebase --abort || true
            git reset --hard "origin/${GITHUB_REF_NAME}"
            cp data/data.json "$RUNNER_TEMP/cbm-data-before.json"
            python scraper.py --verbose --defer-notifications
            validate_data "$RUNNER_TEMP/cbm-data-before.json"
            if ! cmp -s "$RUNNER_TEMP/cbm-data-before.json" data/data.json; then
              data_changed=true
            fi
            stage_data

            if git diff --cached --quiet; then
              echo "The latest remote branch already contains the equivalent dataset."
              pushed=1
              break
            fi

            git commit -m "chore(data): auto-update match & standings data"
            sleep 4
          done

          if [ "$pushed" -ne 1 ]; then
            echo "Could not push the validated dataset after three attempts." >&2
            exit 1
          fi
          echo "data_changed=${data_changed}" >> "$GITHUB_OUTPUT"

      - name: Request a GitHub Pages rebuild for changed public data
        if: success() && steps.commit-data.outputs.data_changed == 'true' && inputs.dry_run != 'true'
        continue-on-error: true
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh api --method POST "/repos/${GITHUB_REPOSITORY}/pages/builds"

      - name: Deliver queued notifications after the data is published
        if: success() && inputs.dry_run != 'true'
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          ADMIN_KEY: ${{ secrets.ADMIN_KEY }}
          REGISTRY_URL: ${{ secrets.REGISTRY_URL }}
          VAPID_PRIVATE_KEY: ${{ secrets.VAPID_PRIVATE_KEY }}
        run: python scraper.py --notify-queued --verbose

      - name: Persist notification delivery state
        if: success() && inputs.dry_run != 'true'
        shell: bash
        run: |
          set -Eeuo pipefail
          git config user.name "cbm-bot"
          git config user.email "cbm-bot@users.noreply.github.com"
          git add -- data/status.json
          if git diff --cached --quiet; then
            echo "No notification delivery-state changes to commit."
            exit 0
          fi

          git commit -m "chore(data): update notification delivery state"
          for attempt in 1 2 3 4; do
            if git push origin "HEAD:${GITHUB_REF_NAME}"; then
              echo "Notification delivery state saved."
              exit 0
            fi
            if ! git fetch origin "${GITHUB_REF_NAME}"; then
              sleep 4
              continue
            fi
            if git rebase "origin/${GITHUB_REF_NAME}"; then
              sleep 3
              continue
            fi
            git rebase --abort || true
            echo "Conflict while saving notification state; refusing to overwrite remote status.json." >&2
            exit 1
          done
          echo "Could not persist notification delivery state after four attempts." >&2
          exit 1

      - name: Alert on workflow failure
        if: failure()
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_RUN_ID: ${{ github.run_id }}
          GITHUB_SERVER_URL: ${{ github.server_url }}
        run: python scripts/notify_failure.py
