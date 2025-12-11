"""
SBNC Photo Gallery System - Face Detection and Recognition
Detect faces in photos and match them to SBNC members.
"""

import json
from pathlib import Path
import logging
import pickle

import numpy as np
import face_recognition

from app.database import get_db
from app.config import (
    FACE_MATCH_HIGH_CONFIDENCE,
    FACE_MATCH_MEDIUM_CONFIDENCE,
    FACE_MATCH_PUBLIC_EVENT_THRESHOLD
)

logger = logging.getLogger(__name__)


class FaceDetector:
    """Detect and recognize faces in photos."""

    def __init__(self):
        self._member_embeddings = None
        self._member_lookup = None

    def load_member_embeddings(self, member_ids=None):
        """
        Load face embeddings for members.

        Args:
            member_ids: Optional list of member IDs to load (e.g., event RSVPs)
                       If None, loads all embeddings.
        """
        with get_db() as conn:
            if member_ids:
                placeholders = ','.join('?' * len(member_ids))
                rows = conn.execute(f'''
                    SELECT fe.id, fe.member_id, fe.embedding, m.display_name
                    FROM face_embeddings fe
                    JOIN members m ON fe.member_id = m.id
                    WHERE fe.member_id IN ({placeholders})
                    AND m.face_recognition_opt_out = FALSE
                ''', member_ids).fetchall()
            else:
                rows = conn.execute('''
                    SELECT fe.id, fe.member_id, fe.embedding, m.display_name
                    FROM face_embeddings fe
                    JOIN members m ON fe.member_id = m.id
                    WHERE m.face_recognition_opt_out = FALSE
                ''').fetchall()

        self._member_embeddings = []
        self._member_lookup = []

        for row in rows:
            embedding = pickle.loads(row['embedding'])
            self._member_embeddings.append(embedding)
            self._member_lookup.append({
                'embedding_id': row['id'],
                'member_id': row['member_id'],
                'display_name': row['display_name']
            })

        logger.info(f"Loaded {len(self._member_embeddings)} face embeddings")

    def detect_faces(self, image_path):
        """
        Detect all faces in an image.

        Returns:
            List of dicts with face locations and embeddings
        """
        try:
            # Load image
            image = face_recognition.load_image_file(image_path)

            # Detect face locations
            face_locations = face_recognition.face_locations(image, model='hog')

            if not face_locations:
                logger.debug(f"No faces found in {image_path}")
                return []

            # Get face encodings (embeddings)
            face_encodings = face_recognition.face_encodings(image, face_locations)

            faces = []
            for location, encoding in zip(face_locations, face_encodings):
                top, right, bottom, left = location
                faces.append({
                    'box_top': top,
                    'box_right': right,
                    'box_bottom': bottom,
                    'box_left': left,
                    'embedding': encoding
                })

            logger.info(f"Detected {len(faces)} faces in {image_path}")
            return faces

        except Exception as e:
            logger.error(f"Face detection failed for {image_path}: {e}")
            return []

    def match_face(self, face_embedding, is_public_event=False, rsvp_member_ids=None):
        """
        Match a face embedding to known members.

        Args:
            face_embedding: 128-dim numpy array
            is_public_event: If True, use stricter thresholds
            rsvp_member_ids: List of member IDs to prioritize (event attendees)

        Returns:
            dict with match results and candidates
        """
        if self._member_embeddings is None:
            self.load_member_embeddings()

        if not self._member_embeddings:
            return {
                'matched_member_id': None,
                'match_confidence': None,
                'match_rank': None,
                'candidates': []
            }

        # Calculate distances to all known faces
        distances = face_recognition.face_distance(
            self._member_embeddings,
            face_embedding
        )

        # Create candidate list with distances
        candidates = []
        for i, distance in enumerate(distances):
            member_info = self._member_lookup[i]
            candidates.append({
                'member_id': member_info['member_id'],
                'display_name': member_info['display_name'],
                'distance': float(distance),
                'confidence': self._distance_to_confidence(distance),
                'is_rsvp': member_info['member_id'] in (rsvp_member_ids or [])
            })

        # Sort by distance (lower is better)
        candidates.sort(key=lambda x: x['distance'])

        # Prioritize RSVP members if close enough
        if rsvp_member_ids:
            rsvp_candidates = [c for c in candidates if c['is_rsvp']]
            if rsvp_candidates:
                # If best RSVP candidate is within reasonable range, boost it
                best_rsvp = rsvp_candidates[0]
                best_overall = candidates[0]
                if best_rsvp['distance'] < FACE_MATCH_MEDIUM_CONFIDENCE:
                    # Only boost if RSVP candidate is close
                    if best_rsvp['distance'] <= best_overall['distance'] + 0.1:
                        candidates = rsvp_candidates + [c for c in candidates if not c['is_rsvp']]

        # Determine match threshold
        if is_public_event:
            high_threshold = FACE_MATCH_PUBLIC_EVENT_THRESHOLD
        else:
            high_threshold = FACE_MATCH_HIGH_CONFIDENCE

        # Get top candidate
        top = candidates[0] if candidates else None
        matched_member_id = None
        match_rank = None

        if top and top['distance'] <= FACE_MATCH_MEDIUM_CONFIDENCE:
            matched_member_id = top['member_id']
            match_rank = 1

        return {
            'matched_member_id': matched_member_id,
            'match_confidence': 1 - top['distance'] if top else None,
            'match_rank': match_rank,
            'candidates': candidates[:5],  # Top 5 candidates
            'is_high_confidence': top['distance'] <= high_threshold if top else False
        }

    def _distance_to_confidence(self, distance):
        """Convert face distance to a confidence percentage."""
        # Distance of 0 = 100% confidence
        # Distance of 0.6 = 0% confidence (typical threshold)
        if distance >= 0.6:
            return 0.0
        return round((1 - distance / 0.6) * 100, 1)

    def process_photo_faces(self, image_path, event_id=None, is_public_event=False):
        """
        Detect faces in a photo and match them to members.

        Args:
            image_path: Path to the image
            event_id: Optional event ID for RSVP prioritization
            is_public_event: If True, use stricter thresholds

        Returns:
            List of face dicts with matches
        """
        # Get RSVP list if event specified
        rsvp_member_ids = None
        if event_id:
            rsvp_member_ids = self._get_event_rsvp_members(event_id)
            if rsvp_member_ids:
                # Preload just these embeddings for faster matching
                self.load_member_embeddings(rsvp_member_ids)

        # Detect faces
        faces = self.detect_faces(image_path)

        # Match each face
        results = []
        for face in faces:
            match = self.match_face(
                face['embedding'],
                is_public_event=is_public_event,
                rsvp_member_ids=rsvp_member_ids
            )

            results.append({
                'box_top': face['box_top'],
                'box_right': face['box_right'],
                'box_bottom': face['box_bottom'],
                'box_left': face['box_left'],
                'embedding': face['embedding'],
                'matched_member_id': match['matched_member_id'],
                'match_confidence': match['match_confidence'],
                'match_rank': match['match_rank'],
                'candidates': match['candidates'],
                'is_high_confidence': match['is_high_confidence']
            })

        return results

    def _get_event_rsvp_members(self, event_id):
        """Get list of member IDs registered for an event."""
        with get_db() as conn:
            rows = conn.execute('''
                SELECT member_id FROM event_registrations
                WHERE event_id = ?
            ''', (event_id,)).fetchall()
            return [row['member_id'] for row in rows]


