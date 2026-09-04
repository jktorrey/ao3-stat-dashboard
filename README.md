# AO3 Stats Dashboard — Windows Setup & Operations

This document covers the **Windows-side setup and operation** of the AO3 Stats Dashboard project.

The application currently supports:

- tracking AO3 works in SQLite
- collecting public AO3 stats
- importing historical snapshots
- manual snapshot entry
- work-event tracking
- AO3 publication/chapter-date backfill
- automatic chapter/completion event detection
- automatic discovery of newly published works
- Streamlit dashboard
- configurable collection interval
- daily 24-hour summary generation
- Resend email delivery
- Windows Task Scheduler integration

The long-term roadmap includes migration to a Raspberry Pi as the always-on source of truth. Until then, this README describes the Windows workflow.

---

## 1. Project Location

Current local project directory:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard
```

Open PowerShell and move into the project:

```powershell
cd C:\Users\jeann\Documents\ao3-stat-dashboard
```

---

## 2. Python Virtual Environment

Activate the virtual environment before running project commands manually:

```powershell
.\.venv\Scripts\Activate.ps1
```

The PowerShell prompt should then begin with:

```text
(.venv)
```

If PowerShell blocks activation, the user-level execution policy previously used for this project is:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Check Python:

```powershell
python --version
```

---

## 3. Install / Restore Dependencies

With the virtual environment activated:

```powershell
pip install -r requirements.txt
```

Whenever dependencies are intentionally added or changed:

```powershell
pip freeze > requirements.txt
```

---

## 4. Important Files

```text
main.py
    Administrative CLI.

database.py
    SQLite schema and database functions.

collector.py
    AO3 HTTP fetching and HTML parsing.

collection.py
    Collects current stats for all tracked works.

scheduled_collection.py
    Checks whether the configured collection interval is due,
    then runs collection and work discovery.

discovery.py
    Finds new works on AO3 and initializes them automatically.

csv_importer.py
    Historical CSV import.

dashboard_data.py
    Read/query/analytics layer for the Streamlit dashboard.

dashboard.py
    Streamlit dashboard.

daily_summary.py
    Builds the previous-24-hour text summary.

email_summary.py
    Sends the daily summary through Resend.

scheduled_daily_summary.py
    Sends the daily summary once per day when the configured
    delivery time has arrived.

ao3_stats.db
    SQLite database. This is intentionally NOT tracked by Git.
```

---

## 5. Git / Database Rule

GitHub stores **code**, not the live database.

The SQLite file:

```text
ao3_stats.db
```

is ignored by Git.

Do not add the live database to the repository.

Normal checkpoint workflow:

```powershell
git status
git add <changed-files>
git commit -m "Describe the change"
git push
```

---

## 6. Administrative CLI

Run:

```powershell
python .\main.py
```

The CLI is used for administrative and manual operations such as:

- adding/editing works
- fetching stats manually
- entering historical snapshots
- importing CSV data
- viewing snapshots
- setting the collection interval
- database cleanup
- adding/editing/deleting work events
- backfilling AO3 events
- configuring daily-summary settings
- sending a test daily-summary email

---

## 7. Manual Stats Collection

Collect current public AO3 stats for every tracked work:

```powershell
python .\collection.py
```

This:

1. fetches current public stats
2. saves one `ao3_public` snapshot per successful work
3. compares chapter counts with the previous live snapshot
4. detects newly added chapters
5. creates chapter events when appropriate
6. detects work-completion transitions
7. uses AO3 chapter/completion dates when available

A failed work does not prevent the other works from being collected.

---

## 8. AO3 Request Behavior

The collector uses public AO3 pages only.

It does **not** need an AO3 login.

The request layer retries transient failures such as:

- HTTP 408
- HTTP 429
- HTTP 5xx errors, including 525
- connection failures
- timeouts

If AO3 remains unavailable after the retry limit, that work/request is skipped and can be collected during a later cycle.

### AO3 525 Errors

AO3/Cloudflare may intermittently return:

```text
525 Server Error
```

This can happen even when the site opens normally in a browser.

Do not add AO3 credentials to work around this.

If errors are transient, allow the scheduled process to retry during a later cycle.

Useful non-saving diagnostic:

```powershell
python -c "from collector import fetch_work_stats; from pprint import pprint; pprint(fetch_work_stats('https://archiveofourown.org/works/91487606'))"
```

---

## 9. Automatic Work Discovery

Manual discovery test:

```powershell
python .\discovery.py
```

Typical no-change result:

```text
AO3 works found: 6
Already tracked: 6
New works: 0

