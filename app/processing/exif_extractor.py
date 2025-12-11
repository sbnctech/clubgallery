"""
SBNC Photo Gallery System - EXIF Extraction
Extract metadata from photos including date, GPS, and camera info.
"""

from datetime import datetime
from pathlib import Path
import logging

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import exifread

logger = logging.getLogger(__name__)


class ExifExtractor:
    """Extract EXIF metadata from images."""

    def __init__(self, image_path):
        self.image_path = Path(image_path)
        self.exif_data = {}
        self._extracted = False

    def extract(self):
        """Extract all EXIF data from the image."""
        if self._extracted:
            return self.exif_data

        try:
            # Use exifread for detailed extraction (better EXIF support)
            with open(self.image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)

            # Also use Pillow for additional data
            with Image.open(self.image_path) as img:
                pillow_exif = img._getexif() if hasattr(img, '_getexif') else None
                self.exif_data['width'] = img.width
                self.exif_data['height'] = img.height

            # Extract date/time
            self.exif_data['taken_at'] = self._extract_datetime(tags)

            # Extract GPS coordinates
            gps_data = self._extract_gps(tags)
            self.exif_data['gps_lat'] = gps_data.get('latitude')
            self.exif_data['gps_lon'] = gps_data.get('longitude')

            # Extract camera info
            self.exif_data['camera_make'] = self._get_tag_value(tags, 'Image Make')
            self.exif_data['camera_model'] = self._get_tag_value(tags, 'Image Model')

            # Orientation for proper display
            orientation = self._get_tag_value(tags, 'Image Orientation')
            self.exif_data['orientation'] = orientation

            self._extracted = True

        except Exception as e:
            logger.error(f"Failed to extract EXIF from {self.image_path}: {e}")

        return self.exif_data

    def _get_tag_value(self, tags, tag_name):
        """Get a tag value as a string."""
        tag = tags.get(tag_name)
        if tag:
            return str(tag)
        return None

    def _extract_datetime(self, tags):
        """Extract the date/time the photo was taken."""
        # Try various date tags in order of preference
        date_tags = [
            'EXIF DateTimeOriginal',
            'EXIF DateTimeDigitized',
            'Image DateTime'
        ]

        for tag_name in date_tags:
            tag = tags.get(tag_name)
            if tag:
                try:
                    # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                    dt_str = str(tag)
                    return datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    continue

        return None

    def _extract_gps(self, tags):
        """Extract GPS coordinates from EXIF data."""
        gps_data = {}

        # Get GPS latitude
        lat_tag = tags.get('GPS GPSLatitude')
        lat_ref = tags.get('GPS GPSLatitudeRef')

        if lat_tag and lat_ref:
            lat = self._convert_gps_to_decimal(lat_tag.values)
            if str(lat_ref) == 'S':
                lat = -lat
            gps_data['latitude'] = lat

        # Get GPS longitude
        lon_tag = tags.get('GPS GPSLongitude')
        lon_ref = tags.get('GPS GPSLongitudeRef')

        if lon_tag and lon_ref:
            lon = self._convert_gps_to_decimal(lon_tag.values)
            if str(lon_ref) == 'W':
                lon = -lon
            gps_data['longitude'] = lon

        return gps_data

    def _convert_gps_to_decimal(self, gps_coords):
        """Convert GPS coordinates from degrees/minutes/seconds to decimal."""
        try:
            degrees = float(gps_coords[0].num) / float(gps_coords[0].den)
            minutes = float(gps_coords[1].num) / float(gps_coords[1].den)
            seconds = float(gps_coords[2].num) / float(gps_coords[2].den)

            return degrees + (minutes / 60.0) + (seconds / 3600.0)
        except (IndexError, ZeroDivisionError, AttributeError):
            return None

    def get_datetime(self):
        """Get the photo's datetime (or None if not available)."""
        if not self._extracted:
            self.extract()
        return self.exif_data.get('taken_at')

    def get_gps(self):
        """Get the photo's GPS coordinates as (lat, lon) tuple."""
        if not self._extracted:
            self.extract()
        lat = self.exif_data.get('gps_lat')
        lon = self.exif_data.get('gps_lon')
        if lat is not None and lon is not None:
            return (lat, lon)
        return None

    def get_camera_info(self):
        """Get camera make and model."""
        if not self._extracted:
            self.extract()
        return {
            'make': self.exif_data.get('camera_make'),
            'model': self.exif_data.get('camera_model')
        }

    def get_dimensions(self):
        """Get image dimensions as (width, height)."""
        if not self._extracted:
            self.extract()
        return (
            self.exif_data.get('width'),
            self.exif_data.get('height')
        )


def extract_exif(image_path):
    """Convenience function to extract EXIF data from an image."""
    extractor = ExifExtractor(image_path)
    return extractor.extract()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Extracting EXIF from: {path}")
        data = extract_exif(path)
        for key, value in data.items():
            print(f"  {key}: {value}")
