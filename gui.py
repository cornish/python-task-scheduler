#!/usr/bin/env python3
"""
Scheduler GUI (gui.py)

Optional Tkinter graphical interface for the job scheduler.
Completely optional - scheduler works without this.

Usage:
    python gui.py
    pythonw gui.py  (Windows, no console)
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path
import yaml

# Import shared functionality
from scheduler_core import (
    load_jobs, save_jobs, format_schedule, update_job_enabled,
    run_command, get_pid, is_running, get_process_info,
    start_scheduler, stop_scheduler, restart_scheduler,
    read_log_tail, get_log_file_path, BASE_DIR, HAS_PSUTIL, CONFIG_FILE
)

# Alias for clarity
JOBS_FILE = Path(CONFIG_FILE)

# =============================================================================
# Job Validation
# =============================================================================

# Define which fields are valid for each schedule unit
VALID_FIELDS_BY_UNIT = {
    "seconds": {"every", "unit"},
    "minutes": {"every", "unit", "at"},
    "hours": {"every", "unit", "at"},
    "days": {"every", "unit", "at"},
    "weeks": {"every", "unit", "at", "day"},
    "months": {"unit", "at", "day_of_month"},
    "startup": {"unit"},
}

# Define which fields are required for each schedule unit
REQUIRED_FIELDS_BY_UNIT = {
    "seconds": {"every"},
    "minutes": {"every"},
    "hours": {"every"},
    "days": {"every"},
    "weeks": {"every"},
    "months": set(),  # day_of_month defaults to 1
    "startup": set(),
}

VALID_UNITS = ["seconds", "minutes", "hours", "days", "weeks", "months", "startup"]
VALID_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def validate_job(job):
    """
    Validate a single job configuration.
    
    Args:
        job: Job dictionary
        
    Returns:
        list: List of error messages (empty if valid)
    """
    errors = []
    name = job.get("name", "")
    
    # Basic required fields
    if not name:
        errors.append("Name is required")
    
    if not job.get("command"):
        errors.append("Command is required")
    
    schedule = job.get("schedule")
    if not schedule:
        errors.append("Schedule is required")
        return errors
    
    if not isinstance(schedule, dict):
        errors.append("Schedule must be a dictionary")
        return errors
    
    unit = schedule.get("unit")
    if not unit:
        errors.append("Schedule unit is required")
        return errors
    
    if unit not in VALID_UNITS:
        errors.append(f"Invalid unit '{unit}' (valid: {', '.join(VALID_UNITS)})")
        return errors
    
    # Check for irrelevant fields
    valid_fields = VALID_FIELDS_BY_UNIT.get(unit, set())
    for field in schedule:
        if field not in valid_fields:
            errors.append(f"Field '{field}' is not used for '{unit}' schedules")
    
    # Check for missing required fields
    required_fields = REQUIRED_FIELDS_BY_UNIT.get(unit, set())
    for field in required_fields:
        if field not in schedule:
            errors.append(f"Field '{field}' is required for '{unit}' schedules")
    
    # Validate 'every' if present
    if "every" in schedule:
        every = schedule["every"]
        if not isinstance(every, int) or every < 1:
            errors.append("'every' must be a positive integer")
    
    # Validate 'at' format if present
    if "at" in schedule:
        at = schedule["at"]
        if not isinstance(at, str):
            errors.append("'at' must be a string")
        else:
            import re
            if not re.match(r'^(\d{2}:\d{2}|:\d{2})$', at):
                errors.append(f"Invalid 'at' format '{at}' (use HH:MM or :MM)")
    
    # Validate 'day' for weekly
    if "day" in schedule:
        day = schedule["day"]
        if day not in VALID_DAYS:
            errors.append(f"Invalid day '{day}' (valid: {', '.join(VALID_DAYS)})")
    
    # Validate 'day_of_month' for monthly
    if "day_of_month" in schedule:
        dom = schedule["day_of_month"]
        if not isinstance(dom, int) or not 1 <= dom <= 31:
            errors.append("'day_of_month' must be an integer 1-31")
    
    return errors


def load_jobs_raw():
    """
    Load jobs from YAML without validation (for GUI display).
    
    Returns:
        tuple: (jobs_list, yaml_error_message or None)
    """
    if not JOBS_FILE.exists():
        return [], None
    
    try:
        with open(JOBS_FILE, 'r') as f:
            data = yaml.safe_load(f)
        
        if data is None:
            return [], None
        
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            return [], "jobs.yaml 'jobs' must be a list"
        
        return jobs, None
    except yaml.YAMLError as e:
        return [], f"YAML syntax error: {e}"
    except Exception as e:
        return [], str(e)


class JobEditorDialog:
    """Dialog for creating/editing jobs."""
    
    UNITS = ["seconds", "minutes", "hours", "days", "weeks", "months", "startup"]
    DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    def __init__(self, parent, job=None):
        """
        Create job editor dialog.
        
        Args:
            parent: Parent window
            job: Existing job dict to edit, or None for new job
        """
        self.result = None
        self.job = job or {}
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Job" if job else "New Job")
        self.dialog.geometry("480x380")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
        self._populate_fields()
        
        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        self.dialog.wait_window()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        main = ttk.Frame(self.dialog, padding="15")
        main.pack(fill="both", expand=True)
        
        # Column layout: 0=label, 1=input, 2=warning (fixed width), 3=hint
        row = 0
        
        # Name
        ttk.Label(main, text="Name:").grid(row=row, column=0, sticky="w", pady=3)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main, textvariable=self.name_var, width=25)
        self.name_entry.grid(row=row, column=1, sticky="w", pady=3)
        self.name_warn = tk.Label(main, text="❗", fg="red", font=('TkDefaultFont', 10), width=2)
        self.name_warn.grid(row=row, column=2, sticky="w", padx=(4, 0))
        self.name_var.trace_add("write", lambda *_: self._update_warnings())
        row += 1
        
        # Command
        ttk.Label(main, text="Command:").grid(row=row, column=0, sticky="w", pady=3)
        self.command_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.command_var, width=25).grid(row=row, column=1, sticky="w", pady=3)
        self.command_warn = tk.Label(main, text="❗", fg="red", font=('TkDefaultFont', 10), width=2)
        self.command_warn.grid(row=row, column=2, sticky="w", padx=(4, 0))
        self.command_var.trace_add("write", lambda *_: self._update_warnings())
        row += 1
        
        # Enabled
        self.enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main, text="Enabled", variable=self.enabled_var).grid(row=row, column=1, sticky="w", pady=3)
        row += 1
        
        # Separator
        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=4, sticky="ew", pady=10)
        row += 1
        
        # Schedule section
        ttk.Label(main, text="Schedule", font=('TkDefaultFont', 9, 'bold')).grid(row=row, column=0, columnspan=4, sticky="w")
        row += 1
        
        # Unit
        ttk.Label(main, text="Unit:").grid(row=row, column=0, sticky="w", pady=3)
        self.unit_var = tk.StringVar(value="minutes")
        self.unit_combo = ttk.Combobox(main, textvariable=self.unit_var, values=self.UNITS, state="readonly", width=12)
        self.unit_combo.grid(row=row, column=1, sticky="w", pady=3)
        self.unit_combo.bind("<<ComboboxSelected>>", self._on_unit_change)
        row += 1
        
        # Every (interval)
        ttk.Label(main, text="Every:").grid(row=row, column=0, sticky="w", pady=3)
        self.every_var = tk.StringVar(value="1")
        self.every_entry = ttk.Entry(main, textvariable=self.every_var, width=8)
        self.every_entry.grid(row=row, column=1, sticky="w", pady=3)
        self.every_warn = tk.Label(main, text="❗", fg="red", font=('TkDefaultFont', 10), width=2)
        self.every_warn.grid(row=row, column=2, sticky="w", padx=(4, 0))
        self.every_hint = ttk.Label(main, text="(interval)")
        self.every_hint.grid(row=row, column=3, sticky="w", padx=(4, 0))
        self.every_var.trace_add("write", lambda *_: self._update_warnings())
        row += 1
        
        # At (time)
        ttk.Label(main, text="At:").grid(row=row, column=0, sticky="w", pady=3)
        self.at_var = tk.StringVar()
        self.at_entry = ttk.Entry(main, textvariable=self.at_var, width=8)
        self.at_entry.grid(row=row, column=1, sticky="w", pady=3)
        self.at_warn = tk.Label(main, text="❗", fg="red", font=('TkDefaultFont', 10), width=2)
        self.at_warn.grid(row=row, column=2, sticky="w", padx=(4, 0))
        self.at_hint = ttk.Label(main, text="(time/offset)")
        self.at_hint.grid(row=row, column=3, sticky="w", padx=(4, 0))
        self.at_var.trace_add("write", lambda *_: self._update_warnings())
        row += 1
        
        # Day (for weekly)
        ttk.Label(main, text="Day:").grid(row=row, column=0, sticky="w", pady=3)
        self.day_var = tk.StringVar()
        self.day_combo = ttk.Combobox(main, textvariable=self.day_var, values=[""] + self.DAYS, state="readonly", width=12)
        self.day_combo.grid(row=row, column=1, sticky="w", pady=3)
        self.day_warn = tk.Label(main, text="❗", fg="red", font=('TkDefaultFont', 10), width=2)
        self.day_warn.grid(row=row, column=2, sticky="w", padx=(4, 0))
        self.day_hint = ttk.Label(main, text="(for weekly)")
        self.day_hint.grid(row=row, column=3, sticky="w", padx=(4, 0))
        self.day_combo.bind("<<ComboboxSelected>>", lambda e: self._update_warnings())
        row += 1
        
        # Day of month (for monthly)
        ttk.Label(main, text="Day of Month:").grid(row=row, column=0, sticky="w", pady=3)
        self.dom_var = tk.StringVar()
        self.dom_entry = ttk.Entry(main, textvariable=self.dom_var, width=8)
        self.dom_entry.grid(row=row, column=1, sticky="w", pady=3)
        # Placeholder label to maintain column width
        tk.Label(main, text="", width=2).grid(row=row, column=2, sticky="w", padx=(4, 0))
        self.dom_hint = ttk.Label(main, text="(1-31, default: 1)")
        self.dom_hint.grid(row=row, column=3, sticky="w", padx=(4, 0))
        row += 1
        
        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=4, pady=(20, 0))
        
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side="left", padx=5)
        
        # Initial state update
        self._on_unit_change()
    
    def _on_unit_change(self, event=None):
        """Update field states based on selected unit."""
        unit = self.unit_var.get()
        
        # Startup: disable most fields
        if unit == "startup":
            self.every_entry.configure(state="disabled")
            self.at_entry.configure(state="disabled")
            self.day_combo.configure(state="disabled")
            self.dom_entry.configure(state="disabled")
            self.every_hint.configure(text="")
            self.at_hint.configure(text="")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="")
        elif unit == "months":
            self.every_entry.configure(state="disabled")
            self.at_entry.configure(state="normal")
            self.day_combo.configure(state="disabled")
            self.dom_entry.configure(state="normal")
            self.every_hint.configure(text="")
            self.at_hint.configure(text="(HH:MM)")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="(1-31, or last day if >)")
        elif unit == "weeks":
            self.every_entry.configure(state="normal")
            self.at_entry.configure(state="normal")
            self.day_combo.configure(state="readonly")
            self.dom_entry.configure(state="disabled")
            self.every_hint.configure(text="(interval)")
            self.at_hint.configure(text="(HH:MM)")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="")
        elif unit == "days":
            self.every_entry.configure(state="normal")
            self.at_entry.configure(state="normal")
            self.day_combo.configure(state="disabled")
            self.dom_entry.configure(state="disabled")
            self.every_hint.configure(text="(interval)")
            self.at_hint.configure(text="(HH:MM)")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="")
        elif unit == "hours":
            self.every_entry.configure(state="normal")
            self.at_entry.configure(state="normal")
            self.day_combo.configure(state="disabled")
            self.dom_entry.configure(state="disabled")
            self.every_hint.configure(text="(interval)")
            self.at_hint.configure(text="(:MM offset, optional)")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="")
        elif unit == "minutes":
            self.every_entry.configure(state="normal")
            self.at_entry.configure(state="normal")
            self.day_combo.configure(state="disabled")
            self.dom_entry.configure(state="disabled")
            self.every_hint.configure(text="(interval)")
            self.at_hint.configure(text="(:SS offset, optional)")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="")
        elif unit == "seconds":
            self.every_entry.configure(state="normal")
            self.at_entry.configure(state="disabled")
            self.day_combo.configure(state="disabled")
            self.dom_entry.configure(state="disabled")
            self.every_hint.configure(text="(interval)")
            self.at_hint.configure(text="")
            self.day_hint.configure(text="")
            self.dom_hint.configure(text="")
        
        # Update warning indicators
        self._update_warnings()
    
    def _update_warnings(self):
        """Show/hide warning indicators for empty required fields."""
        unit = self.unit_var.get()
        
        # Define which fields are required for each unit
        requires_every = unit in ("seconds", "minutes", "hours", "days", "weeks")
        requires_at = unit in ("days", "weeks", "months")
        requires_day = unit == "weeks"
        
        # Name and Command are always required (show/hide by changing text)
        self.name_warn.configure(text="" if self.name_var.get().strip() else "❗")
        self.command_warn.configure(text="" if self.command_var.get().strip() else "❗")
        
        # Every - required for most interval-based schedules
        if requires_every and not self.every_var.get().strip():
            self.every_warn.configure(text="❗")
        else:
            self.every_warn.configure(text="")
        
        # At - required for daily, weekly, monthly
        if requires_at and not self.at_var.get().strip():
            self.at_warn.configure(text="❗")
        else:
            self.at_warn.configure(text="")
        
        # Day - required for weekly
        if requires_day and not self.day_var.get().strip():
            self.day_warn.configure(text="❗")
        else:
            self.day_warn.configure(text="")
    
    def _populate_fields(self):
        """Populate fields from existing job."""
        if not self.job:
            return
        
        self.name_var.set(self.job.get("name", ""))
        self.command_var.set(self.job.get("command", ""))
        self.enabled_var.set(self.job.get("enabled", True))
        
        sched = self.job.get("schedule", {})
        self.unit_var.set(sched.get("unit", "minutes"))
        self.every_var.set(str(sched.get("every", 1)))
        self.at_var.set(sched.get("at", ""))
        self.day_var.set(sched.get("day", ""))
        self.dom_var.set(str(sched.get("day_of_month", "")) if sched.get("day_of_month") else "")
        
        self._on_unit_change()
    
    def _save(self):
        """Validate and save job."""
        name = self.name_var.get().strip()
        command = self.command_var.get().strip()
        unit = self.unit_var.get()
        
        # Build job dict first
        job = {
            "name": name,
            "command": command,
            "enabled": self.enabled_var.get(),
            "schedule": {
                "unit": unit
            }
        }
        
        # Add schedule fields based on unit (only add non-empty values)
        if unit not in ("startup", "months"):
            every_str = self.every_var.get().strip()
            if every_str:
                try:
                    job["schedule"]["every"] = int(every_str)
                except ValueError:
                    pass  # Will be caught by validation
        
        at = self.at_var.get().strip()
        if at:
            job["schedule"]["at"] = at
        
        if unit == "weeks":
            day = self.day_var.get()
            if day:
                job["schedule"]["day"] = day
        
        if unit == "months":
            dom_str = self.dom_var.get().strip()
            if dom_str:
                try:
                    job["schedule"]["day_of_month"] = int(dom_str)
                except ValueError:
                    pass  # Will be caught by validation
        
        # Validate the job
        errors = validate_job(job)
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors), parent=self.dialog)
            return
        
        self.result = job
        self.dialog.destroy()


class SchedulerGUI:
    """Main GUI application class."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Job Scheduler")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Track running state
        self.log_update_running = False
        
        # Track invalid jobs
        self.invalid_jobs = {}  # name -> list of errors
        self.has_enabled_invalid = False  # True if any enabled job is invalid
        
        self._create_widgets()
        self._refresh_all()
        
        # Start log auto-refresh
        self._start_log_refresh()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame with padding
        main = ttk.Frame(self.root, padding="10")
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # === Top: Status and Controls ===
        top_frame = ttk.Frame(main)
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Status indicator
        self.status_var = tk.StringVar(value="Unknown")
        self.status_label = ttk.Label(top_frame, textvariable=self.status_var,
                                       font=('TkDefaultFont', 10, 'bold'))
        self.status_label.grid(row=0, column=0, sticky="w")
        
        # Control buttons
        btn_frame = ttk.Frame(top_frame)
        btn_frame.grid(row=0, column=1, sticky="e")
        
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self._start)
        self.start_btn.grid(row=0, column=0, padx=2)
        
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self._stop)
        self.stop_btn.grid(row=0, column=1, padx=2)
        
        self.restart_btn = ttk.Button(btn_frame, text="Restart", command=self._restart)
        self.restart_btn.grid(row=0, column=2, padx=2)
        
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_all).grid(row=0, column=3, padx=(10, 0))
        
        top_frame.columnconfigure(1, weight=1)
        
        # === Middle: Job List ===
        job_frame = ttk.LabelFrame(main, text="Jobs", padding="5")
        job_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Treeview for jobs
        columns = ("name", "schedule", "enabled", "command")
        self.job_tree = ttk.Treeview(job_frame, columns=columns, show="headings", height=8)
        
        self.job_tree.heading("name", text="Name")
        self.job_tree.heading("schedule", text="Schedule")
        self.job_tree.heading("enabled", text="Enabled")
        self.job_tree.heading("command", text="Command")
        
        self.job_tree.column("name", width=150)
        self.job_tree.column("schedule", width=200)
        self.job_tree.column("enabled", width=70, anchor="center")
        self.job_tree.column("command", width=250)
        
        # Configure tags for job states
        self.job_tree.tag_configure("invalid", foreground="#CC0000")  # Red for invalid
        self.job_tree.tag_configure("disabled", foreground="#888888")  # Gray for disabled
        self.job_tree.tag_configure("invalid_disabled", foreground="#CC6666")  # Light red for invalid+disabled
        
        self.job_tree.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbar for job list
        job_scroll = ttk.Scrollbar(job_frame, orient="vertical", command=self.job_tree.yview)
        job_scroll.grid(row=0, column=1, sticky="ns")
        self.job_tree.configure(yscrollcommand=job_scroll.set)
        
        job_frame.columnconfigure(0, weight=1)
        job_frame.rowconfigure(0, weight=1)
        
        # Job action buttons
        job_btn_frame = ttk.Frame(job_frame)
        job_btn_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        
        ttk.Button(job_btn_frame, text="Add", command=self._add_job).grid(row=0, column=0, padx=2)
        self.edit_btn = ttk.Button(job_btn_frame, text="Edit", command=self._edit_job, state="disabled")
        self.edit_btn.grid(row=0, column=1, padx=2)
        self.delete_btn = ttk.Button(job_btn_frame, text="Delete", command=self._delete_job, state="disabled")
        self.delete_btn.grid(row=0, column=2, padx=2)
        ttk.Separator(job_btn_frame, orient="vertical").grid(row=0, column=3, sticky="ns", padx=8)
        self.run_btn = ttk.Button(job_btn_frame, text="Run Now", command=self._run_job, state="disabled")
        self.run_btn.grid(row=0, column=4, padx=2)
        self.enable_btn = ttk.Button(job_btn_frame, text="Enable", command=lambda: self._toggle_enabled(True), state="disabled")
        self.enable_btn.grid(row=0, column=5, padx=2)
        self.disable_btn = ttk.Button(job_btn_frame, text="Disable", command=lambda: self._toggle_enabled(False), state="disabled")
        self.disable_btn.grid(row=0, column=6, padx=2)
        
        # Double-click to edit
        self.job_tree.bind("<Double-1>", lambda e: self._edit_job())
        
        # Update button states on selection change
        self.job_tree.bind("<<TreeviewSelect>>", self._on_job_selection)
        
        # Show command tooltip on hover
        self.job_tree.bind("<Motion>", self._show_command_tooltip)
        self.job_tree.bind("<Leave>", self._hide_command_tooltip)
        
        # Create tooltip label (initially hidden)
        self.tooltip = None
        
        # === Bottom: Log Viewer ===
        log_frame = ttk.LabelFrame(main, text="Log Output", padding="5")
        log_frame.grid(row=2, column=0, sticky="nsew")
        
        self.log_text = tk.Text(log_frame, height=10, wrap="none", font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        # Configure color tags for log levels
        self.log_text.tag_configure("DEBUG", foreground="#888888")
        self.log_text.tag_configure("INFO", foreground="#0066CC")  # Blue for visibility
        self.log_text.tag_configure("WARNING", foreground="#CC6600", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("ERROR", foreground="#CC0000", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("CRITICAL", foreground="#FFFFFF", background="#CC0000", font=('Consolas', 9, 'bold'))
        
        # Scrollbars for log
        log_yscroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_yscroll.grid(row=0, column=1, sticky="ns")
        log_xscroll = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log_text.xview)
        log_xscroll.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(yscrollcommand=log_yscroll.set, xscrollcommand=log_xscroll.set)
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Log controls
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_btn_frame, text="Auto-scroll", variable=self.auto_scroll_var).grid(row=0, column=0)
        ttk.Button(log_btn_frame, text="Clear", command=self._clear_log).grid(row=0, column=1, padx=(10, 0))
        ttk.Button(log_btn_frame, text="Open Log File", command=self._open_log_file).grid(row=0, column=2, padx=2)
        
        # Log filter controls
        ttk.Separator(log_btn_frame, orient="vertical").grid(row=0, column=3, sticky="ns", padx=10)
        ttk.Label(log_btn_frame, text="Filter:").grid(row=0, column=4, padx=(0, 5))
        
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(log_btn_frame, textvariable=self.filter_var, width=20)
        self.filter_entry.grid(row=0, column=5, padx=2)
        self.filter_entry.bind("<Return>", lambda e: self._apply_log_filter())
        
        ttk.Label(log_btn_frame, text="Level:").grid(row=0, column=6, padx=(10, 5))
        self.level_var = tk.StringVar(value="ALL")
        level_combo = ttk.Combobox(log_btn_frame, textvariable=self.level_var, 
                                    values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                                    state="readonly", width=10)
        level_combo.grid(row=0, column=7, padx=2)
        level_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_log_filter())
        
        # Configure grid weights for main frame
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)  # Jobs
        main.rowconfigure(2, weight=2)  # Log (more space)
    
    def _refresh_all(self):
        """Refresh status and job list."""
        self._update_status()
        self._load_jobs()
    
    def _update_status(self):
        """Update scheduler status display."""
        pid = get_pid()
        
        if pid and is_running(pid):
            info = get_process_info(pid)
            if info:
                self.status_var.set(f"● RUNNING (PID: {pid}, Mem: {info['memory_mb']}MB)")
            else:
                self.status_var.set(f"● RUNNING (PID: {pid})")
            self.status_label.configure(foreground="green")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.restart_btn.configure(state="normal")
        else:
            self.status_var.set("○ STOPPED")
            self.status_label.configure(foreground="red")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.restart_btn.configure(state="disabled")
        
        # Disable Start/Restart if there are enabled invalid jobs
        if self.has_enabled_invalid:
            self.start_btn.configure(state="disabled")
            self.restart_btn.configure(state="disabled")
    
    def _load_jobs(self):
        """Load and display jobs from config, validating each one."""
        # Clear existing
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)
        
        # Reset invalid job tracking
        self.invalid_jobs = {}
        self.has_enabled_invalid = False
        
        # Load jobs without strict validation
        jobs, yaml_error = load_jobs_raw()
        
        if yaml_error:
            messagebox.showerror("YAML Error", f"Failed to parse jobs.yaml:\n{yaml_error}")
            return
        
        for job in jobs:
            name = job.get("name", "(no name)")
            schedule = format_schedule(job)
            enabled = job.get("enabled", True)
            enabled_str = "Yes" if enabled else "No"
            command = job.get("command", "")
            
            # Validate the job
            errors = validate_job(job)
            
            # Determine tag based on validity and enabled state
            tag = ""
            if errors:
                self.invalid_jobs[name] = errors
                if enabled:
                    self.has_enabled_invalid = True
                    tag = "invalid"
                    schedule = f"[INVALID] {schedule}"
                else:
                    tag = "invalid_disabled"
                    schedule = f"[INVALID] {schedule}"
            elif not enabled:
                tag = "disabled"
            
            self.job_tree.insert("", "end", values=(name, schedule, enabled_str, command), tags=(tag,) if tag else ())
        
        # Update frame title to show invalid count
        invalid_enabled_count = sum(1 for name, errs in self.invalid_jobs.items() 
                                    if any(j.get("name") == name and j.get("enabled", True) for j in jobs))
        if invalid_enabled_count > 0:
            self.root.title(f"Job Scheduler - {invalid_enabled_count} INVALID JOB(S)")
        else:
            self.root.title("Job Scheduler")
        
        # Update button states
        self._update_status()
    
    def _get_selected_job_name(self):
        """Get the name of the selected job."""
        selection = self.job_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a job first.")
            return None
        
        item = self.job_tree.item(selection[0])
        return item['values'][0]  # Name is first column
    
    def _on_job_selection(self, event=None):
        """Update button states based on job selection."""
        has_selection = bool(self.job_tree.selection())
        state = "normal" if has_selection else "disabled"
        self.edit_btn.configure(state=state)
        self.delete_btn.configure(state=state)
        self.run_btn.configure(state=state)
        self.enable_btn.configure(state=state)
        self.disable_btn.configure(state=state)
    
    def _show_command_tooltip(self, event):
        """Show tooltip with full command when hovering over command column."""
        # Identify which row/column the mouse is over
        region = self.job_tree.identify_region(event.x, event.y)
        if region != "cell":
            self._hide_command_tooltip()
            return
        
        column = self.job_tree.identify_column(event.x)
        item = self.job_tree.identify_row(event.y)
        
        # Only show tooltip for command column (#4)
        if column != "#4" or not item:
            self._hide_command_tooltip()
            return
        
        # Get the command value
        values = self.job_tree.item(item, "values")
        if len(values) >= 4:
            command = values[3]
            
            # Only show tooltip if command is long enough to be truncated
            if len(command) > 30:
                # Destroy old tooltip if exists
                if self.tooltip:
                    self.tooltip.destroy()
                
                # Create new tooltip
                x = event.x_root + 10
                y = event.y_root + 10
                self.tooltip = tk.Toplevel(self.root)
                self.tooltip.wm_overrideredirect(True)
                self.tooltip.wm_geometry(f"+{x}+{y}")
                
                label = tk.Label(
                    self.tooltip,
                    text=command,
                    background="#ffffe0",
                    relief="solid",
                    borderwidth=1,
                    font=('Consolas', 9),
                    padx=5,
                    pady=3
                )
                label.pack()
    
    def _hide_command_tooltip(self, event=None):
        """Hide the command tooltip."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
    
    def _run_job(self):
        """Run the selected job immediately."""
        job_name = self._get_selected_job_name()
        if not job_name:
            return
        
        # Don't run invalid jobs
        if job_name in self.invalid_jobs:
            errors = self.invalid_jobs[job_name]
            messagebox.showerror("Invalid Job", f"Cannot run invalid job '{job_name}':\n\n{errors[0]}")
            return
        
        try:
            jobs, _ = load_jobs_raw()
            job = None
            for j in jobs:
                if j.get("name") == job_name:
                    job = j
                    break
            
            if not job:
                messagebox.showerror("Error", f"Job '{job_name}' not found")
                return
            
            command = job.get("command", "")
            
            # Run in background thread
            def run():
                result = run_command(command, job_name)
                # Update UI from main thread
                self.root.after(0, lambda: self._show_run_result(job_name, result))
            
            threading.Thread(target=run, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run job: {e}")
    
    def _show_run_result(self, job_name, result):
        """Show result of a job run."""
        if not result['success']:
            messagebox.showerror("Failed", f"Job '{job_name}' failed:\n{result['error']}")
    
    def _toggle_enabled(self, enabled):
        """Enable or disable the selected job."""
        job_name = self._get_selected_job_name()
        if not job_name:
            return
        
        try:
            if update_job_enabled(job_name, enabled):
                self._load_jobs()
            else:
                messagebox.showerror("Error", f"Job '{job_name}' not found")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update job: {e}")
    
    def _add_job(self):
        """Add a new job."""
        dialog = JobEditorDialog(self.root)
        if dialog.result:
            try:
                jobs, _ = load_jobs_raw()
                
                # Check for duplicate name
                for job in jobs:
                    if job.get("name") == dialog.result["name"]:
                        messagebox.showerror("Error", f"Job '{dialog.result['name']}' already exists")
                        return
                
                jobs.append(dialog.result)
                save_jobs(jobs)
                self._load_jobs()
                messagebox.showinfo("Added", f"Job '{dialog.result['name']}' added.\n\nRestart scheduler to apply changes.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add job: {e}")
    
    def _edit_job(self):
        """Edit the selected job."""
        job_name = self._get_selected_job_name()
        if not job_name:
            return
        
        # Show validation errors if job is invalid
        if job_name in self.invalid_jobs:
            errors = self.invalid_jobs[job_name]
            msg = f"Job '{job_name}' has validation errors:\n\n"
            msg += "\n".join(f"• {e}" for e in errors)
            msg += "\n\nEdit the job to fix these errors."
            messagebox.showwarning("Invalid Job", msg)
        
        try:
            jobs, _ = load_jobs_raw()
            job_to_edit = None
            job_index = None
            
            for i, job in enumerate(jobs):
                if job.get("name") == job_name:
                    job_to_edit = job
                    job_index = i
                    break
            
            if not job_to_edit:
                messagebox.showerror("Error", f"Job '{job_name}' not found")
                return
            
            dialog = JobEditorDialog(self.root, job_to_edit)
            if dialog.result:
                jobs[job_index] = dialog.result
                save_jobs(jobs)
                self._load_jobs()
                messagebox.showinfo("Updated", f"Job '{dialog.result['name']}' updated.\n\nRestart scheduler to apply changes.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit job: {e}")
    
    def _delete_job(self):
        """Delete the selected job."""
        job_name = self._get_selected_job_name()
        if not job_name:
            return
        
        if not messagebox.askyesno("Confirm Delete", f"Delete job '{job_name}'?"):
            return
        
        try:
            jobs, _ = load_jobs_raw()
            jobs = [j for j in jobs if j.get("name") != job_name]
            save_jobs(jobs)
            self._load_jobs()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete job: {e}")
    
    def _start(self):
        """Start the scheduler."""
        # Check for enabled invalid jobs
        if self.has_enabled_invalid:
            invalid_names = [name for name in self.invalid_jobs.keys()]
            msg = "Cannot start scheduler with invalid enabled jobs:\n\n"
            for name in invalid_names[:5]:  # Show first 5
                errors = self.invalid_jobs[name]
                msg += f"• {name}: {errors[0]}\n"
            if len(invalid_names) > 5:
                msg += f"\n... and {len(invalid_names) - 5} more"
            msg += "\n\nPlease fix or disable the invalid jobs first."
            messagebox.showerror("Invalid Jobs", msg)
            return
        
        success, msg, pid = start_scheduler()
        if not success:
            messagebox.showerror("Error", msg)
        self._update_status()
    
    def _stop(self):
        """Stop the scheduler."""
        if not HAS_PSUTIL:
            messagebox.showerror("Error", "psutil required for stop operation")
            return
        
        success, msg = stop_scheduler()
        if not success:
            messagebox.showerror("Error", msg)
        self._update_status()
    
    def _restart(self):
        """Restart the scheduler."""
        # Check for enabled invalid jobs
        if self.has_enabled_invalid:
            invalid_names = [name for name in self.invalid_jobs.keys()]
            msg = "Cannot restart scheduler with invalid enabled jobs:\n\n"
            for name in invalid_names[:5]:  # Show first 5
                errors = self.invalid_jobs[name]
                msg += f"• {name}: {errors[0]}\n"
            if len(invalid_names) > 5:
                msg += f"\n... and {len(invalid_names) - 5} more"
            msg += "\n\nPlease fix or disable the invalid jobs first."
            messagebox.showerror("Invalid Jobs", msg)
            return
        
        success, msg, pid = restart_scheduler()
        if not success:
            messagebox.showerror("Error", msg)
        self._update_status()
    
    def _start_log_refresh(self):
        """Start background log refresh."""
        self.log_update_running = True
        self._last_log_content = ""  # Track for change detection
        self._update_log()
    
    def _get_log_level(self, line):
        """Extract log level from a log line."""
        for level in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
            if f" - {level} - " in line:
                return level
        return "INFO"  # Default
    
    def _filter_log_lines(self, lines):
        """Filter log lines based on current filter settings."""
        text_filter = self.filter_var.get().strip().lower()
        level_filter = self.level_var.get()
        
        # Level hierarchy for filtering
        level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
        min_level = level_priority.get(level_filter, -1)  # -1 for ALL
        
        filtered = []
        for line in lines:
            # Level filter
            if min_level >= 0:
                line_level = self._get_log_level(line)
                if level_priority.get(line_level, 0) < min_level:
                    continue
            
            # Text filter
            if text_filter and text_filter not in line.lower():
                continue
            
            filtered.append(line)
        
        return filtered
    
    def _apply_log_filter(self):
        """Force log refresh with current filter."""
        self._last_log_content = ""  # Force refresh
        self._update_log_now()
    
    def _update_log_now(self):
        """Update log display immediately."""
        try:
            lines = read_log_tail(500)  # Read more lines for filtering
            filtered_lines = self._filter_log_lines(lines)
            
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            
            # Insert lines with color tags
            for line in filtered_lines:
                level = self._get_log_level(line)
                self.log_text.insert("end", line, level)
            
            self.log_text.configure(state="disabled")
            
            if self.auto_scroll_var.get():
                self.log_text.see("end")
        except Exception:
            pass
    
    def _update_log(self):
        """Update log display (called periodically)."""
        if not self.log_update_running:
            return
        
        try:
            lines = read_log_tail(500)
            filtered_lines = self._filter_log_lines(lines)
            new_content = ''.join(filtered_lines)
            
            # Only update if content changed
            if new_content != self._last_log_content:
                self._last_log_content = new_content
                
                self.log_text.configure(state="normal")
                self.log_text.delete("1.0", "end")
                
                # Insert lines with color tags
                for line in filtered_lines:
                    level = self._get_log_level(line)
                    self.log_text.insert("end", line, level)
                
                self.log_text.configure(state="disabled")
                
                if self.auto_scroll_var.get():
                    self.log_text.see("end")
        except Exception:
            pass
        
        # Schedule next update
        self.root.after(2000, self._update_log)  # Every 2 seconds
    
    def _clear_log(self):
        """Clear the log display."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
    
    def _open_log_file(self):
        """Open log file in default editor."""
        import os
        log_path = get_log_file_path()
        if log_path.exists():
            os.startfile(str(log_path))
        else:
            messagebox.showwarning("Not Found", "Log file does not exist yet")
    
    def _on_close(self):
        """Handle window close."""
        self.log_update_running = False
        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    
    # Set icon if available
    icon_path = BASE_DIR / "icon.ico"
    if icon_path.exists():
        root.iconbitmap(str(icon_path))
    
    app = SchedulerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
