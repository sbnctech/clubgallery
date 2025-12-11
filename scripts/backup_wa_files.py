#!/usr/bin/env python3
"""
SBNC Photo Gallery System - WebDAV Backup Script
Sync files from Wild Apricot WebDAV to local storage.

Usage:
    python scripts/backup_wa_files.py
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.sync.wa_webdav import run_webdav_sync
from app.database import init_db


def main():
    parser = argparse.ArgumentParser(description='Backup files from Wild Apricot WebDAV')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('backup_wa_files')

    # Ensure database is initialized
    init_db()

    try:
        logger.info("Starting WebDAV backup sync...")
        result = run_webdav_sync()

        if result['success']:
            logger.info(f"Sync complete: {result['files_downloaded']} downloaded, "
                        f"{result['files_skipped']} skipped, "
                        f"{result['files_checked']} checked")
        else:
            logger.error(f"Sync failed: {result.get('error', 'Unknown error')}")
            if result.get('errors'):
                for err in result['errors'][:10]:  # Show first 10 errors
                    logger.error(f"  - {err}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
