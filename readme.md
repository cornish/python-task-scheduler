# Job Scheduler

A production-ready Python job scheduler with configuration validation, logging, and process management.

## Quick Start

### Command Line

```powershell
pip install pyyaml schedule cerberus psutil
python scheduler_ctl.py start
```

### GUI (Optional)

```powershell
pip install pyyaml schedule cerberus psutil
python gui.py
```

The GUI provides:
- Visual job management (add, edit, delete, enable/disable)
- Live log viewer with filtering and color coding
- One-click scheduler control (start/stop/restart)
- Real-time status monitoring
- Job validation with visual indicators
- Manual job execution ("Run Now")

## Files

| File | Purpose |
| --- | --- |
| scheduler.py | Main scheduler daemon |
| scheduler_core.py | Shared core functionality (job execution, process control) |
| scheduler_ctl.py | Command-line control script (start/stop/restart/status) |
| gui.py | Optional Tkinter GUI for management and monitoring |
| watchdog.py | Auto-restart monitor with thrashing detection |
| validate_jobs.py | YAML configuration validator |
| jobs.yaml | Job definitions |
| start_scheduler.bat | Windows startup batch file |

## Control Script

```powershell
python scheduler_ctl.py status   # Show running status, PID, memory, CPU
python scheduler_ctl.py start    # Start scheduler in background
python scheduler_ctl.py stop     # Stop scheduler gracefully
python scheduler_ctl.py restart  # Restart scheduler
```

## GUI Features

Launch with `python gui.py` for a graphical interface with:

### Job Management
- **Create/Edit/Delete Jobs**: Full CRUD operations with validation
- **Enable/Disable Jobs**: Toggle jobs without deleting
- **Run Now**: Execute any job immediately for testing
- **Invalid Job Detection**: Visual indicators for jobs with configuration errors

### Monitoring
- **Live Log Viewer**: Auto-refreshing log display (updates every 2 seconds)
- **Log Filtering**: Filter by log level (ERROR, WARNING, INFO, DEBUG)
- **Color Coding**: Different colors for each log level
- **Status Display**: Shows scheduler state, PID, and last job execution

### Scheduler Control
- **Start/Stop/Restart**: One-click scheduler management
- **Status Monitoring**: Real-time scheduler status updates
- **Validation Blocking**: Prevents starting with invalid enabled jobs

### Dialog Features
- **Dynamic Validation**: Real-time field validation with visual warnings
- **Smart Hints**: Context-sensitive hints based on schedule type
- **Command Tooltips**: Hover over long commands to see full text
- **Required Field Indicators**: Red exclamation marks for missing required fields

## Job Configuration

Jobs are defined in `jobs.yaml`:

```yaml
jobs:
  - name: "daily_backup"
    command: "python scripts/backup.py"
    schedule:
      every: 1
      unit: "days"
      at: "02:00"

  - name: "hourly_check"
    command: "python scripts/check_disk.py"
    schedule:
      every: 1
      unit: "hours"
      at: ":15"

  - name: "weekly_report"
    command: "python scripts/report.py"
    schedule:
      every: 1
      unit: "weeks"
      day: "monday"
      at: "09:00"

  - name: "monthly_invoice"
    command: "python scripts/report.py"
    schedule:
      unit: "months"
      day_of_month: 1
      at: "09:00"

  - name: "init_check"
    command: "python scripts/heartbeat.py"
    schedule:
      unit: "startup"
    enabled: true  # Optional: defaults to true if omitted
```

### Required Fields

- `name`: Unique job identifier
- `command`: Shell command to execute (can include arguments)
- `schedule`: Schedule configuration (see below)

### Optional Fields

- `enabled`: Set to `false` to disable a job without deleting it (defaults to `true`)

### Schedule Types

| Unit | every | at | day | day_of_month |
| --- | --- | --- | --- | --- |
| seconds | required | - | - | - |
| minutes | required | :SS offset | - | - |
| hours | required | :MM offset | - | - |
| days | required | HH:MM | - | - |
| weeks | required | HH:MM | day name | - |
| months | - | HH:MM | - | 1-31 |
| startup | - | - | - | - |

### Time Offsets

Use offsets to stagger jobs and avoid thundering herd:

- Hours: `:15` runs at 15 minutes past each hour
- Minutes: `:30` runs at 30 seconds past each interval

### Startup Jobs

Jobs with `unit: "startup"` run once immediately when the scheduler starts. Useful for initialization tasks, health checks, or cache warming.

### Monthly Jobs

Jobs with `unit: "months"` run on a specific day of the month. The scheduler checks daily and only executes if today matches `day_of_month`.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| SCHEDULER_CONFIG | jobs.yaml | Config file path |
| SCHEDULER_LOG_LEVEL | INFO | Log level |
| SCHEDULER_TIMEOUT | 300 | Default timeout (seconds) |
| SCHEDULER_LOG_SIZE | 10 | Log max size (MB) |
| SCHEDULER_LOG_COUNT | 5 | Log backup count |

## Watchdog

```powershell
pythonw watchdog.py
```

Features:

- Monitors scheduler every 30 seconds
- Auto-restarts if process dies
- Thrashing detection: 5 restarts in 15 min triggers 30 min backoff
- Logs to `logs/watchdog.log`

## Windows Startup

1. Press Win+R, type `shell:startup`
2. Copy `start_scheduler.bat` to the startup folder
3. Edit batch file to set your Python path

## Log Rotation

Automatic rotation via RotatingFileHandler:

- Scheduler: 10MB max, 5 backups
- Watchdog: 5MB max, 3 backups
- Location: `logs/` directory

## Validation

```powershell
python validate_jobs.py
```

Also runs automatically on scheduler startup.

## Troubleshooting

**Scheduler won't start**: Check `python scheduler_ctl.py status`. Delete stale `scheduler.pid` if needed.

**Jobs not running**: Check `logs/scheduler.log`. Validate config with `python validate_jobs.py`.

**Watchdog keeps restarting**: Check both log files for root cause of crashes.
