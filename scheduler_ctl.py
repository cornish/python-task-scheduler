#!/usr/bin/env python3
"""
Scheduler Control Script (scheduler_ctl.py)

Platform-agnostic utility to control the scheduler service.

Usage:
    python scheduler_ctl.py status    # Check if scheduler is running
    python scheduler_ctl.py start     # Start the scheduler
    python scheduler_ctl.py stop      # Stop the scheduler
    python scheduler_ctl.py restart   # Restart the scheduler
"""
import sys

# Import shared functionality
from scheduler_core import (
    get_pid, is_running, get_process_info,
    start_scheduler, stop_scheduler, restart_scheduler,
    HAS_PSUTIL
)


def status():
    """Check scheduler status."""
    pid = get_pid()
    
    if pid is None:
        print("[STOPPED] Scheduler is not running (no PID file)")
        return 1
    
    if is_running(pid):
        info = get_process_info(pid)
        if info:
            print(f"[RUNNING] Scheduler is running")
            print(f"  PID:     {info['pid']}")
            print(f"  Status:  {info['status']}")
            print(f"  Started: {info['started']}")
            print(f"  Memory:  {info['memory_mb']} MB")
            print(f"  CPU:     {info['cpu_percent']}%")
        else:
            print(f"[RUNNING] Scheduler is running (PID: {pid})")
        return 0
    else:
        print(f"[STOPPED] Scheduler is not running (stale PID: {pid})")
        return 1


def start():
    """Start the scheduler."""
    success, msg, pid = start_scheduler()
    print(f"[OK] {msg}" if success else f"[ERROR] {msg}")
    return 0 if success else 1


def stop():
    """Stop the scheduler."""
    if not HAS_PSUTIL:
        print("[ERROR] psutil is required for stop. Install: pip install psutil")
        return 1
    
    success, msg = stop_scheduler()
    print(f"[OK] {msg}" if success else f"[ERROR] {msg}")
    return 0 if success else 1


def restart():
    """Restart the scheduler."""
    print("Restarting scheduler...")
    success, msg, pid = restart_scheduler()
    print(f"[OK] {msg}" if success else f"[ERROR] {msg}")
    return 0 if success else 1


def usage():
    """Print usage information."""
    print(__doc__)
    print("Commands:")
    print("  status   - Check if scheduler is running")
    print("  start    - Start the scheduler in background")
    print("  stop     - Stop the scheduler gracefully")
    print("  restart  - Stop and start the scheduler")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    commands = {
        'status': status,
        'start': start,
        'stop': stop,
        'restart': restart,
    }
    
    if command in commands:
        sys.exit(commands[command]())
    elif command in ('-h', '--help', 'help'):
        usage()
        sys.exit(0)
    else:
        print(f"Unknown command: {command}")
        usage()
        sys.exit(1)
