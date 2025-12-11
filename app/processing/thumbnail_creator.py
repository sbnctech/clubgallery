"""
SBNC Photo Gallery System - Thumbnail Creation
Create display and thumbnail versions of photos.

Supports:
- Standard formats: JPEG, PNG, TIFF, WebP, BMP
- Apple formats: HEIC, HEIF
- RAW formats: Nikon (NEF), Canon (CR2/CR3), Sony (ARW), Fuji (RAF),
               Olympus (ORF), Panasonic (RW2), Pentax (PEF), Adobe DNG
"""

from pathlib import Path
from datetime import datetime
import uuid
import logging

from PIL import Image
import pillow_heif

from app.config import (
    ORIGINALS_DIR, DISPLAY_DIR, THUMBS_DIR,
    THUMBNAIL_SIZE, DISPLAY_SIZE,
    JPEG_QUALITY_THUMB, JPEG_QUALITY_DISPLAY,
    RAW_EXTENSIONS
)

# Register HEIF opener for Apple formats
pillow_heif.register_heif_opener()

# Try to import rawpy for RAW file support
try:
    import rawpy
    import numpy as np
    RAW_SUPPORT = True
except ImportError:
    RAW_SUPPORT = False

logger = logging.getLogger(__name__)


class ThumbnailCreator:
    """Create thumbnail and display versions of photos."""

    def __init__(self, source_path):
        self.source_path = Path(source_path)
        self.photo_id = None

    def _is_raw_file(self):
        """Check if the source file is a RAW format."""
        return self.source_path.suffix.lower() in RAW_EXTENSIONS

    def _open_raw_file(self):
        """
        Open a RAW file using rawpy and convert to PIL Image.

        Returns:
            PIL.Image in RGB mode
        """
        if not RAW_SUPPORT:
            raise RuntimeError(
                f"RAW file support not available. Install rawpy: pip install rawpy"
            )

        with rawpy.imread(str(self.source_path)) as raw:
            # Process RAW to RGB array with auto white balance and exposure
            rgb = raw.postprocess(
                use_camera_wb=True,
                output_bps=8,
                no_auto_bright=False
            )
            # Convert numpy array to PIL Image
            return Image.fromarray(rgb)

    def process(self, photo_id=None):
        """
        Process the source image to create all versions.

        Args:
            photo_id: UUID for the photo. Generated if not provided.

        Returns:
            dict with paths to all versions
        """
        self.photo_id = photo_id or str(uuid.uuid4())

        # Determine date-based subdirectory
        date_subdir = datetime.now().strftime('%Y/%m')

        # Create output paths
        original_dir = ORIGINALS_DIR / date_subdir
        display_dir = DISPLAY_DIR / date_subdir
        thumb_dir = THUMBS_DIR / date_subdir

        for d in [original_dir, display_dir, thumb_dir]:
            d.mkdir(parents=True, exist_ok=True)

        try:
            # Open image - handle RAW files specially
            if self._is_raw_file():
                logger.info(f"Processing RAW file: {self.source_path.name}")
                img = self._open_raw_file()
                # RAW files are already RGB from rawpy
            else:
                img = Image.open(self.source_path)
                # Apply EXIF orientation for standard formats
                img = self._apply_exif_orientation(img)

            # Convert to RGB if necessary (for PNG with alpha, etc.)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            original_size = (img.width, img.height)

            # Save original (as JPG)
            original_path = original_dir / f"{self.photo_id}.jpg"
            img.save(original_path, 'JPEG', quality=95)

            # Create display version
            display_path = display_dir / f"{self.photo_id}.jpg"
            display_img = self._resize_image(img, DISPLAY_SIZE)
            display_img.save(display_path, 'JPEG', quality=JPEG_QUALITY_DISPLAY)

            # Create thumbnail
            thumb_path = thumb_dir / f"{self.photo_id}.jpg"
            thumb_img = self._resize_image(img, THUMBNAIL_SIZE)
            thumb_img.save(thumb_path, 'JPEG', quality=JPEG_QUALITY_THUMB)

            # Return relative paths (from PHOTO_STORAGE_ROOT)
            return {
                'photo_id': self.photo_id,
                'original_path': str(Path('originals') / date_subdir / f"{self.photo_id}.jpg"),
                'display_path': str(Path('display') / date_subdir / f"{self.photo_id}.jpg"),
                'thumb_path': str(Path('thumbs') / date_subdir / f"{self.photo_id}.jpg"),
                'width': original_size[0],
                'height': original_size[1],
                'file_size': original_path.stat().st_size
            }

        except Exception as e:
            logger.error(f"Failed to process image {self.source_path}: {e}")
            raise

    def _resize_image(self, img, max_size):
        """Resize image to fit within max_size while maintaining aspect ratio."""
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        return img

    def _apply_exif_orientation(self, img):
        """Apply EXIF orientation to the image."""
        try:
            exif = img._getexif()
            if exif is None:
                return img

            orientation_key = 274  # EXIF orientation tag
            if orientation_key not in exif:
                return img

            orientation = exif[orientation_key]

            rotations = {
                3: 180,
                6: 270,
                8: 90
            }

            if orientation in rotations:
                return img.rotate(rotations[orientation], expand=True)

            # Handle flip cases
            if orientation == 2:
                return img.transpose(Image.FLIP_LEFT_RIGHT)
            if orientation == 4:
                return img.transpose(Image.FLIP_TOP_BOTTOM)
            if orientation == 5:
                return img.rotate(270, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
            if orientation == 7:
                return img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)

        except Exception as e:
            logger.warning(f"Could not apply EXIF orientation: {e}")

        return img


def create_thumbnails(source_path, photo_id=None):
    """Convenience function to create thumbnails."""
    creator = ThumbnailCreator(source_path)
    return creator.process(photo_id)


def regenerate_thumbnails(photo_id):
    """
    Regenerate thumbnails for an existing photo.
    Useful if thumbnail settings change.
    """
    from app.config import PHOTO_STORAGE_ROOT

    # Find the original
    for subdir in ORIGINALS_DIR.rglob(f"{photo_id}.jpg"):
        original_path = subdir

        # Determine date subdirectory from the path
        date_subdir = str(subdir.parent.relative_to(ORIGINALS_DIR))

        with Image.open(original_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Recreate display
            display_path = DISPLAY_DIR / date_subdir / f"{photo_id}.jpg"
            display_path.parent.mkdir(parents=True, exist_ok=True)
            display_img = img.copy()
            display_img.thumbnail(DISPLAY_SIZE, Image.Resampling.LANCZOS)
            display_img.save(display_path, 'JPEG', quality=JPEG_QUALITY_DISPLAY)

            # Recreate thumb
            thumb_path = THUMBS_DIR / date_subdir / f"{photo_id}.jpg"
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            thumb_img = img.copy()
            thumb_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            thumb_img.save(thumb_path, 'JPEG', quality=JPEG_QUALITY_THUMB)

        logger.info(f"Regenerated thumbnails for {photo_id}")
        return True

    logger.warning(f"Original not found for {photo_id}")
    return False
