"""Configuration and localisation helpers."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    BG_DIR,
    CONFIG_FILE,
    DEFAULT_LANG_CODE,
    DEFAULT_LANG_KEYS,
    HASHTAG_FILE,
    LANG_DIR,
    TEMPLATES_FILE,
)


def ensure_directory(dir_name: str, auto_create: bool = False) -> Tuple[bool, Optional[str]]:
    """Ensure a directory exists, creating it if requested."""
    if os.path.exists(dir_name):
        return True, None

    if not auto_create:
        return False, f"Directory '{dir_name}' does not exist."

    try:
        os.makedirs(dir_name, exist_ok=True)
        return True, None
    except Exception as exc:  # pragma: no cover - filesystem errors are environment specific
        return False, str(exc)


def ensure_lang_dir() -> Tuple[bool, Optional[str]]:
    """Ensure the language directory exists."""
    return ensure_directory(LANG_DIR, auto_create=True)


def ensure_bg_dir() -> str:
    """Ensure the background directory exists and return the path if successful."""
    exists, _ = ensure_directory(BG_DIR, auto_create=True)
    return BG_DIR if exists else ""


def load_json_config(filepath: str, default_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load a JSON configuration file with optional defaults."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            if default_data is not None:
                return default_data
            return {}

    return default_data.copy() if default_data is not None else {}


def save_json_config(filepath: str, data: Dict[str, Any]) -> bool:
    """Persist configuration data to disk."""
    try:
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_language_file(lang_code: str) -> Optional[Dict[str, Any]]:
    """Load a single language file."""
    lang_file_path = os.path.join(LANG_DIR, f"{lang_code}.json")
    try:
        with open(lang_file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def load_language_config(lang_code: str) -> Tuple[Dict[str, str], Optional[str], Optional[str]]:
    """Load language configuration returning language data, warning, and critical error."""
    ensure_lang_dir()

    lang_data = load_language_file(lang_code)
    warning = None
    error = None

    if lang_data is None and lang_code != DEFAULT_LANG_CODE:
        warning = DEFAULT_LANG_KEYS["lang_load_error"].format(lang_code=lang_code, lang_dir=LANG_DIR)
        lang_data = load_language_file(DEFAULT_LANG_CODE)

    if lang_data is None:
        error = DEFAULT_LANG_KEYS["lang_default_load_error"].format(lang_code=DEFAULT_LANG_CODE)
        return DEFAULT_LANG_KEYS, warning, error

    return lang_data, warning, error


def get_available_languages() -> List[Tuple[str, str]]:
    """Return the list of available language codes and display names."""
    languages: List[Tuple[str, str]] = []
    exists, _ = ensure_lang_dir()
    if not exists:
        return [(DEFAULT_LANG_CODE, DEFAULT_LANG_CODE)]

    try:
        for filename in os.listdir(LANG_DIR):
            if not filename.endswith(".json"):
                continue

            lang_code = filename[:-5]
            lang_path = os.path.join(LANG_DIR, filename)
            try:
                with open(lang_path, "r", encoding="utf-8") as handle:
                    lang_data = json.load(handle)
                display_name = lang_data.get("language_name", lang_code)
                languages.append((lang_code, display_name))
            except Exception:
                languages.append((lang_code, lang_code))
    except Exception:
        languages.append((DEFAULT_LANG_CODE, DEFAULT_LANG_CODE))

    if not languages:
        languages.append((DEFAULT_LANG_CODE, DEFAULT_LANG_CODE))

    return languages


def load_main_config() -> Dict[str, Any]:
    """Load the main application configuration."""
    default_config = {"language": DEFAULT_LANG_CODE, "use_solid_bg": True}
    return load_json_config(CONFIG_FILE, default_config)


def save_main_config(config: Dict[str, Any]) -> bool:
    """Save the main application configuration."""
    return save_json_config(CONFIG_FILE, config)


def load_templates_config() -> Dict[str, Any]:
    """Load clothing templates configuration with defaults."""
    default_templates = {
        "Dress": {
            "fields": ["length", "bust", "waist"],
            "default_tags": ["dress", "women", "clothing"],
        },
        "Shirt": {
            "fields": ["size", "chest", "length"],
            "default_tags": ["shirt", "top", "clothing"],
        },
    }
    return load_json_config(TEMPLATES_FILE, default_templates)


def save_templates_config(templates: Dict[str, Any]) -> bool:
    """Persist templates configuration."""
    return save_json_config(TEMPLATES_FILE, templates)


def load_hashtag_mapping_config() -> Dict[str, Any]:
    """Load hashtag mapping configuration."""
    default_mapping = {
        "vintage": ["vintage", "retro", "classic"],
        "boho": ["boho", "bohemian", "hippie"],
    }
    return load_json_config(HASHTAG_FILE, default_mapping)


def save_hashtag_mapping_config(mapping: Dict[str, Any]) -> bool:
    """Persist hashtag mapping configuration."""
    return save_json_config(HASHTAG_FILE, mapping)
