import logging
import re
from typing import cast

from langchain_core.messages import HumanMessage

from app.ai.llm import llm

logger = logging.getLogger(__name__)

_IMAGE_INTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(generate|create|make|draw|design|render|produce)\b.{0,40}\b(image|picture|photo|illustration|art|logo|poster|wallpaper|icon)\b", re.IGNORECASE),
    re.compile(r"\b(image|picture|photo|illustration|art|logo|poster|wallpaper|icon)\b.{0,40}\b(generate|create|make|draw|design|render|produce)\b", re.IGNORECASE),
    re.compile(r"\btext[- ]to[- ]image\b", re.IGNORECASE),
)

_IMAGE_MODIFICATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(change|modify|adjust|edit|alter|transform)\b.{0,40}\b(color|brightness|contrast|saturation|size|hue)\b", re.IGNORECASE),
    re.compile(r"\b(make|turn|paint|recolor)\b.{0,20}\b(white|black|red|blue|green|yellow|pink|orange|purple|gray)\b", re.IGNORECASE),
    re.compile(r"\b(brighten|darken|lighten|increase contrast|decrease contrast)\b", re.IGNORECASE),
    re.compile(r"\b(resize|scale|enlarge|reduce|crop)\b.{0,20}\b(image|picture|photo)\b", re.IGNORECASE),
)

_CLASSIFIER_PROMPT = (
    "Classify if the user wants image generation. "
    "Respond with only YES or NO. "
    "YES only when the request is explicitly asking to create a new image/artwork.\n\n"
    "User message: "
)


async def detect_image_generation_intent(message: str, user_email: str) -> bool:
    cleaned = message.strip()
    if not cleaned:
        return False

    if any(pattern.search(cleaned) for pattern in _IMAGE_INTENT_PATTERNS):
        logger.info("Image intent detected via keyword pattern")
        return True

    # Lightweight LLM classifier fallback for ambiguous prompts.
    try:
        result = await llm.ainvoke(
            [HumanMessage(content=f"{_CLASSIFIER_PROMPT}{cleaned[:500]}")],
            config={"metadata": {"user_email": user_email}},
        )
        raw_content = cast(object, result.content)  # type: ignore[reportUnknownMemberType]
        normalized = " ".join(str(item) for item in raw_content) if isinstance(raw_content, list) else str(raw_content)
        decision = normalized.strip().upper()
        detected = decision.startswith("YES")
        logger.info("Image intent LLM classifier decision=%s", "YES" if detected else "NO")
        return detected
    except Exception as exc:
        logger.warning("Image intent classifier failed, defaulting to non-image path: %s", exc)
        return False


def detect_image_modification_intent(message: str) -> tuple[bool, str]:
    """Detect if user wants to modify an image.
    
    Returns:
        Tuple of (is_modification, operation_type)
        operation_type: "color_change", "brightness", "contrast", "resize", "analyze", or ""
    """
    cleaned = message.lower().strip()
    logger.info(f"[DEBUG] DETECT MODIFICATION: checking message: '{cleaned[:100]}'")
    
    if not cleaned:
        return False, ""

    # DETECT COLOR CHANGE - Much simpler and more flexible
    color_words = ["white", "black", "red", "blue", "green", "yellow", "pink", "orange", "purple", "gray", "grey"]
    action_words = ["change", "make", "turn", "paint", "recolor", "color"]
    
    # Check if message contains both action and color words
    has_action = any(word in cleaned for word in action_words)
    has_color = any(word in cleaned for word in color_words)
    
    if has_action and has_color:
        logger.info(f"[DEBUG] COLOR CHANGE DETECTED: has_action={has_action}, has_color={has_color}")
        return True, "color_change"
    
    # Detect brightness/contrast
    if any(word in cleaned for word in ["brighten", "darken", "lighter", "darker", "brightness"]):
        logger.info(f"[DEBUG] BRIGHTNESS MODIFICATION DETECTED")
        return True, "brightness"
    
    if any(word in cleaned for word in ["contrast", "more contrast", "less contrast"]):
        logger.info(f"[DEBUG] CONTRAST MODIFICATION DETECTED")
        return True, "contrast"
    
    # Detect resize
    if any(word in cleaned for word in ["resize", "scale", "enlarge", "reduce", "crop", "smaller", "bigger", "larger"]):
        logger.info(f"[DEBUG] RESIZE MODIFICATION DETECTED")
        return True, "resize"
    
    # Detect analysis
    if any(word in cleaned for word in ["count", "describe", "analyze", "tell me about", "how many", "what"]) and any(word in cleaned for word in ["image", "picture", "photo"]):
        logger.info(f"[DEBUG] ANALYZE MODIFICATION DETECTED")
        return True, "analyze"
    
    logger.info(f"[DEBUG] NO MODIFICATION DETECTED for: '{cleaned[:100]}'")
    return False, ""


async def extract_modification_params(message: str, operation: str, user_email: str) -> dict:
    """Extract parameters for image modification operation."""
    if operation == "color_change":
        # Extract object and target color
        # Simple pattern matching - can be enhanced with LLM if needed
        colors = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "red": (255, 0, 0),
            "blue": (0, 0, 255),
            "green": (0, 255, 0),
            "yellow": (255, 255, 0),
            "pink": (255, 192, 203),
            "orange": (255, 165, 0),
            "purple": (128, 0, 128),
            "gray": (128, 128, 128),
        }
        
        target_color = (255, 255, 255)  # default to white
        found_color = None
        for color_name, rgb in colors.items():
            if color_name in message.lower():
                target_color = rgb
                found_color = color_name
                logger.info(f"[DEBUG] Detected color: {color_name} -> RGB{rgb}")
                break
        
        if not found_color:
            logger.warning(f"[DEBUG] No color found in message, defaulting to white")
        
        # Extract object noun from message - ordered from most specific to least specific
        object_desc = "object"
        _object_keywords = [
            "mango", "mangoes", "monkey", "fur", "skin", "apple", "apples",
            "banana", "bananas", "sky", "cloud", "clouds", "leaf", "leaves",
            "tree", "trees", "grass", "flower", "flowers", "background",
            "shirt", "dress", "hat", "hair", "eye", "eyes",
        ]
        for kw in _object_keywords:
            if kw in message.lower():
                object_desc = kw
                break
        
        logger.info(f"[DEBUG] extract_modification_params: object_desc={object_desc}, target_color={target_color}")
        
        return {
            "object_description": object_desc,
            "target_color": target_color,
            "tolerance": 30,
        }
    
    elif operation == "brightness":
        # Extract brightness factor
        if "brighten" in message.lower() or "lighter" in message.lower():
            return {"factor": 1.5}
        elif "darken" in message.lower() or "darker" in message.lower():
            return {"factor": 0.7}
        return {"factor": 1.0}
    
    elif operation == "contrast":
        if "increase" in message.lower() or "more" in message.lower():
            return {"factor": 1.5}
        elif "decrease" in message.lower() or "less" in message.lower():
            return {"factor": 0.7}
        return {"factor": 1.0}
    
    elif operation == "resize":
        return {"max_width": 800, "max_height": 600}
    
    return {}
