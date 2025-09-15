"""Description and hashtag helpers."""
from __future__ import annotations

import re
from typing import Dict, Iterable

from .project import ProjectData


def clean_hashtag(tag: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "", tag)
    cleaned = cleaned.lower()
    cleaned = re.sub(r"^\d+", "", cleaned)
    return cleaned


def process_hashtags(tags: Iterable[str], hashtag_mapping: Dict[str, Iterable[str]]) -> str:
    hashtags = set()
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue

        found_mapping = False
        lower_tag = tag.lower()
        for key, values in hashtag_mapping.items():
            mapping_values = list(values)
            if lower_tag == key.lower() or lower_tag in (value.lower() for value in mapping_values):
                for hashtag in mapping_values:
                    cleaned = clean_hashtag(hashtag)
                    if cleaned:
                        hashtags.add(f"#{cleaned}")
                found_mapping = True
                break

        if not found_mapping:
            cleaned = clean_hashtag(tag)
            if cleaned:
                hashtags.add(f"#{cleaned}")

    return " ".join(sorted(hashtags))


def generate_description(project: ProjectData, lang: Dict[str, str], units: str, hashtag_mapping: Dict[str, Iterable[str]]) -> str:
    if not project:
        return ""

    parts = []
    
    # State without prefix
    if project.state:
        parts.append(project.state)
    
    # Measurements with emoji
    measurements = []
    for field, value in project.measurements.items():
        if value:
            field_display = field.replace("_", " ").replace("-", " ").capitalize()
            measurements.append(f"{field_display}: {value} {units}")
    
    if measurements:
        if parts:
            parts.append("")  # Empty line for spacing
        parts.append("📏 Measurements:")
        parts.append("\n".join(measurements))
    
    # Tags with emoji
    all_tags = []
    if project.selected_tags:
        all_tags.extend(project.selected_tags)
    if project.selected_colors:
        all_tags.extend(project.selected_colors)
    if project.custom_hashtags:
        all_tags.extend(project.custom_hashtags.split())
    
    if all_tags:
        hashtags = process_hashtags(all_tags, hashtag_mapping)
        if hashtags:
            if parts:
                parts.append("")  # Empty line for spacing
            parts.append("✨ Tags:")
            parts.append(hashtags)
    
    # Storage reference with emoji
    if project.owner_letter and project.storage_letter:
        import datetime
        date_tag = datetime.datetime.now().strftime("%m%y")
        storage_tag = f"{project.owner_letter.upper()}{project.storage_letter.upper()}{date_tag}"
        if parts:
            parts.append("")  # Empty line for spacing
        parts.append(f"📦 Ref: {storage_tag}")
    
    description = "\n".join(parts)
    project.generated_description = description
    return description
