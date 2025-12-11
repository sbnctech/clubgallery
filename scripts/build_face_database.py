#!/usr/bin/env python3
"""
SBNC Photo Gallery System - Build Face Database
Download member photos and create face embeddings for recognition.

Usage:
    python scripts/build_face_database.py [--rebuild]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.processing.face_detector import build_face_database_from_profiles
from app.database import init_db


def main():
    parser = argparse.ArgumentParser(description='Build face recognition database')
    parser.add_argument('--rebuild', action='store_true',
                        help='Rebuild all embeddings (otherwise only add new)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('build_face_db')

    # Ensure database is initialized
    init_db()

    if args.rebuild:
        logger.info("Rebuilding entire face database...")
        from app.database import get_db
        with get_db() as conn:
            conn.execute("DELETE FROM face_embeddings WHERE source IN ('profile', 'directory')")
        logger.info("Cleared existing profile embeddings")

    try:
        logger.info("Building face database from member photos...")
        result = build_face_database_from_profiles()
        logger.info(f"Complete: {result['processed']} processed, {result['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to build face database: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
