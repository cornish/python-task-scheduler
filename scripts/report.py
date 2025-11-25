#!/usr/bin/env python3
"""
Daily Report Script
Generates and sends a daily activity report.
"""
import logging
from datetime import datetime, timedelta
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_report():
    """Generate a daily activity report."""
    logger.info("Generating daily report...")
    
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    # Simulate collecting metrics
    metrics = {
        "active_users": random.randint(50, 200),
        "transactions": random.randint(100, 500),
        "errors": random.randint(0, 10),
        "avg_response_time_ms": random.randint(50, 300),
    }
    
    logger.info(f"Report for {report_date}:")
    logger.info(f"  Active Users: {metrics['active_users']}")
    logger.info(f"  Transactions: {metrics['transactions']}")
    logger.info(f"  Errors: {metrics['errors']}")
    logger.info(f"  Avg Response Time: {metrics['avg_response_time_ms']}ms")
    
    # Simulate sending report
    logger.info("Report sent to administrators")
    
    return True

if __name__ == "__main__":
    try:
        success = generate_report()
        if success:
            logger.info("Daily report completed successfully")
            exit(0)
        else:
            logger.error("Daily report failed")
            exit(1)
    except Exception as e:
        logger.error(f"Report generation error: {e}", exc_info=True)
        exit(1)
