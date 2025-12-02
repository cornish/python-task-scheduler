"""
Scheduler Core Module (scheduler_core.py)

Shared functionality for scheduler, control script, and GUI.
This module provides reusable functions without running the scheduler itself.
"""
import os
import sys
import signal
import subprocess
import time
import yaml
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from validate_jobs import validate_config

# Directory paths
BASE_DIR = Path(__file__).parent
PID_FILE = BASE_DIR / "scheduler.pid"
SCHEDULER_SCRIPT = BASE_DIR / "scheduler.py"
CONFIG_FILE = os.environ.get("SCHEDULER_CONFIG", BASE_DIR / "jobs.yaml")
LOGS_DIR = Path(os.environ.get("SCHEDULER_LOG_DIR", BASE_DIR / "logs"))
LOG_FILE = LOGS_DIR / "scheduler.log"
JOB_TIMEOUT = int(os.environ.get("SCHEDULER_TIMEOUT", "300"))

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)


# =============================================================================
# Job Management Functions
# =============================================================================

def load_jobs(config_path=None):
    """
    Load and validate job configurations from YAML file.
    
    Args:
        config_path: Path to jobs.yaml (uses CONFIG_FILE if None)
        
    Returns:
        list: List of job dictionaries
    """
    if config_path is None:
        config_path = CONFIG_FILE
    
    data = validate_config(config_path)
    return data["jobs"]


def save_jobs(jobs, config_path=None):
    """
    Save job configurations to YAML file.
    
    Args:
        jobs: List of job dictionaries
        config_path: Path to jobs.yaml (uses CONFIG_FILE if None)
    """
    if config_path is None:
        config_path = CONFIG_FILE
    
    with open(config_path, 'w') as f:
        yaml.dump({"jobs": jobs}, f, default_flow_style=False, sort_keys=False)


def get_job_by_name(jobs, name):
    """Find a job by name."""
    for job in jobs:
        if job.get("name") == name:
            return job
    return None


def update_job_enabled(job_name, enabled, config_path=None):
    """
    Update the enabled status of a job.
    
    Args:
        job_name: Name of the job to update
        enabled: True to enable, False to disable
        config_path: Path to jobs.yaml
        
    Returns:
        bool: True if job was found and updated
    """
    jobs = load_jobs(config_path)
    for job in jobs:
        if job.get("name") == job_name:
            job["enabled"] = enabled
            save_jobs(jobs, config_path)
            return True
    return False


def format_schedule(job):
    """Format a job's schedule as human-readable string."""
    sched = job.get("schedule", {})
    unit = sched.get("unit", "")
    every = sched.get("every", 1)
    at = sched.get("at", "")
    day = sched.get("day", "")
    day_of_month = sched.get("day_of_month", "")
    
    if unit == "startup":
        return "On startup"
    elif unit == "months":
        s = f"Monthly day {day_of_month}"
        if at:
            s += f" at {at}"
        return s
    elif unit == "weeks" and day:
        s = f"Every {every} week(s) on {day}"
        if at:
            s += f" at {at}"
        return s
    else:
        s = f"Every {every} {unit}"
        if at:
            s += f" at {at}"
        return s


# =============================================================================
# Command Execution
# =============================================================================

