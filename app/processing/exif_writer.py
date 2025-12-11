"""
SBNC Photo Gallery System - EXIF/XMP Tag Writer
Write tags, people, and event info to photo metadata for portability.
"""

import subprocess
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Check if exiftool is available
EXIFTOOL_AVAILABLE = shutil.which('exiftool') is not None


def write_tags_to_photo(photo_path, tags=None, people=None, event_name=None,
                        event_date=None, location=None, faces_with_regions=None,
                        submitter_name=None, submitter_email=None, source=None):
    """
    Write metadata tags to a photo file using exiftool.

    Args:
        photo_path: Path to the photo file
        tags: List of keyword tags (strings)
        people: List of people names identified in the photo
        event_name: Name of the event
        event_date: Date of the event (string)
        location: Location name
        faces_with_regions: List of dicts with 'name', 'x', 'y', 'w', 'h' for face regions
                           (coordinates as percentages 0-1)
        submitter_name: Name of person who submitted the photo
        submitter_email: Email of submitter
        source: How photo was submitted (email, upload, bulk_import, etc.)

    Returns:
        bool: True if successful, False otherwise
    """
    if not EXIFTOOL_AVAILABLE:
        logger.warning("exiftool not installed - skipping EXIF write")
        return False

    photo_path = Path(photo_path)
    if not photo_path.exists():
        logger.error(f"Photo not found: {photo_path}")
        return False

    args = ['exiftool', '-overwrite_original', '-ignoreMinorErrors']

    # Keywords/Subject tags (IPTC and XMP)
    if tags:
        for tag in tags:
            # Clean tag for EXIF (no special chars)
            clean_tag = str(tag).replace('"', '').replace("'", '')
            args.append(f'-IPTC:Keywords={clean_tag}')
            args.append(f'-XMP:Subject={clean_tag}')

    # People in image (XMP standard)
    if people:
        for person in people:
            clean_name = str(person).replace('"', '').replace("'", '')
            args.append(f'-XMP:PersonInImage={clean_name}')

    # Event/Caption
    if event_name:
        clean_event = str(event_name).replace('"', '').replace("'", '')
        args.append(f'-IPTC:Caption-Abstract={clean_event}')
        args.append(f'-XMP:Description={clean_event}')
        args.append(f'-IPTC:Headline={clean_event}')

    # Date
    if event_date:
        args.append(f'-IPTC:DateCreated={event_date}')

    # Location
    if location:
        clean_loc = str(location).replace('"', '').replace("'", '')
        args.append(f'-IPTC:Sub-location={clean_loc}')
        args.append(f'-XMP:Location={clean_loc}')

    # Submitter info (who sent the photo and how)
    if submitter_name:
        clean_submitter = str(submitter_name).replace('"', '').replace("'", '')
        # Credit field is standard for "who provided this image"
        args.append(f'-IPTC:Credit={clean_submitter}')
        args.append(f'-XMP:Credit={clean_submitter}')
        # Also add to special instructions for visibility
        args.append(f'-IPTC:SpecialInstructions=Submitted by: {clean_submitter}')

    if submitter_email:
        clean_email = str(submitter_email).replace('"', '').replace("'", '')
        # Use IPTC Contact field for email
        args.append(f'-XMP-iptcCore:CreatorContactInfoCiEmailWork={clean_email}')

    if source:
        clean_source = str(source).replace('"', '').replace("'", '')
        # Source field indicates how/where image was obtained
        args.append(f'-IPTC:Source={clean_source}')
        args.append(f'-XMP:Source={clean_source}')

    # Face regions (XMP-mwg-rs standard - used by Lightroom, Picasa, etc.)
    # This is more complex and requires proper XMP structure
    if faces_with_regions:
        # For face regions, we need to build a proper XMP structure
        # Using exiftool's struct notation
        for i, face in enumerate(faces_with_regions):
            if face.get('name') and all(k in face for k in ['x', 'y', 'w', 'h']):
                # MWG Region format (used by Lightroom, Picasa)
                # Coordinates are relative (0-1)
                args.append(f'-XMP-mwg-rs:RegionAppliedToDimensionsUnit=normalized')
                args.append(f'-XMP-mwg-rs:RegionAppliedToDimensionsW=1')
                args.append(f'-XMP-mwg-rs:RegionAppliedToDimensionsH=1')

                # Each region
                prefix = f'-XMP-mwg-rs:RegionAreaX={face["x"]}'
                args.append(prefix)
                args.append(f'-XMP-mwg-rs:RegionAreaY={face["y"]}')
                args.append(f'-XMP-mwg-rs:RegionAreaW={face["w"]}')
                args.append(f'-XMP-mwg-rs:RegionAreaH={face["h"]}')
                args.append(f'-XMP-mwg-rs:RegionName={face["name"]}')
                args.append(f'-XMP-mwg-rs:RegionType=Face')

    args.append(str(photo_path))

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.warning(f"exiftool warning for {photo_path}: {result.stderr}")
        else:
            logger.debug(f"Wrote EXIF tags to {photo_path}")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"exiftool timeout for {photo_path}")
        return False
    except Exception as e:
        logger.error(f"Failed to write EXIF to {photo_path}: {e}")
        return False


