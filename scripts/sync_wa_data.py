#!/usr/bin/env python3
"""
SBNC Photo Gallery System - Wild Apricot Sync Script
Sync members, events, and registrations from Wild Apricot.

Usage:
    python scripts/sync_wa_data.py [--members] [--events] [--registrations]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.sync.member_sync import MemberSync, EventSync, run_full_sync
from app.database import init_db


def main():
    parser = argparse.ArgumentParser(description='Sync data from Wild Apricot')
    parser.add_argument('--members', action='store_true', help='Sync members only')
    parser.add_argument('--events', action='store_true', help='Sync events only')
    parser.add_argument('--registrations', action='store_true', help='Sync registrations only')
    parser.add_argument('--all', action='store_true', help='Sync everything (default)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('sync_wa_data')

    # Ensure database is initialized
    init_db()

    # If no specific option, do all
    if not (args.members or args.events or args.registrations):
        args.all = True

    try:
        if args.all:
            logger.info("Running full sync...")
            result = run_full_sync()
            logger.info(f"Full sync complete: {result['members']} members, "
                        f"{result['events']} events, {result['registrations']} registrations")
        else:
            if args.members:
                logger.info("Syncing members...")
                member_sync = MemberSync()
                count = member_sync.sync_all_members()
                logger.info(f"Synced {count} members")

            if args.events:
                logger.info("Syncing events...")
                event_sync = EventSync()
                count = event_sync.sync_events()
                logger.info(f"Synced {count} events")

            if args.registrations:
                logger.info("Syncing registrations...")
                event_sync = EventSync()
                count = event_sync.sync_all_recent_registrations()
                logger.info(f"Synced {count} registrations")

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
