import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import os

def extract_text(image: Image.Image) -> str:
    try:
        gray = image.convert("L")

        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.5)

        sharpened = enhanced.filter(ImageFilter.SHARPEN)

        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(sharpened, config=custom_config)

        text = text.strip()

        if not text:
            return "❌ No readable text found. Try clearer lighting or move closer."

        return text

    except Exception as e:
        return f"⚠️ OCR Error: {e}"