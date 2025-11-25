#!/usr/bin/env python3
"""
Scheduler Watchdog Script

Monitors the scheduler service and restarts it if it's not running.
Designed to be run periodically by Windows Task Scheduler (e.g., every 5 minutes).

Includes thrashing detection to prevent endless restart loops.

Environment Variables:
    WATCHDOG_LOG_SIZE  - Max log file size in MB (default: 5)
    WATCHDOG_LOG_COUNT - Number of backup log files (default: 3)
"""
import os
import sys
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import psutil
import json
from datetime import datetime, timedelta

# Directory paths
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Environment variable configuration with defaults
LOG_MAX_SIZE_MB = int(os.environ.get("WATCHDOG_LOG_SIZE", "5"))
LOG_BACKUP_COUNT = int(os.environ.get("WATCHDOG_LOG_COUNT", "3"))

# Setup logging with rotation
def setup_logging():
    """Configure logging with rotating file handler."""
    log_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOGS_DIR / 'watchdog.log',
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# Configuration
PID_FILE = BASE_DIR / "scheduler.pid"
SCHEDULER_SCRIPT = BASE_DIR / "scheduler.py"
PYTHON_EXE = sys.executable
RESTART_HISTORY_FILE = LOGS_DIR / "watchdog_restarts.json"

# Thrashing detection settings
MAX_RESTARTS_IN_WINDOW = 5  # Maximum restarts allowed
RESTART_WINDOW_MINUTES = 15  # Time window for counting restarts
BACKOFF_MINUTES = 30  # How long to wait before trying again after thrashing detected

def is_process_running(pid):
    """Check if a process with given PID is running."""
    try:
        process = psutil.Process(pid)
        # Check if it's actually the scheduler (not just any process with that PID)
        cmdline = ' '.join(process.cmdline()).lower()
        if 'scheduler.py' in cmdline:
            return True
        else:
            logger.warning(f"PID {pid} exists but is not scheduler (cmdline: {cmdline})")
            return False
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        logger.warning(f"Access denied checking PID {pid}, assuming it's running")
        return True
    except Exception as e:
        logger.error(f"Error checking process {pid}: {e}")
        return False

def get_scheduler_pid():
    """Read the scheduler PID from the PID file."""
    try:
        if PID_FILE.exists():
            pid_str = PID_FILE.read_text().strip()
            return int(pid_str)
        else:
            logger.info("PID file does not exist")
            return None
    except ValueError as e:
        logger.error(f"Invalid PID in file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading PID file: {e}")
        return None

def cleanup_stale_pid_file():
    """Remove PID file if it exists but process is not running."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info("Removed stale PID file")
    except Exception as e:
        logger.error(f"Failed to remove stale PID file: {e}")

def load_restart_history():
    """Load restart history from file."""
    try:
        if RESTART_HISTORY_FILE.exists():
            data = json.loads(RESTART_HISTORY_FILE.read_text())
            # Convert ISO strings back to datetime
            data['restarts'] = [datetime.fromisoformat(dt) for dt in data['restarts']]
            if data.get('backoff_until'):
                data['backoff_until'] = datetime.fromisoformat(data['backoff_until'])
            return data
        return {'restarts': [], 'backoff_until': None}
    except Exception as e:
        logger.error(f"Error loading restart history: {e}")
        return {'restarts': [], 'backoff_until': None}

def save_restart_history(history):
    """Save restart history to file."""
    try:
        # Convert datetime to ISO strings for JSON
        data = {
            'restarts': [dt.isoformat() for dt in history['restarts']],
            'backoff_until': history['backoff_until'].isoformat() if history['backoff_until'] else None
        }
        RESTART_HISTORY_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Error saving restart history: {e}")

def record_restart(history):
    """Record a new restart attempt and check for thrashing."""
    now = datetime.now()
    history['restarts'].append(now)
    
    # Remove restarts outside the time window
    cutoff = now - timedelta(minutes=RESTART_WINDOW_MINUTES)
    history['restarts'] = [dt for dt in history['restarts'] if dt > cutoff]
    
    # Check for thrashing
    if len(history['restarts']) >= MAX_RESTARTS_IN_WINDOW:
        logger.critical(
            f"THRASHING DETECTED: {len(history['restarts'])} restarts in {RESTART_WINDOW_MINUTES} minutes!"
        )
        logger.critical(f"The scheduler is crashing immediately after restart.")
        logger.critical(f"Entering backoff mode for {BACKOFF_MINUTES} minutes.")
        logger.critical(f"Check scheduler.log for errors!")
        
        history['backoff_until'] = now + timedelta(minutes=BACKOFF_MINUTES)
        save_restart_history(history)
        return False
    
    save_restart_history(history)
    return True

def is_in_backoff(history):
    """Check if we're currently in backoff mode."""
    if history.get('backoff_until'):
        now = datetime.now()
        if now < history['backoff_until']:
            remaining = (history['backoff_until'] - now).total_seconds() / 60
            logger.warning(
                f"In backoff mode: {remaining:.1f} minutes remaining. "
                f"Will retry at {history['backoff_until'].strftime('%H:%M:%S')}"
            )
            return True
        else:
            # Backoff period expired, clear it
            logger.info("Backoff period expired, resuming normal operation")
            history['backoff_until'] = None
            history['restarts'] = []  # Clear history after successful backoff
            save_restart_history(history)
            return False
    return False

