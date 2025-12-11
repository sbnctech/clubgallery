"""
SBNC Photo Gallery System - Processing Pipeline
Orchestrate the full photo processing workflow.
"""

import uuid
import pickle
from datetime import datetime
from pathlib import Path
import logging

from app.database import get_db
from app.config import PhotoStatus, PHOTO_STORAGE_ROOT
from app.ingest.queue_manager import QueueManager
from app.processing.exif_extractor import ExifExtractor
from app.processing.event_matcher import EventMatcher
from app.processing.face_detector import FaceDetector
from app.processing.thumbnail_creator import ThumbnailCreator
from app.processing.tag_generator import TagGenerator, save_photo_tags
from app.processing.exif_writer import write_photo_metadata

logger = logging.getLogger(__name__)


class PhotoProcessor:
    """Process a single photo through the full pipeline."""

    def __init__(self, queue_item):
        """
        Initialize with a queue item.

        Args:
            queue_item: dict from processing_queue table
        """
        self.queue_item = queue_item
        self.photo_path = Path(queue_item['photo_path'])
        self.submitter_member_id = queue_item.get('submitter_member_id')
        self.submitter_email = queue_item.get('submitter_email')
        self.photo_id = str(uuid.uuid4())
        self.result = {}

    def process(self):
        """
        Run the full processing pipeline.

        Returns:
            dict with processing results
        """
        logger.info(f"Processing photo: {self.photo_path}")

        try:
            # 1. Extract EXIF metadata
            exif_data = self._extract_exif()

            # 2. Create thumbnails and save originals
            image_data = self._create_images()

            # 3. Match to event
            event_match = self._match_event(exif_data)

            # 4. Detect and recognize faces
            faces = self._process_faces(event_match)

            # 5. Generate tags
            tags = self._generate_tags(exif_data, event_match, faces)

            # 6. Save to database
            photo_record = self._save_photo_record(exif_data, image_data, event_match)

            # 7. Save faces to database
            self._save_faces(faces)

            # 8. Write tags to EXIF/XMP for portability
            self._write_exif_tags(image_data, exif_data, faces, tags, event_match)

            self.result = {
                'success': True,
                'photo_id': self.photo_id,
                'event_matched': event_match.get('event_id') is not None,
                'faces_detected': len(faces),
                'tags_generated': len(tags)
            }

            logger.info(f"Successfully processed photo {self.photo_id}")
            return self.result

        except Exception as e:
            logger.error(f"Failed to process photo {self.photo_path}: {e}")
            self.result = {
                'success': False,
                'error': str(e)
            }
            return self.result

    def _extract_exif(self):
        """Extract EXIF metadata."""
        extractor = ExifExtractor(self.photo_path)
        return extractor.extract()

    def _create_images(self):
        """Create thumbnails and store original."""
        creator = ThumbnailCreator(self.photo_path)
        return creator.process(self.photo_id)

    def _match_event(self, exif_data):
        """Match photo to an event."""
        matcher = EventMatcher()

        gps_coords = None
        if exif_data.get('gps_lat') and exif_data.get('gps_lon'):
            gps_coords = (exif_data['gps_lat'], exif_data['gps_lon'])

        return matcher.find_matching_event(
            photo_datetime=exif_data.get('taken_at'),
            gps_coords=gps_coords,
            submitter_member_id=self.submitter_member_id
        )

    def _process_faces(self, event_match):
        """Detect and recognize faces."""
        detector = FaceDetector()

        # Get event info for public event check
        is_public_event = False
        if event_match.get('event_id'):
            with get_db() as conn:
                event = conn.execute(
                    'SELECT is_public FROM events WHERE id = ?',
                    (event_match['event_id'],)
                ).fetchone()
                if event:
                    is_public_event = event['is_public']

        return detector.process_photo_faces(
            self.photo_path,
            event_id=event_match.get('event_id'),
            is_public_event=is_public_event
        )

    def _generate_tags(self, exif_data, event_match, faces):
        """Generate tags for the photo."""
        photo_data = {
            'taken_at': exif_data.get('taken_at'),
            'event_id': event_match.get('event_id'),
            'submitter_member_id': self.submitter_member_id,
            'faces': faces
        }

        generator = TagGenerator(photo_data)
        tags = generator.generate_all_tags()

        save_photo_tags(self.photo_id, tags)
        return tags

    def _save_photo_record(self, exif_data, image_data, event_match):
        """Save the photo record to the database."""
        with get_db() as conn:
            conn.execute('''
                INSERT INTO photos (
                    id, original_filename, submitter_member_id, submitter_email,
                    submitted_at, submitted_via,
                    taken_at, gps_lat, gps_lon, camera_make, camera_model,
                    event_id, event_match_confidence, event_match_method,
                    processed_at, status,
                    original_path, display_path, thumb_path,
                    width, height, file_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.photo_id,
                self.queue_item.get('original_filename'),
                self.submitter_member_id,
                self.submitter_email,
                self.queue_item.get('submitted_at'),
                self.queue_item.get('source', 'upload'),
                exif_data.get('taken_at'),
                exif_data.get('gps_lat'),
                exif_data.get('gps_lon'),
                exif_data.get('camera_make'),
                exif_data.get('camera_model'),
                event_match.get('event_id'),
                event_match.get('confidence'),
                event_match.get('match_method'),
                datetime.utcnow(),
                PhotoStatus.AWAITING_APPROVAL,
                image_data.get('original_path'),
                image_data.get('display_path'),
                image_data.get('thumb_path'),
                image_data.get('width'),
                image_data.get('height'),
                image_data.get('file_size')
            ))

        return self.photo_id

    def _save_faces(self, faces):
        """Save detected faces to the database."""
        import json

        with get_db() as conn:
            for face in faces:
                # Serialize candidates as JSON
                candidates_json = json.dumps(face.get('candidates', []))

                conn.execute('''
                    INSERT INTO photo_faces (
                        photo_id, box_top, box_right, box_bottom, box_left,
                        embedding, matched_member_id, match_confidence, match_rank,
                        candidates_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    self.photo_id,
                    face['box_top'],
                    face['box_right'],
                    face['box_bottom'],
                    face['box_left'],
                    pickle.dumps(face['embedding']),
                    face.get('matched_member_id'),
                    face.get('match_confidence'),
                    face.get('match_rank'),
                    candidates_json
                ))

    def _write_exif_tags(self, image_data, exif_data, faces, tags, event_match):
        """Write tags to the original photo's EXIF/XMP metadata."""
        try:
            # Get the original file path
            original_path = PHOTO_STORAGE_ROOT / image_data.get('original_path')

            # Get event details if matched
            event = None
            if event_match.get('event_id'):
                with get_db() as conn:
                    event_row = conn.execute(
                        'SELECT * FROM events WHERE id = ?',
                        (event_match['event_id'],)
                    ).fetchone()
                    if event_row:
                        event = dict(event_row)

            # Prepare photo data for EXIF writer
            photo_data = {
                'width': image_data.get('width'),
                'height': image_data.get('height')
            }

            # Write metadata to original
            write_photo_metadata(original_path, photo_data, faces, tags, event)
            logger.debug(f"Wrote EXIF tags to {original_path}")

        except Exception as e:
            # Don't fail the whole process if EXIF writing fails
            logger.warning(f"Failed to write EXIF tags: {e}")


