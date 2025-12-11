"""
SBNC Photo Gallery System - Wild Apricot API Client
Handle authentication and API calls to Wild Apricot.
"""

import requests
from datetime import datetime, timedelta
import base64
import logging
from functools import wraps
import time

from app.config import WA_API_KEY, WA_ACCOUNT_ID, WA_API_BASE_URL, WA_AUTH_URL

logger = logging.getLogger(__name__)


class WildApricotAPI:
    """Client for the Wild Apricot API v2.2"""

    def __init__(self, api_key=None, account_id=None):
        self.api_key = api_key or WA_API_KEY
        self.account_id = account_id or WA_ACCOUNT_ID
        self.base_url = WA_API_BASE_URL
        self.auth_url = WA_AUTH_URL
        self.access_token = None
        self.token_expires_at = None
        self.session = requests.Session()

    def _get_access_token(self):
        """Get or refresh the OAuth2 access token."""
        if self.access_token and self.token_expires_at:
            if datetime.utcnow() < self.token_expires_at - timedelta(minutes=5):
                return self.access_token

        # Encode API key for Basic auth
        auth_string = f"APIKEY:{self.api_key}"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        headers = {
            'Authorization': f'Basic {auth_bytes}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'client_credentials',
            'scope': 'auto'
        }

        try:
            response = requests.post(self.auth_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            logger.info("Successfully obtained WA access token")
            return self.access_token

        except requests.RequestException as e:
            logger.error(f"Failed to get WA access token: {e}")
            raise

    def _make_request(self, method, endpoint, params=None, json_data=None, retry_count=3):
        """Make an authenticated API request."""
        token = self._get_access_token()

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        url = f"{self.base_url}/accounts/{self.account_id}/{endpoint}"

        for attempt in range(retry_count):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=30
                )

                if response.status_code == 429:  # Rate limited
                    wait_time = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json() if response.text else None

            except requests.RequestException as e:
                if attempt == retry_count - 1:
                    logger.error(f"API request failed after {retry_count} attempts: {e}")
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def get_members(self, filter_string=None, select_fields=None):
        """
        Get members from Wild Apricot.

        Args:
            filter_string: OData filter (e.g., "Status eq 'Active'")
            select_fields: List of fields to return

        Returns:
            List of member dictionaries
        """
        params = {}
        if filter_string:
            params['$filter'] = filter_string
        if select_fields:
            params['$select'] = ','.join(select_fields)

        # Use async filter for large result sets
        params['$async'] = 'false'

        result = self._make_request('GET', 'contacts', params=params)

        if isinstance(result, dict) and 'Contacts' in result:
            return result['Contacts']
        return result or []

    def get_member(self, member_id):
        """Get a single member by ID."""
        return self._make_request('GET', f'contacts/{member_id}')

    def get_member_by_email(self, email):
        """Get a member by email address."""
        members = self.get_members(filter_string=f"Email eq '{email}'")
        return members[0] if members else None

    def get_events(self, start_date=None, end_date=None, include_past=True):
        """
        Get events from Wild Apricot.

        Args:
            start_date: Filter events starting after this date
            end_date: Filter events ending before this date
            include_past: Include past events (default True)

        Returns:
            List of event dictionaries
        """
        params = {}

        if start_date:
            params['$filter'] = f"StartDate ge {start_date.isoformat()}"
        if not include_past and not start_date:
            params['$filter'] = f"StartDate ge {datetime.utcnow().date().isoformat()}"

        result = self._make_request('GET', 'events', params=params)
        return result or []

    def get_event(self, event_id):
        """Get a single event by ID."""
        return self._make_request('GET', f'events/{event_id}')

    def get_event_registrations(self, event_id):
        """Get all registrations for an event."""
        result = self._make_request('GET', f'eventregistrations', params={
            'eventId': event_id
        })
        return result or []

    def get_member_profile_photo_url(self, member_id):
        """Get the profile photo URL for a member."""
        member = self.get_member(member_id)
        if member:
            for field in member.get('FieldValues', []):
                if field.get('SystemCode') == 'Photo':
                    return field.get('Value', {}).get('Url')
        return None

    def get_all_active_members(self):
        """Get all active members with relevant fields."""
        return self.get_members(
            filter_string="Status eq 'Active' OR Status eq 'PendingRenewal'",
            select_fields=[
                'Id', 'Email', 'FirstName', 'LastName', 'DisplayName',
                'ProfilePicture', 'MembershipLevel', 'Status'
            ]
        )

    def search_members(self, query, limit=20):
        """Search members by name or email."""
        # WA doesn't have a great search, so we filter
        filter_string = (
            f"substringof('{query}', FirstName) or "
            f"substringof('{query}', LastName) or "
            f"substringof('{query}', Email)"
        )
        members = self.get_members(filter_string=filter_string)
        return members[:limit]


# Singleton instance
_api_client = None


def get_wa_api():
    """Get the singleton WA API client."""
    global _api_client
    if _api_client is None:
        _api_client = WildApricotAPI()
    return _api_client
