"""
SBNC Photo Gallery System - Duplicate Photo Detection
Prevent importing the same photo twice by checking file content hash.

Uses SHA-256 hash of file content for reliable duplicate detection.
This catches duplicates regardless of filename (IMG_1234.jpg vs copy_IMG_1234.jpg).
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

# Hash algorithm - SHA-256 is reliable and fast enough for photos
HASH_ALGORITHM = 'sha256'
CHUNK_SIZE = 65536  # 64KB chunks for large files


def compute_file_hash(file_path: str) -> Optional[str]:
    """
    Compute SHA-256 hash of a file's contents.

    Args:
        file_path: Path to the file

    Returns:
        Hex string of hash, or None if file can't be read
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"File not found for hashing: {file_path}")
        return None

    try:
        hasher = hashlib.new(HASH_ALGORITHM)
        with open(file_path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash file {file_path}: {e}")
        return None


def check_duplicate(file_path: str) -> Tuple[bool, Optional[Dict]]:
    """
    Check if a file is a duplicate of an already imported photo.

    Args:
        file_path: Path to the file to check

    Returns:
        Tuple of (is_duplicate: bool, existing_photo: dict or None)
        If duplicate, existing_photo contains the matching photo record
    """
    from app.database import get_db

    file_hash = compute_file_hash(file_path)
    if not file_hash:
        # Can't compute hash - not a duplicate (or file error)
        return False, None

    with get_db() as conn:
        existing = conn.execute('''
            SELECT id, original_filename, submitted_at, status, file_path
            FROM photos
            WHERE content_hash = ?
        ''', (file_hash,)).fetchone()

    if existing:
        logger.info(f"Duplicate detected: {file_path} matches existing photo {existing['id']}")
        return True, dict(existing)

    return False, None


def check_duplicates_batch(file_paths: list) -> Dict[str, Dict]:
    """
    Check multiple files for duplicates in one batch.

    Args:
        file_paths: List of file paths to check

    Returns:
        Dict mapping file_path -> existing_photo_record for duplicates only
    """
    from app.database import get_db

    # Compute all hashes
    hash_to_path = {}
    for file_path in file_paths:
        file_hash = compute_file_hash(file_path)
        if file_hash:
            hash_to_path[file_hash] = file_path

    if not hash_to_path:
        return {}

    # Check all hashes at once
    duplicates = {}
    with get_db() as conn:
        # SQLite IN clause with many values
        placeholders = ','.join('?' * len(hash_to_path))
        query = f'''
            SELECT id, original_filename, submitted_at, status, file_path, content_hash
            FROM photos
            WHERE content_hash IN ({placeholders})
        '''
        results = conn.execute(query, list(hash_to_path.keys())).fetchall()

        for row in results:
            original_path = hash_to_path.get(row['content_hash'])
            if original_path:
                duplicates[original_path] = dict(row)
                logger.info(f"Duplicate: {original_path} matches photo {row['id']}")

    return duplicates


def get_or_compute_hash(photo_id: str, file_path: str) -> Optional[str]:
    """
    Get existing hash from database or compute and store it.

    Args:
        photo_id: Photo database ID
        file_path: Path to photo file

    Returns:
        Hash string or None
    """
    from app.database import get_db

    # Check if we already have a hash
    with get_db() as conn:
        existing = conn.execute(
            'SELECT content_hash FROM photos WHERE id = ?',
            (photo_id,)
        ).fetchone()

        if existing and existing['content_hash']:
            return existing['content_hash']

    # Compute hash
    file_hash = compute_file_hash(file_path)
    if not file_hash:
        return None

    # Store it
    with get_db() as conn:
        conn.execute(
            'UPDATE photos SET content_hash = ? WHERE id = ?',
            (file_hash, photo_id)
        )

    return file_hash


class DuplicateChecker:
    """
    Helper class for checking duplicates during batch imports.
    Caches hashes to avoid redundant database queries.
    """

    def __init__(self):
        self.known_hashes = set()
        self._load_existing_hashes()

    def _load_existing_hashes(self):
        """Load all existing photo hashes from database."""
        from app.database import get_db

        try:
            with get_db() as conn:
                rows = conn.execute(
                    'SELECT content_hash FROM photos WHERE content_hash IS NOT NULL'
                ).fetchall()
                self.known_hashes = {row['content_hash'] for row in rows}
                logger.info(f"Loaded {len(self.known_hashes)} existing photo hashes")
        except Exception as e:
            logger.warning(f"Could not load existing hashes: {e}")
            self.known_hashes = set()

    def is_duplicate(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if file is a duplicate.

        Args:
            file_path: Path to file to check

        Returns:
            Tuple of (is_duplicate, file_hash)
        """
        file_hash = compute_file_hash(file_path)
        if not file_hash:
            return False, None

        if file_hash in self.known_hashes:
            return True, file_hash

        return False, file_hash

    def add_hash(self, file_hash: str):
        """Add a hash to the known set (after successful import)."""
        if file_hash:
            self.known_hashes.add(file_hash)

    def check_batch(self, file_paths: list) -> Dict[str, bool]:
        """
        Check multiple files, returning which are duplicates.

        Returns:
            Dict mapping file_path -> is_duplicate
        """
        results = {}
        for file_path in file_paths:
            is_dup, _ = self.is_duplicate(file_path)
            results[file_path] = is_dup
        return results


# For testing
if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        for path in sys.argv[1:]:
            file_hash = compute_file_hash(path)
            print(f"{path}: {file_hash}")
    else:
        print("Usage: python duplicate_detector.py <file1> [file2] ...")
