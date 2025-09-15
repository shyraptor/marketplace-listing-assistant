"""Project related data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProjectData:
    """Represents a project containing images, metadata, and processing settings."""

    name: str
    clothing_images: List[Any] = field(default_factory=list)
    processed_images: List[Any] = field(default_factory=list)
    clothing_type: str = ""
    state: str = ""
    measurements: Dict[str, Any] = field(default_factory=dict)
    selected_tags: List[str] = field(default_factory=list)
    selected_colors: List[str] = field(default_factory=list)
    custom_hashtags: str = ""
    generated_description: str = ""
    owner_letter: str = ""
    storage_letter: str = ""
    project_bg_path: Optional[str] = None

    def __repr__(self) -> str:  # pragma: no cover - utility repr
        return f"<ProjectData '{self.name}' ({len(self.clothing_images)} images)>"
