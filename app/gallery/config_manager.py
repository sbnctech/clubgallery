"""
SBNC Photo Gallery System - Configuration Manager
Manage configurable settings that can be edited without code changes.
"""

import json
from pathlib import Path
from datetime import datetime
import logging

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

# Path to the config file
CONFIG_FILE = BASE_DIR / 'data' / 'gallery_config.json'

# Default configuration - used if no config file exists
DEFAULT_CONFIG = {
    "version": "1.0",
    "lastModified": None,

    # Gallery display settings
    "gallery": {
        "title": "SBNC Photo Gallery",
        "subtitle": "Browse photos from Santa Barbara Newcomers Club events",
        "thumbnailHeight": 180,
        "gutterWidth": 8,
        "gutterHeight": 8,
        "maxRows": 20
    },

    # File upload settings
    "upload": {
        "validTypes": ["image/jpeg", "image/png", "image/heic", "image/heif"],
        "validExtensions": [".jpg", ".jpeg", ".png", ".heic", ".heif"],
        "maxFileSizeMB": 20
    },

    # External library CDN URLs (for easy upgrades)
    "libraries": {
        "jquery": "https://cdn.jsdelivr.net/npm/jquery@3/dist/jquery.min.js",
        "nanogallery2Js": "https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/jquery.nanogallery2.min.js",
        "nanogallery2Css": "https://cdn.jsdelivr.net/npm/nanogallery2@3/dist/css/nanogallery2.min.css",
        "select2Js": "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js",
        "select2Css": "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css"
    },

    # UI Labels (for easy text changes or localization)
    "labels": {
        "title": "SBNC Photo Gallery",
        "subtitle": "Browse photos from Santa Barbara Newcomers Club events",
        "findMember": "Find Member",
        "activity": "Activity",
        "event": "Event",
        "year": "Year",
        "clear": "Clear",
        "loading": "Loading...",
        "browseEvents": "Browse Events",
        "eventPhotos": "Event Photos",
        "memberPhotos": "Member Photos",
        "activityEvents": "Activity Events"
    },

    # Face recognition settings
    "faceRecognition": {
        "highConfidenceThreshold": 0.4,
        "mediumConfidenceThreshold": 0.5,
        "publicEventThreshold": 0.35
    },

    # Gallery presentation settings (what members see)
    "presentation": {
        # Which filters are visible
        "filters": {
            "showMemberSearch": True,
            "showActivityFilter": True,
            "showEventFilter": True,
            "showYearFilter": True
        },

        # Activity groups configuration
        "activityGroups": {
            # List of activity IDs to hide (empty = show all)
            "hidden": [],
            # Custom display order (empty = alphabetical)
            "displayOrder": [],
            # Custom display names (activity_id: "Custom Name")
            "customNames": {}
        },

        # Default view when gallery loads
        "defaultView": {
            # Pre-select an activity on load (null = none)
            "activity": None,
            # Pre-select a year on load (null = none)
            "year": None,
            # Show only recent events (0 = all)
            "recentMonths": 0
        },

        # Featured content
        "featured": {
            # Event IDs to pin at top
            "pinnedEvents": [],
            # Show "Featured" section
            "showFeaturedSection": False
        },

        # Header display
        "header": {
            "show": True,
            "showSubtitle": True
        }
    }
}


def get_config():
    """
    Load the current configuration.
    Returns saved config if exists, otherwise returns defaults.

    Returns:
        dict: Configuration dictionary
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                return _merge_config(DEFAULT_CONFIG, saved_config)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading config file: {e}")

    return DEFAULT_CONFIG.copy()


def save_config(config):
    """
    Save configuration to file.

    Args:
        config: Configuration dictionary to save

    Returns:
        bool: True if successful
    """
    try:
        # Ensure directory exists
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Update modification timestamp
        config['lastModified'] = datetime.utcnow().isoformat()

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Configuration saved to {CONFIG_FILE}")
        return True

    except IOError as e:
        logger.error(f"Error saving config file: {e}")
        return False


def update_config(section, key, value):
    """
    Update a specific configuration value.

    Args:
        section: Config section (e.g., 'gallery', 'labels')
        key: Key within the section
        value: New value

    Returns:
        bool: True if successful
    """
    config = get_config()

    if section not in config:
        config[section] = {}

    config[section][key] = value
    return save_config(config)


def reset_config():
    """
    Reset configuration to defaults.

    Returns:
        bool: True if successful
    """
    return save_config(DEFAULT_CONFIG.copy())


def get_config_value(section, key, default=None):
    """
    Get a specific configuration value.

    Args:
        section: Config section
        key: Key within section
        default: Default value if not found

    Returns:
        The configuration value or default
    """
    config = get_config()
    return config.get(section, {}).get(key, default)


def _merge_config(default, saved):
    """
    Deep merge saved config into default config.
    Ensures all default keys exist while preserving saved values.
    """
    result = default.copy()

    for key, value in saved.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value

    return result


# Initialize config file with defaults if it doesn't exist
def init_config():
    """Create default config file if it doesn't exist."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG.copy())
        logger.info("Created default configuration file")
