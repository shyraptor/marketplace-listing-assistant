"""Image processing helpers for the backend."""
from __future__ import annotations

import hashlib
import math
import threading
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from PIL import Image
from rembg import remove  # type: ignore

from .constants import (
    DEFAULT_CANVAS_HEIGHT_H,
    DEFAULT_CANVAS_HEIGHT_V,
    DEFAULT_CANVAS_WIDTH_H,
    DEFAULT_CANVAS_WIDTH_V,
    DEFAULT_HORIZONTAL_OFFSET,
    DEFAULT_SIZE_SCALE,
    DEFAULT_VERTICAL_OFFSET,
)

ImageLike = Union[str, Image.Image]


class ImageProcessor:
    """Perform background removal, fitting, and colour analysis."""

    def __init__(self) -> None:
        self.canvas_width_v = DEFAULT_CANVAS_WIDTH_V
        self.canvas_height_v = DEFAULT_CANVAS_HEIGHT_V
        self.canvas_width_h = DEFAULT_CANVAS_WIDTH_H
        self.canvas_height_h = DEFAULT_CANVAS_HEIGHT_H

        self._dominant_color_cache: Dict[Tuple[str, Tuple[int, int], bool], Tuple[int, int, int]] = {}
        self._thumbnail_cache: Dict[Tuple[str, Tuple[int, int]], Image.Image] = {}
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Canvas configuration
    # ------------------------------------------------------------------
    def update_canvas_settings(
        self,
        canvas_width_v: int,
        canvas_height_v: int,
        canvas_width_h: int,
        canvas_height_h: int,
    ) -> None:
        self.canvas_width_v = canvas_width_v
        self.canvas_height_v = canvas_height_v
        self.canvas_width_h = canvas_width_h
        self.canvas_height_h = canvas_height_h

    # ------------------------------------------------------------------
    # Image loading helpers
    # ------------------------------------------------------------------
    @staticmethod
    def load_image(image_path: str) -> Optional[Image.Image]:
        """Load an image from disk as RGBA."""
        try:
            img = Image.open(image_path)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            return img
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Background removal and colour analysis
    # ------------------------------------------------------------------
    def remove_background(self, pil_image: Image.Image, max_size: int = 1200) -> Image.Image:
        """Remove the background from an image using rembg."""
        try:
            orig_width, orig_height = pil_image.size
            scale_factor = 1.0

            if max(orig_width, orig_height) > max_size:
                scale_factor = max_size / max(orig_width, orig_height)
                new_size = (int(orig_width * scale_factor), int(orig_height * scale_factor))
                pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

            if pil_image.mode != "RGBA":
                pil_image = pil_image.convert("RGBA")

            buffer = BytesIO()
            pil_image.save(buffer, format="PNG")
            output_data = remove(buffer.getvalue())

            result = Image.open(BytesIO(output_data))
            if result.mode != "RGBA":
                result = result.convert("RGBA")

            if scale_factor < 1.0:
                result = result.resize((orig_width, orig_height), Image.Resampling.LANCZOS)

            return result
        except Exception:
            if pil_image.mode != "RGBA":
                return pil_image.convert("RGBA")
            return pil_image

    def compute_dominant_color(self, image: Image.Image, ignore_transparent: bool = True) -> Tuple[int, int, int]:
        """Compute and cache the dominant colour for an image."""
        try:
            img_hash = hashlib.md5(image.tobytes()).hexdigest()
            cache_key = (img_hash, image.size, ignore_transparent)

            with self._cache_lock:
                cached = self._dominant_color_cache.get(cache_key)
            if cached is not None:
                return cached

            if image.mode != "RGBA":
                image = image.convert("RGBA")

            small = image.resize((30, 30), Image.Resampling.LANCZOS)
            pixels = list(small.getdata())
            r = g = b = count = 0

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

            with self._cache_lock:
                self._dominant_color_cache[cache_key] = color
                if len(self._dominant_color_cache) > 200:
                    for key in list(self._dominant_color_cache.keys())[:50]:
                        del self._dominant_color_cache[key]

            return color
        except Exception:
            return (128, 128, 128)

    @staticmethod
    def _color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

    def _complementary_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        r, g, b = color
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        diff = max_c - min_c

        if diff == 0:
            base = 255 - max_c
            return (base, base, base)

        # Normalised hue shift
        hue_shift = 180 / 360
        rf = r / 255.0
        gf = g / 255.0
        bf = b / 255.0

        maxf = max(rf, gf, bf)
        minf = min(rf, gf, bf)
        diff_f = maxf - minf

        if diff_f == 0:
            hue = 0
        elif maxf == rf:
            hue = ((gf - bf) / diff_f) % 6
        elif maxf == gf:
            hue = (bf - rf) / diff_f + 2
        else:
            hue = (rf - gf) / diff_f + 4

        hue = (hue / 6.0 + hue_shift) % 1.0

        # Convert HSV back to RGB (keeping saturation/value from original)
        value = maxf
        saturation = 0 if maxf == 0 else diff_f / maxf

        def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
            i = int(h * 6)
            f = h * 6 - i
            p = v * (1 - s)
            q = v * (1 - f * s)
            t = v * (1 - (1 - f) * s)
            i = i % 6
            if i == 0:
                r_, g_, b_ = v, t, p
            elif i == 1:
                r_, g_, b_ = q, v, p
            elif i == 2:
                r_, g_, b_ = p, v, t
            elif i == 3:
                r_, g_, b_ = p, q, v
            elif i == 4:
                r_, g_, b_ = t, p, v
            else:
                r_, g_, b_ = v, p, q
            return int(r_ * 255), int(g_ * 255), int(b_ * 255)

        return hsv_to_rgb(hue, saturation, value)

    # ------------------------------------------------------------------
    # Background selection helpers
    # ------------------------------------------------------------------
    def find_best_background(self, clothing_image: Image.Image, background_paths: Sequence[str]) -> Optional[str]:
        best_bg = None
        best_distance = 0  # Changed: We want to maximize distance for contrast
        clothing_color = self.compute_dominant_color(clothing_image)
        
        # Get complementary color for better contrast
        target_color = self._complementary_color(clothing_color)
        
        for bg_path in background_paths:
            try:
                bg_image = Image.open(bg_path)
            except Exception:
                continue
            
            bg_color = self.compute_dominant_color(bg_image, ignore_transparent=False)
            
            # Find background closest to complementary color (for contrast)
            distance = self._color_distance(target_color, bg_color)
            
            # Also consider direct contrast (inverted logic - prefer larger distance from clothing)
            direct_distance = self._color_distance(clothing_color, bg_color)
            
            # Weighted score: prefer backgrounds that are close to complementary OR far from original
            score = direct_distance - (distance * 0.5)
            
            if score > best_distance:
                best_distance = score
                best_bg = bg_path
        
        return best_bg

    def find_best_background_for_project(self, no_bg_images: Iterable[Image.Image], background_paths: Sequence[str]) -> Optional[str]:
        dominant_colors = [self.compute_dominant_color(img) for img in no_bg_images]
        if not dominant_colors:
            return None

        avg_color = tuple(sum(c[i] for c in dominant_colors) // len(dominant_colors) for i in range(3))
        return self._find_best_background_by_color(avg_color, background_paths)

    def _find_best_background_by_color(self, target_color: Tuple[int, int, int], background_paths: Sequence[str]) -> Optional[str]:
        best_bg = None
        best_distance = float("inf")

        for bg_path in background_paths:
            try:
                bg_image = Image.open(bg_path)
                bg_color = self.compute_dominant_color(bg_image, ignore_transparent=False)
            except Exception:
                continue

            distance = self._color_distance(target_color, bg_color)
            if distance < best_distance:
                best_distance = distance
                best_bg = bg_path

        return best_bg

    # ------------------------------------------------------------------
    # Composition helpers
    # ------------------------------------------------------------------
    def _effective_bbox(self, image: Image.Image, alpha_threshold: int = 10) -> Optional[Tuple[int, int, int, int]]:
        """Return a bounding box trimmed by alpha threshold to drop near-transparent halos."""

        if image.mode != "RGBA":
            image = image.convert("RGBA")

        try:
            alpha = image.getchannel("A")
        except ValueError:
            return image.getbbox()

        if alpha_threshold > 0:
            # Treat very transparent pixels as empty to avoid huge boxes from faint remnants
            lut = [0] * (alpha_threshold + 1) + [255] * (255 - alpha_threshold)
            alpha = alpha.point(lut)

        bbox = alpha.getbbox()
        if bbox is None and image.mode == "RGBA":
            # Fallback so completely transparent images still yield something sensible
            return image.getbbox()
        return bbox

    def fit_clothing(
        self,
        clothing_image: Image.Image,
        background_image: Optional[Image.Image],
        vof: float,
        hof: float,
        scale: float,
        is_horizontal: bool,
        use_solid_bg: bool,
        rotation_angle: float = 0,
    ) -> Image.Image:
        canvas_width = self.canvas_width_h if is_horizontal else self.canvas_width_v
        canvas_height = self.canvas_height_h if is_horizontal else self.canvas_height_v

        try:
            if rotation_angle != 0:
                clothing_image = clothing_image.rotate(-rotation_angle, expand=True, fillcolor=(0, 0, 0, 0))

            if use_solid_bg or background_image is None:
                bg_color = self.compute_dominant_color(clothing_image)
                comp_color = self._complementary_color(bg_color)
                canvas = Image.new("RGBA", (canvas_width, canvas_height), comp_color)
            else:
                canvas = background_image.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                if canvas.mode != "RGBA":
                    canvas = canvas.convert("RGBA")

            bbox = self._effective_bbox(clothing_image)
            if bbox:
                clothing_cropped = clothing_image.crop(bbox)
                cloth_w, cloth_h = clothing_cropped.size
            else:
                clothing_cropped = clothing_image
                cloth_w, cloth_h = clothing_image.size

            scale_w = canvas_width / cloth_w
            scale_h = canvas_height / cloth_h
            fit_scale = min(scale_w, scale_h)

            final_scale = fit_scale * scale
            new_size = (int(cloth_w * final_scale), int(cloth_h * final_scale))
            clothing_resized = clothing_cropped.resize(new_size, Image.Resampling.LANCZOS)

            base_x = (canvas_width - new_size[0]) // 2
            base_y = (canvas_height - new_size[1]) // 2

            offset_x = int(hof * canvas_width)
            offset_y = int(vof * canvas_height)
            final_x = max(0, min(base_x + offset_x, canvas_width - new_size[0]))
            final_y = max(0, min(base_y + offset_y, canvas_height - new_size[1]))

            canvas.paste(clothing_resized, (final_x, final_y), clothing_resized)
            return canvas
        except Exception:
            return Image.new("RGBA", (canvas_width, canvas_height), (200, 200, 200))

    # ------------------------------------------------------------------
    # Thumbnail cache
    # ------------------------------------------------------------------
    def get_cached_thumbnail(self, image: ImageLike, size: Tuple[int, int] = (150, 150)) -> Image.Image:
        cache_key = (str(image) if isinstance(image, str) else str(id(image)), size)

        with self._cache_lock:
            thumbnail = self._thumbnail_cache.get(cache_key)
        if thumbnail is not None:
            return thumbnail

        if isinstance(image, str):
            img = Image.open(image)
        else:
            img = image

        thumbnail = img.copy()
        thumbnail.thumbnail(size, Image.Resampling.LANCZOS)

        with self._cache_lock:
            self._thumbnail_cache[cache_key] = thumbnail
            if len(self._thumbnail_cache) > 100:
                for key in list(self._thumbnail_cache.keys())[:20]:
                    del self._thumbnail_cache[key]

        return thumbnail

    # ------------------------------------------------------------------
    # Helpers for processed defaults
    # ------------------------------------------------------------------
    @staticmethod
    def default_processed_entry(path: str, use_solid_bg: bool) -> Dict[str, object]:
        return {
            "path": path,
            "no_bg": None,
            "bg_path": None,
            "user_bg_path": None,
            "processed": None,
            "vof": DEFAULT_VERTICAL_OFFSET,
            "hof": DEFAULT_HORIZONTAL_OFFSET,
            "scale": DEFAULT_SIZE_SCALE,
            "is_horizontal": False,
            "use_solid_bg": use_solid_bg,
            "skip_bg_removal": False,
            "rotation_angle": 0,
        }
