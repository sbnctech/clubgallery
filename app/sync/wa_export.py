"""
SBNC Photo Gallery System - Export to Wild Apricot
Upload approved photos to WA file storage with proper folder structure.

IMPORTANT: This is for NEW photos going forward only.
Legacy photos in WA file storage should NOT be reorganized - many newsletters
and pages have hardcoded URLs to existing photo locations.

Folder structure for new exports: Pictures/{Term}/{Committee}/{Event_Name}
Example: Pictures/Fall_25/Arts_Committee/Arts_Better_Together_Gallery_Tours

Terms:
- Fall: July 1 - December 31 (Fall_YY)
- Spring: January 1 - June 30 (Spring_YY)

Target: Playground site (sbnc-website-redesign-playground.wildapricot.org)
"""

import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from webdav3.client import Client

from app.config import (
    WA_WEBDAV_URL, WA_WEBDAV_USER, WA_WEBDAV_PASSWORD,
    PHOTO_STORAGE_ROOT
)

logger = logging.getLogger(__name__)

# Base folder for photo exports in WA
WA_PICTURES_ROOT = 'Pictures'


def get_term_from_date(event_date) -> str:
    """
    Determine the SBNC term from a date.

    Terms:
    - Fall: July 1 - December 31 → "Fall_YY"
    - Spring: January 1 - June 30 → "Spring_YY"

    Args:
        event_date: datetime, date string (YYYY-MM-DD), or None

    Returns:
        Term string like "Fall_25" or "Spring_26"
    """
    if event_date is None:
        # Default to current term
        event_date = datetime.now()

    if isinstance(event_date, str):
        try:
            event_date = datetime.fromisoformat(event_date[:10])
        except ValueError:
            event_date = datetime.now()

    year = event_date.year
    month = event_date.month

    # Fall: July-December, Spring: January-June
    if month >= 7:
        term = "Fall"
        # Fall 2025 = Fall_25
        year_suffix = str(year)[-2:]
    else:
        term = "Spring"
        # Spring 2026 = Spring_26
        year_suffix = str(year)[-2:]

    return f"{term}_{year_suffix}"


def sanitize_folder_name(name: str, max_length: int = 80) -> str:
    """
    Sanitize a string for use as a folder name.

    - Replace spaces and special chars with underscores
    - Remove characters not safe for file systems
    - Collapse multiple underscores
    - Truncate to max_length

    Args:
        name: Original name string
        max_length: Maximum length for folder name

    Returns:
        Sanitized folder name
    """
    if not name:
        return "Unknown"

    # Replace common separators and special chars with underscores
    sanitized = re.sub(r'[\s\-:;,/\\|&~]+', '_', name)

    # Remove characters not safe for folder names
    sanitized = re.sub(r'[<>:"/\\|?*\'"!@#$%^(){}[\]]+', '', sanitized)

    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')

    # Truncate if too long (try to break at underscore)
    if len(sanitized) > max_length:
        truncated = sanitized[:max_length]
        # Try to break at last underscore
        last_underscore = truncated.rfind('_')
        if last_underscore > max_length // 2:
            truncated = truncated[:last_underscore]
        sanitized = truncated.rstrip('_')

    return sanitized or "Unknown"


def get_committee_folder_name(event: Dict) -> str:
    """
    Extract committee/activity group name for folder.

    Args:
        event: Event dict with 'activity_group' or 'committee' field

    Returns:
        Sanitized committee folder name like "Arts_Committee"
    """
    # Try different field names
    committee = (
        event.get('activity_group') or
        event.get('committee') or
        event.get('organizer') or
        'General'
    )

    # Clean up common patterns
    committee = str(committee)

    # Add "Committee" suffix if not present (for consistency)
    if not committee.lower().endswith('committee') and committee != 'General':
        # Check if it's an activity group name like "Arts" or "Travel"
        if '_' not in committee and len(committee) < 20:
            committee = f"{committee}_Committee"

    return sanitize_folder_name(committee)


def get_event_folder_name(event: Dict) -> str:
    """
    Create folder name from event title.

    Args:
        event: Event dict with 'name' or 'title' field

    Returns:
        Sanitized event folder name
    """
    event_name = event.get('name') or event.get('title') or 'Unknown_Event'
    return sanitize_folder_name(event_name)


def build_export_path(event: Dict, base_path: str = WA_PICTURES_ROOT) -> str:
    """
    Build the full WA folder path for a photo export.

    Structure: {base_path}/{Term}/{Committee}/{Event_Name}
    Example: Pictures/Fall_25/Arts_Committee/Arts_Better_Together_Gallery_Tours

    Args:
        event: Event dict with date, activity_group/committee, and name
        base_path: Base folder in WA (default: Pictures)

    Returns:
        Full folder path string
    """
    # Get term from event date
    event_date = event.get('start_date') or event.get('date') or event.get('event_date')
    term = get_term_from_date(event_date)

    # Get committee folder
    committee = get_committee_folder_name(event)

    # Get event folder
    event_folder = get_event_folder_name(event)

    # Build path
    path = f"{base_path}/{term}/{committee}/{event_folder}"

    # Clean up any double slashes
    path = re.sub(r'/+', '/', path)

    return path


