"""Non-destructive image quality checks and conservative enhancement for crop photos."""
from __future__ import annotations
from io import BytesIO
from typing import Any

MAX_PIXELS = 25_000_000


def inspect_and_enhance(image_bytes: bytes) -> dict[str, Any]:
    """Validate/decode image and return an enhanced copy only when it may help.

    The original bytes are never modified. Enhancement is not used to create or infer symptoms.
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageStat, UnidentifiedImageError
    except ImportError:
        return {"valid": True, "quality_check": "unavailable", "enhanced_bytes": image_bytes,
                "enhanced": False, "warnings": ["Pillow is not installed; image quality checks were skipped."]}
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            source.verify()
        with Image.open(BytesIO(image_bytes)) as source:
            if source.width * source.height > MAX_PIXELS:
                return {"valid": False, "reason": "Image dimensions are too large; use a smaller image."}
            image = source.convert("RGB")
            stat = ImageStat.Stat(image.convert("L"))
            mean_luma = stat.mean[0]
            std_luma = stat.stddev[0]
            # Laplacian variance is a rough blur signal, not a diagnosis.
            gray = image.convert("L")
            edge = gray.filter(ImageFilter.FIND_EDGES)
            edge_var = ImageStat.Stat(edge).var[0]
            warnings = []
            if mean_luma < 45: warnings.append("Image is dark; use brighter, indirect daylight if possible.")
            if std_luma < 22: warnings.append("Image has low contrast; move closer and focus on the affected area.")
            if edge_var < 65: warnings.append("Image may be blurry or out of focus; retake a closer, steady photo if details are unclear.")
            too_unclear = edge_var < 12 or mean_luma < 18
            enhanced = False
            working = image.copy()
            # Apply only modest enhancement when illumination/contrast is poor.
            if mean_luma < 65:
                working = ImageEnhance.Brightness(working).enhance(1.12)
                enhanced = True
            if std_luma < 30:
                working = ImageEnhance.Contrast(working).enhance(1.12)
                enhanced = True
            if enhanced:
                working = working.filter(ImageFilter.UnsharpMask(radius=1, percent=105, threshold=4))
                output = BytesIO(); working.save(output, format="JPEG", quality=92, optimize=True)
                enhanced_bytes = output.getvalue()
            else:
                enhanced_bytes = image_bytes
            return {"valid": True, "quality_check": "completed", "enhanced_bytes": enhanced_bytes,
                    "enhanced": enhanced, "too_unclear": too_unclear, "mean_brightness": round(mean_luma, 1),
                    "contrast_estimate": round(std_luma, 1), "edge_detail_estimate": round(edge_var, 1),
                    "warnings": warnings}
    except Exception:
        return {"valid": False, "reason": "The uploaded file is not a complete, readable image. Please upload a valid JPEG, PNG, or WebP image."}
