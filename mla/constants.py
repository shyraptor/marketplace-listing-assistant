"""Core constants for the Marketplace Listing Assistant backend."""

from typing import Dict

TEMPLATES_FILE = "templates.json"
HASHTAG_FILE = "hashtag_mapping.json"
CONFIG_FILE = "config.json"
LANG_DIR = "lang"
BG_DIR = "bg"
DEFAULT_LANG_CODE = "en"
APP_NAME = "Listing Assistant"

DEFAULT_LANG_KEYS: Dict[str, str] = {
    "critical_error_title": "Critical Error",
    "lang_load_error": (
        "Could not load language file '{lang_code}'. Ensure '{lang_code}.json' exists "
        "in the '{lang_dir}' folder or reinstall the application. Using default language."
    ),
    "lang_default_load_error": (
        "Could not load default language file ('{lang_code}.json'). Application cannot "
        "start. Please reinstall."
    ),
}

DEFAULT_CANVAS_WIDTH_V = 600
DEFAULT_CANVAS_HEIGHT_V = 800
DEFAULT_CANVAS_WIDTH_H = 800
DEFAULT_CANVAS_HEIGHT_H = 600

DEFAULT_VERTICAL_OFFSET = 0.0
DEFAULT_HORIZONTAL_OFFSET = 0.0
DEFAULT_SIZE_SCALE = 0.85
