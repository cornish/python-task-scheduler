# Job Scheduler

A production-ready Python job scheduler with configuration validation, logging, and process management. Fully supports UNC network paths and cross-platform operation.

## Quick Start

### Windows (PowerShell - Recommended)

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\activate_venv.ps1

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Start scheduler
.\scheduler_ctl.ps1 start       # Background mode (daemon)
# or
.\start_scheduler.ps1           # Foreground mode (see logs)
.\start_scheduler.ps1 -bg       # Background mode
```

### Command Line (Python)

```bash
# Install dependencies
pip install -r requirements.txt

# Start scheduler
python scheduler_ctl.py start
```

### GUI (Optional)

```powershell
# Install dependencies
pip install -r requirements.txt

# Launch GUI
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
| **Python Scripts** | |
| scheduler.py | Main scheduler daemon |
| scheduler_core.py | Shared core functionality (job execution, process control) |
| scheduler_ctl.py | Command-line control script (start/stop/restart/status) |
| gui.py | Optional Tkinter GUI for management and monitoring |
| watchdog.py | Auto-restart monitor with thrashing detection |
| validate_jobs.py | YAML configuration validator |
| jobs.yaml | Job definitions |
| **PowerShell Scripts** | |
| scheduler_ctl.ps1 | PowerShell control script (wraps Python version) |
| start_scheduler.ps1 | Start scheduler with foreground/background modes |
| run_watchdog.ps1 | Run watchdog monitor |
| activate_venv.ps1 | Activate virtual environment |
| **Batch Files** | |
| start_scheduler.bat | Windows startup batch file (background mode) |

## Control Scripts

### PowerShell (Recommended for Windows)

```powershell
.\scheduler_ctl.ps1 status   # Show running status, PID, memory, CPU
.\scheduler_ctl.ps1 start    # Start scheduler in background
.\scheduler_ctl.ps1 stop     # Stop scheduler gracefully
.\scheduler_ctl.ps1 restart  # Restart scheduler
```

### Python (Cross-Platform)

```powershell
python scheduler_ctl.py status   # Show running status, PID, memory, CPU
python scheduler_ctl.py start    # Start scheduler in background
python scheduler_ctl.py stop     # Stop scheduler gracefully
python scheduler_ctl.py restart  # Restart scheduler
```

## Starting the Scheduler

### PowerShell Scripts

#### Foreground Mode (Interactive)
```powershell
.\start_scheduler.ps1
```
- Shows live logs and output
- Useful for debugging
- Press Ctrl+C to stop

#### Background Mode (Daemon)
```powershell
.\start_scheduler.ps1 background
.\start_scheduler.ps1 bg
```
- Runs hidden in background
- No console window
- Verifies PID file creation
- Returns immediately

### Using Control Script
```powershell
.\scheduler_ctl.ps1 start    # Always background mode
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

## Path Handling

The scheduler fully supports both relative and absolute paths, including UNC network paths:

### Relative Paths
Relative paths in job commands are resolved from the scheduler directory:
```yaml
command: "python scripts/backup.py"
```

### Absolute Paths
Full paths work on both local and network drives:
```yaml
command: "python C:\\tools\\backup.py"
command: "python \\\\server\\share\\scripts\\backup.py"
```

### UNC Path Support
When the scheduler runs from a UNC path (e.g., `\\server\share\scheduler`), the system automatically handles CMD.EXE limitations using `pushd`/`popd` to temporarily map network paths to drive letters.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| SCHEDULER_CONFIG | jobs.yaml | Config file path |
| SCHEDULER_LOG_LEVEL | INFO | Log level |
| SCHEDULER_TIMEOUT | 300 | Default timeout (seconds) |
| SCHEDULER_LOG_SIZE | 10 | Log max size (MB) |
| SCHEDULER_LOG_COUNT | 5 | Log backup count |

## Watchdog

The watchdog is a monitoring script that checks if the scheduler is running and restarts it if needed. It's designed to be run periodically by an external scheduler (like Windows Task Scheduler or cron).

### Manual Execution

#### PowerShell
```powershell
.\run_watchdog.ps1
```

#### Python
```powershell
python watchdog.py
```

### Automated Monitoring Setup

The watchdog is a one-shot script - it checks once and exits. For continuous monitoring, schedule it to run periodically using **Windows Task Scheduler or cron** (external to the scheduler process):

#### Windows Task Scheduler (Recommended)
1. Open Task Scheduler
2. Create a new task to run the watchdog every 5-10 minutes
3. Set trigger: "Repeat task every 5 minutes"
4. Action - Choose one:
   - **PowerShell**: 
     - Program: `powershell.exe`
     - Arguments: `-ExecutionPolicy Bypass -File "\\mcwcorp\Departments\Pathology\Users\tcornish\automation\scheduler\run_watchdog.ps1"`
   - **Python directly**:
     - Program: `pythonw.exe` (from your venv or system Python)
     - Arguments: `"\\mcwcorp\Departments\Pathology\Users\tcornish\automation\scheduler\watchdog.py"`

#### Linux/Mac (cron)
```bash
*/5 * * * * /path/to/venv/bin/python /path/to/watchdog.py
```

**Important**: The watchdog must be scheduled **externally** (not by the scheduler itself) so it can restart the scheduler if it crashes.

### Features

- Checks if scheduler is running (single check per execution)
- Auto-restarts if process has died
- Thrashing detection: 5 restarts in 15 min triggers 30 min backoff
- Logs to `logs/watchdog.log`
- Designed for external scheduling (not a continuous service)

**Note**: The watchdog performs a single check each time it runs. Schedule it externally for continuous monitoring.

## Windows Startup

### Option 1: PowerShell Script (Recommended)
1. Press Win+R, type `shell:startup`
2. Create a shortcut to `start_scheduler.ps1 -bg`
3. Right-click shortcut → Properties → Target:
   ```
   powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "\\mcwcorp\Departments\Pathology\Users\tcornish\automation\scheduler\start_scheduler.ps1" -bg
   ```

### Option 2: Batch File
1. Press Win+R, type `shell:startup`
2. Copy `start_scheduler.bat` to the startup folder
3. Edit batch file to set your Python path

### Option 3: Task Scheduler
Create a scheduled task to run `.\scheduler_ctl.ps1 start` at system startup.

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

**Scheduler won't start**: Check `.\scheduler_ctl.ps1 status` or `python scheduler_ctl.py status`. Delete stale `scheduler.pid` if needed.

**Jobs not running**: Check `logs/scheduler.log`. Validate config with `python validate_jobs.py`.

**Watchdog keeps restarting**: Check both log files for root cause of crashes.

**UNC path errors**: The scheduler now handles UNC paths automatically. If you see "UNC paths are not supported" errors, ensure you're using the latest version of `scheduler_core.py`.

**Virtual environment issues**: Use `.\activate_venv.ps1` to properly activate the venv, or ensure PowerShell execution policy is set with `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`.

## Platform Support

- **Windows**: Full support with PowerShell and batch scripts
- **Linux/Mac**: Python scripts work natively (PowerShell scripts are Windows-only)
- **UNC Paths**: Fully supported on Windows with automatic `pushd`/`popd` handling
