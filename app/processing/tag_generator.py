"""
SBNC Photo Gallery System - Tag Generation
Generate searchable tags for photos based on metadata.
"""

import re
from datetime import datetime
import logging

from app.database import get_db

logger = logging.getLogger(__name__)


class TagGenerator:
    """Generate tags for photos."""

    def __init__(self, photo_data):
        """
        Initialize with photo data.

        Args:
            photo_data: dict with photo metadata including:
                - taken_at: datetime
                - event_id: event ID if matched
                - submitter_member_id: who submitted
                - faces: list of detected/identified faces
        """
        self.photo_data = photo_data
        self.tags = []

    def generate_all_tags(self):
        """Generate all tags for the photo."""
        self.tags = []

        # Date-based tags
        if self.photo_data.get('taken_at'):
            self._add_date_tags(self.photo_data['taken_at'])

        # Event-based tags
        if self.photo_data.get('event_id'):
            self._add_event_tags(self.photo_data['event_id'])

        # Person tags from faces
        if self.photo_data.get('faces'):
            self._add_person_tags(self.photo_data['faces'])

        # Submitter tag
        if self.photo_data.get('submitter_member_id'):
            self._add_submitter_tag(self.photo_data['submitter_member_id'])

        return self.tags

    def _add_date_tags(self, taken_at):
        """Add date-based tags."""
        if isinstance(taken_at, str):
            taken_at = datetime.fromisoformat(taken_at)

        # Year tag
        self.tags.append({
            'tag': str(taken_at.year),
            'tag_type': 'date'
        })

        # Month-Year tag (e.g., "Nov2024")
        month_year = taken_at.strftime('%b%Y')
        self.tags.append({
            'tag': month_year,
            'tag_type': 'date'
        })

    def _add_event_tags(self, event_id):
        """Add event and activity tags."""
        with get_db() as conn:
            event = conn.execute('''
                SELECT name, activity_group, location_name
                FROM events WHERE id = ?
            ''', (event_id,)).fetchone()

        if not event:
            return

        # Event name tag (sanitized)
        event_tag = self._sanitize_tag(event['name'])
        if event_tag:
            self.tags.append({
                'tag': event_tag,
                'tag_type': 'event'
            })

        # Activity group tag
        if event['activity_group']:
            activity_tag = self._sanitize_tag(event['activity_group'])
            if activity_tag:
                self.tags.append({
                    'tag': activity_tag,
                    'tag_type': 'activity'
                })

        # Location tag
        if event['location_name']:
            location_tag = self._sanitize_tag(event['location_name'])
            if location_tag:
                self.tags.append({
                    'tag': location_tag,
                    'tag_type': 'location'
                })

    def _add_person_tags(self, faces):
        """Add tags for identified people."""
        for face in faces:
            member_id = face.get('confirmed_member_id') or face.get('matched_member_id')
            if member_id and not face.get('is_guest'):
                with get_db() as conn:
                    member = conn.execute(
                        'SELECT display_name FROM members WHERE id = ?',
                        (member_id,)
                    ).fetchone()

                if member:
                    person_tag = self._sanitize_tag(member['display_name'])
                    if person_tag:
                        self.tags.append({
                            'tag': person_tag,
                            'tag_type': 'person'
                        })

    def _add_submitter_tag(self, member_id):
        """Add tag for who submitted the photo."""
        with get_db() as conn:
            member = conn.execute(
                'SELECT display_name FROM members WHERE id = ?',
                (member_id,)
            ).fetchone()

        if member:
            submitter_tag = f"SubmittedBy{self._sanitize_tag(member['display_name'])}"
            self.tags.append({
                'tag': submitter_tag,
                'tag_type': 'submitter'
            })

    def _sanitize_tag(self, text):
        """
        Sanitize text for use as a tag.
        Converts to CamelCase and removes special characters.
        """
        if not text:
            return None

        # Split on spaces and special characters
        words = re.split(r'[\s\-_,./]+', text)

        # Capitalize each word and join
        camel = ''.join(word.capitalize() for word in words if word)

        # Remove any remaining non-alphanumeric characters
        camel = re.sub(r'[^a-zA-Z0-9]', '', camel)

        # Limit length
        return camel[:30] if camel else None


def save_photo_tags(photo_id, tags, auto_generated=True):
    """Save tags for a photo to the database."""
    with get_db() as conn:
        for tag in tags:
            conn.execute('''
                INSERT OR IGNORE INTO photo_tags (photo_id, tag, tag_type, auto_generated)
                VALUES (?, ?, ?, ?)
            ''', (photo_id, tag['tag'], tag['tag_type'], auto_generated))


def get_photo_tags(photo_id):
    """Get all tags for a photo."""
    with get_db() as conn:
        rows = conn.execute('''
            SELECT tag, tag_type, auto_generated
            FROM photo_tags
            WHERE photo_id = ?
            ORDER BY tag_type, tag
        ''', (photo_id,)).fetchall()
        return [dict(row) for row in rows]


def generate_and_save_tags(photo_id, taken_at, event_id, submitter_member_id, faces):
    """
    Generate and save all tags for a photo.

    This is a convenience function for the processing pipeline.
    """
    photo_data = {
        'taken_at': taken_at,
        'event_id': event_id,
        'submitter_member_id': submitter_member_id,
        'faces': faces
    }

    generator = TagGenerator(photo_data)
    tags = generator.generate_all_tags()

    save_photo_tags(photo_id, tags)
    return tags