class WAPhotoExporter:
    """Export approved photos to Wild Apricot file storage."""

    def __init__(self):
        self.webdav_url = WA_WEBDAV_URL
        self.username = WA_WEBDAV_USER
        self.password = WA_WEBDAV_PASSWORD
        self.client = None
        self._created_folders = set()  # Cache to avoid redundant mkdir calls

    def connect(self) -> bool:
        """Connect to the WebDAV server."""
        if not self.webdav_url:
            logger.warning("WebDAV URL not configured")
            return False

        options = {
            'webdav_hostname': self.webdav_url,
            'webdav_login': self.username,
            'webdav_password': self.password,
        }

        try:
            self.client = Client(options)
            self.client.list('/')
            logger.info(f"Connected to WebDAV at {self.webdav_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebDAV: {e}")
            return False

    def ensure_folder_exists(self, folder_path: str) -> bool:
        """
        Ensure a folder path exists, creating parent folders as needed.

        Args:
            folder_path: Full folder path like "Pictures/Fall_25/Arts_Committee"

        Returns:
            True if folder exists or was created
        """
        if folder_path in self._created_folders:
            return True

        if not self.client:
            if not self.connect():
                return False

        # Build path incrementally
        parts = folder_path.strip('/').split('/')
        current_path = ''

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part

            if current_path in self._created_folders:
                continue

            try:
                if not self.client.check(current_path):
                    logger.info(f"Creating folder: {current_path}")
                    self.client.mkdir(current_path)
                self._created_folders.add(current_path)
            except Exception as e:
                # Folder might already exist, try mkdir anyway
                try:
                    self.client.mkdir(current_path)
                    self._created_folders.add(current_path)
                except:
                    # If mkdir also fails, check if it exists
                    try:
                        if self.client.check(current_path):
                            self._created_folders.add(current_path)
                        else:
                            logger.error(f"Failed to create folder {current_path}: {e}")
                            return False
                    except:
                        logger.error(f"Failed to create folder {current_path}: {e}")
                        return False

        return True

    def export_photo(self, local_path: str, event: Dict,
                     overwrite: bool = False,
                     photo_data: Dict = None,
                     submitter_data: Dict = None) -> Tuple[bool, str]:
        """
        Export a single photo to WA with proper folder structure.

        Args:
            local_path: Path to the local photo file
            event: Event dict for folder path determination
            overwrite: Whether to overwrite existing files
            photo_data: Photo record for filename generation
            submitter_data: Submitter info for filename generation

        Returns:
            Tuple of (success: bool, remote_path: str)
        """
        local_path = Path(local_path)
        if not local_path.exists():
            logger.error(f"Photo not found: {local_path}")
            return False, ""

        # Build destination path
        folder_path = build_export_path(event)

        # Generate meaningful filename if we have photo data
        if photo_data:
            from app.processing.photo_naming import generate_export_filename_from_photo
            filename = generate_export_filename_from_photo(photo_data, submitter_data)
        else:
            filename = local_path.name

        remote_path = f"{folder_path}/{filename}"

        # Ensure folder exists
        if not self.ensure_folder_exists(folder_path):
            return False, ""

        # Check if file already exists
        if not overwrite:
            try:
                if self.client.check(remote_path):
                    logger.info(f"Skipping (exists): {remote_path}")
                    return True, remote_path  # Success but didn't upload
            except:
                pass

        # Upload
        try:
            logger.info(f"Uploading: {local_path.name} -> {remote_path}")
            self.client.upload_sync(str(local_path), remote_path)
            return True, remote_path
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False, ""

    def export_photos_for_event(self, photos: List[Dict], event: Dict,
                                overwrite: bool = False) -> Dict:
        """
        Export multiple photos for an event.

        Args:
            photos: List of photo dicts with 'path', 'photo_data', 'submitter_data'
                   Can also be list of strings (paths) for backwards compatibility
            event: Event dict
            overwrite: Whether to overwrite existing files

        Returns:
            Dict with export statistics
        """
        stats = {
            'total': len(photos),
            'uploaded': 0,
            'skipped': 0,
            'errors': 0,
            'folder_path': build_export_path(event),
            'uploaded_files': [],
            'exported_filenames': {},  # Maps local path to remote filename
            'error_files': []
        }

        if not self.client:
            if not self.connect():
                stats['errors'] = stats['total']
                return stats

        for photo in photos:
            # Support both dict and string (path) inputs
            if isinstance(photo, str):
                photo_path = photo
                photo_data = None
                submitter_data = None
            else:
                photo_path = photo.get('path')
                photo_data = photo.get('photo_data')
                submitter_data = photo.get('submitter_data')

            success, remote_path = self.export_photo(
                photo_path, event, overwrite, photo_data, submitter_data
            )
            if success:
                if remote_path:
                    stats['uploaded'] += 1
                    stats['uploaded_files'].append(remote_path)
                    stats['exported_filenames'][photo_path] = remote_path
                else:
                    stats['skipped'] += 1
            else:
                stats['errors'] += 1
                stats['error_files'].append(photo_path)

        return stats

    def export_approved_photos(self, overwrite: bool = False) -> Dict:
        """
        Export all approved photos that haven't been exported yet.

        Returns:
            Dict with export statistics
        """
        from app.database import get_db

        stats = {
            'events_processed': 0,
            'photos_uploaded': 0,
            'photos_skipped': 0,
            'photos_errors': 0,
            'by_event': []
        }

        if not self.client:
            if not self.connect():
                return stats

        with get_db() as conn:
            # Get approved photos with full details for renaming
            photos = conn.execute('''
                SELECT p.id, p.file_path, p.original_filename, p.taken_at,
                       p.event_id, p.submitter_member_id, p.submitter_email,
                       e.name as event_name, e.start_date, e.activity_group,
                       m.display_name as submitter_name
                FROM photos p
                LEFT JOIN events e ON p.event_id = e.id
                LEFT JOIN members m ON p.submitter_member_id = m.id
                WHERE p.status = 'approved'
                  AND (p.exported_to_wa IS NULL OR p.exported_to_wa = 0)
                ORDER BY e.start_date, e.name
            ''').fetchall()

        if not photos:
            logger.info("No photos to export")
            return stats

        # Group by event, keeping full photo data
        events = {}
        for photo in photos:
            event_id = photo['event_id'] or 'no_event'
            if event_id not in events:
                events[event_id] = {
                    'event': {
                        'id': photo['event_id'],
                        'name': photo['event_name'] or 'Miscellaneous',
                        'start_date': photo['start_date'],
                        'activity_group': photo['activity_group'] or 'General'
                    },
                    'photos': []
                }
            events[event_id]['photos'].append({
                'id': photo['id'],
                'path': photo['file_path'],
                'photo_data': {
                    'id': photo['id'],
                    'original_filename': photo['original_filename'],
                    'taken_at': photo['taken_at'],
                    'event_date': photo['start_date']
                },
                'submitter_data': {
                    'display_name': photo['submitter_name']
                } if photo['submitter_name'] else None
            })

        # Export each event's photos
        for event_id, data in events.items():
            event = data['event']
            photos_to_export = data['photos']  # Full photo dicts with data

            event_stats = self.export_photos_for_event(photos_to_export, event, overwrite)

            stats['events_processed'] += 1
            stats['photos_uploaded'] += event_stats['uploaded']
            stats['photos_skipped'] += event_stats['skipped']
            stats['photos_errors'] += event_stats['errors']
            stats['by_event'].append({
                'event_name': event['name'],
                'folder': event_stats['folder_path'],
                **event_stats
            })

            # Mark successfully uploaded photos with their new filenames
            if event_stats['uploaded'] > 0:
                with get_db() as conn:
                    for photo in photos_to_export:
                        photo_path = photo['path']
                        photo_id = photo['id']
                        if photo_path not in event_stats.get('error_files', []):
                            # Get the actual exported path (with renamed filename)
                            remote_path = event_stats['exported_filenames'].get(photo_path)
                            if remote_path:
                                conn.execute('''
                                    UPDATE photos
                                    SET exported_to_wa = 1, exported_at = ?, wa_export_path = ?
                                    WHERE id = ?
                                ''', (datetime.utcnow(), remote_path, photo_id))

        return stats


