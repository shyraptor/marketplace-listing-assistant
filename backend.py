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
DEFAULT_SIZE_SCALE = 0.85

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
    Backend logic for Marketplace Listing Assistant.
    
    Handles all data processing, image manipulation, configuration management,
    and business logic for the application.
    """
    
    def __init__(self):
        """Initialize the backend with default settings and load configurations."""
        import threading
        import queue
        from concurrent.futures import ThreadPoolExecutor
        
        self.initialization_error = None
        self.initialization_warning = None
        
        # Load configuration and language files
        self.config_data = self._load_main_config()
        self.selected_language_code = self.config_data.get("language", DEFAULT_LANG_CODE)
        self.lang = self._load_language_config(self.selected_language_code)
        
        # Load templates and hashtag mappings
        self.templates = self._load_templates_config()
        self.hashtag_mapping = self._load_hashtag_mapping_config()
        self.backgrounds = []
        
        # Project data
        self.projects = []
        self.current_project_index = None
        self.temp_extract_dir = None
        self._dominant_color_cache = {}
        
        # Threading support for performance
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.processing_queue = queue.Queue()
        self.progress_callback = None
        self._processing_lock = threading.Lock()
        
        # Image cache for thumbnails
        self._thumbnail_cache = {}
        self._cache_lock = threading.Lock()
        
        self._apply_settings_from_config()

    def _apply_settings_from_config(self):
        """Apply settings from the loaded configuration."""
        # Apply general settings
        self.use_solid_bg = self.config_data.get("use_solid_bg", True)
        self.units = self.config_data.get("units", "cm")
        self.output_prefix = self.config_data.get("output_prefix", "")
        
        self.canvas_width_v = self.config_data.get("canvas_width_v", DEFAULT_CANVAS_WIDTH_V)
        self.canvas_height_v = self.config_data.get("canvas_height_v", DEFAULT_CANVAS_HEIGHT_V)
        self.canvas_width_h = self.config_data.get("canvas_width_h", DEFAULT_CANVAS_WIDTH_H)
        self.canvas_height_h = self.config_data.get("canvas_height_h", DEFAULT_CANVAS_HEIGHT_H)
    
    def _ensure_directory(self, dir_name, auto_create=False):
        """
        Ensures a directory exists, optionally creating it if missing.
        
        Args:
            dir_name: Name of the directory to check
            auto_create: Whether to create the directory if it doesn't exist
            
        Returns:
            tuple: (exists, error_message)
        """
        if not os.path.exists(dir_name):
            if auto_create:
                try:
                    os.makedirs(dir_name)
                    return True, None
                except Exception as e:
                    return False, str(e)
            else:
                return False, f"Directory '{dir_name}' does not exist."
        return True, None

    def _ensure_lang_dir(self):
        """Ensure the language directory exists."""
        return self._ensure_directory(LANG_DIR, auto_create=True)

    def _ensure_bg_dir(self):
        """Ensure the background directory exists."""
        exists, err = self._ensure_directory(BG_DIR, auto_create=True)
        return BG_DIR if exists else ""

    def _get_bg_folder_path(self):
        """
        Get the background folder path, creating it if necessary.
        
        Returns:
            str: Path to the background folder or empty string if creation failed
        """
        try:
            os.makedirs(BG_DIR, exist_ok=True)
            return BG_DIR
        except:
            return ""
    
    def get_available_languages(self):
        """
        Get list of available languages from the language directory.
        
        Returns:
            list: List of tuples (language_code, display_name)
        """
        languages = []
        
        exists, err = self._ensure_lang_dir()
        if not exists:
            return [(DEFAULT_LANG_CODE, DEFAULT_LANG_CODE)]
            
        try:
            for filename in os.listdir(LANG_DIR):
                if filename.endswith(".json"):
                    lang_code = filename[:-5]
                    lang_path = os.path.join(LANG_DIR, filename)
                    
                    try:
                        with open(lang_path, "r", encoding="utf-8") as f:
                            lang_data = json.load(f)
                        display_name = lang_data.get("language_name", lang_code)
                        languages.append((lang_code, display_name))
                    except:
                        languages.append((lang_code, lang_code))
                        
            if not languages:
                languages.append((DEFAULT_LANG_CODE, DEFAULT_LANG_CODE))
                
        except Exception as e:
            languages.append((DEFAULT_LANG_CODE, DEFAULT_LANG_CODE))
            
        return languages

    def _load_language_file(self, lang_code):
        """
        Load a language file by its code.
        
        Args:
            lang_code: Language code (e.g., 'en', 'es')
            
        Returns:
            dict: Language data or None if loading failed
        """
        lang_file_path = os.path.join(LANG_DIR, f"{lang_code}.json")
        try:
            with open(lang_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            return None

    def _load_language_config(self, lang_code):
        """
        Load language configuration with fallback to default.
        
        Args:
            lang_code: Language code to load
            
        Returns:
            dict: Language configuration
        """
        exists, err = self._ensure_lang_dir()
        
        lang_data = self._load_language_file(lang_code)
        
        if lang_data is None and lang_code != DEFAULT_LANG_CODE:
            self.initialization_warning = DEFAULT_LANG_KEYS["lang_load_error"].format(
                lang_code=lang_code, lang_dir=LANG_DIR
            )
            lang_data = self._load_language_file(DEFAULT_LANG_CODE)
            
        if lang_data is None:
            self.initialization_error = DEFAULT_LANG_KEYS["lang_default_load_error"].format(
                lang_code=DEFAULT_LANG_CODE
            )
            return DEFAULT_LANG_KEYS
            
        return lang_data
    
    def _load_json_config(self, filepath, default_data=None):
        """
        Load a JSON configuration file with optional default data.
        
        Args:
            filepath: Path to the JSON file
            default_data: Default data to use if file doesn't exist
            
        Returns:
            dict: Loaded configuration or default data
        """
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                if default_data is not None:
                    return default_data
                return {}
        elif default_data is not None:
            return default_data
        return {}

    def _save_json_config(self, filepath, data):
        """
        Save data to a JSON configuration file.
        
        Args:
            filepath: Path to save the JSON file
            data: Data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            return False

    def _load_main_config(self):
        """
        Load the main application configuration.
        
        Returns:
            dict: Main configuration data
        """
        default_config = {
            "language": DEFAULT_LANG_CODE,
            "use_solid_bg": True
        }
        return self._load_json_config(CONFIG_FILE, default_config)

    def save_main_config(self):
        """
        Save the main application configuration.
        
        Returns:
            bool: True if successful
        """
        config_to_save = {
            "language": self.selected_language_code,
            "use_solid_bg": self.use_solid_bg,
            "units": self.units,
            "output_prefix": self.output_prefix,
            "canvas_width_v": self.canvas_width_v,
            "canvas_height_v": self.canvas_height_v,
            "canvas_width_h": self.canvas_width_h,
            "canvas_height_h": self.canvas_height_h
        }
        return self._save_json_config(CONFIG_FILE, config_to_save)

    def _load_templates_config(self):
        """
        Load clothing type templates configuration.
        
        Returns:
            dict: Templates configuration
        """
        default_templates = {
            "Dress": {
                "fields": ["length", "bust", "waist"],
                "default_tags": ["dress", "women", "clothing"]
            },
            "Shirt": {
                "fields": ["size", "chest", "length"],
                "default_tags": ["shirt", "top", "clothing"]
            }
        }
        return self._load_json_config(TEMPLATES_FILE, default_templates)

    def _load_hashtag_mapping_config(self):
        """
        Load hashtag mapping configuration.
        
        Returns:
            dict: Hashtag mapping configuration
        """
        default_mapping = {
            "vintage": ["vintage", "retro", "classic"],
            "boho": ["boho", "bohemian", "hippie"]
        }
        return self._load_json_config(HASHTAG_FILE, default_mapping)

    def save_templates_config(self):
        """
        Save the templates configuration.
        
        Returns:
            bool: True if successful
        """
        return self._save_json_config(TEMPLATES_FILE, self.templates)

    def save_hashtag_mapping_config(self):
        """
        Save the hashtag mapping configuration.
        
        Returns:
            bool: True if successful
        """
        return self._save_json_config(HASHTAG_FILE, self.hashtag_mapping)
    
    def scan_backgrounds_folder(self):
        """
        Scan the backgrounds folder and load all valid background images.
        
        Returns:
            int: Number of backgrounds loaded
        """
        bg_folder = self._get_bg_folder_path()
        if not bg_folder:
            return 0
            
        self.backgrounds = self._load_backgrounds_from_folder(bg_folder)
        return len(self.backgrounds)

    def _load_backgrounds_from_folder(self, folder_path):
        """
        Load background images from a folder.
        
        Args:
            folder_path: Path to the folder containing background images
            
        Returns:
            list: List of valid image paths
        """
        backgrounds = []
        supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        
        try:
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(supported_formats):
                    full_path = os.path.join(folder_path, filename)
                    if os.path.isfile(full_path):
                        backgrounds.append(full_path)
        except Exception as e:
            pass
            
        return backgrounds

    def add_background_files(self, file_paths):
        """
        Add background files by copying them to the backgrounds folder.
        
        Args:
            file_paths: List of file paths to add
            
        Returns:
            tuple: (success_count, error_messages)
        """
        bg_folder = self._get_bg_folder_path()
        if not bg_folder:
            return 0, ["Background folder does not exist"]
            
        success_count = 0
        errors = []
        
        for src_path in file_paths:
            try:
                if not os.path.exists(src_path):
                    errors.append(f"File not found: {src_path}")
                    continue
                    
                filename = os.path.basename(src_path)
                dest_path = os.path.join(bg_folder, filename)
                
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest_path):
                        new_filename = f"{base}_{counter}{ext}"
                        dest_path = os.path.join(bg_folder, new_filename)
                        counter += 1
                        
                shutil.copy2(src_path, dest_path)
                self.backgrounds.append(dest_path)
                success_count += 1
                
            except Exception as e:
                errors.append(f"Error copying {os.path.basename(src_path)}: {str(e)}")
                
        return success_count, errors

    def add_backgrounds_from_folder(self, folder_path):
        """
        Add all valid background images from a folder.
        
        Args:
            folder_path: Path to folder containing background images
            
        Returns:
            int: Number of backgrounds added
        """
        if not os.path.exists(folder_path):
            return 0
            
        image_files = []
        supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(supported_formats):
                full_path = os.path.join(folder_path, filename)
                if os.path.isfile(full_path):
                    image_files.append(full_path)
                    
        success_count, _ = self.add_background_files(image_files)
        return success_count

    def remove_bg_file(self, bg_path):
        """
        Remove a background file from the system.
        
        Args:
            bg_path: Path to the background file to remove
            
        Returns:
            bool: True if successful
        """
        try:
            if bg_path in self.backgrounds:
                self.backgrounds.remove(bg_path)
                
            if os.path.exists(bg_path):
                os.remove(bg_path)
                
            return True
        except Exception as e:
            return False
    
    def add_new_project(self, name):
        """
        Add a new project to the list.
        
        Args:
            name: Name for the new project
            
        Returns:
            int: Index of the new project
        """
        project = ProjectData(name)
        self.projects.append(project)
        self.current_project_index = len(self.projects) - 1
        return self.current_project_index

    def _load_image(self, image_path):
        """
        Load an image from file path.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            PIL.Image or None if loading failed
        """
        try:
            img = Image.open(image_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            return img
        except Exception as e:
            return None

    def load_single_project_images(self, image_paths):
        """
        Load images for a single project.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            tuple: (success, errors)
        """
        if not image_paths:
            return False, ["No images provided"]
            
        # Always use index-based naming
        project_index = self.add_new_project(f"Project_{len(self.projects) + 1}")
        project = self.projects[project_index]
        
        errors = []
        for path in image_paths:
            img = self._load_image(path)
            if img:
                project.clothing_images.append({
                    "path": path,
                    "image": img
                })
            else:
                errors.append(f"Failed to load: {os.path.basename(path)}")
                
        if not project.clothing_images:
            self.projects.pop(project_index)
            self.current_project_index = len(self.projects) - 1 if self.projects else None
            return False, errors if errors else ["No valid images loaded"]
            
        return True, errors

    def load_projects_from_zip(self, zip_path):
        """
        Load multiple projects from a ZIP file.
        
        Args:
            zip_path: Path to the ZIP file
            
        Returns:
            tuple: (project_count, errors)
        """
        errors = []
        project_count = 0
        
        try:
            self.temp_extract_dir = tempfile.mkdtemp()
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_extract_dir)
                
            root_items = os.listdir(self.temp_extract_dir)
            
            # Check if ZIP contains single folder or multiple items
            if len(root_items) == 1 and os.path.isdir(os.path.join(self.temp_extract_dir, root_items[0])):
                projects_root = os.path.join(self.temp_extract_dir, root_items[0])
            else:
                projects_root = self.temp_extract_dir
                
            # Load each folder as a project with index-based naming
            folders = [item for item in os.listdir(projects_root) 
                      if os.path.isdir(os.path.join(projects_root, item))]
            
            for idx, item in enumerate(folders):
                item_path = os.path.join(projects_root, item)
                
                # Use index-based naming
                project_name = f"Project_{len(self.projects) + 1}"
                project = ProjectData(project_name)
                image_loaded = False
                
                # Load description if exists
                desc_file = os.path.join(item_path, "description.txt")
                if os.path.exists(desc_file):
                    try:
                        with open(desc_file, 'r', encoding='utf-8') as f:
                            project.generated_description = f.read()
                    except:
                        pass
                        
                # Load images
                for filename in os.listdir(item_path):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                        img_path = os.path.join(item_path, filename)
                        img = self._load_image(img_path)
                        if img:
                            project.clothing_images.append({
                                "path": img_path,
                                "image": img
                            })
                            image_loaded = True
                            
                if image_loaded:
                    self.projects.append(project)
                    project_count += 1
                        
            if project_count > 0:
                self.current_project_index = 0
                
        except Exception as e:
            errors.append(f"Error extracting ZIP: {str(e)})")
            
        return project_count, errors

    def get_project_count(self):
        """Get the total number of projects."""
        return len(self.projects)

    def get_current_project_index(self):
        """Get the index of the current project."""
        return self.current_project_index

    def set_current_project_index(self, index):
        """
        Set the current project index.
        
        Args:
            index: New project index
            
        Returns:
            bool: True if index is valid
        """
        if 0 <= index < len(self.projects):
            self.current_project_index = index
            return True
        return False

    def get_project(self, index):
        """
        Get a project by index.
        
        Args:
            index: Project index
            
        Returns:
            ProjectData or None
        """
        if index is not None and 0 <= index < len(self.projects):
            return self.projects[index]
        return None

    def get_current_project(self):
        """Get the current project."""
        return self.get_project(self.current_project_index)

    def update_project_data(self, index, **kwargs):
        """
        Update project data with provided keyword arguments.
        
        Args:
            index: Project index
            **kwargs: Project attributes to update
        """
        project = self.get_project(index)
        if project:
            for key, value in kwargs.items():
                if hasattr(project, key):
                    setattr(project, key, value)

    def remove_project(self, index):
        """
        Remove a project by index.
        
        Args:
            index: Project index to remove
            
        Returns:
            bool: True if successful
        """
        if index is not None and 0 <= index < len(self.projects):
            self.projects.pop(index)
            
            if len(self.projects) == 0:
                self.current_project_index = None
            elif self.current_project_index >= len(self.projects):
                self.current_project_index = len(self.projects) - 1
            elif index < self.current_project_index:
                self.current_project_index -= 1
                
            return True
        return False
    
    def process_single_image(self, project_index, image_index, skip_bg_removal=False, user_bg_path=None):
        """
        Process a single image from a project.
        
        Args:
            project_index: Index of the project
            image_index: Index of the image within the project
            skip_bg_removal: Whether to skip background removal
            user_bg_path: Optional custom background path
            
        Returns:
            tuple: (success, error_message)
        """
        proj = self.get_project(project_index)
        if not proj or image_index >= len(proj.clothing_images):
            return False, "Invalid project or image index"
            
        try:
            original_img = proj.clothing_images[image_index]["image"]
            path = proj.clothing_images[image_index]["path"]
            
            # Initialize or get existing processed image data
            if image_index >= len(proj.processed_images):
                proj.processed_images.append({
                    "path": path,
                    "vof": DEFAULT_VERTICAL_OFFSET,
                    "hof": DEFAULT_HORIZONTAL_OFFSET,
                    "scale": DEFAULT_SIZE_SCALE,
                    "is_horizontal": False,
                    "use_solid_bg": self.use_solid_bg,
                    "skip_bg_removal": skip_bg_removal,
                    "rotation_angle": 0
                })
                
            proc_item = proj.processed_images[image_index]
            proc_item["skip_bg_removal"] = skip_bg_removal
            
            # Process image
            if skip_bg_removal:
                no_bg = original_img
            else:
                no_bg = self.remove_background(original_img)
                
            proc_item["no_bg"] = no_bg
            
            # Determine background
            bg_source = None
            if user_bg_path:
                proc_item["user_bg_path"] = user_bg_path
                proc_item["bg_path"] = user_bg_path
                try:
                    bg_source = Image.open(user_bg_path)
                except:
                    pass
            elif not proc_item.get("use_solid_bg", self.use_solid_bg) and self.backgrounds:
                best_bg = self._find_best_background(no_bg, self.backgrounds)
                if best_bg:
                    proc_item["bg_path"] = best_bg
                    try:
                        bg_source = Image.open(best_bg)
                    except:
                        pass
                        
            # Fit clothing
            final_img = self.fit_clothing(
                no_bg, bg_source,
                proc_item["vof"], proc_item["hof"], proc_item["scale"],
                proc_item["is_horizontal"],
                proc_item.get("use_solid_bg", self.use_solid_bg),
                proc_item.get("rotation_angle", 0)
            )
            
            proc_item["processed"] = final_img
            return True, None
            
        except Exception as e:
            return False, str(e)

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
            if pil_image.mode != 'RGBA':
                return pil_image.convert("RGBA")
            return pil_image

    def _compute_dominant_color(self, image, ignore_transparent=True):
        """
        Computes the dominant color of an image with improved caching.
        
        Args:
            image: PIL Image to analyze
            ignore_transparent: Whether to ignore transparent pixels
            
        Returns:
            tuple: (r, g, b) color values
        """
        try:
            # Create a more stable cache key
            import hashlib
            
            # Use image data hash for cache key
            img_bytes = image.tobytes()
            img_hash = hashlib.md5(img_bytes).hexdigest()
            cache_key = (img_hash, image.size, ignore_transparent)
            
            # Check cache first
            with self._cache_lock:
                if cache_key in self._dominant_color_cache:
                    return self._dominant_color_cache[cache_key]
            
            if image.mode != 'RGBA':
                image = image.convert("RGBA")
                
            # Use smaller sample for faster computation
            small = image.resize((30, 30), Image.Resampling.LANCZOS)
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
                
            # Store in cache with better eviction
            with self._cache_lock:
                self._dominant_color_cache[cache_key] = color
                
                # Improved cache eviction - keep most recent 200 entries
                if len(self._dominant_color_cache) > 200:
                    # Remove oldest 50 entries
                    keys_to_remove = list(self._dominant_color_cache.keys())[:50]
                    for key in keys_to_remove:
                        del self._dominant_color_cache[key]
                
            return color
        except Exception as e:
            return (128, 128, 128)

    def _color_distance(self, c1, c2):
        """Calculate Euclidean distance between two RGB colors."""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))
    
    def _complementary_color(self, color):
        """
        Calculate complementary color for better contrast.
        
        Args:
            color: RGB color tuple
            
        Returns:
            tuple: Complementary RGB color
        """
        r, g, b = color
        
        # Convert to HSV for better complementary calculation
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        diff = max_c - min_c
        
        if diff == 0:
            h = 0
        elif max_c == r:
            h = ((g - b) / diff) % 6
        elif max_c == g:
            h = (b - r) / diff + 2
        else:
            h = (r - g) / diff + 4
            
        h = h * 60
        
        # Rotate hue by 180 degrees for complementary
        h_comp = (h + 180) % 360
        
        # Convert back to RGB (simplified)
        c = 1.0
        x = c * (1 - abs((h_comp / 60) % 2 - 1))
        m = 0.5
        
        if 0 <= h_comp < 60:
            r_comp, g_comp, b_comp = c, x, 0
        elif 60 <= h_comp < 120:
            r_comp, g_comp, b_comp = x, c, 0
        elif 120 <= h_comp < 180:
            r_comp, g_comp, b_comp = 0, c, x
        elif 180 <= h_comp < 240:
            r_comp, g_comp, b_comp = 0, x, c
        elif 240 <= h_comp < 300:
            r_comp, g_comp, b_comp = x, 0, c
        else:
            r_comp, g_comp, b_comp = c, 0, x
            
        # Scale to 0-255 range
        return (
            int((r_comp + m) * 255),
            int((g_comp + m) * 255),
            int((b_comp + m) * 255)
        )

    def _find_best_background(self, clothing_image, background_paths):
        """
        Find the best matching background for a clothing image.
        
        Args:
            clothing_image: PIL Image of clothing
            background_paths: List of background image paths
            
        Returns:
            str: Path to best matching background or None
        """
        if not background_paths:
            return None
            
        try:
            clothing_color = self._compute_dominant_color(clothing_image)
            target_color = self._complementary_color(clothing_color)
            
            best_bg = None
            best_score = float('inf')
            
            for bg_path in background_paths:
                try:
                    # Use cached thumbnail if available
                    cache_key = (bg_path, 'thumb')
                    with self._cache_lock:
                        if cache_key in self._thumbnail_cache:
                            bg_thumb = self._thumbnail_cache[cache_key]
                        else:
                            bg_img = Image.open(bg_path)
                            bg_thumb = bg_img.resize((100, 100), Image.Resampling.LANCZOS)
                            self._thumbnail_cache[cache_key] = bg_thumb
                            
                            # Limit thumbnail cache size
                            if len(self._thumbnail_cache) > 50:
                                # Remove oldest entries
                                keys = list(self._thumbnail_cache.keys())[:10]
                                for k in keys:
                                    del self._thumbnail_cache[k]
                    
                    bg_color = self._compute_dominant_color(bg_thumb, ignore_transparent=False)
                    distance = self._color_distance(bg_color, target_color)
                    
                    if distance < best_score:
                        best_score = distance
                        best_bg = bg_path
                        
                except:
                    continue
                    
            return best_bg
            
        except Exception as e:
            return background_paths[0] if background_paths else None

    def _find_best_background_for_project(self, no_bg_images):
        """
        Find the best background for an entire project based on all images.
        
        Args:
            no_bg_images: List of PIL Images with backgrounds removed
            
        Returns:
            str: Path to best background or None
        """
        if not self.backgrounds or not no_bg_images:
            return None
            
        # Compute average dominant color across all images
        colors = []
        for img in no_bg_images:
            colors.append(self._compute_dominant_color(img))
            
        avg_color = tuple(sum(c[i] for c in colors) // len(colors) for i in range(3))
        
        # Find best background based on average
        return self._find_best_background_by_color(avg_color)
    
    def _find_best_background_by_color(self, target_color):
        """Helper to find best background for a target color."""
        if not self.backgrounds:
            return None
            
        complement = self._complementary_color(target_color)
        best_bg = None
        best_score = float('inf')
        
        for bg_path in self.backgrounds:
            try:
                # Use cached thumbnail
                cache_key = (bg_path, 'thumb')
                with self._cache_lock:
                    if cache_key in self._thumbnail_cache:
                        bg_thumb = self._thumbnail_cache[cache_key]
                    else:
                        bg_img = Image.open(bg_path)
                        bg_thumb = bg_img.resize((100, 100), Image.Resampling.LANCZOS)
                        self._thumbnail_cache[cache_key] = bg_thumb
                
                bg_color = self._compute_dominant_color(bg_thumb, ignore_transparent=False)
                distance = self._color_distance(bg_color, complement)
                
                if distance < best_score:
                    best_score = distance
                    best_bg = bg_path
            except:
                continue
                
        return best_bg

    def fit_clothing(self, clothing_image, background_image, vof, hof, scale, is_horizontal, use_solid_bg, rotation_angle=0):
        """
        Fit clothing image onto background or solid color.
        
        Args:
            clothing_image: PIL Image of clothing
            background_image: PIL Image of background or None
            vof: Vertical offset factor
            hof: Horizontal offset factor
            scale: Scale factor
            is_horizontal: Whether to use horizontal canvas
            use_solid_bg: Whether to use solid background
            rotation_angle: Rotation angle in degrees
            
        Returns:
            PIL.Image: Composite image
        """
        try:
            # Determine canvas size
            if is_horizontal:
                canvas_width = self.canvas_width_h
                canvas_height = self.canvas_height_h
            else:
                canvas_width = self.canvas_width_v
                canvas_height = self.canvas_height_v
                
            # Apply rotation if needed
            if rotation_angle != 0:
                clothing_image = clothing_image.rotate(-rotation_angle, expand=True, fillcolor=(0, 0, 0, 0))
                
            # Create canvas
            if use_solid_bg or background_image is None:
                # Solid color background
                bg_color = self._compute_dominant_color(clothing_image)
                comp_color = self._complementary_color(bg_color)
                canvas = Image.new('RGBA', (canvas_width, canvas_height), comp_color)
            else:
                # Use provided background
                canvas = background_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                if canvas.mode != 'RGBA':
                    canvas = canvas.convert('RGBA')
                    
            # Scale clothing
            cloth_w, cloth_h = clothing_image.size
            max_w = int(canvas_width * scale)
            max_h = int(canvas_height * scale)
            
            scale_w = max_w / cloth_w
            scale_h = max_h / cloth_h
            final_scale = min(scale_w, scale_h)
            
            new_w = int(cloth_w * final_scale)
            new_h = int(cloth_h * final_scale)
            
            clothing_resized = clothing_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Calculate position with offsets
            base_x = (canvas_width - new_w) // 2
            base_y = (canvas_height - new_h) // 2
            
            offset_x = int(hof * canvas_width)
            offset_y = int(vof * canvas_height)
            
            final_x = base_x + offset_x
            final_y = base_y + offset_y
            
            # Ensure clothing stays within canvas
            final_x = max(0, min(final_x, canvas_width - new_w))
            final_y = max(0, min(final_y, canvas_height - new_h))
            
            # Composite
            canvas.paste(clothing_resized, (final_x, final_y), clothing_resized)
            
            return canvas
            
        except Exception as e:
            # Return a placeholder image on error
            canvas = Image.new('RGBA', (canvas_width, canvas_height), (200, 200, 200))
            return canvas

    def process_project_images_async(self, project_index, progress_callback=None):
        """
        Process project images asynchronously with progress updates.
        
        Args:
            project_index: Index of the project to process
            progress_callback: Optional callback for progress updates
            
        Returns:
            concurrent.futures.Future
        """
        self.progress_callback = progress_callback
        future = self.executor.submit(self._process_project_images_worker, project_index)
        return future
    
    def _process_project_images_worker(self, project_index):
        """Worker function for processing project images in background thread."""
        proj = self.get_project(project_index)
        if not proj or not proj.clothing_images:
            return False, ["No project/images"]
        
        errors = []
        total_images = len(proj.clothing_images)
        current_global_setting = self.use_solid_bg
        
        # Process each image
        for idx, item in enumerate(proj.clothing_images):
            if self.progress_callback:
                self.progress_callback(idx + 1, total_images, f"Processing image {idx + 1}/{total_images}")
            
            try:
                path = item["path"]
                original_img = item["image"]
                
                # Check if needs processing
                needs_processing = False
                if idx >= len(proj.processed_images) or proj.processed_images[idx].get("processed") is None:
                    needs_processing = True
                else:
                    processed_item = proj.processed_images[idx]
                    if (not processed_item.get("individual_override", False)) and \
                       (processed_item.get("use_solid_bg", None) != current_global_setting):
                        needs_processing = True
                
                if needs_processing:
                    # Remove background
                    no_bg = self.remove_background(original_img)
                    
                    # Initialize processed data
                    processed_data = {
                        "path": path,
                        "no_bg": no_bg,
                        "bg_path": None,
                        "user_bg_path": None,
                        "processed": None,
                        "vof": DEFAULT_VERTICAL_OFFSET,
                        "hof": DEFAULT_HORIZONTAL_OFFSET,
                        "scale": DEFAULT_SIZE_SCALE,
                        "is_horizontal": False,
                        "use_solid_bg": self.use_solid_bg,
                        "skip_bg_removal": False,
                        "rotation_angle": 0
                    }
                    
                    # Find best background if using image backgrounds
                    bg_source = None
                    if not self.use_solid_bg and self.backgrounds:
                        best_bg = self._find_best_background(no_bg, self.backgrounds)
                        if best_bg:
                            processed_data["bg_path"] = best_bg
                            try:
                                bg_source = Image.open(best_bg)
                            except:
                                pass
                    
                    # Fit clothing
                    final_img = self.fit_clothing(
                        no_bg, bg_source,
                        processed_data["vof"], processed_data["hof"], processed_data["scale"],
                        processed_data["is_horizontal"],
                        processed_data.get("use_solid_bg", self.use_solid_bg),
                        processed_data.get("rotation_angle", 0)
                    )
                    processed_data["processed"] = final_img
                    
                    # Update project data
                    with self._processing_lock:
                        if idx < len(proj.processed_images):
                            proj.processed_images[idx].update(processed_data)
                        else:
                            proj.processed_images.append(processed_data)
                            
            except Exception as e:
                errors.append(f"Error processing image {idx}: {str(e)}")
        
        if self.progress_callback:
            self.progress_callback(total_images, total_images, "Processing complete")
        
        return True, errors

    def process_project_images(self, project_index):
        """
        Synchronous wrapper for backward compatibility.
        
        Args:
            project_index: Index of the project to process
            
        Returns:
            tuple: (success, errors)
        """
        future = self.process_project_images_async(project_index)
        return future.result()

    def apply_image_adjustments(self, project_index, image_index, **adjustments):
        """
        Apply adjustments to a processed image.
        
        Args:
            project_index: Project index
            image_index: Image index within project
            **adjustments: Adjustment parameters
            
        Returns:
            tuple: (success, error_message)
        """
        proj = self.get_project(project_index)
        if not proj or image_index >= len(proj.processed_images):
            return False, "Invalid indices"
            
        try:
            proc_item = proj.processed_images[image_index]
            
            # Update adjustment parameters
            for key in ["vof", "hof", "scale", "is_horizontal", "use_solid_bg", "skip_bg_removal", "rotation_angle"]:
                if key in adjustments:
                    proc_item[key] = adjustments[key]
                    
            # Handle background selection
            if "bg_path" in adjustments:
                user_bg = adjustments["bg_path"]
                if user_bg and user_bg != "(Auto)" and user_bg != "(Solid Color)":
                    proc_item["user_bg_path"] = user_bg
                    proc_item["bg_path"] = user_bg
                else:
                    proc_item["user_bg_path"] = None
                    if not proc_item.get("use_solid_bg", self.use_solid_bg) and self.backgrounds:
                        proc_item["bg_path"] = self._find_best_background(proc_item["no_bg"], self.backgrounds)
                        
            # Mark as having individual override if use_solid_bg changed
            if "use_solid_bg" in adjustments:
                proc_item["individual_override"] = True
                
            # Re-process image
            no_bg = proc_item.get("no_bg")
            if not no_bg:
                original_img = proj.clothing_images[image_index]["image"]
                if proc_item.get("skip_bg_removal", False):
                    no_bg = original_img
                else:
                    no_bg = self.remove_background(original_img)
                proc_item["no_bg"] = no_bg
                
            # Load background if needed
            bg_source = None
            if proc_item.get("bg_path") and not proc_item.get("use_solid_bg", self.use_solid_bg):
                try:
                    bg_source = Image.open(proc_item["bg_path"])
                except:
                    pass
                    
            # Fit clothing with new adjustments
            final_img = self.fit_clothing(
                no_bg, bg_source,
                proc_item["vof"], proc_item["hof"], proc_item["scale"],
                proc_item["is_horizontal"],
                proc_item.get("use_solid_bg", self.use_solid_bg),
                proc_item.get("rotation_angle", 0)
            )
            
            proc_item["processed"] = final_img
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    def _clean_hashtag(self, tag):
        """
        Clean a hashtag by removing special characters and converting to lowercase.
        
        Args:
            tag: Tag to clean
            
        Returns:
            str: Cleaned tag
        """
        # Remove special characters except underscore
        cleaned = re.sub(r'[^a-zA-Z0-9_]', '', tag)
        # Convert to lowercase
        cleaned = cleaned.lower()
        # Remove leading numbers
        cleaned = re.sub(r'^\d+', '', cleaned)
        return cleaned

    def _process_hashtags(self, tags_list):
        """
        Process a list of tags into hashtags using the mapping.
        
        Args:
            tags_list: List of tags
            
        Returns:
            str: Space-separated hashtags
        """
        hashtags = set()
        
        for tag in tags_list:
            tag = tag.strip()
            if not tag:
                continue
                
            # Check if tag exists in mapping
            found_mapping = False
            for key, values in self.hashtag_mapping.items():
                if tag.lower() == key.lower() or tag.lower() in [v.lower() for v in values]:
                    # Add all hashtags from this mapping
                    for hashtag in values:
                        cleaned = self._clean_hashtag(hashtag)
                        if cleaned:
                            hashtags.add(f"#{cleaned}")
                    found_mapping = True
                    break
                    
            # If no mapping found, use the tag itself
            if not found_mapping:
                cleaned = self._clean_hashtag(tag)
                if cleaned:
                    hashtags.add(f"#{cleaned}")
                    
        return " ".join(sorted(hashtags))

    def generate_description_for_project(self, project_index):
        """
        Generate a description for a project based on its metadata.
        
        Args:
            project_index: Index of the project
            
        Returns:
            str: Generated description
        """
        proj = self.get_project(project_index)
        if not proj:
            return ""
            
        parts = []
        
        # Add state if available
        if proj.state:
            parts.append(f"{self.lang.get('state', 'State')}: {proj.state}")
            
        # Add clothing type
        if proj.clothing_type:
            parts.append(f"{self.lang.get('type', 'Type')}: {proj.clothing_type}")
            
        # Add measurements
        measurements = []
        for field, value in proj.measurements.items():
            if value:
                measurements.append(f"{field}: {value} {self.units}")
        if measurements:
            parts.append(f"{self.lang.get('measurements', 'Measurements')}: {', '.join(measurements)}")
            
        # Add owner
        if proj.owner:
            parts.append(f"{self.lang.get('owner', 'Owner')}: {proj.owner}")
            
        # Add storage
        if proj.storage:
            parts.append(f"{self.lang.get('storage', 'Storage')}: {proj.storage}")
            
        # Process tags and colors into hashtags
        all_tags = []
        
        # Add selected tags
        if proj.selected_tags:
            all_tags.extend(proj.selected_tags)
            
        # Add selected colors
        if proj.selected_colors:
            all_tags.extend(proj.selected_colors)
            
        # Add custom hashtags
        if proj.custom_hashtags:
            custom = proj.custom_hashtags.split()
            all_tags.extend(custom)
            
        # Process all tags into hashtags
        if all_tags:
            hashtags = self._process_hashtags(all_tags)
            if hashtags:
                parts.append(hashtags)
                
        # Join all parts
        description = "\n".join(parts)
        
        # Save to project
        proj.generated_description = description
        
        return description
    
    def save_project_output(self, project_index, output_dir):
        """
        Save project output (images and description) to a directory.
        
        Args:
            project_index: Index of the project
            output_dir: Directory to save output
            
        Returns:
            tuple: (success, message)
        """
        proj = self.get_project(project_index)
        if not proj:
            return False, "No project selected"
            
        try:
            # Create project folder using index
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if self.output_prefix:
                folder_name = f"{self.output_prefix}_Project_{project_index + 1}_{timestamp}"
            else:
                folder_name = f"Project_{project_index + 1}_{timestamp}"
                
            project_folder = os.path.join(output_dir, folder_name)
            os.makedirs(project_folder, exist_ok=True)
            
            # Save processed images
            for i, proc_item in enumerate(proj.processed_images):
                if proc_item.get("processed"):
                    img = proc_item["processed"]
                    filename = f"processed_{i+1:03d}.png"
                    img.save(os.path.join(project_folder, filename))
                    
            # Save description
            if proj.generated_description:
                desc_path = os.path.join(project_folder, "description.txt")
                with open(desc_path, 'w', encoding='utf-8') as f:
                    f.write(proj.generated_description)
                    
            return True, f"Saved to {folder_name}"
            
        except Exception as e:
            return False, str(e)
    
    def cleanup_temp_dir(self):
        """Clean up temporary extraction directory."""
        if self.temp_extract_dir and os.path.exists(self.temp_extract_dir):
            try:
                shutil.rmtree(self.temp_extract_dir)
                self.temp_extract_dir = None
            except:
                pass
    
    def get_cached_thumbnail(self, image_path, size=(150, 150)):
        """
        Get a cached thumbnail for an image.
        
        Args:
            image_path: Path to the image or PIL Image object
            size: Thumbnail size
            
        Returns:
            PIL.Image: Thumbnail image
        """
        cache_key = (str(image_path) if isinstance(image_path, str) else id(image_path), size)
        
        with self._cache_lock:
            if cache_key in self._thumbnail_cache:
                return self._thumbnail_cache[cache_key]
        
        # Create thumbnail
        if isinstance(image_path, str):
            img = Image.open(image_path)
        else:
            img = image_path
        
        thumbnail = img.copy()
        thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Cache it
        with self._cache_lock:
            self._thumbnail_cache[cache_key] = thumbnail
            
            # Limit cache size
            if len(self._thumbnail_cache) > 100:
                # Remove oldest entries
                keys = list(self._thumbnail_cache.keys())[:20]
                for k in keys:
                    del self._thumbnail_cache[k]
        
        return thumbnail