def build_face_database_from_profiles():
    """
    Build the face embeddings database from member profile photos.
    This is a one-time setup or periodic refresh task.
    """
    import requests
    from PIL import Image
    from io import BytesIO

    logger.info("Building face database from member profiles...")

    with get_db() as conn:
        # Get members with profile or directory photos
        rows = conn.execute('''
            SELECT id, display_name, profile_photo_url, directory_headshot_url
            FROM members
            WHERE face_recognition_opt_out = FALSE
            AND (profile_photo_url IS NOT NULL OR directory_headshot_url IS NOT NULL)
        ''').fetchall()

    processed = 0
    failed = 0

    for row in rows:
        member = dict(row)
        # Prefer directory headshot over profile photo
        photo_url = member.get('directory_headshot_url') or member.get('profile_photo_url')
        source = 'directory' if member.get('directory_headshot_url') else 'profile'

        if not photo_url:
            continue

        try:
            # Download the photo
            response = requests.get(photo_url, timeout=30)
            response.raise_for_status()

            # Load as image
            img = Image.open(BytesIO(response.content))

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Save temporarily
            temp_path = f"/tmp/face_build_{member['id']}.jpg"
            img.save(temp_path, 'JPEG')

            # Detect face
            image = face_recognition.load_image_file(temp_path)
            face_locations = face_recognition.face_locations(image)

            if len(face_locations) == 1:
                # Found exactly one face - good
                encoding = face_recognition.face_encodings(image, face_locations)[0]

                with get_db() as conn:
                    # Check if embedding already exists
                    existing = conn.execute('''
                        SELECT id FROM face_embeddings
                        WHERE member_id = ? AND source = ?
                    ''', (member['id'], source)).fetchone()

                    if existing:
                        conn.execute('''
                            UPDATE face_embeddings
                            SET embedding = ?
                            WHERE id = ?
                        ''', (pickle.dumps(encoding), existing['id']))
                    else:
                        conn.execute('''
                            INSERT INTO face_embeddings (member_id, embedding, source)
                            VALUES (?, ?, ?)
                        ''', (member['id'], pickle.dumps(encoding), source))

                processed += 1
                logger.debug(f"Added face for {member['display_name']}")

            elif len(face_locations) == 0:
                logger.warning(f"No face found in photo for {member['display_name']}")
                failed += 1
            else:
                logger.warning(f"Multiple faces in photo for {member['display_name']}")
                failed += 1

            # Cleanup temp file
            Path(temp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to process {member['display_name']}: {e}")
            failed += 1

    logger.info(f"Face database build complete: {processed} processed, {failed} failed")
    return {'processed': processed, 'failed': failed}


def save_confirmed_face_embedding(photo_face_id, member_id):
    """
    Save a confirmed face from a photo as a new embedding for the member.
    This improves recognition over time as admins confirm faces.
    """
    with get_db() as conn:
        # Get the face embedding
        face = conn.execute('''
            SELECT embedding FROM photo_faces WHERE id = ?
        ''', (photo_face_id,)).fetchone()

        if not face:
            return False

        # Add as a new confirmed embedding
        conn.execute('''
            INSERT INTO face_embeddings (member_id, embedding, source)
            VALUES (?, ?, 'confirmed')
        ''', (member_id, face['embedding']))

        return True
