"""Image processing service for modifying uploaded images."""

import base64
import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """Service for processing and modifying images."""

    @staticmethod
    def decode_image(image_base64: str) -> Image.Image:
        """Decode base64 image to PIL Image object.
        
        Args:
            image_base64: Base64 encoded image string (with or without data URI prefix)
        
        Returns:
            PIL Image object
        """
        # Remove data URI prefix if present
        if image_base64.startswith("data:image"):
            image_base64 = image_base64.split(",", 1)[1]
        
        image_bytes = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(image_bytes))

    @staticmethod
    def encode_image(image: Image.Image, format: str = "PNG") -> str:
        """Encode PIL Image to base64 string.
        
        Args:
            image: PIL Image object
            format: Image format (default: PNG)
        
        Returns:
            Base64 encoded image string
        """
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        image_bytes = buffer.getvalue()
        return base64.b64encode(image_bytes).decode()

    @staticmethod
    async def change_object_color(
        image_base64: str,
        object_description: str,
        target_color: tuple,
        tolerance: int = 30,
    ) -> str:
        """Change the color of a specific object in the image.
        
        Args:
            image_base64: Base64 encoded source image
            object_description: Description of the object to modify (e.g., "monkey fur")
            target_color: RGB tuple for target color (e.g., (255, 255, 255) for white)
            tolerance: Color tolerance for detection (0-255)
        
        Returns:
            Base64 encoded modified image
        """
        try:
            # Decode image
            image = ImageProcessingService.decode_image(image_base64)
            
            # Convert to RGB if necessary
            if image.mode == "RGBA":
                # Convert RGBA to RGB
                rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[3] if len(image.split()) > 3 else None)
                image = rgb_image
            elif image.mode != "RGB":
                image = image.convert("RGB")
            
            # Convert to numpy array for processing
            img_array = np.array(image, dtype=np.float32)
            
            # Detect and modify based on object description
            # This uses a simple HSV-based approach for robust color detection
            modified = await ImageProcessingService._apply_color_modification(
                img_array, target_color, object_description, tolerance
            )
            
            # Convert back to PIL Image
            modified_image = Image.fromarray(np.uint8(modified))
            
            # Encode to base64
            return ImageProcessingService.encode_image(modified_image)
            
        except Exception as e:
            logger.error(f"Error changing object color: {e}")
            raise

    @staticmethod
    async def _apply_color_modification(
        img_array: np.ndarray,
        target_color: tuple,
        object_description: str,
        tolerance: int,
    ) -> np.ndarray:
        """Apply color modification based on object detection.
        
        Uses HSV color space for more robust detection.
        """
        import cv2
        
        try:
            # Ensure image is in correct format
            if img_array.dtype != np.uint8:
                img_array = np.uint8(img_array)
            
            # Convert RGB to HSV for better color detection
            img_hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # Define color ranges based on object description
            logger.info(f"[DEBUG] Applying color modification for object: {object_description}")
            
            # Object → typical HSV range mapping
            # Ranges are (lower_hsv, upper_hsv); items with two pairs use bitwise_or for wraparound
            _OBJECT_HSV: dict[str, list] = {
                "mango":      [(20, 100, 100), (45, 255, 255)],
                "mangoes":    [(20, 100, 100), (45, 255, 255)],
                "banana":     [(20, 100, 100), (45, 255, 255)],
                "bananas":    [(20, 100, 100), (45, 255, 255)],
                "monkey":     [(5,  40,  40),  (25, 255, 255)],
                "fur":        [(5,  40,  40),  (25, 255, 255)],
                "skin":       [(0,  10,  60),  (20,  40, 200)],
                "apple":      [(0,  50,  50),  (10, 255, 255), (170, 50, 50), (180, 255, 255)],  # red wrap
                "apples":     [(0,  50,  50),  (10, 255, 255), (170, 50, 50), (180, 255, 255)],
                "sky":        [(90, 50,  50),  (130, 255, 255)],
                "cloud":      [(0,  0,  180),  (180,  30, 255)],  # near-white
                "clouds":     [(0,  0,  180),  (180,  30, 255)],
                "leaf":       [(35, 50,  50),  (85,  255, 255)],
                "leaves":     [(35, 50,  50),  (85,  255, 255)],
                "tree":       [(35, 50,  50),  (85,  255, 255)],
                "trees":      [(35, 50,  50),  (85,  255, 255)],
                "grass":      [(35, 50,  50),  (85,  255, 255)],
                "flower":     [(0,  80,  80),  (180, 255, 255)],
                "flowers":    [(0,  80,  80),  (180, 255, 255)],
            }

            obj_key = object_description.lower().strip()
            if obj_key in _OBJECT_HSV:
                hsv_def = _OBJECT_HSV[obj_key]
                logger.info(f"[DEBUG] Using named object HSV range for: {obj_key}")
                if len(hsv_def) == 4:  # Two ranges (wrap-around, e.g. red)
                    mask = cv2.bitwise_or(
                        cv2.inRange(img_hsv, np.array(hsv_def[0]), np.array(hsv_def[1])),
                        cv2.inRange(img_hsv, np.array(hsv_def[2]), np.array(hsv_def[3])),
                    )
                else:
                    mask = cv2.inRange(img_hsv, np.array(hsv_def[0]), np.array(hsv_def[1]))

                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask_3d = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
                result = img_array.astype(np.float32)
                target_color_array = np.array(target_color, dtype=np.float32)
                mask_normalized = mask_3d.astype(np.float32) / 255.0
                result = (result * (1 - mask_normalized * 0.85)) + (target_color_array * mask_normalized * 0.85)
                result = np.clip(result, 0, 255).astype(np.uint8)
                logger.info(f"[DEBUG] Named-object color modification applied, pixels changed: {np.count_nonzero(mask)}")
                return result
            else:
                # Unknown object — fall back to detecting the most saturated/dominant hue cluster
                logger.info(f"[DEBUG] Unknown object '{obj_key}', using dominant-hue detection")
                # Find the dominant hue band (ignore low-saturation/near-grey pixels)
                sat_mask = img_hsv[:, :, 1] > 60
                val_mask = img_hsv[:, :, 2] > 40
                valid = sat_mask & val_mask
                if valid.sum() > 0:
                    hues = img_hsv[:, :, 0][valid]
                    hist, edges = np.histogram(hues, bins=36, range=(0, 180))
                    dominant_bin = int(np.argmax(hist))
                    center_hue = int(edges[dominant_bin] + (edges[1] - edges[0]) / 2)
                    h_lo = max(0, center_hue - 15)
                    h_hi = min(180, center_hue + 15)
                    lower = np.array([h_lo, 50, 50])
                    upper = np.array([h_hi, 255, 255])
                    logger.info(f"[DEBUG] Dominant hue band: {h_lo}-{h_hi} (center {center_hue})")
                else:
                    lower = np.array([0, 30, 30])
                    upper = np.array([180, 255, 255])
            
            # Create mask for detected regions
            mask = cv2.inRange(img_hsv, lower, upper)
            logger.info(f"[DEBUG] Mask created, mask shape: {mask.shape}, non-zero pixels: {np.count_nonzero(mask)}")
            
            # Apply morphological operations to clean up mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Expand mask to 3 channels for blending
            mask_3d = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
            
            # Apply color change using the mask with smooth blending
            result = img_array.astype(np.float32)
            target_color_array = np.array(target_color, dtype=np.float32)
            mask_normalized = mask_3d.astype(np.float32) / 255.0
            
            # Blend: use 80% target color, 20% original for stronger effect
            result = (result * (1 - mask_normalized * 0.8)) + (target_color_array * mask_normalized * 0.8)
            result = np.clip(result, 0, 255).astype(np.uint8)
            
            logger.info(f"[DEBUG] Color modification applied successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in _apply_color_modification: {e}", exc_info=True)
            raise

    @staticmethod
    async def adjust_brightness(image_base64: str, factor: float) -> str:
        """Adjust image brightness.
        
        Args:
            image_base64: Base64 encoded image
            factor: Brightness factor (1.0 = original, >1.0 = brighter, <1.0 = darker)
        
        Returns:
            Base64 encoded modified image
        """
        try:
            image = ImageProcessingService.decode_image(image_base64)
            enhancer = ImageEnhance.Brightness(image)
            modified = enhancer.enhance(factor)
            return ImageProcessingService.encode_image(modified)
        except Exception as e:
            logger.error(f"Error adjusting brightness: {e}")
            raise

    @staticmethod
    async def adjust_contrast(image_base64: str, factor: float) -> str:
        """Adjust image contrast.
        
        Args:
            image_base64: Base64 encoded image
            factor: Contrast factor (1.0 = original, >1.0 = more contrast, <1.0 = less)
        
        Returns:
            Base64 encoded modified image
        """
        try:
            image = ImageProcessingService.decode_image(image_base64)
            enhancer = ImageEnhance.Contrast(image)
            modified = enhancer.enhance(factor)
            return ImageProcessingService.encode_image(modified)
        except Exception as e:
            logger.error(f"Error adjusting contrast: {e}")
            raise

    @staticmethod
    async def resize_image(image_base64: str, max_width: int, max_height: int) -> str:
        """Resize image to fit within max dimensions while preserving aspect ratio.
        
        Args:
            image_base64: Base64 encoded image
            max_width: Maximum width
            max_height: Maximum height
        
        Returns:
            Base64 encoded resized image
        """
        try:
            image = ImageProcessingService.decode_image(image_base64)
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            return ImageProcessingService.encode_image(image)
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            raise

    @staticmethod
    async def analyze_image_content(image_base64: str) -> dict:
        """Analyze image content and return metadata.
        
        Args:
            image_base64: Base64 encoded image
        
        Returns:
            Dict with image analysis (size, colors, format, etc.)
        """
        try:
            image = ImageProcessingService.decode_image(image_base64)
            
            # Get basic properties
            width, height = image.size
            
            # Get dominant colors (simplified)
            resized = image.resize((100, 100))
            pixels = np.array(resized).reshape(-1, 3)
            
            # Get color statistics
            dominant_color = tuple(pixels.mean(axis=0).astype(int))
            
            return {
                "width": width,
                "height": height,
                "format": image.format,
                "mode": image.mode,
                "dominant_color": dominant_color,
                "file_size_estimate": len(image_base64) * 0.75,  # Rough estimate
            }
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            raise
