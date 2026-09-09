# Empath Funding Monitor — TIA + MultiChoice

This GitHub Actions project monitors two official funding pages for changes:

1. **Technology Innovation Agency (TIA) — Open Calls**
   https://www.tia.org.za/category/open-calls/
2. **MultiChoice Innovation Fund**
   https://www.multichoice.com/enriching-lives/multichoice-innovation-fund/

It runs **daily** and creates a GitHub Issue when:

- TIA has a new Open Call; or
- the relevant MultiChoice Innovation Fund page content changes.

The monitor does not decide eligibility. When an alert appears, verify the official call's ownership, B-BBEE requirements, sector, funding amount/type, deadline, eligible costs and previous-government-funding rules.

## First-time setup

1. Create a GitHub repository.
2. Upload these files/folders:
   - `funding_monitor.py`
   - `requirements.txt`
   - `data/funding_seen.json`
   - `.github/workflows/funding-monitor.yml`
3. Push to your default branch.
4. Go to **Actions → Monitor TIA and MultiChoice Funding**.
5. Click **Run workflow** once.
6. The first run creates a baseline and does not alert on everything already on the pages.
7. From then on, GitHub checks daily.

## GitHub permissions

The workflow uses GitHub's built-in `GITHUB_TOKEN`. You do not need to create a personal access token.

The workflow needs:
- `contents: write` to save the seen-state file.
- `issues: write` to create alerts.

## Important MultiChoice note

The MultiChoice Innovation Fund URL is based on the page shown in the supplied screenshot. If MultiChoice changes the page URL, update the `url` value in `funding_monitor.py`.

## Daily vs weekly

The workflow currently checks daily. To check weekly instead, replace the cron line with:

```yaml
- cron: "0 6 * * 1"
```

That checks every Monday at 06:00 UTC (08:00 South Africa time).

## What it alerts you about

For TIA, it watches for new Open Call links.

For MultiChoice, it compares the relevant funding-page content and alerts when that content changes, which is useful when a page changes from "closed" to a new application window.
