#!/usr/bin/env python3
"""
Disk Space Check Script
Monitors disk space usage and alerts if threshold is exceeded.
"""
import logging
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_disk_space(path=".", threshold_percent=80):
    """Check disk space and alert if usage exceeds threshold."""
    logger.info("Checking disk space...")
    
    try:
        usage = shutil.disk_usage(path)
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        percent_used = (usage.used / usage.total) * 100
        
        logger.info(f"Total: {total_gb:.2f} GB")
        logger.info(f"Used: {used_gb:.2f} GB ({percent_used:.1f}%)")
        logger.info(f"Free: {free_gb:.2f} GB")
        
        if percent_used > threshold_percent:
            logger.warning(f"⚠️  Disk usage ({percent_used:.1f}%) exceeds threshold ({threshold_percent}%)")
            return False
        else:
            logger.info(f"✅ Disk space is healthy ({percent_used:.1f}% used)")
            return True
            
    except Exception as e:
        logger.error(f"Error checking disk space: {e}")
        raise

if __name__ == "__main__":
    try:
        check_disk_space()
        logger.info("Disk check completed")
        exit(0)
    except Exception as e:
        logger.error(f"Disk check error: {e}", exc_info=True)
        exit(1)
