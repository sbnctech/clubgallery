"""
SBNC Photo Gallery System - Member/Event Sync
Synchronize members, events, and registrations from Wild Apricot.
"""

from datetime import datetime, timedelta
import logging
import requests
from io import BytesIO

from app.database import get_db
from app.sync.wa_api import get_wa_api

logger = logging.getLogger(__name__)


class MemberSync:
    """Sync members from Wild Apricot to local database."""

    def __init__(self):
        self.api = get_wa_api()

    def sync_all_members(self):
        """Sync all active members from WA."""
        logger.info("Starting member sync...")
        start_time = datetime.utcnow()

        try:
            members = self.api.get_all_active_members()
            logger.info(f"Retrieved {len(members)} members from WA")

            synced = 0
            with get_db() as conn:
                for member in members:
                    self._upsert_member(conn, member)
                    synced += 1

                # Update sync status
                conn.execute('''
                    UPDATE sync_status
                    SET last_sync_at = ?, last_sync_status = 'success', items_synced = ?
                    WHERE sync_type = 'members'
                ''', (datetime.utcnow(), synced))

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Member sync complete: {synced} members in {elapsed:.1f}s")
            return synced

        except Exception as e:
            logger.error(f"Member sync failed: {e}")
            with get_db() as conn:
                conn.execute('''
                    UPDATE sync_status
                    SET last_sync_at = ?, last_sync_status = 'failed', last_error = ?
                    WHERE sync_type = 'members'
                ''', (datetime.utcnow(), str(e)))
            raise

    def _upsert_member(self, conn, member):
        """Insert or update a member record."""
        # Extract profile photo URL
        profile_photo_url = None
        directory_headshot_url = None

        for field in member.get('FieldValues', []):
            system_code = field.get('SystemCode', '')
            if system_code == 'Photo':
                value = field.get('Value')
                if isinstance(value, dict):
                    profile_photo_url = value.get('Url')
            # Check for directory headshot field (custom field name may vary)
            if 'headshot' in field.get('FieldName', '').lower():
                value = field.get('Value')
                if isinstance(value, dict):
                    directory_headshot_url = value.get('Url')

        conn.execute('''
            INSERT INTO members (id, email, first_name, last_name, display_name,
                                profile_photo_url, directory_headshot_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email = excluded.email,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                display_name = excluded.display_name,
                profile_photo_url = excluded.profile_photo_url,
                directory_headshot_url = COALESCE(excluded.directory_headshot_url, directory_headshot_url),
                updated_at = excluded.updated_at
        ''', (
            str(member['Id']),
            member.get('Email', ''),
            member.get('FirstName', ''),
            member.get('LastName', ''),
            member.get('DisplayName', f"{member.get('FirstName', '')} {member.get('LastName', '')}".strip()),
            profile_photo_url,
            directory_headshot_url,
            datetime.utcnow()
        ))


class EventSync:
    """Sync events from Wild Apricot to local database."""

    def __init__(self):
        self.api = get_wa_api()

    def sync_events(self, days_back=365, days_forward=90):
        """Sync events within the specified date range."""
        logger.info(f"Starting event sync ({days_back} days back, {days_forward} forward)...")
        start_time = datetime.utcnow()

        try:
            start_date = datetime.utcnow() - timedelta(days=days_back)
            events = self.api.get_events(start_date=start_date)
            logger.info(f"Retrieved {len(events)} events from WA")

            synced = 0
            with get_db() as conn:
                for event in events:
                    self._upsert_event(conn, event)
                    synced += 1

                conn.execute('''
                    UPDATE sync_status
                    SET last_sync_at = ?, last_sync_status = 'success', items_synced = ?
                    WHERE sync_type = 'events'
                ''', (datetime.utcnow(), synced))

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Event sync complete: {synced} events in {elapsed:.1f}s")
            return synced

        except Exception as e:
            logger.error(f"Event sync failed: {e}")
            with get_db() as conn:
                conn.execute('''
                    UPDATE sync_status
                    SET last_sync_at = ?, last_sync_status = 'failed', last_error = ?
                    WHERE sync_type = 'events'
                ''', (datetime.utcnow(), str(e)))
            raise

    def _upsert_event(self, conn, event):
        """Insert or update an event record."""
        # Extract location info
        location = event.get('Location', {})
        location_name = location.get('Name', '')
        location_address = location.get('Address', '')

        # Determine activity group from tags or organizer
        activity_group = self._determine_activity_group(event)

        # Check if public event
        access_level = event.get('AccessLevel', '')
        is_public = access_level == 'Public'

        conn.execute('''
            INSERT INTO events (id, name, description, start_date, end_date,
                               location_name, location_address, activity_group,
                               is_public, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                location_name = excluded.location_name,
                location_address = excluded.location_address,
                activity_group = excluded.activity_group,
                is_public = excluded.is_public,
                updated_at = excluded.updated_at
        ''', (
            str(event['Id']),
            event.get('Name', ''),
            event.get('Details', {}).get('DescriptionHtml', ''),
            event.get('StartDate'),
            event.get('EndDate'),
            location_name,
            location_address,
            activity_group,
            is_public,
            datetime.utcnow()
        ))

    def _determine_activity_group(self, event):
        """Determine the activity group for an event."""
        name = event.get('Name', '').lower()
        tags = [t.lower() for t in event.get('Tags', [])]

        # Map keywords to activity groups
        activity_map = {
            'hik': 'Happy Hikers',
            'golf': 'Golf',
            'wine': 'Wine Club',
            'cycl': 'Cycling',
            'bike': 'Cycling',
            'book': 'Book Club',
            'din': 'Dining Out',
            'lunch': 'Dining Out',
            'social': 'Social Events',
            'party': 'Social Events',
            'picnic': 'Social Events',
            'gala': 'Social Events',
        }

        for keyword, group in activity_map.items():
            if keyword in name or any(keyword in tag for tag in tags):
                return group

        return 'General'

    def sync_registrations(self, event_id):
        """Sync registrations for a specific event."""
        try:
            registrations = self.api.get_event_registrations(event_id)

            with get_db() as conn:
                # Clear existing registrations for this event
                conn.execute('DELETE FROM event_registrations WHERE event_id = ?', (event_id,))

                # Insert new registrations
                for reg in registrations:
                    contact = reg.get('Contact', {})
                    member_id = str(contact.get('Id', ''))
                    if member_id:
                        conn.execute('''
                            INSERT OR IGNORE INTO event_registrations (event_id, member_id, registration_type)
                            VALUES (?, ?, ?)
                        ''', (event_id, member_id, reg.get('RegistrationType', {}).get('Name', 'attending')))

            return len(registrations)

        except Exception as e:
            logger.error(f"Failed to sync registrations for event {event_id}: {e}")
            return 0

    def sync_all_recent_registrations(self, days=30):
        """Sync registrations for all recent events."""
        with get_db() as conn:
            events = conn.execute('''
                SELECT id FROM events
                WHERE start_date >= date('now', ? || ' days')
                AND start_date <= date('now', '+30 days')
            ''', (f'-{days}',)).fetchall()

        total = 0
        for event in events:
            count = self.sync_registrations(event['id'])
            total += count

        logger.info(f"Synced registrations for {len(events)} events, {total} total registrations")
        return total


def run_full_sync():
    """Run a full sync of members, events, and registrations."""
    member_sync = MemberSync()
    event_sync = EventSync()

    members = member_sync.sync_all_members()
    events = event_sync.sync_events()
    registrations = event_sync.sync_all_recent_registrations()

    return {
        'members': members,
        'events': events,
        'registrations': registrations
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_full_sync()
