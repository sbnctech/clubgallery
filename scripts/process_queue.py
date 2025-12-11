#!/usr/bin/env python3
"""
SBNC Photo Gallery System - Queue Processing Script
Run via cron to process pending photo uploads.

Usage:
    python scripts/process_queue.py [--batch-size N]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.processing.pipeline import process_queue
from app.database import init_db


def main():
    parser = argparse.ArgumentParser(description='Process photo queue')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='Maximum photos to process per run')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('process_queue')

    logger.info(f"Starting queue processing (batch size: {args.batch_size})")

    try:
        # Ensure database is initialized
        init_db()

        # Process the queue
        result = process_queue(batch_size=args.batch_size)

        logger.info(f"Processing complete: {result['processed']} processed, "
                    f"{result['failed']} failed, {result['total']} total")

        # Exit with error code if any failures
        if result['failed'] > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Queue processing failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