def export_photo_to_wa(photo_path: str, event: Dict,
                       overwrite: bool = False) -> Tuple[bool, str]:
    """
    Convenience function to export a single photo.

    Args:
        photo_path: Path to local photo
        event: Event dict
        overwrite: Whether to overwrite existing

    Returns:
        Tuple of (success, remote_path)
    """
    exporter = WAPhotoExporter()
    return exporter.export_photo(photo_path, event, overwrite)


def run_export():
    """Run export of all approved photos."""
    exporter = WAPhotoExporter()
    return exporter.export_approved_photos()


# For testing path generation
if __name__ == '__main__':
    # Test cases
    test_events = [
        {
            'name': 'Arts: Better Together ~ Gallery Tours with Colette Cosentino & Peter Horjus',
            'start_date': '2025-09-15',
            'activity_group': 'Arts'
        },
        {
            'name': 'Travel: Day Trip to Ojai Wine Country',
            'start_date': '2025-03-20',
            'activity_group': 'Travel'
        },
        {
            'name': 'New Member Coffee & Orientation',
            'start_date': '2025-11-05',
            'activity_group': 'Membership'
        },
    ]

    print("Export Path Examples:")
    print("-" * 60)
    for event in test_events:
        path = build_export_path(event)
        print(f"Event: {event['name'][:50]}...")
        print(f"Date:  {event['start_date']}")
        print(f"Path:  {path}")
        print()