def run_command(command, job_name="unknown", timeout=None):
    """
    Execute a job command.
    
    Handles both relative and absolute paths (including UNC paths).
    For UNC paths, uses pushd/popd to work around CMD.EXE limitations.
    
    Args:
        command: Command string to run (can include arguments)
        job_name: Name for logging
        timeout: Timeout in seconds (uses JOB_TIMEOUT if None)
        
    Returns:
        dict: Result with 'success', 'stdout', 'stderr', 'error' keys
    """
    if timeout is None:
        timeout = JOB_TIMEOUT
    
    result = {
        'success': False,
        'stdout': '',
        'stderr': '',
        'error': None
    }
    
    try:
        # Prepare the command - if BASE_DIR is a UNC path, wrap command with pushd/popd
        # This allows CMD to temporarily map the UNC path and work around the limitation
        final_command = command
        working_dir = str(BASE_DIR)  # Default: use BASE_DIR as working directory
        
        if sys.platform == 'win32':
            base_dir_str = str(BASE_DIR)
            # Check if BASE_DIR is a UNC path and command appears to use relative paths
            if base_dir_str.startswith('\\\\'):
                # For UNC paths, use pushd/popd which temporarily maps to a drive letter
                # This works for both relative paths in the command and allows cwd context
                final_command = f'pushd "{base_dir_str}" && {command} & popd'
                working_dir = None  # pushd handles the directory, don't set cwd
            else:
                # For regular Windows paths, we can safely use cwd parameter
                working_dir = base_dir_str
        # For Linux/Mac, working_dir is already set to BASE_DIR above
        
        # Windows-specific: hide console window
        startupinfo = None
        creationflags = 0
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
        
        proc_result = subprocess.run(
            final_command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        result['success'] = True
        result['stdout'] = proc_result.stdout
        result['stderr'] = proc_result.stderr
        
    except subprocess.TimeoutExpired:
        result['error'] = f"Timed out after {timeout} seconds"
    except subprocess.CalledProcessError as e:
        result['error'] = f"Exit code {e.returncode}"
        result['stderr'] = e.stderr
    except FileNotFoundError:
        result['error'] = f"Script not found: {command}"
    except Exception as e:
        result['error'] = str(e)
    
    return result


# =============================================================================
# Process Control Functions
# =============================================================================

def get_pid():
    """Read PID from file."""
    try:
        if PID_FILE.exists():
            return int(PID_FILE.read_text().strip())
    except (ValueError, IOError):
        pass
    return None


def is_running(pid=None):
    """
    Check if scheduler process is running.
    
    Args:
        pid: Process ID to check (reads from PID file if None)
        
    Returns:
        bool: True if scheduler is running
    """
    if not HAS_PSUTIL:
        # Fallback: just check if PID file exists
        return PID_FILE.exists()
    
    if pid is None:
        pid = get_pid()
    
    if pid is None:
        return False
    
    try:
        proc = psutil.Process(pid)
        cmdline = ' '.join(proc.cmdline()).lower()
        return 'scheduler.py' in cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def get_process_info(pid=None):
    """
    Get detailed process information.
    
    Args:
        pid: Process ID (reads from PID file if None)
        
    Returns:
        dict: Process info or None if not running
    """
    if not HAS_PSUTIL:
        return None
    
    if pid is None:
        pid = get_pid()
    
    if pid is None:
        return None
    
    try:
        proc = psutil.Process(pid)
        create_time = time.strftime('%Y-%m-%d %H:%M:%S', 
                                     time.localtime(proc.create_time()))
        memory = proc.memory_info().rss / 1024 / 1024  # MB
        return {
            'pid': pid,
            'status': proc.status(),
            'started': create_time,
            'memory_mb': round(memory, 1),
            'cpu_percent': proc.cpu_percent(interval=0.1)
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def start_scheduler():
    """
    Start the scheduler process.
    
    Returns:
        tuple: (success: bool, message: str, pid: int or None)
    """
    pid = get_pid()
    
    if pid and is_running(pid):
        return (True, f"Scheduler is already running (PID: {pid})", pid)
    
    # Clean up stale PID file
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except:
            pass
    
    try:
        if sys.platform == 'win32':
            python_exe = sys.executable
            pythonw = Path(python_exe).parent / "pythonw.exe"
            if pythonw.exists():
                python_exe = str(pythonw)
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            
            subprocess.Popen(
                [python_exe, str(SCHEDULER_SCRIPT)],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            subprocess.Popen(
                [sys.executable, str(SCHEDULER_SCRIPT)],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        # Wait for PID file
        for _ in range(10):
            time.sleep(0.5)
            if PID_FILE.exists():
                break
        
        new_pid = get_pid()
        if new_pid and is_running(new_pid):
            return (True, f"Scheduler started (PID: {new_pid})", new_pid)
        else:
            return (False, "Scheduler failed to start - check logs", None)
            
    except Exception as e:
        return (False, f"Failed to start: {e}", None)


def stop_scheduler():
    """
    Stop the scheduler process.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not HAS_PSUTIL:
        return (False, "psutil required for stop operation")
    
    pid = get_pid()
    
    if pid is None:
        return (True, "Scheduler is not running (no PID file)")
    
    if not is_running(pid):
        try:
            PID_FILE.unlink()
        except:
            pass
        return (True, f"Scheduler is not running (stale PID: {pid})")
    
    try:
        proc = psutil.Process(pid)
        
        if sys.platform == 'win32':
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        
        try:
            proc.wait(timeout=10)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except:
                pass
        
        return (True, "Scheduler stopped")
        
    except psutil.NoSuchProcess:
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except:
                pass
        return (True, "Scheduler already stopped")
    except Exception as e:
        return (False, f"Failed to stop: {e}")


def restart_scheduler():
    """
    Restart the scheduler process.
    
    Returns:
        tuple: (success: bool, message: str, pid: int or None)
    """
    success, msg = stop_scheduler()
    if not success:
        return (False, msg, None)
    
    time.sleep(1)
    return start_scheduler()


# =============================================================================
# Log Functions
# =============================================================================

def read_log_tail(lines=50):
    """
    Read the last N lines of the scheduler log.
    
    Args:
        lines: Number of lines to read
        
    Returns:
        list: List of log lines
    """
    if not LOG_FILE.exists():
        return []
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception:
        return []


def get_log_file_path():
    """Return the path to the log file."""
    return LOG_FILE