def write_photo_metadata(photo_path, photo_data, faces, tags, event=None,
                         submitter_name=None, submitter_email=None, source=None):
    """
    Convenience function to write all metadata for a processed photo.

    Args:
        photo_path: Path to the photo file
        photo_data: Dict with photo info (taken_at, etc.)
        faces: List of face dicts with member info
        tags: List of tag dicts with 'tag' and 'tag_type' keys
        event: Event dict or None
        submitter_name: Name of person who submitted the photo
        submitter_email: Email of submitter
        source: How photo was submitted (email, upload, bulk_import, etc.)
    """
    # Extract tag strings
    tag_strings = [t['tag'] for t in tags]

    # Extract people names from confirmed/matched faces
    people = []
    faces_with_regions = []

    for face in faces:
        name = None
        if face.get('confirmed_member_id') and not face.get('is_guest'):
            # Get confirmed name from database
            from app.database import get_member_by_id
            member = get_member_by_id(face['confirmed_member_id'])
            if member:
                name = member['display_name']
        elif face.get('matched_member_id') and face.get('is_high_confidence'):
            # Use high-confidence match
            from app.database import get_member_by_id
            member = get_member_by_id(face['matched_member_id'])
            if member:
                name = member['display_name']

        if name:
            people.append(name)

            # Calculate face region as percentages
            if all(k in face for k in ['box_left', 'box_top', 'box_right', 'box_bottom']):
                width = photo_data.get('width', 1)
                height = photo_data.get('height', 1)

                if width and height:
                    faces_with_regions.append({
                        'name': name,
                        'x': (face['box_left'] + (face['box_right'] - face['box_left']) / 2) / width,
                        'y': (face['box_top'] + (face['box_bottom'] - face['box_top']) / 2) / height,
                        'w': (face['box_right'] - face['box_left']) / width,
                        'h': (face['box_bottom'] - face['box_top']) / height
                    })

    # Event info
    event_name = event.get('name') if event else None
    event_date = None
    location = None

    if event:
        if event.get('start_date'):
            # Format as YYYY:MM:DD for IPTC
            event_date = str(event['start_date'])[:10].replace('-', ':')
        location = event.get('location_name')

    return write_tags_to_photo(
        photo_path,
        tags=tag_strings,
        people=people,
        event_name=event_name,
        event_date=event_date,
        location=location,
        faces_with_regions=faces_with_regions if faces_with_regions else None,
        submitter_name=submitter_name,
        submitter_email=submitter_email,
        source=source
    )


def read_embedded_tags(photo_path):
    """
    Read tags back from a photo's EXIF/XMP data.
    Useful for rebuilding database from photos.

    Returns:
        dict with 'keywords', 'people', 'caption', 'location', 'submitter', 'submitter_email', 'source'
    """
    if not EXIFTOOL_AVAILABLE:
        return {}

    try:
        result = subprocess.run([
            'exiftool', '-json',
            '-IPTC:Keywords',
            '-XMP:Subject',
            '-XMP:PersonInImage',
            '-IPTC:Caption-Abstract',
            '-IPTC:Sub-location',
            '-IPTC:Credit',
            '-XMP:Credit',
            '-IPTC:Source',
            '-XMP:Source',
            '-XMP-iptcCore:CreatorContactInfoCiEmailWork',
            str(photo_path)
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            if data:
                item = data[0]
                return {
                    'keywords': item.get('Keywords', []) or item.get('Subject', []),
                    'people': item.get('PersonInImage', []),
                    'caption': item.get('Caption-Abstract', ''),
                    'location': item.get('Sub-location', ''),
                    'submitter': item.get('Credit', ''),
                    'submitter_email': item.get('CreatorContactInfoCiEmailWork', ''),
                    'source': item.get('Source', '')
                }
    except Exception as e:
        logger.error(f"Failed to read EXIF from {photo_path}: {e}")

    return {}


def check_exiftool():
    """Check if exiftool is installed and return version."""
    if not EXIFTOOL_AVAILABLE:
        return None

    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return None
