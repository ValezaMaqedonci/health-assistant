import easyocr
import numpy as np
from PIL import Image
from google import genai

# ----------------------------
# Gemini
# ----------------------------

import streamlit as st

API_KEY = st.secrets["GOOGLE_API_KEY"]

client = genai.Client(api_key=API_KEY)

# ----------------------------
# EasyOCR (fallback)
# ----------------------------

reader = easyocr.Reader(["en"], gpu=False)


def extract_text(image: Image.Image):

    try:

        # First try Gemini Vision

        prompt = """
If the image contains:

• medicine
→ explain the medicine

• skin rash
→ describe what it looks like
→ possible causes
→ when to see a doctor

• wound
→ explain severity
→ basic first aid

• prescription
→ explain it simply

• lab report
→ explain results

• food
→ estimate calories

If uncertain, clearly state uncertainty.

Never claim a medical diagnosis.
Recommend seeing a healthcare professional for concerning findings.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image]
        )

        if response.text:
            return "💊 Gemini Analysis\n\n" + response.text

    except Exception:
        pass

    # ----------------------------
    # Fallback OCR
    # ----------------------------

    try:

        img = np.array(image)

        results = reader.readtext(img, detail=0)

        if not results:
            return "❌ No readable text found."

        text = "\n".join(results)

        return f"📝 OCR Text\n\n{text}"

    except Exception as e:

        return f"❌ Error:\n{e}"