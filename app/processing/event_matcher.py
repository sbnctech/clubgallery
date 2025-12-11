"""
SBNC Photo Gallery System - Event Matching
Match photos to SBNC events based on date, GPS, and submitter RSVPs.
"""

from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
import logging

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

from app.database import get_db
from app.config import (
    EVENT_MATCH_HIGH_CONFIDENCE_METERS,
    EVENT_MATCH_MEDIUM_CONFIDENCE_METERS,
    GOOGLE_MAPS_API_KEY,
    USE_GOOGLE_GEOCODING
)

logger = logging.getLogger(__name__)

# Geocoder for converting addresses to coordinates
geocoder = Nominatim(user_agent="sbnc-photos")


class EventMatcher:
    """Match photos to SBNC events."""

    def __init__(self):
        self.geocode_cache = {}

    def find_matching_event(self, photo_datetime, gps_coords=None, submitter_member_id=None):
        """
        Find the best matching event for a photo.

        Args:
            photo_datetime: When the photo was taken
            gps_coords: (lat, lon) tuple or None
            submitter_member_id: WA member ID of submitter

        Returns:
            dict with event_id, confidence, and match_method
        """
        if not photo_datetime:
            return self._no_match("No photo datetime available")

        # Get candidate events from the same day (±1 day for multi-day events)
        candidates = self._get_candidate_events(photo_datetime)

        if not candidates:
            return self._no_match("No events found for this date")

        best_match = None
        best_score = 0

        for event in candidates:
            score, method = self._score_event(
                event, photo_datetime, gps_coords, submitter_member_id
            )
            if score > best_score:
                best_score = score
                best_match = {
                    'event_id': event['id'],
                    'event_name': event['name'],
                    'confidence': score,
                    'match_method': method
                }

        if best_match and best_match['confidence'] >= 0.3:
            return best_match

        # If no good GPS match, check if submitter was registered for any event that day
        if submitter_member_id:
            rsvp_match = self._check_submitter_rsvp(candidates, submitter_member_id)
            if rsvp_match:
                return rsvp_match

        return self._no_match("No confident match found")

    def _get_candidate_events(self, photo_datetime):
        """Get events that could match the photo's datetime."""
        photo_date = photo_datetime.date()
        date_range_start = photo_date - timedelta(days=1)
        date_range_end = photo_date + timedelta(days=1)

        with get_db() as conn:
            rows = conn.execute('''
                SELECT id, name, start_date, end_date, location_name, location_address,
                       location_lat, location_lon, activity_group, is_public
                FROM events
                WHERE date(start_date) BETWEEN date(?) AND date(?)
                   OR date(end_date) BETWEEN date(?) AND date(?)
                   OR (date(start_date) <= date(?) AND date(end_date) >= date(?))
            ''', (
                date_range_start.isoformat(),
                date_range_end.isoformat(),
                date_range_start.isoformat(),
                date_range_end.isoformat(),
                photo_date.isoformat(),
                photo_date.isoformat()
            )).fetchall()

            return [dict(row) for row in rows]

    def _score_event(self, event, photo_datetime, gps_coords, submitter_member_id):
        """
        Score how well an event matches the photo.

        Returns:
            (score, method) tuple where score is 0.0-1.0
        """
        # Start with date match
        score = 0.5  # Base score for date match
        method = 'date'

        # If we have GPS, check distance
        if gps_coords:
            event_coords = self._get_event_coordinates(event)
            if event_coords:
                distance = self._calculate_distance(gps_coords, event_coords)

                if distance <= EVENT_MATCH_HIGH_CONFIDENCE_METERS:
                    score = 0.95
                    method = 'gps_high'
                elif distance <= EVENT_MATCH_MEDIUM_CONFIDENCE_METERS:
                    score = 0.75
                    method = 'gps_medium'
                else:
                    # Too far, reduce score
                    score = 0.3
                    method = 'gps_low'

        # Boost score if submitter was registered for this event
        if submitter_member_id:
            if self._is_registered(event['id'], submitter_member_id):
                score = min(score + 0.2, 0.95)
                method = f"{method}+rsvp"

        return score, method

    def _get_event_coordinates(self, event):
        """Get GPS coordinates for an event (from cache or geocoding)."""
        # Check if coordinates are already in the event
        if event.get('location_lat') and event.get('location_lon'):
            return (event['location_lat'], event['location_lon'])

        # Try to geocode the address
        address = event.get('location_address') or event.get('location_name')
        if not address:
            return None

        # Check cache
        if address in self.geocode_cache:
            return self.geocode_cache[address]

        try:
            # Add "Santa Barbara, CA" if not present for better results
            if 'santa barbara' not in address.lower():
                address = f"{address}, Santa Barbara, CA"

            location = geocoder.geocode(address, timeout=10)
            if location:
                coords = (location.latitude, location.longitude)
                self.geocode_cache[address] = coords

                # Update database with coordinates
                self._update_event_coordinates(event['id'], coords)

                return coords

        except GeocoderTimedOut:
            logger.warning(f"Geocoding timeout for: {address}")
        except Exception as e:
            logger.error(f"Geocoding error for {address}: {e}")

        self.geocode_cache[address] = None
        return None

    def _update_event_coordinates(self, event_id, coords):
        """Update event with geocoded coordinates."""
        with get_db() as conn:
            conn.execute('''
                UPDATE events
                SET location_lat = ?, location_lon = ?
                WHERE id = ?
            ''', (coords[0], coords[1], event_id))

    def _calculate_distance(self, coord1, coord2):
        """
        Calculate distance between two GPS coordinates in meters.
        Uses the Haversine formula.
        """
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        R = 6371000  # Earth's radius in meters

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def _is_registered(self, event_id, member_id):
        """Check if a member is registered for an event."""
        with get_db() as conn:
            row = conn.execute('''
                SELECT 1 FROM event_registrations
                WHERE event_id = ? AND member_id = ?
            ''', (event_id, member_id)).fetchone()
            return row is not None

    def _check_submitter_rsvp(self, candidates, member_id):
        """Check if submitter was registered for any candidate event."""
        for event in candidates:
            if self._is_registered(event['id'], member_id):
                return {
                    'event_id': event['id'],
                    'event_name': event['name'],
                    'confidence': 0.6,
                    'match_method': 'submitter_rsvp'
                }
        return None

    def _no_match(self, reason):
        """Return a no-match result."""
        return {
            'event_id': None,
            'event_name': None,
            'confidence': 0.0,
            'match_method': 'none',
            'reason': reason
        }


def match_photo_to_event(photo_datetime, gps_coords=None, submitter_member_id=None):
    """Convenience function to match a photo to an event."""
    matcher = EventMatcher()
    return matcher.find_matching_event(photo_datetime, gps_coords, submitter_member_id)
