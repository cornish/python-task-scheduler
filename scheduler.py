"""
Python Job Scheduler Service
Runs scheduled jobs defined in jobs.yaml configuration file.

Environment Variables:
    SCHEDULER_CONFIG    - Path to jobs.yaml (default: jobs.yaml)
    SCHEDULER_LOG_DIR   - Log directory (default: ./logs)
    SCHEDULER_LOG_LEVEL - Logging level (default: INFO)
    SCHEDULER_LOG_SIZE  - Max log file size in MB (default: 10)
    SCHEDULER_LOG_COUNT - Number of backup log files (default: 5)
    SCHEDULER_TIMEOUT   - Job timeout in seconds (default: 300)
"""
import schedule
import time
import logging
from logging.handlers import RotatingFileHandler
import threading
import os
import sys
import atexit
from pathlib import Path

# Import shared functionality
from scheduler_core import (
    BASE_DIR, PID_FILE, LOGS_DIR, LOG_FILE,
    load_jobs, run_command as core_run_command
)

# Environment variable configuration with defaults
CONFIG_FILE = os.environ.get("SCHEDULER_CONFIG", "jobs.yaml")
LOG_LEVEL = os.environ.get("SCHEDULER_LOG_LEVEL", "INFO").upper()
LOG_MAX_SIZE_MB = int(os.environ.get("SCHEDULER_LOG_SIZE", "10"))
LOG_BACKUP_COUNT = int(os.environ.get("SCHEDULER_LOG_COUNT", "5"))
JOB_TIMEOUT = int(os.environ.get("SCHEDULER_TIMEOUT", "300"))


# Configure logging with rotation
def setup_logging():
    """Configure logging with rotating file handler."""
    log_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()


def write_pid_file():
    """Write the current process ID to a file."""
    try:
        PID_FILE.write_text(str(os.getpid()))
        logger.info(f"PID file created: {PID_FILE} (PID: {os.getpid()})")
    except Exception as e:
        logger.error(f"Failed to write PID file: {e}")


def remove_pid_file():
    """Remove the PID file on shutdown."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info("PID file removed")
    except Exception as e:
        logger.error(f"Failed to remove PID file: {e}")

atexit.register(remove_pid_file)


def run_command_logged(command, job_name="unknown"):
    """Execute a command with logging (wrapper around core function)."""
    logger.info(f"Starting job '{job_name}': {command}")
    result = core_run_command(command, job_name, JOB_TIMEOUT)
    
    if result['success']:
        logger.info(f"Job '{job_name}' completed successfully")
        if result['stdout']:
            logger.debug(f"Job '{job_name}' output: {result['stdout']}")
    else:
        logger.error(f"Job '{job_name}' failed: {result['error']}")
        if result['stderr']:
            logger.error(f"Job '{job_name}' stderr: {result['stderr']}")


def run_threaded(job_func, *args):
    """Run a job function in a separate thread."""
    job_thread = threading.Thread(target=job_func, args=args, daemon=True)
    job_thread.start()
    logger.debug(f"Started thread {job_thread.name} for job execution")


def run_monthly_job(command, job_name, target_day):
    """Wrapper for monthly jobs - only runs on the specified day of month."""
    import datetime
    today = datetime.datetime.now().day
    if today == target_day:
        logger.info(f"Monthly job '{job_name}' triggered (day {target_day})")
        run_threaded(run_command_logged, command, job_name)
    else:
        logger.debug(f"Monthly job '{job_name}' skipped (today={today}, target={target_day})")


def schedule_job(job):
    """Schedule a single job based on its configuration."""
    try:
        job_name = job.get("name", "unknown")
        
        if not job.get("enabled", True):
            logger.info(f"Skipping disabled job '{job_name}'")
            return "disabled"
        
        unit = job["schedule"]["unit"]
        at = job["schedule"].get("at")
        day = job["schedule"].get("day")
        day_of_month = job["schedule"].get("day_of_month")
        every_val = job["schedule"].get("every", 1)
        
        if unit == "startup":
            logger.info(f"Startup job '{job_name}' will run once at initialization")
            return "startup"
        
        if unit == "months":
            if not day_of_month:
                logger.warning(f"Monthly job '{job_name}' missing day_of_month, defaulting to 1st")
                day_of_month = 1
            
            sched = schedule.every().day
            if at:
                sched = sched.at(at)
                logger.info(f"Scheduled job '{job_name}': monthly on day {day_of_month} at {at}")
            else:
                logger.info(f"Scheduled job '{job_name}': monthly on day {day_of_month}")
            
            sched.do(run_monthly_job, job["command"], job_name, day_of_month)
            return None
        
        every = schedule.every(every_val)
        sched = getattr(every, unit)
        
        if unit == "weeks" and day:
            day_lower = day.lower()
            if hasattr(sched, day_lower):
                sched = getattr(sched, day_lower)
                if at:
                    sched = sched.at(at)
                    logger.info(f"Scheduled job '{job_name}': every {every_val} {unit} on {day} at {at}")
                else:
                    logger.info(f"Scheduled job '{job_name}': every {every_val} {unit} on {day}")
            else:
                logger.warning(f"Invalid day '{day}' for job '{job_name}', scheduling without day constraint")
                if at:
                    sched = sched.at(at)
        elif at and hasattr(sched, "at"):
            sched = sched.at(at)
            logger.info(f"Scheduled job '{job_name}': every {every_val} {unit} at {at}")
        else:
            logger.info(f"Scheduled job '{job_name}': every {every_val} {unit}")

        sched.do(run_threaded, run_command_logged, job["command"], job_name)
        return None
    except AttributeError as e:
        logger.error(f"Invalid schedule unit '{unit}' for job '{job_name}': {e}")
        raise
    except Exception as e:
        logger.error(f"Error scheduling job '{job_name}': {e}")
        raise


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Starting Scheduler Service")
    logger.info("="*60)
    logger.info(f"Configuration: {CONFIG_FILE}")
    logger.info(f"Log directory: {LOGS_DIR}")
    logger.info(f"Log level: {LOG_LEVEL}")
    logger.info(f"Log rotation: {LOG_MAX_SIZE_MB}MB x {LOG_BACKUP_COUNT} files")
    logger.info(f"Job timeout: {JOB_TIMEOUT}s")
    
    write_pid_file()
    
    try:
        jobs = load_jobs(CONFIG_FILE)
        
        if not jobs:
            logger.warning("No jobs found in configuration file")
        
        startup_jobs = []
        for job in jobs:
            result = schedule_job(job)
            if result == "startup":
                startup_jobs.append(job)
        
        logger.info(f"Scheduler initialized with {len(jobs)} jobs ({len(startup_jobs)} startup)")
        
        for job in startup_jobs:
            logger.info(f"Running startup job: {job['name']}")
            run_threaded(run_command_logged, job["command"], job["name"])
        
        logger.info("Press Ctrl+C to stop the scheduler")
        
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise
