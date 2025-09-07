# backend.py
import os
import sys
import json
import datetime
import math
from PIL import Image, ImageOps
from rembg import remove
from io import BytesIO
import zipfile
import tempfile
import shutil
import re
import glob

# ====================== CONSTANTS ======================
TEMPLATES_FILE = "templates.json"
HASHTAG_FILE = "hashtag_mapping.json"
CONFIG_FILE = "config.json"
LANG_DIR = "lang"
BG_DIR = "bg"
DEFAULT_LANG_CODE = "en"
APP_NAME = "Listing Assistant"

# Default language keys (used only if critical loading fails)
DEFAULT_LANG_KEYS = {
    "critical_error_title": "Critical Error",
    "lang_load_error": "Could not load language file '{lang_code}'. Ensure '{lang_code}.json' exists in the '{lang_dir}' folder or reinstall the application. Using default language.",
    "lang_default_load_error": "Could not load default language file ('{lang_code}.json'). Application cannot start. Please reinstall."
}

# Processing constants
DEFAULT_CANVAS_WIDTH_V, DEFAULT_CANVAS_HEIGHT_V = 600, 800  # Vertical canvas
DEFAULT_CANVAS_WIDTH_H, DEFAULT_CANVAS_HEIGHT_H = 800, 600  # Horizontal canvas

DEFAULT_VERTICAL_OFFSET = 0.0
DEFAULT_HORIZONTAL_OFFSET = 0.0
DEFAULT_SIZE_SCALE = 1.0

# ====================== PROJECT DATA CLASS ======================
class ProjectData:
    """
    Represents a project containing images, metadata, and processing settings.
    Each project can have multiple clothing images and their processed versions.
    """
    def __init__(self, name):
        self.name = name
        self.clothing_images = []      # Original images
        self.processed_images = []     # Processed images with metadata
        self.clothing_type = ""        # Type from templates
        self.state = ""                # Condition description
        self.measurements = {}         # Size measurements
        self.selected_tags = []        # Selected hashtag categories
        self.custom_hashtags = ""      # Additional custom hashtags
        self.generated_description = "" # Final description text
        self.owner_letter = ""         # Owner initial for storage code
        self.storage_letter = ""       # Storage code letter
        self.project_bg_path = None    # Project-wide background path

    def __repr__(self):
        return f"<ProjectData '{self.name}' ({len(self.clothing_images)} images)>"

