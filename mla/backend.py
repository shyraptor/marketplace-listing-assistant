"""Core backend implementation orchestrating all helper modules."""
from __future__ import annotations

import os
import queue
import shutil
import tempfile
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from . import config
from .backgrounds import BackgroundLibrary
from .constants import (
    APP_NAME,
    DEFAULT_HORIZONTAL_OFFSET,
    DEFAULT_LANG_CODE,
    DEFAULT_SIZE_SCALE,
    DEFAULT_VERTICAL_OFFSET,
)
from .description_generator import generate_description
from .exporter import save_project_output
from .image_processing import ImageProcessor
from .project import ProjectData


class Backend:
    """Backend logic for Marketplace Listing Assistant."""

    def __init__(self) -> None:
        import threading

        self.initialization_error: Optional[str] = None
        self.initialization_warning: Optional[str] = None

        self.config_data: Dict[str, Any] = config.load_main_config()
        self.selected_language_code: str = self.config_data.get("language", DEFAULT_LANG_CODE)
        self.lang, warning, error = config.load_language_config(self.selected_language_code)
        if warning:
            self.initialization_warning = warning
        if error:
            self.initialization_error = error

        self.templates: Dict[str, Any] = config.load_templates_config()
        self.hashtag_mapping: Dict[str, Any] = config.load_hashtag_mapping_config()

        self.background_library = BackgroundLibrary()
        self.background_library.refresh()

        self.projects: List[ProjectData] = []
        self.current_project_index: Optional[int] = None
        self.temp_extract_dir: Optional[str] = None

        self.image_processor = ImageProcessor()

        self.executor = ThreadPoolExecutor(max_workers=4)
        self.processing_queue: "queue.Queue[Any]" = queue.Queue()
        self.progress_callback: Optional[Any] = None
        self._processing_lock = threading.Lock()

        self._apply_settings_from_config()

    # ------------------------------------------------------------------
    # Configuration management
    # ------------------------------------------------------------------
    def _apply_settings_from_config(self) -> None:
        self.use_solid_bg = self.config_data.get("use_solid_bg", True)
        self.units = self.config_data.get("units", "cm")
        self.output_prefix = self.config_data.get("output_prefix", "")

        canvas_width_v = self.config_data.get("canvas_width_v", self.image_processor.canvas_width_v)
        canvas_height_v = self.config_data.get("canvas_height_v", self.image_processor.canvas_height_v)
        canvas_width_h = self.config_data.get("canvas_width_h", self.image_processor.canvas_width_h)
        canvas_height_h = self.config_data.get("canvas_height_h", self.image_processor.canvas_height_h)

        self.canvas_width_v = canvas_width_v
        self.canvas_height_v = canvas_height_v
        self.canvas_width_h = canvas_width_h
        self.canvas_height_h = canvas_height_h

        self.config_data.update(
            {
                "canvas_width_v": canvas_width_v,
                "canvas_height_v": canvas_height_v,
                "canvas_width_h": canvas_width_h,
                "canvas_height_h": canvas_height_h,
                "units": self.units,
                "output_prefix": self.output_prefix,
                "language": self.selected_language_code,
            }
        )

        self.image_processor.update_canvas_settings(
            canvas_width_v, canvas_height_v, canvas_width_h, canvas_height_h
        )

    def save_main_config(self, updated_config: Optional[Dict[str, Any]] = None) -> bool:
        config_snapshot = self.config_data.copy()
        if updated_config:
            config_snapshot.update(updated_config)

        language = config_snapshot.get("language") or config_snapshot.get("selected_language")
        if not language:
            language = self.selected_language_code
        self.selected_language_code = language
        config_snapshot["language"] = language
        config_snapshot.pop("selected_language", None)

        self.use_solid_bg = config_snapshot.get("use_solid_bg", self.use_solid_bg)
        self.units = config_snapshot.get("units", self.units)
        self.output_prefix = config_snapshot.get("output_prefix", self.output_prefix)
        self.canvas_width_v = config_snapshot.get("canvas_width_v", self.canvas_width_v)
        self.canvas_height_v = config_snapshot.get("canvas_height_v", self.canvas_height_v)
        self.canvas_width_h = config_snapshot.get("canvas_width_h", self.canvas_width_h)
        self.canvas_height_h = config_snapshot.get("canvas_height_h", self.canvas_height_h)

        self.image_processor.update_canvas_settings(
            self.canvas_width_v,
            self.canvas_height_v,
            self.canvas_width_h,
            self.canvas_height_h,
        )

        self.config_data = config_snapshot

        config_to_save: Dict[str, Any] = {
            "language": self.selected_language_code,
            "use_solid_bg": self.use_solid_bg,
            "units": self.units,
            "output_prefix": self.output_prefix,
            "canvas_width_v": self.canvas_width_v,
            "canvas_height_v": self.canvas_height_v,
            "canvas_width_h": self.canvas_width_h,
            "canvas_height_h": self.canvas_height_h,
        }
        return config.save_main_config(config_to_save)

    def save_templates_config(self, templates: Optional[Dict[str, Any]] = None) -> bool:
        if templates is not None:
            self.templates = templates
        return config.save_templates_config(self.templates)

    def save_hashtag_mapping_config(self, mapping: Optional[Dict[str, Any]] = None) -> bool:
        if mapping is not None:
            self.hashtag_mapping = mapping
        return config.save_hashtag_mapping_config(self.hashtag_mapping)

    def get_available_languages(self) -> List[Tuple[str, str]]:
        return config.get_available_languages()

    # ------------------------------------------------------------------
    # Background helpers
    # ------------------------------------------------------------------
    @property
    def backgrounds(self) -> List[str]:
        return self.background_library.items

    def scan_backgrounds_folder(self) -> int:
        return self.background_library.refresh()

    def add_background_files(self, file_paths: Sequence[str]) -> Tuple[int, List[str]]:
        return self.background_library.add_files(file_paths)

    def add_backgrounds_from_folder(self, folder_path: str) -> Tuple[int, int]:
        return self.background_library.add_from_folder(folder_path)

    def remove_bg_file(self, bg_path: str) -> bool:
        return self.background_library.remove(bg_path)

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------
    def add_new_project(self, name: str) -> ProjectData:
        project = ProjectData(name)
        self.projects.append(project)
        self.current_project_index = len(self.projects) - 1
        return project

    def _load_image(self, image_path: str) -> Optional[Image.Image]:
        return self.image_processor.load_image(image_path)

    def load_single_project_images(self, image_paths: Sequence[str]) -> Tuple[bool, List[str]]:
        if not image_paths:
            return False, ["No images provided"]

        project = self.add_new_project(f"Project_{len(self.projects) + 1}")

        errors: List[str] = []
        for path in image_paths:
            img = self._load_image(path)
            if img is None:
                errors.append(f"Failed to load: {os.path.basename(path)}")
                continue
            project.clothing_images.append({"path": path, "image": img})

        if not project.clothing_images:
            self.projects.remove(project)
            self.current_project_index = len(self.projects) - 1 if self.projects else None
            return False, errors if errors else ["No valid images loaded"]

        return True, errors

    def load_projects_from_zip(self, zip_path: str) -> Tuple[int, List[str]]:
        errors: List[str] = []
        project_count = 0

        try:
            self.temp_extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(self.temp_extract_dir)

            root_items = os.listdir(self.temp_extract_dir)
            if len(root_items) == 1:
                sole_item = os.path.join(self.temp_extract_dir, root_items[0])
                projects_root = sole_item if os.path.isdir(sole_item) else self.temp_extract_dir
            else:
                projects_root = self.temp_extract_dir

            folders = [
                item
                for item in os.listdir(projects_root)
                if os.path.isdir(os.path.join(projects_root, item))
            ]

            for item in folders:
                item_path = os.path.join(projects_root, item)
                project = ProjectData(f"Project_{len(self.projects) + 1}")
                images_loaded = False

                desc_file = os.path.join(item_path, "description.txt")
                if os.path.exists(desc_file):
                    try:
                        with open(desc_file, "r", encoding="utf-8") as handle:
                            project.generated_description = handle.read()
                    except Exception:
                        pass

                for filename in os.listdir(item_path):
                    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
                        continue
                    img_path = os.path.join(item_path, filename)
                    img = self._load_image(img_path)
                    if img is None:
                        continue
                    project.clothing_images.append({"path": img_path, "image": img})
                    images_loaded = True

                if images_loaded:
                    self.projects.append(project)
                    project_count += 1

            if project_count > 0:
                self.current_project_index = len(self.projects) - project_count
        except Exception as exc:
            errors.append(f"Error extracting ZIP: {exc}")

        return project_count, errors

    def get_project_count(self) -> int:
        return len(self.projects)

    def get_current_project_index(self) -> Optional[int]:
        return self.current_project_index

    def set_current_project_index(self, index: Optional[int]) -> bool:
        if index is None:
            self.current_project_index = None
            return True

        if 0 <= index < len(self.projects):
            self.current_project_index = index
            return True
        return False

    def get_project(self, index: int) -> Optional[ProjectData]:
        if 0 <= index < len(self.projects):
            return self.projects[index]
        return None

    def get_current_project(self) -> Optional[ProjectData]:
        if self.current_project_index is None:
            return None
        return self.get_project(self.current_project_index)

    def update_project_data(self, index: int, **kwargs: Any) -> bool:
        project = self.get_project(index)
        if not project:
            return False
        for key, value in kwargs.items():
            if hasattr(project, key):
                setattr(project, key, value)
        return True

    def remove_project(self, index: int) -> bool:
        if not (0 <= index < len(self.projects)):
            return False

        self.projects.pop(index)
        if not self.projects:
            self.current_project_index = None
        elif self.current_project_index is not None and self.current_project_index >= len(self.projects):
            self.current_project_index = len(self.projects) - 1
        elif self.current_project_index is not None and index < self.current_project_index:
            self.current_project_index -= 1
        return True

    # ------------------------------------------------------------------
    # Image processing
    # ------------------------------------------------------------------
    def _ensure_processed_entry(self, project: ProjectData, index: int, skip_bg_removal: bool) -> Dict[str, Any]:
        if index < len(project.processed_images):
            processed = project.processed_images[index]
        else:
            processed = ImageProcessor.default_processed_entry(
                project.clothing_images[index]["path"], self.use_solid_bg
            )
            project.processed_images.append(processed)

        processed.setdefault("vof", DEFAULT_VERTICAL_OFFSET)
        processed.setdefault("hof", DEFAULT_HORIZONTAL_OFFSET)
        processed.setdefault("scale", DEFAULT_SIZE_SCALE)
        processed.setdefault("is_horizontal", False)
        processed.setdefault("use_solid_bg", self.use_solid_bg)
        processed.setdefault("skip_bg_removal", skip_bg_removal)
        processed.setdefault("rotation_angle", 0)
        return processed

    def process_single_image(
        self,
        project_index: int,
        image_index: int,
        skip_bg_removal: bool = False,
        user_bg_path: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        project = self.get_project(project_index)
        if not project or image_index >= len(project.clothing_images):
            return False, "Invalid project or image index"

        try:
            original_img = project.clothing_images[image_index]["image"]
            processed = self._ensure_processed_entry(project, image_index, skip_bg_removal)
            processed["skip_bg_removal"] = skip_bg_removal

            if skip_bg_removal:
                no_bg = original_img
            else:
                no_bg = self.image_processor.remove_background(original_img)
            processed["no_bg"] = no_bg

            bg_source = None
            if user_bg_path:
                processed["user_bg_path"] = user_bg_path
                processed["bg_path"] = user_bg_path
                try:
                    bg_source = Image.open(user_bg_path)
                except Exception:
                    bg_source = None
            elif not processed.get("use_solid_bg", self.use_solid_bg) and self.backgrounds:
                best_bg = self.image_processor.find_best_background(no_bg, self.backgrounds)
                if best_bg:
                    processed["bg_path"] = best_bg
                    try:
                        bg_source = Image.open(best_bg)
                    except Exception:
                        bg_source = None

            final_img = self.image_processor.fit_clothing(
                no_bg,
                bg_source,
                processed["vof"],
                processed["hof"],
                processed["scale"],
                processed["is_horizontal"],
                processed.get("use_solid_bg", self.use_solid_bg),
                processed.get("rotation_angle", 0),
            )
            processed["processed"] = final_img
            return True, None
        except Exception as exc:
            return False, str(exc)

    def process_project_images_async(
        self, project_index: int, progress_callback: Optional[Any] = None
    ) -> Future[Tuple[bool, List[str]]]:
        self.progress_callback = progress_callback
        return self.executor.submit(self._process_project_images_worker, project_index)

    def _process_project_images_worker(self, project_index: int) -> Tuple[bool, List[str]]:
        project = self.get_project(project_index)
        if not project or not project.clothing_images:
            return False, ["No project/images"]

        errors: List[str] = []
        total_images = len(project.clothing_images)
        current_global_setting = self.use_solid_bg

        for idx, item in enumerate(project.clothing_images):
            if self.progress_callback:
                self.progress_callback(idx + 1, total_images, f"Processing image {idx + 1}/{total_images}")
            try:
                original_img = item["image"]
                processed = self._ensure_processed_entry(project, idx, False)

                needs_processing = False
                if processed.get("processed") is None:
                    needs_processing = True
                elif (
                    not processed.get("individual_override", False)
                    and processed.get("use_solid_bg", None) != current_global_setting
                ):
                    needs_processing = True

                if not needs_processing:
                    continue

                no_bg = self.image_processor.remove_background(original_img)
                processed.update(ImageProcessor.default_processed_entry(item["path"], self.use_solid_bg))
                processed["no_bg"] = no_bg

                bg_source = None
                if not self.use_solid_bg and self.backgrounds:
                    best_bg = self.image_processor.find_best_background(no_bg, self.backgrounds)
                    if best_bg:
                        processed["bg_path"] = best_bg
                        try:
                            bg_source = Image.open(best_bg)
                        except Exception:
                            bg_source = None

                final_img = self.image_processor.fit_clothing(
                    no_bg,
                    bg_source,
                    processed["vof"],
                    processed["hof"],
                    processed["scale"],
                    processed["is_horizontal"],
                    processed.get("use_solid_bg", self.use_solid_bg),
                    processed.get("rotation_angle", 0),
                )
                processed["processed"] = final_img
            except Exception as exc:
                errors.append(f"Error processing image {idx}: {exc}")

        if self.progress_callback:
            self.progress_callback(total_images, total_images, "Processing complete")

        return True, errors

    def process_project_images(self, project_index: int) -> Tuple[bool, List[str]]:
        future = self.process_project_images_async(project_index)
        return future.result()

    def apply_image_adjustments(self, project_index: int, image_index: int, **adjustments: Any) -> Tuple[bool, Optional[str]]:
        project = self.get_project(project_index)
        if not project or image_index >= len(project.processed_images):
            return False, "Invalid indices"

        try:
            processed = project.processed_images[image_index]

            for key in [
                "vof",
                "hof",
                "scale",
                "is_horizontal",
                "use_solid_bg",
                "skip_bg_removal",
                "rotation_angle",
            ]:
                if key in adjustments:
                    processed[key] = adjustments[key]

            no_bg = processed.get("no_bg")
            if not no_bg:
                original_img = project.clothing_images[image_index]["image"]
                if processed.get("skip_bg_removal", False):
                    no_bg = original_img
                else:
                    no_bg = self.image_processor.remove_background(original_img)
                processed["no_bg"] = no_bg

            if "bg_path" in adjustments:
                user_bg = adjustments["bg_path"]
                if user_bg and user_bg not in {"(Auto)", "(Solid Color)"}:
                    processed["user_bg_path"] = user_bg
                    processed["bg_path"] = user_bg
                else:
                    processed["user_bg_path"] = None
                    if not processed.get("use_solid_bg", self.use_solid_bg) and self.backgrounds:
                        processed["bg_path"] = self.image_processor.find_best_background(no_bg, self.backgrounds)

            bg_source = None
            if processed.get("bg_path") and not processed.get("use_solid_bg", self.use_solid_bg):
                try:
                    bg_source = Image.open(processed["bg_path"])
                except Exception:
                    bg_source = None

            final_img = self.image_processor.fit_clothing(
                no_bg,
                bg_source,
                processed["vof"],
                processed["hof"],
                processed["scale"],
                processed["is_horizontal"],
                processed.get("use_solid_bg", self.use_solid_bg),
                processed.get("rotation_angle", 0),
            )
            processed["processed"] = final_img
            return True, None
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Description & export
    # ------------------------------------------------------------------
    def generate_description_for_project(self, project_index: int) -> str:
        project = self.get_project(project_index)
        if not project:
            return ""
        return generate_description(project, self.lang, self.units, self.hashtag_mapping)

    def save_project_output(self, project_index: int, output_dir: str) -> Tuple[bool, str, int, int, bool]:
        project = self.get_project(project_index)
        if project is None:
            return False, "Project not found", 0, 0, False
        return save_project_output(project, project_index, output_dir, self.output_prefix)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------
    def cleanup_temp_dir(self) -> None:
        if self.temp_extract_dir and os.path.exists(self.temp_extract_dir):
            try:
                shutil.rmtree(self.temp_extract_dir)
            except Exception:
                pass
            finally:
                self.temp_extract_dir = None

    def get_cached_thumbnail(self, image_path: Any, size: Tuple[int, int] = (150, 150)) -> Image.Image:
        return self.image_processor.get_cached_thumbnail(image_path, size)


__all__ = ["Backend", "ProjectData", "APP_NAME"]
