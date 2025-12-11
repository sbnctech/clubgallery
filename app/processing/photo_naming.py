"""
SBNC Photo Gallery System - Photo Naming Convention
Generate meaningful, unique filenames for photos at export time.

Naming format: {YYYYMMDD}_{HHMMSS}_{submitter_initials}_{short_id}.{ext}
Example: 20250915_143022_JD_a7b3.jpg

This replaces generic names like IMG_1234.jpg with:
- Date/time the photo was taken (from EXIF)
- Submitter initials (who sent it)
- Short unique suffix (collision avoidance)
"""

import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict


def get_initials(name: str, max_chars: int = 2) -> str:
    """
    Extract initials from a name.

    Examples:
        "John Doe" -> "JD"
        "Mary Jane Watson" -> "MJ" (first 2)
        "Madonna" -> "MA"
        None -> "XX"
    """
    if not name:
        return "XX"

    # Split on spaces and get first letter of each word
    words = name.strip().split()
    if len(words) >= 2:
        # Take first letter of first and last name
        initials = words[0][0] + words[-1][0]
    elif len(words) == 1:
        # Single name - take first two letters
        initials = words[0][:2]
    else:
        initials = "XX"

    return initials.upper()[:max_chars]


def generate_short_id(photo_path: str, length: int = 4) -> str:
    """
    Generate a short unique ID from photo path/content.

    Uses hash of original path + timestamp for uniqueness.
    """
    unique_string = f"{photo_path}_{datetime.now().isoformat()}"
    hash_hex = hashlib.md5(unique_string.encode()).hexdigest()
    return hash_hex[:length].lower()


def format_datetime_for_filename(dt: datetime) -> str:
    """
    Format datetime as YYYYMMDD_HHMMSS for filename.

    Args:
        dt: datetime object

    Returns:
        String like "20250915_143022"
    """
    return dt.strftime("%Y%m%d_%H%M%S")


def parse_exif_datetime(exif_datetime: str) -> Optional[datetime]:
    """
    Parse EXIF datetime string to datetime object.

    EXIF format is typically "YYYY:MM:DD HH:MM:SS"
    """
    if not exif_datetime:
        return None

    # Common EXIF datetime formats
    formats = [
        "%Y:%m:%d %H:%M:%S",      # Standard EXIF
        "%Y-%m-%d %H:%M:%S",      # ISO-ish
        "%Y-%m-%dT%H:%M:%S",      # ISO
        "%Y:%m:%d",               # Date only
        "%Y-%m-%d",               # ISO date only
    ]

    for fmt in formats:
        try:
            return datetime.strptime(exif_datetime.strip(), fmt)
        except ValueError:
            continue

    return None


def generate_export_filename(
    original_path: str,
    taken_at: Optional[datetime] = None,
    submitter_name: Optional[str] = None,
    event_date: Optional[str] = None,
    photo_id: Optional[str] = None
) -> str:
    """
    Generate a meaningful filename for photo export.

    Format: {YYYYMMDD}_{HHMMSS}_{initials}_{short_id}.{ext}

    Args:
        original_path: Original file path (for extension and fallback ID)
        taken_at: When photo was taken (datetime)
        submitter_name: Name of person who submitted
        event_date: Event date as fallback if no taken_at
        photo_id: Database photo ID for uniqueness

    Returns:
        New filename like "20250915_143022_JD_a7b3.jpg"
    """
    original = Path(original_path)
    ext = original.suffix.lower()

    # Normalize extension
    if ext == '.jpeg':
        ext = '.jpg'

    # Get date component
    if taken_at:
        if isinstance(taken_at, str):
            taken_at = parse_exif_datetime(taken_at)

        if taken_at:
            date_part = format_datetime_for_filename(taken_at)
        else:
            date_part = None
    else:
        date_part = None

    # Fallback to event date if no EXIF date
    if not date_part and event_date:
        try:
            if isinstance(event_date, str):
                event_dt = datetime.fromisoformat(event_date[:10])
            else:
                event_dt = event_date
            # Use noon as placeholder time for event date
            date_part = event_dt.strftime("%Y%m%d") + "_120000"
        except:
            date_part = None

    # Last fallback - current timestamp
    if not date_part:
        date_part = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get submitter initials
    initials = get_initials(submitter_name)

    # Get unique suffix
    if photo_id:
        # Use last 4 chars of photo ID if available
        short_id = str(photo_id)[-4:].lower()
        # Ensure it's alphanumeric
        short_id = re.sub(r'[^a-z0-9]', '', short_id) or generate_short_id(original_path)
    else:
        short_id = generate_short_id(original_path)

    # Ensure minimum length
    if len(short_id) < 4:
        short_id = short_id.ljust(4, '0')

    return f"{date_part}_{initials}_{short_id}{ext}"


def generate_export_filename_from_photo(photo_data: Dict, submitter_data: Dict = None) -> str:
    """
    Generate export filename from photo and submitter database records.

    Args:
        photo_data: Dict with photo info (taken_at, id, original_filename, etc.)
        submitter_data: Dict with submitter info (display_name, email, etc.)

    Returns:
        New filename
    """
    original_path = photo_data.get('original_filename') or photo_data.get('original_path', 'photo.jpg')
    taken_at = photo_data.get('taken_at')
    photo_id = photo_data.get('id')

    # Get submitter name
    submitter_name = None
    if submitter_data:
        submitter_name = submitter_data.get('display_name') or submitter_data.get('name')
    if not submitter_name:
        # Try to get from photo record
        submitter_name = photo_data.get('submitter_name')

    # Get event date as fallback
    event_date = photo_data.get('event_date') or photo_data.get('event_start_date')

    return generate_export_filename(
        original_path=original_path,
        taken_at=taken_at,
        submitter_name=submitter_name,
        event_date=event_date,
        photo_id=photo_id
    )


# For testing
if __name__ == '__main__':
    # Test cases
    tests = [
        {
            'original_path': 'IMG_1234.jpg',
            'taken_at': datetime(2025, 9, 15, 14, 30, 22),
            'submitter_name': 'John Doe',
            'photo_id': 'abc123xyz'
        },
        {
            'original_path': 'photo.heic',
            'taken_at': None,
            'submitter_name': 'Mary Jane Watson',
            'event_date': '2025-10-20',
            'photo_id': 'def456'
        },
        {
            'original_path': 'DSC_9999.JPG',
            'taken_at': '2025:11:05 09:15:00',
            'submitter_name': None,
            'photo_id': None
        },
    ]

    print("Filename Generation Examples:")
    print("-" * 60)
    for test in tests:
        result = generate_export_filename(**test)
        print(f"Original: {test['original_path']}")
        print(f"Taken: {test.get('taken_at')}")
        print(f"Submitter: {test.get('submitter_name')}")
        print(f"Result: {result}")
        print()
