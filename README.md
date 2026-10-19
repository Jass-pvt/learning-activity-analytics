# Learning Activity Tracker

A small Python project that checks your **public** Google Skills, LeetCode, and GeeksforGeeks profiles, writes dated snapshots, and records only activity that can actually be observed. It does not create dummy commits or claim that an activity happened on a date when the source only provides aggregate totals.

## Profiles configured

- Google Skills: https://www.skills.google/public_profiles/def4bf30-fead-4bf0-81b4-d1c68bcbb7bc
- LeetCode: https://leetcode.com/u/JaswanthRathore/
- GeeksforGeeks: https://www.geeksforgeeks.org/profile/jaswanthrathore

## What it can collect

- **Google Skills:** attempts to extract explicitly labelled badge names from the public profile page. Google's markup may change; if it exposes no parseable labels, the collector records an empty list rather than guessing.
- **LeetCode:** public profile stats and a limited list of recent accepted submissions from the public GraphQL endpoint. This is not a complete lifetime feed.
- **GeeksforGeeks:** tries to extract explicitly labelled aggregate counts from the profile page; if unavailable, it tries a no-auth community stats endpoint as a fallback. This fallback is third-party and may stop working. Unavailable values stay `null`.

The collector may be blocked by rate limits, bot protection, or changes to any platform. Check the Actions log when a source fails. Do not add platform cookies, passwords, or session tokens to the repository.

## Local setup (Windows PowerShell)

```powershell
cd learning-activity-tracker
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m tracker.run
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m tracker.run
```

Outputs:

- `data/latest.json` — latest successfully observed profile state
- `data/snapshots/YYYY-MM-DD.json` — dated snapshots in India Standard Time
- `data/activity-log.json` — new accepted submissions/badges or aggregate changes that were observed between successful checks
- `data/state.json` — latest run status

The first run establishes a baseline; it does **not** backfill old events. If a platform only exposes a current total, the tracker can detect a later increase but cannot prove the exact solve date or problem name.

## Publish to GitHub and enable the schedule

1. Create a **new empty repository** named `learning-activity-tracker` under your GitHub account. Do not initialize it with a README (this folder already has one).
2. From this project folder, run:

   ```bash
   git init -b main
   git add .
   git commit -m "feat: add learning activity tracker"
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/learning-activity-tracker.git
   git push -u origin main
   ```

3. On GitHub, open **Settings → Actions → General** and ensure workflows are allowed to run. The workflow has `contents: write` permission so it can commit snapshots.
4. Open **Actions → Daily learning activity snapshot → Run workflow** for a first hosted test.
5. Scheduled runs occur daily at 01:00 UTC (06:30 IST). GitHub may delay scheduled workflows during busy periods; scheduled workflows are not guaranteed to run at the exact minute.

## Contribution streak behavior

The workflow stores a dated snapshot plus the latest successful state, so a successful daily poll normally creates a tracker-data commit even if the platform metrics did not change. That commit documents a real automated observation; it is **not evidence that you personally solved a problem or earned a badge that day**. Activity events are logged separately and only when new activity can be observed. GitHub's contribution graph has its own eligibility rules; commits to the default branch of this repository generally count when the repository is not a fork and the commit email is associated with your GitHub account. Confirm the contribution graph after the first successful push. If your goal is a learning streak, use the platform activity log—not automated snapshot commits—as the source of truth.

## Troubleshooting

- If LeetCode returns HTTP 403/429, retry later; don't add private session cookies to public GitHub Actions.
- If Google Skills or GFG returns an empty field, inspect the public profile page and the run log. Page structure and third-party APIs may change.
- Snapshots preserve the previous successful source data when a later fetch fails, so a transient failure doesn't erase the last known profile state.
- Use `workflow_dispatch` to run a manual check.