def cleanup_stale_pid_file():
    """Remove PID file if it exists but process is not running."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info("Removed stale PID file")
    except Exception as e:
        logger.error(f"Failed to remove stale PID file: {e}")

def start_scheduler():
    """Start the scheduler process in the background."""
    try:
        # Check restart history for thrashing
        history = load_restart_history()
        
        # Check if we're in backoff mode
        if is_in_backoff(history):
            return False
        
        # Record this restart attempt
        if not record_restart(history):
            return False  # Thrashing detected, don't restart
        
        logger.info(f"Starting scheduler: {SCHEDULER_SCRIPT}")
        logger.info(f"Restart count in last {RESTART_WINDOW_MINUTES} minutes: {len(history['restarts'])}/{MAX_RESTARTS_IN_WINDOW}")
        
        # Start the scheduler process detached (Windows specific)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE - hide window
        
        process = subprocess.Popen(
            [PYTHON_EXE, str(SCHEDULER_SCRIPT)],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        
        logger.info(f"Scheduler started with PID: {process.pid}")
        
        # Give it a moment to start and write PID file
        import time
        time.sleep(2)
        
        # Verify it started
        if PID_FILE.exists():
            logger.info("[OK] Scheduler successfully started and PID file created")
            return True
        else:
            logger.warning("[WARNING] Scheduler started but PID file not yet created")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)
        return False

def check_and_restart():
    """Main watchdog logic: check if scheduler is running, restart if not."""
    logger.info("="*60)
    logger.info("Watchdog check starting")
    
    # Load restart history
    history = load_restart_history()
    
    # Check if we're in backoff mode from previous thrashing
    if is_in_backoff(history):
        logger.info("Skipping check - in backoff mode")
        return False
    
    pid = get_scheduler_pid()
    
    if pid is None:
        logger.warning("Scheduler PID not found - scheduler appears to be down")
        cleanup_stale_pid_file()
        return start_scheduler()
    
    logger.info(f"Found scheduler PID: {pid}")
    
    if is_process_running(pid):
        logger.info(f"[OK] Scheduler is running (PID: {pid})")
        return True
    else:
        logger.warning(f"[FAIL] Scheduler process (PID: {pid}) is not running")
        cleanup_stale_pid_file()
        return start_scheduler()

if __name__ == "__main__":
    # Check for reset command
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        logger.info("Resetting watchdog restart history and backoff state")
        try:
            if RESTART_HISTORY_FILE.exists():
                RESTART_HISTORY_FILE.unlink()
                logger.info("Restart history cleared")
            else:
                logger.info("No restart history to clear")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error resetting: {e}")
            sys.exit(1)
    
    try:
        success = check_and_restart()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.critical(f"Watchdog error: {e}", exc_info=True)
        sys.exit(1)