No new works found.
```

When a new work is found, discovery:

1. identifies it by AO3 **work ID**
2. fetches current stats before writing to SQLite
3. adds the work
4. saves its first live snapshot
5. creates a work-publication event
6. retrieves chapter metadata when applicable
7. backfills historical chapter events when available

Titles are not used as identity, so renaming an AO3 work does not create a duplicate.

---

## 10. Combined Scheduled Collection Cycle

The unattended cycle is handled by:

```powershell
python .\scheduled_collection.py
```

The script itself checks whether the configured collection interval has elapsed.

When due, it:

1. collects all already-tracked works
2. checks AO3 for newly published works
3. initializes any new works
4. records the scheduled-cycle timestamp

Collection happens **before discovery** so a newly discovered work does not receive two nearly identical snapshots in the same cycle.

### Direct Combined-Cycle Test

To test collection + discovery without changing the scheduler timestamp:

```powershell
python -c "from scheduled_collection import run_scheduled_cycle; run_scheduled_cycle()"
```

---

## 11. Collection Interval

The current interval is stored in SQLite.

Configure it through:

```powershell
python .\main.py
```

and choose:

```text
Collection interval
```

The current intended collection interval is:

```text
6 hours
```

Windows Task Scheduler may check more frequently; the Python script decides whether collection is actually due.

---

## 12. Streamlit Dashboard

Start the dashboard:

```powershell
streamlit run dashboard.py
```

The project has a Streamlit configuration that binds to IPv4 loopback:

```text
127.0.0.1
```

This was required because `localhost:8501` could hang on this Windows environment while `127.0.0.1:8501` worked immediately.

Open:

```text
http://127.0.0.1:8501
```

The dashboard is read-only. Administrative writes remain in the CLI.

---

## 13. Daily Summary

Generate the previous-24-hour summary in the terminal:

```powershell
python .\daily_summary.py
```

The summary uses the same 24-hour change logic as the dashboard.

Portfolio totals appear only when every tracked work has a valid baseline for the selected period.

Works without a 24-hour baseline are reported explicitly rather than counted as zero.

Recent publication/chapter/completion events are included.

AO3 date-only events are labeled as date-only instead of pretending an exact time is known.

---

## 14. Daily Summary Settings

Configure through:

```powershell
python .\main.py
```

Choose:

```text
Daily summary settings
```

Settings stored in SQLite:

- sender email address
- recipient email address
- daily delivery time

Current sender domain:

```text
jeannektorrey.com
```

Resend is used for outbound delivery.

Gmail is only the recipient.

---

## 15. Resend Configuration

The project uses **Resend**, not Gmail SMTP.

The sending domain:

```text
jeannektorrey.com
```

has been verified in Resend.

The Resend API token must never be committed to Git or stored in SQLite.

### Install Keyring Support

If restoring the environment:

```powershell
pip install keyring
pip freeze > requirements.txt
```

### Store the Resend API Token in Windows Credential Locker

Run:

```powershell
python -m keyring set ao3-stat-dashboard resend_api_key
```

When prompted, paste the Resend API token.

Do not paste the token into source code.

### Verify That a Token Exists Without Printing It

```powershell
python -c "import keyring; print('stored' if keyring.get_password('ao3-stat-dashboard','resend_api_key') else 'missing')"
```

Expected:

```text
stored
```

### Temporary Development Environment Variable

For temporary/manual development, the program can also use:

```powershell
$env:RESEND_API_KEY = "re_your_token"
```

This applies only to the current PowerShell session.

The Windows Credential Locker is preferred for unattended operation.

---

## 16. Test Daily Summary Email

Run:

```powershell
python .\main.py
```

Choose:

```text
Send test daily summary
```

A successful result should report:

```text
Email sent successfully.
Recipient: ...
Subject: AO3 Daily Stats Summary — ...
```

The email should arrive in the configured Gmail inbox from the configured `@jeannektorrey.com` sender.

A manual test email does **not** update the scheduled-delivery timestamp.

---

## 17. Scheduled Daily Summary

The scheduler script is:

```powershell
python .\scheduled_daily_summary.py
```

It checks:

1. whether a recipient is configured
2. whether a delivery time is configured
3. whether today's delivery time has arrived
4. whether today's summary has already been sent

If the email succeeds, the script records the successful send time.

If sending fails, the last-send timestamp is **not** updated, allowing a later scheduled check to retry.

---

# WINDOWS TASK SCHEDULER

The project uses Windows Task Scheduler only as a periodic trigger.

The Python scripts themselves decide whether work is due.

---

## 18. AO3 Stats Collector Scheduled Task

Task name:

```text
AO3 Stats Collector
```

The task should run the virtual-environment Python executable:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard\.venv\Scripts\python.exe
```