# ====================== BACKEND CLASS ======================
class Backend:
    """
    Main backend class handling data operations, image processing, and configuration.
    
    Responsible for:
    - Loading/saving configuration files
    - Managing language settings
    - Processing images (background removal, resizing)
    - Generating descriptions
    - Managing projects and their data
    """
    def __init__(self):
        self.initialization_error = None
        self.initialization_warning = None
        self._ensure_lang_dir()
        self._ensure_bg_dir()
        self.config_data = self._load_main_config()
        self.selected_language_code = self.config_data.get("selected_language", DEFAULT_LANG_CODE)
        self.lang = self._load_language_config(self.selected_language_code)

        if self.lang:
            self.templates = self._load_templates_config()
            self.hashtag_mapping = self._load_hashtag_mapping_config()
            self.backgrounds = []  # Will be populated by scan_backgrounds_folder()
            self._apply_settings_from_config()
            self.scan_backgrounds_folder()  # Scan for background images
            self.projects = []
            self.current_project_index = -1
            self.temp_extract_dir = None
            self._dominant_color_cache = {}  # Cache for dominant colors
        else:
            print("Backend initialization incomplete due to language loading failure.")

    def _apply_settings_from_config(self):
        """Applies settings loaded from config_data."""
        self.use_solid_bg = self.config_data.get("use_solid_bg", False)
        self.units = self.config_data.get("units", "cm")
        self.output_prefix = self.config_data.get("output_prefix", "mla_")
        
        # Canvas dimensions
        self.canvas_width_v = self.config_data.get("canvas_width_v", DEFAULT_CANVAS_WIDTH_V)
        self.canvas_height_v = self.config_data.get("canvas_height_v", DEFAULT_CANVAS_HEIGHT_V)
        self.canvas_width_h = self.config_data.get("canvas_width_h", DEFAULT_CANVAS_WIDTH_H)
        self.canvas_height_h = self.config_data.get("canvas_height_h", DEFAULT_CANVAS_HEIGHT_H)

    # ====================== DIRECTORY MANAGEMENT ======================
    def _ensure_lang_dir(self):
        """Ensures the language directory exists."""
        if not os.path.isdir(LANG_DIR):
            try:
                os.makedirs(LANG_DIR)
                print(f"Created language directory: {LANG_DIR}")
            except OSError as e:
                print(f"Error creating language directory '{LANG_DIR}': {e}")
                self.initialization_error = f"Cannot create language directory: {LANG_DIR}"
    
    def _ensure_bg_dir(self):
        """Ensures the backgrounds directory exists."""
        bg_dir = self._get_bg_folder_path()
        if not os.path.isdir(bg_dir):
            try:
                os.makedirs(bg_dir)
                print(f"Created backgrounds directory: {bg_dir}")
            except OSError as e:
                print(f"Error creating backgrounds directory '{bg_dir}': {e}")
                self.initialization_warning = f"Cannot create backgrounds directory: {bg_dir}"
    
    def _get_bg_folder_path(self):
        if getattr(sys, 'frozen', False):
            # When frozen, use the folder next to the executable
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        bg_path = os.path.join(base_path, "bg")
        if not os.path.isdir(bg_path):
            os.makedirs(bg_path, exist_ok=True)
        return bg_path

    # ====================== LANGUAGE HANDLING ======================
    def get_available_languages(self):
        """
        Returns a dictionary of available language codes to display names.
        
        Returns:
            dict: Mapping of language codes to display names
        """
        codes = {}
        if not os.path.isdir(LANG_DIR):
            return {DEFAULT_LANG_CODE: "English (Default)"}

        try:
            for filepath in glob.glob(os.path.join(LANG_DIR, "*.json")):
                basename = os.path.basename(filepath)
                lang_code = os.path.splitext(basename)[0]
                display_name = lang_code
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    display_name = data.get("_language_name", lang_code.capitalize())
                except Exception:
                    pass
                codes[lang_code] = display_name
        except Exception as e:
            print(f"Error scanning language directory: {e}")

        if DEFAULT_LANG_CODE not in codes:
            codes[DEFAULT_LANG_CODE] = "English (Default)"

        return dict(sorted(codes.items(), key=lambda item: item[1]))

    def _load_language_file(self, lang_code):
        """
        Attempts to load a language file for the given code.
        
        Args:
            lang_code: The language code to load
            
        Returns:
            dict: The loaded language data or None if loading failed
        """
        filepath = os.path.join(LANG_DIR, f"{lang_code}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading language file '{filepath}': {e}")
                return None
        else:
            print(f"Language file not found: '{filepath}'")
            return None

    def _load_language_config(self, lang_code):
        """
        Loads language file, handling errors with fallbacks.
        
        Args:
            lang_code: The language code to attempt to load
            
        Returns:
            dict: The loaded language data or None if loading critically failed
        """
        selected_data = self._load_language_file(lang_code)

        if selected_data:
            return selected_data
        else:
            if lang_code == DEFAULT_LANG_CODE:
                self.initialization_error = DEFAULT_LANG_KEYS.get("lang_default_load_error", "Critical language load error.").format(lang_code=DEFAULT_LANG_CODE)
                return None
            else:
                print(f"Warning: Failed to load '{lang_code}', falling back to '{DEFAULT_LANG_CODE}'")
                default_data = self._load_language_file(DEFAULT_LANG_CODE)
                if default_data:
                    self.initialization_warning = DEFAULT_LANG_KEYS.get("lang_load_error", "Language load error.").format(lang_code=lang_code, lang_dir=LANG_DIR)
                    self.selected_language_code = DEFAULT_LANG_CODE
                    return default_data
                else:
                    self.initialization_error = DEFAULT_LANG_KEYS.get("lang_default_load_error", "Critical language load error.").format(lang_code=DEFAULT_LANG_CODE)
                    return None

    # ====================== CONFIG LOADING/SAVING ======================
    def _load_main_config(self):
        """
        Loads the main application config file.
        
        Returns:
            dict: The loaded config or an empty dict if loading failed
        """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config '{CONFIG_FILE}': {e}")
        return {}

    def save_main_config(self, config_data):
        """
        Saves the provided config data to the main config file.
        
        Args:
            config_data: The configuration data to save
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            self.config_data = config_data
            self.selected_language_code = self.config_data.get("selected_language", self.selected_language_code)
            self._apply_settings_from_config()
            self.lang = self._load_language_config(self.selected_language_code)
            if not self.lang:
                return False

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving main config: {e}")
            return False

    def _load_templates_config(self):
        """
        Loads the clothing templates configuration.
        
        Returns:
            dict: The loaded templates or default templates if loading failed
        """
        if os.path.exists(TEMPLATES_FILE):
            try:
                with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    v.setdefault("fields", [])
                    v.setdefault("default_tags", [])
                return data
            except Exception as e:
                print(f"Error loading '{TEMPLATES_FILE}': {e}")
        return {
            "T-shirt": {"fields": ["Length", "Width (chest)"], "default_tags": ["base", "t-shirt", "top"]},
            "Pants": {"fields": ["Length", "Waist"], "default_tags": ["base", "pants"]}
        }

    def _load_hashtag_mapping_config(self):
        """
        Loads the hashtag mapping configuration.
        
        Returns:
            dict: The loaded hashtag mappings or default mappings if loading failed
        """
        if os.path.exists(HASHTAG_FILE):
            try:
                with open(HASHTAG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading '{HASHTAG_FILE}': {e}")
        return {"vintage": ["vintage", "retro"], "y2k": ["y2k", "2000s"]}

    def save_templates_config(self, templates_data):
        """
        Saves the templates configuration to file.
        
        Args:
            templates_data: The templates data to save
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            self.templates = templates_data
            with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.templates, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving templates config: {e}")
            return False

    def save_hashtag_mapping_config(self, mapping_data):
        """
        Saves the hashtag mapping configuration to file.
        
        Args:
            mapping_data: The hashtag mapping data to save
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            self.hashtag_mapping = mapping_data
            with open(HASHTAG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.hashtag_mapping, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving hashtag mapping config: {e}")
            return False

    # ====================== BACKGROUND HANDLING ======================
    def scan_backgrounds_folder(self):
        """
        Scans the backgrounds folder and updates the list of available backgrounds.
        
        Returns:
            int: The number of background images found
        """
        bg_dir = self._get_bg_folder_path()
        self.backgrounds = []
        
        if os.path.isdir(bg_dir):
            self.backgrounds = self._load_backgrounds_from_folder(bg_dir)
            self.backgrounds.sort()
        
        return len(self.backgrounds)

    def _load_backgrounds_from_folder(self, folder):
        """
        Loads background image files from a folder.
        
        Args:
            folder: The folder path to scan for images
            
        Returns:
            list: Paths to image files found in the folder
        """
        exts = (".png", ".jpg", ".jpeg", ".webp")
        out = []
        try:
            for f in os.listdir(folder):
                if f.lower().endswith(exts):
                    full = os.path.join(folder, f)
                    if os.path.isfile(full):
                        out.append(os.path.normpath(full))
        except OSError as e:
            print(f"Error reading BG folder {folder}: {e}")
        return out

    def add_background_files(self, file_paths):
        """
        Adds background files by copying them to the bg directory.
        
        Args:
            file_paths: List of file paths to add
            
        Returns:
            tuple: (added_count, skipped_files_info)
        """
        if not file_paths:
            return 0, []
            
        bg_dir = self._get_bg_folder_path()
        added_count = 0
        skipped = []
        
        for source_file in file_paths:
            if not os.path.isfile(source_file):
                skipped.append((os.path.basename(source_file), "Not a file"))
                continue
                
            filename = os.path.basename(source_file)
            target_path = os.path.join(bg_dir, filename)
            
            # Check if file already exists
            if os.path.exists(target_path):
                skipped.append((filename, "Already exists"))
                continue
                
            try:
                shutil.copy2(source_file, target_path)
                added_count += 1
            except Exception as e:
                print(f"Error copying background {source_file}: {e}")
                skipped.append((filename, f"Copy error: {e}"))
        
        # Refresh backgrounds list if files were added
        if added_count > 0:
            self.scan_backgrounds_folder()
            
        return added_count, skipped

    def add_backgrounds_from_folder(self, folder_path):
        """
        Adds backgrounds from a folder to the bg directory.
        
        Args:
            folder_path: Folder containing background images
            
        Returns:
            tuple: (added_count, skipped_files_info)
        """
        if not folder_path or not os.path.isdir(folder_path):
            return 0, []
            
        # Get background files from source folder
        files = self._load_backgrounds_from_folder(folder_path)
        return self.add_background_files(files)

    def remove_bg_file(self, bg_path):
        """
        Removes a background file from the bg directory.
        
        Args:
            bg_path: Path to the background file to remove
            
        Returns:
            tuple: (success, error_message)
        """
        if not bg_path or not os.path.exists(bg_path):
            return False, "File not found"
            
        try:
            os.remove(bg_path)
            # Refresh backgrounds list
            self.scan_backgrounds_folder()
            return True, None
        except Exception as e:
            return False, f"Error removing file: {e}"

    # ====================== PROJECT MANAGEMENT ======================
    def add_new_project(self, name="New Project"):
        """
        Adds a new project with the given name.
        
        Args:
            name: The name for the new project
            
        Returns:
            int: The index of the newly created project
        """
        proj = ProjectData(name)
        self.projects.append(proj)
        return len(self.projects) - 1

    def load_single_project_images(self, project_index, image_paths):
        """
        Loads images into a specific project.
        
        Args:
            project_index: The index of the project to add images to
            image_paths: List of image file paths to load
            
        Returns:
            tuple: (success, loaded_count, errors)
        """
        if not (0 <= project_index < len(self.projects)):
            return False, 0, ["Invalid project index"]
            
        proj = self.projects[project_index]
        loaded_count = 0
        errors = []
        
        for path in image_paths:
            try:
                img = Image.open(path)
                img = ImageOps.exif_transpose(img)
                img.load()
                proj.clothing_images.append({"path": path, "image": img})
                loaded_count += 1
            except FileNotFoundError:
                errors.append(f"Not found: {os.path.basename(path)}")
            except Exception as e:
                errors.append(f"Load fail ({os.path.basename(path)}): {e}")
                
        return loaded_count > 0 or not errors, loaded_count, errors

    def load_projects_from_zip(self, zip_path):
        """
        Loads projects from a zip file with a folder structure.
        
        Args:
            zip_path: Path to the zip file
            
        Returns:
            tuple: (success, message, total_images_loaded, load_errors)
        """
        self.cleanup_temp_dir()
        self.temp_extract_dir = tempfile.mkdtemp(prefix="mla_unzip_")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(self.temp_extract_dir)
        except Exception as e:
            self.cleanup_temp_dir()
            return False, f"Zip Extract Fail: {e}", 0, []
                
        subfolders = []
        load_errors = []
        
        try:
            for name in os.listdir(self.temp_extract_dir):
                full_sub = os.path.join(self.temp_extract_dir, name)
                if os.path.isdir(full_sub):
                    subfolders.append(full_sub)
        except OSError as e:
            self.cleanup_temp_dir()
            return False, f"Folder List Fail: {e}", 0, []
                
        if not subfolders:
            self.cleanup_temp_dir()
            return False, "No subfolders in zip.", 0, []
            
        # Store existing projects instead of clearing them
        existing_projects = self.projects.copy()  
        new_projects = []
        total_images_loaded = 0
        exts = (".png", ".jpg", ".jpeg", ".webp")
        
        for sf in subfolders:
            proj_name = os.path.basename(sf) or "Unnamed"
            proj = ProjectData(proj_name)
            images_in_proj = 0
            
            try:
                for fname in os.listdir(sf):
                    if fname.lower().endswith(exts):
                        full_path = os.path.join(sf, fname)
                        if os.path.isfile(full_path):
                            try:
                                img = Image.open(full_path)
                                img = ImageOps.exif_transpose(img)
                                img.load()
                                proj.clothing_images.append({"path": full_path, "image": img})
                                images_in_proj += 1
                            except Exception as e:
                                load_errors.append(f"Err: {proj_name}/{fname}: {e}")
            except OSError as e:
                load_errors.append(f"Err reading {proj_name}: {e}")
                    
            if proj.clothing_images:
                new_projects.append(proj)
                total_images_loaded += images_in_proj
                    
        if not new_projects:
            self.current_project_index = -1 if not existing_projects else self.current_project_index
            return False, "No valid projects found.", 0, load_errors
        else:
            # Append new projects to existing ones instead of replacing them
            self.projects = existing_projects + new_projects
            
            # Set current project to the first new one
            if existing_projects:
                self.current_project_index = len(existing_projects)
            else:
                self.current_project_index = 0
                
            return True, f"Loaded {len(new_projects)} projects.", total_images_loaded, load_errors

    def get_project_count(self):
        """Returns the number of projects."""
        return len(self.projects)

    def get_current_project_index(self):
        """Returns the index of the current project."""
        return self.current_project_index

    def set_current_project_index(self, index):
        """
        Sets the current project index if valid.
        
        Args:
            index: Index to set as current
            
        Returns:
            bool: True if set successfully, False otherwise
        """
        if 0 <= index < len(self.projects):
            self.current_project_index = index
            return True
        elif not self.projects and index == -1:
            self.current_project_index = -1
            return True
        return False

    def get_project(self, index):
        """
        Gets a project by index.
        
        Args:
            index: Index of the project to get
            
        Returns:
            ProjectData: The project at the given index or None if invalid
        """
        return self.projects[index] if 0 <= index < len(self.projects) else None

    def get_current_project(self):
        """Returns the current project or None if no project is selected."""
        return self.get_project(self.current_project_index)

    def update_project_data(self, index, data_dict):
        """
        Updates a project's data with the provided dictionary.
        
        Args:
            index: Index of the project to update
            data_dict: Dictionary of attributes to update
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        proj = self.get_project(index)
        if not proj:
            return False
            
        for key, value in data_dict.items():
            if hasattr(proj, key):
                setattr(proj, key, value)
                
        return True
    
    def remove_project(self, project_index):
        """
        Removes a project by index.
        
        Args:
            project_index: Index of the project to remove
            
        Returns:
            bool: True if removed successfully, False otherwise
        """
        if 0 <= project_index < len(self.projects):
            self.projects.pop(project_index)
            
            if not self.projects:
                self.current_project_index = -1
            elif project_index >= len(self.projects):
                self.current_project_index = len(self.projects) - 1
                
            return True
        return False

    # ====================== IMAGE PROCESSING LOGIC ======================
    def process_single_image(self, project_index, image_index):
        """
        Processes a single image from a project.
        
        Args:
            project_index: Index of the project containing the image
            image_index: Index of the image within the project
            
        Returns:
            tuple: (success, error_message)
        """
        proj = self.get_project(project_index)
        if not proj or image_index >= len(proj.clothing_images):
            return False, "Invalid project or image index"

        # If already processed with current settings, skip reprocessing
        if image_index < len(proj.processed_images):
            processed_item = proj.processed_images[image_index]
            if (processed_item.get("processed") is not None and 
                processed_item.get("use_solid_bg", None) == self.use_solid_bg):
                return True, None

        try:
            item = proj.clothing_images[image_index]
            path = item["path"]
            original_img = item["image"]

            # Remove background with error handling
            try:
                no_bg = self.remove_background(original_img)
            except Exception as e:
                no_bg = original_img.convert('RGBA')
                error_msg = f"Background removal error: {e}"
            else:
                error_msg = None

            # Determine background source if not using a solid background
            bg_path_auto = None
            bg_source = None
            use_image_bg = (not self.use_solid_bg) and self.backgrounds
            if use_image_bg:
                bg_path_auto = self._find_best_background(no_bg)
                if bg_path_auto:
                    try:
                        bg_source = Image.open(bg_path_auto)
                    except Exception as e_bg:
                        print(f"BG Load Err: {bg_path_auto}: {e_bg}")
                        bg_path_auto = None

            # Default adjustment values
            vof = DEFAULT_VERTICAL_OFFSET
            hof = DEFAULT_HORIZONTAL_OFFSET
            scale = DEFAULT_SIZE_SCALE
            is_horizontal = False

            final_img = self.fit_clothing(no_bg, bg_source, vof, hof, scale, is_horizontal)

            processed_data = {
                "path": path,
                "no_bg": no_bg,
                "bg_path": bg_path_auto,
                "user_bg_path": None,
                "processed": final_img,
                "vof": vof,
                "hof": hof,
                "scale": scale,
                "is_horizontal": is_horizontal,
                "use_solid_bg": self.use_solid_bg,  # update to current global setting
                "skip_bg_removal": False,
                "rotation_angle": 0  # Initialize rotation angle
            }
            if image_index < len(proj.processed_images):
                proj.processed_images[image_index].update(processed_data)
            else:
                proj.processed_images.append(processed_data)
            return True, error_msg
        except Exception as e:
            return False, f"Error processing {os.path.basename(path)}: {e}"

    def remove_background(self, pil_image, max_size=1200):
        """
        Removes the background from an image using rembg.
        
        Args:
            pil_image: PIL Image to process
            max_size: Maximum size for scaling before processing
            
        Returns:
            PIL.Image: Image with background removed
        """
        try:
            # Downscale large images before processing
            orig_width, orig_height = pil_image.size
            scale_factor = 1.0
            
            if max(orig_width, orig_height) > max_size:
                scale_factor = max_size / max(orig_width, orig_height)
                new_width = int(orig_width * scale_factor)
                new_height = int(orig_height * scale_factor)
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert('RGBA')
                
            buf = BytesIO()
            pil_image.save(buf, format="PNG")
            input_data = buf.getvalue()
            
            # Remove background
            output_data = remove(input_data)
            
            result = Image.open(BytesIO(output_data))
            if result.mode != 'RGBA':
                result = result.convert("RGBA")
            
            # Scale back to original size if needed
            if scale_factor < 1.0:
                result = result.resize((orig_width, orig_height), Image.Resampling.LANCZOS)
                
            return result
        except Exception as e:
            print(f"BG Removal Err: {e}")
            if pil_image.mode != 'RGBA':
                return pil_image.convert("RGBA")
            return pil_image

    def _compute_dominant_color(self, image, ignore_transparent=True):
        """
        Computes the dominant color of an image.
        
        Args:
            image: PIL Image to analyze
            ignore_transparent: Whether to ignore transparent pixels
            
        Returns:
            tuple: (r, g, b) color values
        """
        try:
            # Create a cache key from image properties
            cache_key = (id(image), image.size, ignore_transparent)
            
            # Check cache first
            if cache_key in self._dominant_color_cache:
                return self._dominant_color_cache[cache_key]
            
            if image.mode != 'RGBA':
                image = image.convert("RGBA")
                
            small = image.resize((50, 50), Image.Resampling.LANCZOS)
            pixels = list(small.getdata())
            r, g, b, count = 0, 0, 0, 0
            
            for pr, pg, pb, pa in pixels:
                if not ignore_transparent or pa > 128:
                    r += pr
                    g += pg
                    b += pb
                    count += 1
                    
            if count == 0:
                color = (128, 128, 128)
            else:
                color = (r // count, g // count, b // count)
                
            # Store in cache
            self._dominant_color_cache[cache_key] = color
            
            # Limit cache size to prevent memory issues
            if len(self._dominant_color_cache) > 100:
                # Remove oldest entries
                keys_to_remove = list(self._dominant_color_cache.keys())[:20]
                for key in keys_to_remove:
                    del self._dominant_color_cache[key]
                
            return color
        except Exception as e:
            print(f"Dominant Color Err: {e}")
            return (128, 128, 128)

    def _color_distance(self, c1, c2):
        """Calculates Euclidean distance between two RGB colors."""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
    

    def _complementary_color(self, color):
        """
        Returns a complementary color that makes the object stand out.
        
        Args:
            color: RGB tuple of the original color
            
        Returns:
            tuple: RGB tuple of the complementary color
        """
        r, g, b = color
        
        # Base complementary color (opposite on color wheel)
        comp_r, comp_g, comp_b = 255 - r, 255 - g, 255 - b
        
        # Calculate luminance of original color
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        
        # For dark objects, use a light background
        if luminance < 128:
            # Brighten the complementary color
            comp_r = min(255, comp_r + 40)
            comp_g = min(255, comp_g + 40)
            comp_b = min(255, comp_b + 40)
        else:
            # For light objects, use a darker background
            comp_r = max(0, comp_r - 40)
            comp_g = max(0, comp_g - 40)
            comp_b = max(0, comp_b - 40)
        
        # Enhance contrast by increasing difference in dominant channels
        max_channel = max(r, g, b)
        if r == max_channel:
            comp_r = min(255, comp_r + 20)
        if g == max_channel:
            comp_g = min(255, comp_g + 20)
        if b == max_channel:
            comp_b = min(255, comp_b + 20)
        
        return (comp_r, comp_g, comp_b)

    def _find_best_background(self, cutout_image):
        """
        Finds the background that provides the best contrast with the cutout.
        
        Args:
            cutout_image: Image with transparent background
            
        Returns:
            str: Path to the best background image or None if none available
        """
        if not self.backgrounds:
            return None
            
        dom_color = self._compute_dominant_color(cutout_image)
        best_bg_path = None
        max_dist = -1
        
        for bg_path in self.backgrounds:
            try:
                with Image.open(bg_path) as bg_img:
                    avg_bg_color = self._compute_dominant_color(bg_img, ignore_transparent=False)
                    dist = self._color_distance(dom_color, avg_bg_color)
                    
                    if dist > max_dist:
                        max_dist = dist
                        best_bg_path = bg_path
            except Exception as e:
                print(f"BG Candidate Err {bg_path}: {e}")
                
        return best_bg_path
    
    def _find_best_background_for_project(self, cutout_images):
        """
        Finds the best background for an entire project based on average color of all cutouts.
        
        Args:
            cutout_images: List of RGBA images with transparent backgrounds
            
        Returns:
            str: Path to the best background image or None if none available
        """
        if not self.backgrounds or not cutout_images:
            return None
            
        # Calculate average color across all cutout images
        total_r, total_g, total_b = 0, 0, 0
        count = 0
        
        for cutout in cutout_images:
            try:
                color = self._compute_dominant_color(cutout)
                total_r += color[0]
                total_g += color[1]
                total_b += color[2]
                count += 1
            except Exception as e:
                print(f"Error computing color for cutout: {e}")
                
        if count == 0:
            return None
            
        # Average color of all items
        avg_item_color = (total_r // count, total_g // count, total_b // count)
        
        # Find background with best contrast to average
        best_bg_path = None
        max_dist = -1
        
        for bg_path in self.backgrounds:
            try:
                with Image.open(bg_path) as bg_img:
                    avg_bg_color = self._compute_dominant_color(bg_img, ignore_transparent=False)
                    dist = self._color_distance(avg_item_color, avg_bg_color)
                    
                    if dist > max_dist:
                        max_dist = dist
                        best_bg_path = bg_path
            except Exception as e:
                print(f"BG Candidate Err {bg_path}: {e}")
                
        return best_bg_path

    def fit_clothing(self, cutout_image, background_image, vof, hof, scale, is_horizontal=False, use_solid_bg=None, rotation_angle=0):
        """
        Fits a cutout clothing image onto a background.
        
        Args:
            cutout_image: Image with transparent background
            background_image: Optional background image
            vof: Vertical offset factor (-1.0 to 1.0)
            hof: Horizontal offset factor (-1.0 to 1.0)
            scale: Scale factor
            is_horizontal: Whether to use horizontal canvas dimensions
            use_solid_bg: Override for solid background setting
            rotation_angle: Rotation angle in degrees (0, 90, 180, 270)
            
        Returns:
            PIL.Image: Final composed image
        """
        try:
            target_w = self.canvas_width_h if is_horizontal else self.canvas_width_v
            target_h = self.canvas_height_h if is_horizontal else self.canvas_height_v
            
            bbox = cutout_image.getbbox()
            content = cutout_image.crop(bbox) if bbox else cutout_image
            
            if content.size[0] == 0 or content.size[1] == 0:
                return Image.new("RGBA", (target_w, target_h), (0,0,0,0))
            
            # Apply rotation if needed
            if rotation_angle != 0:
                content = content.rotate(-rotation_angle, expand=True)
                
            cw, ch = content.size
            scale_factor_w = target_w / cw if cw > 0 else 1
            scale_factor_h = target_h / ch if ch > 0 else 1
            
            final_scale = min(scale_factor_w, scale_factor_h) * scale
            new_w = max(1, int(cw * final_scale))
            new_h = max(1, int(ch * final_scale))
            content_resized = content.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Use provided use_solid_bg parameter if given, otherwise use the global setting
            image_use_solid_bg = self.use_solid_bg if use_solid_bg is None else use_solid_bg
            
            if background_image and not image_use_solid_bg:
                bg_to_use = background_image.copy()
                bg_resized = bg_to_use.resize((target_w, target_h), Image.Resampling.LANCZOS)
                if bg_resized.mode != 'RGBA':
                    final_canvas = bg_resized.convert("RGBA")
                else:
                    final_canvas = bg_resized
            else:
                dom_color = self._compute_dominant_color(content_resized)
                comp_color = self._complementary_color(dom_color)
                final_canvas = Image.new("RGBA", (target_w, target_h), comp_color)
                
            # Calculate center position
            base_x = (target_w - new_w) // 2
            base_y = (target_h - new_h) // 2
            
            # Apply offsets
            # Horizontal: positive = move right, negative = move left
            # Vertical: positive = move up, negative = move down
            x_offset = int(hof * target_w / 2)  # Scale to half the width of canvas
            y_offset = int(-vof * target_h / 2)  # Scale to half the height of canvas, negative to match UI direction
            
            paste_x = base_x + x_offset
            paste_y = base_y + y_offset
            
            # Composite: Background -> Object
            final_canvas.paste(content_resized, (paste_x, paste_y), content_resized)
            return final_canvas
        except Exception as e:
            print(f"Fit Clothing Err: {e}")
            return Image.new("RGBA", (self.canvas_width_v, self.canvas_height_v), (255,0,0,128))

    def process_project_images(self, project_index):
        """
        Processes all images in a project.
        
        Args:
            project_index: Index of the project to process
            
        Returns:
            tuple: (success, errors)
        """
        proj = self.get_project(project_index)
        if not proj or not proj.clothing_images:
            return False, ["No project/images"]
                
        use_image_bg = not self.use_solid_bg and self.backgrounds
        errors = []
        current_global_setting = self.use_solid_bg  # global setting
        
        # First pass: Extract all images (no_bg)
        all_no_bg_images = []

        for idx, item in enumerate(proj.clothing_images):
            path = item["path"]
            original_img = item["image"]
                
            needs_processing = False
                
            # If the image was never processed or processing failed.
            if idx >= len(proj.processed_images) or proj.processed_images[idx].get("processed") is None:
                needs_processing = True
            else:
                processed_item = proj.processed_images[idx]
                # Only force re‑processing if there is no individual override and the stored use_solid_bg is out‑of‑date.
                if (not processed_item.get("individual_override", False)) and (processed_item.get("use_solid_bg", None) != current_global_setting):
                    needs_processing = True
                # Collect existing no_bg images
                if processed_item.get("no_bg") is not None:
                    all_no_bg_images.append(processed_item["no_bg"])
                
            if needs_processing:
                try:
                    no_bg = self.remove_background(original_img)
                    all_no_bg_images.append(no_bg)
                    
                    # Store temporarily without finalizing
                    processed_data = {
                        "path": path,
                        "no_bg": no_bg,
                        "bg_path": None,
                        "user_bg_path": None,
                        "processed": None,  # Will be finalized later
                        "vof": DEFAULT_VERTICAL_OFFSET,
                        "hof": DEFAULT_HORIZONTAL_OFFSET,
                        "scale": DEFAULT_SIZE_SCALE,
                        "is_horizontal": False,
                        "use_solid_bg": self.use_solid_bg,
                        "skip_bg_removal": False,
                        "rotation_angle": 0
                    }
                        
                    if idx < len(proj.processed_images):
                        proj.processed_images[idx].update(processed_data)
                    else:
                        proj.processed_images.append(processed_data)
                except Exception as e:
                    errors.append(f"BG Removal Err ({os.path.basename(path)}): {e}")
        
        # Second pass: Select project-wide background based on all extracted images
        if use_image_bg and all_no_bg_images:
            proj.project_bg_path = self._find_best_background_for_project(all_no_bg_images)
        else:
            proj.project_bg_path = None
            
        # Third pass: Apply the project background to all images
        bg_source = None
        if proj.project_bg_path:
            try:
                bg_source = Image.open(proj.project_bg_path)
            except Exception as e:
                print(f"Failed to load project background {proj.project_bg_path}: {e}")
                bg_source = None
                
        # Now finalize all processed images with the same background
        for idx, item in enumerate(proj.processed_images):
            if item.get("processed") is None:  # Only process unfinalized images
                try:
                    no_bg = item["no_bg"]
                    item["bg_path"] = proj.project_bg_path
                    
                    # Fit clothing with project background
                    final_img = self.fit_clothing(
                        no_bg, bg_source, 
                        item["vof"], item["hof"], item["scale"], 
                        item["is_horizontal"],
                        item.get("use_solid_bg", self.use_solid_bg),
                        item.get("rotation_angle", 0)
                    )
                    item["processed"] = final_img
                except Exception as e:
                    errors.append(f"Finalization error for image {idx}: {e}")
                        
        return True, errors

    def apply_image_adjustments(self, project_index, image_index, vof, hof, scale, 
                            user_bg_path=None, is_horizontal=False, skip_bg_removal=False, 
                            use_solid_bg=None, force_reprocess=False, rotation_angle=0):
        """
        Applies adjustments to a processed image.
        
        Args:
            project_index: Index of the project
            image_index: Index of the image within the project
            vof: Vertical offset factor
            hof: Horizontal offset factor
            scale: Scale factor
            user_bg_path: Optional user-selected background path
            is_horizontal: Whether to use horizontal canvas dimensions
            skip_bg_removal: Whether to skip background removal
            use_solid_bg: Override for solid background setting
            force_reprocess: Whether to force reprocessing from original
            
        Returns:
            PIL.Image: New processed image or None if failed
        """
        proj = self.get_project(project_index)
        if not proj or not (0 <= image_index < len(proj.processed_images)):
            return None

        item = proj.processed_images[image_index]
        item["vof"] = vof
        item["hof"] = hof
        item["scale"] = scale
        item["user_bg_path"] = user_bg_path
        item["is_horizontal"] = is_horizontal
        item["skip_bg_removal"] = skip_bg_removal
        item["rotation_angle"] = rotation_angle

        # Update the individual solid background setting and mark override if it differs from the global default.
        if use_solid_bg is not None:
            item["use_solid_bg"] = use_solid_bg
            if use_solid_bg != self.use_solid_bg:
                item["individual_override"] = True
            else:
                item.pop("individual_override", None)

        no_bg = item["no_bg"]

        if force_reprocess:
            # Re-generate no_bg using the original image.
            orig_image = None
            for img_data in proj.clothing_images:
                if img_data["path"] == item["path"]:
                    orig_image = img_data["image"]
                    break
            if orig_image:
                if skip_bg_removal:
                    if orig_image.mode != 'RGBA':
                        no_bg = orig_image.convert("RGBA")
                    else:
                        no_bg = orig_image
                else:
                    no_bg = self.remove_background(orig_image)
                item["no_bg"] = no_bg

        bg_source = None
        # Determine the effective background path:
        effective_bg_path = user_bg_path if user_bg_path is not None else item.get("bg_path")
        # If no background path is stored and the individual setting requests an image background,
        # try to auto-find one.
        if effective_bg_path is None and not item.get("use_solid_bg", self.use_solid_bg) and self.backgrounds:
            effective_bg_path = self._find_best_background(no_bg)
            item["bg_path"] = effective_bg_path

        if effective_bg_path and not item.get("use_solid_bg", self.use_solid_bg) and not skip_bg_removal:
            try:
                bg_source = Image.open(effective_bg_path)
            except Exception as e:
                print(f"Warn: Reload BG {effective_bg_path} failed: {e}")

        try:
            new_final = self.fit_clothing(no_bg, bg_source, vof, hof, scale, is_horizontal,
                                        item.get("use_solid_bg", self.use_solid_bg), rotation_angle)
            item["processed"] = new_final
            return new_final
        except Exception as e:
            print(f"Adjustment Err img {image_index}: {e}")
            return None

    # ====================== DESCRIPTION GENERATION ======================
    def generate_description_for_project(self, project_index):
        """
        Generates a formatted description for a project based on its data.
        
        Args:
            project_index: Index of the project
            
        Returns:
            str: Generated description text
        """
        proj = self.get_project(project_index)
        if not proj:
            return ""
            
        # Ensure data used for generation is current by getting it from proj directly
        state_text = proj.state.strip()
        measurement_lines = []
        
        for field, val in proj.measurements.items():
            val_str = val.strip()
            if val_str:
                field_display = field.replace("_", " ").replace("-", " ").capitalize()
                measurement_lines.append(f"{field_display}: {val_str}{self.units}")
                
        measurement_desc = "\n".join(measurement_lines)
        hashtags = set()
        
        for tag in proj.selected_tags:
            tag_lower = tag.lower()
            if tag_lower in self.hashtag_mapping:
                for ht in self.hashtag_mapping[tag_lower]:
                    clean_ht = ht.strip().replace(" ", "_")
                    if clean_ht:
                        if not clean_ht.startswith('#'):
                            clean_ht = '#' + clean_ht
                        hashtags.add(clean_ht.lower())
            elif tag:
                clean_ht = tag.strip().replace(" ", "_")
                if clean_ht:
                    if not clean_ht.startswith('#'):
                        clean_ht = '#' + clean_ht
                    hashtags.add(clean_ht.lower())
                    
        custom_list = [c.strip() for c in proj.custom_hashtags.split(',') if c.strip()] if proj.custom_hashtags else []
        
        for ctag in custom_list:
            clean_ctag = ctag.replace(" ", "_")
            if not clean_ctag.startswith('#'):
                clean_ctag = '#' + clean_ctag
            hashtags.add(clean_ctag.lower())
            
        sorted_hashtags = sorted(list(hashtags))
        hashtags_text = " ".join(sorted_hashtags)
        storage_tag = ""
        
        owner = proj.owner_letter.strip().upper()
        storage = proj.storage_letter.strip().upper()
        
        if owner or storage:
            date_tag = datetime.datetime.now().strftime("%m%y")
            storage_tag = f"{owner}{storage}{date_tag}"
            
        desc_parts = []
        
        if state_text:
            desc_parts.append(state_text)
            
        if measurement_desc:
            if desc_parts:
                desc_parts.append("")
            desc_parts.append("📏 Measurements:")
            desc_parts.append(measurement_desc)
            
        if hashtags_text:
            if desc_parts:
                desc_parts.append("")
            desc_parts.append("✨ Tags:")
            desc_parts.append(hashtags_text)
            
        if storage_tag:
            if desc_parts:
                desc_parts.append("")
            desc_parts.append(f"📦 Ref: {storage_tag}")
            
        final_description = "\n".join(desc_parts)
        proj.generated_description = final_description
        
        return final_description

    # ====================== OUTPUT SAVING ======================
    def save_project_output(self, project_index, base_folder):
        """
        Saves project images and description to the specified folder.
        
        Args:
            project_index: Index of the project to save
            base_folder: Base folder path to save to
            
        Returns:
            tuple: (success, output_folder/error_message, img_ok, img_err, desc_saved)
        """
        proj = self.get_project(project_index)
        if not proj or not proj.processed_images:
            return False, "No processed images.", 0, 0, False
            
        proj_name_sanitized = re.sub(r'[^\w\-_\. ]', '_', proj.name.strip())
        proj_name_sanitized = re.sub(r'\s+', '_', proj_name_sanitized)
        
        if not proj_name_sanitized:
            proj_name_sanitized = f"output_{datetime.datetime.now():%Y%m%d_%H%M%S}"
            
        output_folder = os.path.join(base_folder, proj_name_sanitized)
        
        try:
            os.makedirs(output_folder, exist_ok=True)
        except OSError as e:
            return False, f"Folder Create Fail: {e}", 0, 0, False
            
        img_ok, img_err = 0, 0
        
        for i, item in enumerate(proj.processed_images):
            original_basename = re.sub(r'[^\w\-_\.]', '_', os.path.splitext(os.path.basename(item["path"]))[0])
            save_name = f"{self.output_prefix}{proj_name_sanitized}_{i+1:02d}_{original_basename}.png"
            save_path = os.path.join(output_folder, save_name)
            
            try:
                item["processed"].save(save_path, format='PNG')
                img_ok += 1
            except Exception as e:
                print(f"Save Err: {save_path}: {e}")
                img_err += 1
                
        desc_path = os.path.join(output_folder, f"{proj_name_sanitized}_description.txt")
        desc_saved = False
        
        try:
            desc_content = proj.generated_description
            with open(desc_path, "w", encoding="utf-8") as f:
                f.write(desc_content)
            desc_saved = True
        except Exception as e:
            print(f"Save Desc Err: {desc_path}: {e}")
            
        return True, output_folder, img_ok, img_err, desc_saved

    # ====================== CLEANUP ======================
    def cleanup_temp_dir(self):
        """Cleans up the temporary extraction directory."""
        if self.temp_extract_dir and os.path.isdir(self.temp_extract_dir):
            try:
                shutil.rmtree(self.temp_extract_dir, ignore_errors=True)
                self.temp_extract_dir = None
            except Exception as e:
                print(f"Warn: failed remove {self.temp_extract_dir}: {e}")