def process_queue(batch_size=50):
    """
    Process pending items from the queue.

    Args:
        batch_size: Maximum number of items to process

    Returns:
        dict with processing statistics
    """
    queue = QueueManager()
    pending_items = queue.get_pending_items(limit=batch_size)

    stats = {
        'total': len(pending_items),
        'processed': 0,
        'failed': 0
    }

    for item in pending_items:
        queue_id = item['id']
        queue.mark_processing(queue_id)

        try:
            processor = PhotoProcessor(item)
            result = processor.process()

            if result['success']:
                queue.mark_completed(queue_id, result.get('photo_id'))
                stats['processed'] += 1

                # Clean up the source file
                source_path = Path(item['photo_path'])
                if source_path.exists():
                    source_path.unlink()
            else:
                queue.mark_failed(queue_id, result.get('error', 'Unknown error'))
                stats['failed'] += 1

        except Exception as e:
            queue.mark_failed(queue_id, str(e))
            stats['failed'] += 1
            logger.error(f"Queue item {queue_id} failed: {e}")

    logger.info(f"Queue processing complete: {stats}")
    return stats


def reprocess_photo(photo_id):
    """
    Reprocess an existing photo (e.g., to update face recognition).
    """
    with get_db() as conn:
        photo = conn.execute(
            'SELECT * FROM photos WHERE id = ?',
            (photo_id,)
        ).fetchone()

    if not photo:
        return {'success': False, 'error': 'Photo not found'}

    photo = dict(photo)
    original_path = PHOTO_STORAGE_ROOT / photo['original_path']

    if not original_path.exists():
        return {'success': False, 'error': 'Original file not found'}

    # Re-run face detection
    detector = FaceDetector()

    # Get event info
    is_public_event = False
    if photo.get('event_id'):
        with get_db() as conn:
            event = conn.execute(
                'SELECT is_public FROM events WHERE id = ?',
                (photo['event_id'],)
            ).fetchone()
            if event:
                is_public_event = event['is_public']

    faces = detector.process_photo_faces(
        original_path,
        event_id=photo.get('event_id'),
        is_public_event=is_public_event
    )

    # Clear existing unconfirmed faces
    with get_db() as conn:
        conn.execute('''
            DELETE FROM photo_faces
            WHERE photo_id = ? AND confirmed = FALSE
        ''', (photo_id,))

    # Save new faces
    import json
    with get_db() as conn:
        for face in faces:
            candidates_json = json.dumps(face.get('candidates', []))
            conn.execute('''
                INSERT INTO photo_faces (
                    photo_id, box_top, box_right, box_bottom, box_left,
                    embedding, matched_member_id, match_confidence, match_rank,
                    candidates_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                photo_id,
                face['box_top'],
                face['box_right'],
                face['box_bottom'],
                face['box_left'],
                pickle.dumps(face['embedding']),
                face.get('matched_member_id'),
                face.get('match_confidence'),
                face.get('match_rank'),
                candidates_json
            ))

    return {'success': True, 'faces_detected': len(faces)}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    process_queue()