with this script:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard\scheduled_collection.py
```

and this working directory:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard
```

### Intended Trigger

The Windows trigger can run every:

```text
15 minutes
```

The Python script checks whether the configured six-hour interval is actually due.

### Important Behavior

The task should:

- run only when Windows is awake
- not wake the laptop
- allow execution on battery if desired
- use `IgnoreNew` / avoid overlapping runs
- start when available if a scheduled check was missed

---

## 19. Disable / Enable the AO3 Collector

The collector has previously been disabled during work use.

Disable:

```powershell
Disable-ScheduledTask -TaskName "AO3 Stats Collector"
```

Enable:

```powershell
Enable-ScheduledTask -TaskName "AO3 Stats Collector"
```

Check state:

```powershell
Get-ScheduledTask -TaskName "AO3 Stats Collector"
```

Check last/next-run information:

```powershell
Get-ScheduledTaskInfo -TaskName "AO3 Stats Collector"
```

Manual collection remains available even when the scheduled task is disabled.

---

## 20. Create the Daily Summary Scheduled Task

Recommended task name:

```text
AO3 Daily Summary
```

The task should run:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard\.venv\Scripts\python.exe
```

with argument:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard\scheduled_daily_summary.py
```

and working directory:

```text
C:\Users\jeann\Documents\ao3-stat-dashboard
```

### Recommended Trigger

Run the task every:

```text
15 minutes
```

The Python script enforces the actual configured delivery time and guarantees at most one successful send per local calendar day.

This design is intentional:

```text
Windows:
    "Check every 15 minutes."

Python:
    "Is the configured delivery time here yet?"
    "Was today's message already sent?"
```

This means the delivery time can be changed inside the application without recreating the Windows task.

### Recommended Task Behavior

Use settings similar to the collector:

- run under the same Windows user account that owns the Credential Locker entry
- do not wake the laptop
- allow Start When Available
- prevent overlapping instances
- retry naturally at the next 15-minute check if Resend/network delivery fails

Because the API token is stored in Windows Credential Locker, the task should run under the same Windows user account used to store it.

---

## 21. Test a Scheduled Task Manually

Run the task from PowerShell:

```powershell
Start-ScheduledTask -TaskName "AO3 Stats Collector"
```

or:

```powershell
Start-ScheduledTask -TaskName "AO3 Daily Summary"
```

