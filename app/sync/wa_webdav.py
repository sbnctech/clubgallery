"""
SBNC Photo Gallery System - WebDAV Backup
Sync photos from Wild Apricot's file storage via WebDAV.
"""

import os
from pathlib import Path
from datetime import datetime
import logging

from webdav3.client import Client

from app.config import (
    WA_WEBDAV_URL, WA_WEBDAV_USER, WA_WEBDAV_PASSWORD,
    PHOTO_STORAGE_ROOT
)

logger = logging.getLogger(__name__)


class WebDAVSync:
    """Sync files from Wild Apricot via WebDAV."""

    def __init__(self):
        self.webdav_url = WA_WEBDAV_URL
        self.username = WA_WEBDAV_USER
        self.password = WA_WEBDAV_PASSWORD
        self.local_backup_dir = PHOTO_STORAGE_ROOT / 'wa-backup'
        self.client = None

    def connect(self):
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
            # Test connection
            self.client.list('/')
            logger.info(f"Connected to WebDAV at {self.webdav_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebDAV: {e}")
            return False

    def sync_pictures_folder(self, remote_path='Resources/Pictures'):
        """
        Sync the Pictures folder from WA to local storage.

        Args:
            remote_path: Path to the pictures folder on WA WebDAV

        Returns:
            dict with sync statistics
        """
        if not self.client:
            if not self.connect():
                return {'success': False, 'error': 'Failed to connect'}

        stats = {
            'success': True,
            'files_checked': 0,
            'files_downloaded': 0,
            'files_skipped': 0,
            'errors': []
        }

        try:
            self._sync_directory(remote_path, self.local_backup_dir, stats)

            # Update sync status in database
            from app.database import get_db
            with get_db() as conn:
                conn.execute('''
                    UPDATE sync_status
                    SET last_sync_at = ?, last_sync_status = 'success',
                        items_synced = ?
                    WHERE sync_type = 'webdav'
                ''', (datetime.utcnow(), stats['files_downloaded']))

        except Exception as e:
            stats['success'] = False
            stats['errors'].append(str(e))
            logger.error(f"WebDAV sync failed: {e}")

        return stats

    def _sync_directory(self, remote_path, local_path, stats):
        """Recursively sync a directory."""
        local_path = Path(local_path)
        local_path.mkdir(parents=True, exist_ok=True)

        try:
            items = self.client.list(remote_path)
        except Exception as e:
            logger.error(f"Failed to list {remote_path}: {e}")
            stats['errors'].append(f"Failed to list {remote_path}")
            return

        for item in items:
            if item == '' or item == remote_path.split('/')[-1] + '/':
                continue

            remote_item_path = f"{remote_path}/{item}".replace('//', '/')
            local_item_path = local_path / item.rstrip('/')

            if item.endswith('/'):
                # It's a directory, recurse
                self._sync_directory(remote_item_path.rstrip('/'), local_item_path, stats)
            else:
                # It's a file
                stats['files_checked'] += 1
                self._sync_file(remote_item_path, local_item_path, stats)

    def _sync_file(self, remote_path, local_path, stats):
        """Sync a single file if it's newer or doesn't exist locally."""
        try:
            # Get remote file info
            remote_info = self.client.info(remote_path)
            remote_modified = remote_info.get('modified')

            # Check if local file exists and is up to date
            if local_path.exists():
                local_modified = datetime.fromtimestamp(local_path.stat().st_mtime)
                if remote_modified and local_modified >= datetime.fromisoformat(remote_modified.replace('Z', '+00:00').replace('+00:00', '')):
                    stats['files_skipped'] += 1
                    return

            # Download the file
            local_path.parent.mkdir(parents=True, exist_ok=True)
            self.client.download_sync(remote_path, str(local_path))
            stats['files_downloaded'] += 1
            logger.debug(f"Downloaded: {remote_path}")

        except Exception as e:
            logger.error(f"Failed to sync {remote_path}: {e}")
            stats['errors'].append(f"Failed to sync {remote_path}")

    def list_remote_photos(self, remote_path='Resources/Pictures'):
        """List all photos in the remote Pictures folder."""
        if not self.client:
            if not self.connect():
                return []

        photos = []
        self._collect_photos(remote_path, photos)
        return photos

    def _collect_photos(self, remote_path, photos, extensions={'.jpg', '.jpeg', '.png', '.heic'}):
        """Recursively collect photo file paths."""
        try:
            items = self.client.list(remote_path)
            for item in items:
                if item == '' or item.endswith('/'):
                    if item.endswith('/') and item != remote_path.split('/')[-1] + '/':
                        self._collect_photos(f"{remote_path}/{item}".rstrip('/'), photos, extensions)
                else:
                    ext = Path(item).suffix.lower()
                    if ext in extensions:
                        photos.append(f"{remote_path}/{item}")
        except Exception as e:
            logger.error(f"Failed to list {remote_path}: {e}")


def run_webdav_sync():
    """Run a WebDAV sync."""
    sync = WebDAVSync()
    return sync.sync_pictures_folder()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    result = run_webdav_sync()
    print(f"Sync result: {result}")
