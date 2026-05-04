import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import os

# 🔹 Make sure path is correct
pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"

def extract_text(image: Image.Image) -> str:
    try:
        # Convert to grayscale
        gray = image.convert("L")

        # Increase contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.5)

        # Sharpen image
        sharpened = enhanced.filter(ImageFilter.SHARPEN)

        # OCR config
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(sharpened, config=custom_config)

        # Clean result
        text = text.strip()
        if not text:
            return "❌ No readable text found. Try clearer lighting or move closer."

        # Just return the OCR result (no "unknown medicine")
        return text

    except Exception as e:
        return f"⚠️ OCR Error: {e}"
