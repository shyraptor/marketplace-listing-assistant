"""Utilities for working with background images."""
from __future__ import annotations

import os
import shutil
from typing import List, Sequence, Tuple

from . import config

SUPPORTED_IMAGE_FORMATS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")


class BackgroundLibrary:
    """Manage available background files."""

    def __init__(self) -> None:
        self._backgrounds: List[str] = []

    @property
    def items(self) -> List[str]:
        """Return the in-memory list of backgrounds."""
        return self._backgrounds

    def refresh(self) -> int:
        """Scan the background folder and refresh the cached list."""
        folder = self._get_folder_path()
        if not folder:
            self._backgrounds = []
            return 0

        self._backgrounds = self._load_from_folder(folder)
        return len(self._backgrounds)

    def add_files(self, file_paths: Sequence[str]) -> Tuple[int, List[str]]:
        """Copy background files into the background directory."""
        folder = self._get_folder_path()
        if not folder:
            return 0, ["Background folder does not exist"]

        success = 0
        errors: List[str] = []

        for src_path in file_paths:
            try:
                if not os.path.exists(src_path):
                    errors.append(f"File not found: {src_path}")
                    continue

                filename = os.path.basename(src_path)
                dest_path = os.path.join(folder, filename)

                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(folder, f"{base}_{counter}{ext}")
                        counter += 1

                shutil.copy2(src_path, dest_path)
                self._backgrounds.append(dest_path)
                success += 1
            except Exception as exc:
                errors.append(f"Error copying {os.path.basename(src_path)}: {exc}")

        return success, errors

    def add_from_folder(self, folder_path: str) -> Tuple[int, int]:
        """Add all valid images from a folder."""
        if not os.path.exists(folder_path):
            return 0, 0

        image_files = [
            os.path.join(folder_path, filename)
            for filename in os.listdir(folder_path)
            if filename.lower().endswith(SUPPORTED_IMAGE_FORMATS)
            and os.path.isfile(os.path.join(folder_path, filename))
        ]

        success, _ = self.add_files(image_files)
        return success, 0

    def remove(self, bg_path: str) -> bool:
        """Remove a background image from disk and the cached list."""
        try:
            if bg_path in self._backgrounds:
                self._backgrounds.remove(bg_path)

            if os.path.exists(bg_path):
                os.remove(bg_path)

            return True
        except Exception:
            return False

    def _get_folder_path(self) -> str:
        """Ensure the background directory exists and return it."""
        return config.ensure_bg_dir()

    @staticmethod
    def _load_from_folder(folder_path: str) -> List[str]:
        backgrounds: List[str] = []
        try:
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(SUPPORTED_IMAGE_FORMATS):
                    full_path = os.path.join(folder_path, filename)
                    if os.path.isfile(full_path):
                        backgrounds.append(full_path)
        except Exception:
            pass
        return backgrounds