Then inspect:

```powershell
Get-ScheduledTaskInfo -TaskName "AO3 Stats Collector"
```

or:

```powershell
Get-ScheduledTaskInfo -TaskName "AO3 Daily Summary"
```

You can also run the underlying Python scripts directly for easier debugging:

```powershell
python .\scheduled_collection.py
```

```powershell
python .\scheduled_daily_summary.py
```

---

## 22. Current Workweek Preference

The AO3 collector may intentionally remain disabled when the laptop is being used for work.

This is not a problem.

Manual commands continue to work, and the scheduled tasks can be re-enabled later.

The eventual Raspberry Pi migration is intended to eliminate this conflict entirely.

---

# TROUBLESHOOTING

## 23. `localhost:8501` Hangs

Use:

```text
http://127.0.0.1:8501
```

The project contains a Streamlit configuration that binds the server to IPv4 loopback.

---

## 24. AO3 Returns 525

Do not add AO3 credentials.

Allow the retry/backoff logic to handle transient failures.

Useful diagnostic:

```powershell
curl.exe -sS -o NUL -w "HTTP %{http_code}`n" "https://archiveofourown.org/works/91487606?view_adult=true"
```

Python diagnostic:

```powershell
python -c "from collector import fetch_work_stats; from pprint import pprint; pprint(fetch_work_stats('https://archiveofourown.org/works/91487606'))"
```

If a scheduled pull fails, the next scheduled cycle can collect again later.

---

## 25. Resend Says the API Key Is Missing

Verify Credential Locker:

```powershell
python -c "import keyring; print('stored' if keyring.get_password('ao3-stat-dashboard','resend_api_key') else 'missing')"
```

If missing:

```powershell
python -m keyring set ao3-stat-dashboard resend_api_key
```

---

## 26. Resend Says the Sender Is Not Configured

Run:

```powershell
python .\main.py
```

Choose:

```text
Daily summary settings
```

Enter the verified `@jeannektorrey.com` sender address.

---

## 27. Scheduled Email Does Not Send

First run manually:

```powershell
python .\scheduled_daily_summary.py
```

Possible expected messages include:

```text
Today's delivery time has not arrived yet.
```

```text
Today's daily summary has already been sent.
```

or:

```text
Daily summary is due.
```

If it says the email is due but delivery fails, check the Resend token, sender configuration, internet connectivity, and Resend account status.

---

## 28. Scheduled Collector Does Not Run

Check task state:

```powershell
Get-ScheduledTask -TaskName "AO3 Stats Collector"
```

Check details:

```powershell
Get-ScheduledTaskInfo -TaskName "AO3 Stats Collector"
```

Make sure the task has not intentionally been disabled.

Then test the Python script itself:

```powershell
python .\scheduled_collection.py
```

---

# BACKUP / FUTURE MIGRATION

## 29. SQLite Backup Rule

Do not live-sync an actively written SQLite database through Git, OneDrive, Dropbox, or similar file-sync tools.

For backup, make a **copy** of the database and sync/archive the copy.

Conceptually:

```text
LIVE
ao3_stats.db

BACKUPS
ao3_stats_YYYY-MM-DD.db
```

---

## 30. Raspberry Pi Roadmap

The eventual target architecture is:

```text
                  AO3
                   |
                   v
             Raspberry Pi
        +----------------------+
        | collector / scheduler|
        | SQLite database      |
        | Streamlit dashboard  |
        | daily Resend email   |
        | new-work discovery   |
        +----------------------+
             ^            ^
             |            |
          laptop        desktop
             browser access
```

The Raspberry Pi will eventually become the always-on single source of truth.

GitHub remains the code source.

The live SQLite database remains outside Git.

Laptop and desktop will access the same Pi-hosted dashboard/data instead of maintaining separate live SQLite databases.

Until that migration happens, the Windows setup in this README is the operational environment.
