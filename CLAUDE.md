# CLAUDE.md

## Project Overview

Python job scheduler with YAML-based configuration, Tkinter GUI, and process management. Runs on Windows (primary target, including UNC network paths) with cross-platform Python support.

## Architecture

```
scheduler.py          # Main daemon — reads jobs.yaml, schedules via `schedule` lib, runs in background
scheduler_core.py     # Shared module — job CRUD, format_schedule, process control, command execution
scheduler_ctl.py      # CLI control script (start/stop/restart/status)
gui.py                # Tkinter GUI — job editor, log viewer, scheduler control
validate_jobs.py      # Cerberus schema validation for jobs.yaml
watchdog.py           # External auto-restart monitor with thrashing detection
jobs.yaml             # Job definitions (the live config)
```

**Key dependency chain**: `scheduler.py` and `gui.py` both import from `scheduler_core.py`, which imports from `validate_jobs.py`.

## Important Conventions

### Validation is defined in two places
- **`validate_jobs.py`**: Cerberus schema (`JOB_SCHEMA`) + field-relevance checks (`VALID_FIELDS_BY_UNIT`). Used by the scheduler on startup.
- **`gui.py`**: Its own `VALID_FIELDS_BY_UNIT` + `validate_job()` function for real-time GUI validation.

When adding/changing schedule fields, **both files must be updated** to stay in sync.

### Schedule field rules
Each schedule `unit` has a defined set of valid and required fields. Adding a new schedule field means updating:
1. `validate_jobs.py` — `JOB_SCHEMA`, `VALID_FIELDS_BY_UNIT`
2. `gui.py` — `VALID_FIELDS_BY_UNIT`, `validate_job()`, `JobEditorDialog` (widget + `_on_unit_change` + `_populate_fields` + `_save`)
3. `scheduler_core.py` — `format_schedule()` for display
4. `scheduler.py` — `schedule_job()` and any wrapper functions (e.g., `run_monthly_job`)

### GUI dialog layout
The `JobEditorDialog` uses a 4-column grid: `0=warning icon, 1=label, 2=input, 3=hint`. The Name and Command fields span columns 2-3 (they're wider). Schedule field inputs stay in column 2 only, with hints in column 3.

## Commands

```powershell
# Validate config
python validate_jobs.py

# Launch GUI
python gui.py

# Scheduler control
python scheduler_ctl.py start|stop|restart|status

# Run scheduler directly (foreground)
python scheduler.py
```

## Dependencies

PyYAML, schedule, cerberus, psutil — installed via `pip install -r requirements.txt` in the local venv.

## Platform Notes

- Primary environment: Windows 11, Python 3.12, runs from UNC network path
- UNC paths handled via `pushd`/`popd` wrapping in `scheduler_core.py`
- GUI uses `pythonw.exe` when available to avoid console window
