"""
SBNC Photo Gallery System - Web Upload Handler
Handle photo uploads via the web interface.
"""

import uuid
from datetime import datetime
from pathlib import Path
import logging

from werkzeug.utils import secure_filename
from PIL import Image
import pillow_heif

from app.config import PHOTO_STORAGE_ROOT, SUPPORTED_IMAGE_EXTENSIONS
from app.database import get_db

logger = logging.getLogger(__name__)

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()


class UploadHandler:
    """Handle web-based photo uploads."""

    def __init__(self, member_id, member_email):
        self.member_id = member_id
        self.member_email = member_email
        self.queue_dir = PHOTO_STORAGE_ROOT / 'queue' / datetime.now().strftime('%Y/%m')
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def process_upload(self, file_storage, event_id=None):
        """
        Process a single uploaded file.

        Args:
            file_storage: Werkzeug FileStorage object
            event_id: Optional pre-selected event ID

        Returns:
            dict with success status and details
        """
        result = {
            'success': False,
            'filename': None,
            'queue_id': None,
            'error': None
        }

        try:
            # Get original filename
            original_filename = secure_filename(file_storage.filename)
            result['filename'] = original_filename

            # Validate file extension
            ext = Path(original_filename).suffix.lower()
            if ext not in SUPPORTED_IMAGE_EXTENSIONS:
                result['error'] = f"Unsupported file type: {ext}"
                return result

            # Generate unique filename
            unique_name = f"{uuid.uuid4()}{ext}"
            file_path = self.queue_dir / unique_name

            # Save the file
            file_storage.save(str(file_path))
            logger.info(f"Saved upload: {file_path}")

            # Convert HEIC to JPG if needed
            if ext in {'.heic', '.heif'}:
                jpg_path = self._convert_heic_to_jpg(file_path)
                if jpg_path:
                    file_path.unlink()  # Remove original HEIC
                    file_path = jpg_path

            # Validate it's a real image
            try:
                with Image.open(file_path) as img:
                    img.verify()
            except Exception as e:
                file_path.unlink()
                result['error'] = f"Invalid image file: {e}"
                return result

            # Check for duplicates
            from app.processing.duplicate_detector import check_duplicate
            is_duplicate, existing_photo = check_duplicate(str(file_path))
            if is_duplicate:
                file_path.unlink()  # Remove the duplicate
                result['error'] = f"Duplicate photo - already imported as {existing_photo.get('original_filename', 'unknown')}"
                result['duplicate_of'] = existing_photo.get('id')
                logger.info(f"Rejected duplicate upload: {original_filename}")
                return result

            # Add to processing queue
            queue_id = self._add_to_queue(str(file_path), original_filename, event_id)
            result['queue_id'] = queue_id
            result['success'] = True

        except Exception as e:
            logger.error(f"Upload processing failed: {e}")
            result['error'] = str(e)

        return result

    def process_multiple_uploads(self, files, event_id=None):
        """
        Process multiple uploaded files.

        Args:
            files: List of Werkzeug FileStorage objects
            event_id: Optional pre-selected event ID

        Returns:
            dict with overall status and individual results
        """
        results = []
        for file in files:
            if file and file.filename:
                result = self.process_upload(file, event_id)
                results.append(result)

        successful = sum(1 for r in results if r['success'])
        return {
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'results': results
        }

    def _convert_heic_to_jpg(self, heic_path):
        """Convert HEIC file to JPG."""
        try:
            jpg_path = heic_path.with_suffix('.jpg')
            with Image.open(heic_path) as img:
                # Convert to RGB if necessary (HEIC might be RGBA)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.save(jpg_path, 'JPEG', quality=95)
            logger.info(f"Converted HEIC to JPG: {jpg_path}")
            return jpg_path
        except Exception as e:
            logger.error(f"HEIC conversion failed: {e}")
            return None

    def _add_to_queue(self, file_path, original_filename, event_id=None):
        """Add a photo to the processing queue."""
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO processing_queue
                (photo_path, submitter_email, submitter_member_id, source, original_filename, status)
                VALUES (?, ?, ?, 'upload', ?, 'pending')
            ''', (file_path, self.member_email, self.member_id, original_filename))
            return cursor.lastrowid


def get_upload_progress(batch_id):
    """Get the processing progress for an upload batch."""
    # TODO: Implement batch tracking
    pass
