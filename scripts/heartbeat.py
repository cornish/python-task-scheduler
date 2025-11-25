#!/usr/bin/env python3
"""
Heartbeat Script
Sends a heartbeat signal to indicate the system is alive.
"""
import logging
from datetime import datetime
import socket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_heartbeat():
    """Send heartbeat signal to monitoring system."""
    timestamp = datetime.now().isoformat()
    hostname = socket.gethostname()
    
    logger.info(f"💓 Heartbeat from {hostname} at {timestamp}")
    logger.info("System status: RUNNING")
    
    # Simulate checking critical services
    services = {
        "database": "OK",
        "web_server": "OK",
        "cache": "OK",
    }
    
    for service, status in services.items():
        logger.info(f"  {service}: {status}")
    
    return True

if __name__ == "__main__":
    try:
        send_heartbeat()
        exit(0)
    except Exception as e:
        logger.error(f"Heartbeat error: {e}", exc_info=True)
        exit(1)
