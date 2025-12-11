#!/usr/bin/env python3
"""
SBNC Photo Gallery System - Email Check Script
Check the photos@sbnewcomers.org inbox for new submissions.

Usage:
    python scripts/check_email.py [--once] [--interval SECONDS]
"""

import sys
import argparse
import logging
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingest.email_monitor import run_email_check
from app.database import init_db


def main():
    parser = argparse.ArgumentParser(description='Check email for photo submissions')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=300,
                        help='Check interval in seconds (default: 300)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('check_email')

    # Ensure database is initialized
    init_db()

    try:
        if args.once:
            logger.info("Checking email inbox...")
            results = run_email_check()
            photos = sum(len(r['photos']) for r in results)
            logger.info(f"Processed {len(results)} emails, queued {photos} photos")
        else:
            logger.info(f"Starting email monitor (interval: {args.interval}s)")
            while True:
                try:
                    results = run_email_check()
                    photos = sum(len(r['photos']) for r in results)
                    if photos:
                        logger.info(f"Queued {photos} photos from {len(results)} emails")
                except Exception as e:
                    logger.error(f"Email check failed: {e}")

                time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Email check failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
