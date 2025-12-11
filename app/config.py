"""
SBNC Photo Gallery System - Configuration
Load settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
PHOTO_STORAGE_ROOT = Path(os.getenv('PHOTO_STORAGE_ROOT', BASE_DIR / 'photos'))
DATABASE_PATH = Path(os.getenv('DATABASE_PATH', BASE_DIR / 'data' / 'photos.db'))

# Ensure directories exist
PHOTO_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Photo storage subdirectories
ORIGINALS_DIR = PHOTO_STORAGE_ROOT / 'originals'
DISPLAY_DIR = PHOTO_STORAGE_ROOT / 'display'
THUMBS_DIR = PHOTO_STORAGE_ROOT / 'thumbs'

for d in [ORIGINALS_DIR, DISPLAY_DIR, THUMBS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Email ingestion settings
IMAP_SERVER = os.getenv('IMAP_SERVER', 'mail.sbnewcomers.org')
IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
IMAP_USER = os.getenv('IMAP_USER', 'photos@sbnewcomers.org')
IMAP_PASSWORD = os.getenv('IMAP_PASSWORD', '')

# Wild Apricot API
WA_API_KEY = os.getenv('WA_API_KEY', '')
WA_ACCOUNT_ID = os.getenv('WA_ACCOUNT_ID', '')
WA_API_BASE_URL = 'https://api.wildapricot.org/v2.2'
WA_AUTH_URL = 'https://oauth.wildapricot.org/auth/token'

# Wild Apricot WebDAV
WA_WEBDAV_URL = os.getenv('WA_WEBDAV_URL', '')
WA_WEBDAV_USER = os.getenv('WA_WEBDAV_USER', '')
WA_WEBDAV_PASSWORD = os.getenv('WA_WEBDAV_PASSWORD', '')

# Geocoding (optional - for event location matching)
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
USE_GOOGLE_GEOCODING = bool(GOOGLE_MAPS_API_KEY)

# Face recognition thresholds
# Lower distance = higher confidence match
FACE_MATCH_HIGH_CONFIDENCE = float(os.getenv('FACE_MATCH_HIGH_CONFIDENCE', '0.4'))
FACE_MATCH_MEDIUM_CONFIDENCE = float(os.getenv('FACE_MATCH_MEDIUM_CONFIDENCE', '0.5'))

# For public events, use stricter thresholds
FACE_MATCH_PUBLIC_EVENT_THRESHOLD = float(os.getenv('FACE_MATCH_PUBLIC_EVENT_THRESHOLD', '0.35'))

# Image processing settings
THUMBNAIL_SIZE = (300, 300)  # Max dimensions for thumbnails
DISPLAY_SIZE = (1200, 1200)  # Max dimensions for display images
JPEG_QUALITY_THUMB = 80
JPEG_QUALITY_DISPLAY = 85

# Processing settings
PROCESS_BATCH_SIZE = int(os.getenv('PROCESS_BATCH_SIZE', '50'))

# Flask settings
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# GPS distance thresholds for event matching (in meters)
EVENT_MATCH_HIGH_CONFIDENCE_METERS = 500
EVENT_MATCH_MEDIUM_CONFIDENCE_METERS = 2000

# Supported image formats
SUPPORTED_IMAGE_EXTENSIONS = {
    # Standard formats
    '.jpg', '.jpeg', '.png', '.heic', '.heif',
    '.tiff', '.tif', '.webp', '.bmp',

    # RAW formats - Camera manufacturers
    '.nef', '.nrw',      # Nikon
    '.cr2', '.cr3',      # Canon
    '.arw', '.srf',      # Sony
    '.raf',              # Fujifilm
    '.orf',              # Olympus
    '.rw2',              # Panasonic/Lumix
    '.pef',              # Pentax
    '.dng',              # Adobe Digital Negative (universal)
    '.raw',              # Generic RAW
}

# RAW formats that need special processing (rawpy/libraw)
RAW_EXTENSIONS = {
    '.nef', '.nrw', '.cr2', '.cr3', '.arw', '.srf',
    '.raf', '.orf', '.rw2', '.pef', '.dng', '.raw'
}

# Photo status values
class PhotoStatus:
    AWAITING_APPROVAL = 'awaiting_approval'
    MEMBERS_ONLY = 'members_only'
    PUBLIC = 'public'
    DO_NOT_POST = 'do_not_post'

# Submission sources
class SubmissionSource:
    EMAIL = 'email'
    UPLOAD = 'upload'
    WA_SYNC = 'wa_sync'
    TELEGRAM = 'telegram'

# Telegram Bot settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', 'SBNCPhotosBot')
TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
