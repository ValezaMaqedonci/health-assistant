import os
import html
import streamlit as st
from pathlib import Path

MODEL_URL = "/app/static/models"

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "static" / "models"


ORGANS = {
    "Brain": {
        "name": "Brain",
        "system": "Nervous system",
        "model": f"{MODEL_URL}/human-brain.glb",
        "function": (
            "The brain processes information, supports learning and memory, "
            "and coordinates many body functions."
        ),
        "facts": [
            "It communicates with the body through nerves.",
            "It helps control movement and memory.",
            "Sleep supports learning and brain function.",
        ],
    },
    "Heart": {
        "name": "Heart",
        "system": "Circulatory system",
        "model": f"{MODEL_URL}/human-heart.glb",
        "function": (
            "The heart pumps blood around the body, delivering oxygen "
            "and nutrients to tissues."
        ),
        "facts": [
            "It has four chambers.",
            "Valves help blood flow in the correct direction.",
            "It works continuously to circulate blood.",
        ],
    },
    "Lungs": {
        "name": "Lungs",
        "system": "Respiratory system",
        "model": f"{MODEL_URL}/human-lungs.glb",
        "function": (
            "The lungs bring oxygen into the body and help remove "
            "carbon dioxide when you breathe."
        ),
        "facts": [
            "The right lung is generally larger than the left.",
            "The diaphragm helps you breathe.",
            "The lungs contain branching airways.",
        ],
    },
    "Liver": {
        "name": "Liver",
        "system": "Digestive system",
        "model": f"{MODEL_URL}/human-liver.glb",
        "function": (
            "The liver processes nutrients, produces bile, and helps "
            "the body process medicines."
        ),
        "facts": [
            "Bile helps digest fats.",
            "The liver stores certain nutrients.",
            "It performs many important chemical processes.",
        ],
    },
    "Kidneys": {
        "name": "Kidneys",
        "system": "Urinary system",
        "model": f"{MODEL_URL}/human-kidney.glb",
        "function": (
            "The kidneys filter the blood, remove waste into urine, "
            "and help regulate fluid and mineral balance."
        ),
        "facts": [
            "Most people have two kidneys.",
            "They help regulate fluid balance.",
            "They also contribute to blood pressure regulation.",
        ],
    },
    "Stomach": {
        "name": "Stomach",
        "system": "Digestive system",
        # The supplied code reused the liver model here. Keep the URL for now,
        # but show a clear note so it is not misrepresented as a separate model.
        "model": f"{MODEL_URL}/human-stomach.glb",
        "model_note": "The current 3D asset is shared with the liver. Replace it with a dedicated stomach GLB for an anatomically correct view.",
        "function": (
            "The stomach mixes food with acid and digestive enzymes "
            "to help break it down."
        ),
        "facts": [
            "Its muscular walls mix food.",
            "Its lining helps protect it from stomach acid.",
            "Digestion continues in the small intestine.",
        ],
    },
}


def tr(text):
    return str(text)


def _organ_label(key):
    return ORGANS[key]["name"]

def render_3d_model(model_url, organ_name, model_note=None):
    """Show a larger, interactive 3D model with rotation, zoom and lighting."""
    safe_url = html.escape(model_url, quote=True)
    safe_name = html.escape(organ_name, quote=True)
    viewer_html = f"""
    <!doctype html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <script type="module"
            src="https://cdn.jsdelivr.net/npm/@google/model-viewer@4.0.0/dist/model-viewer.min.js">
      </script>
      <style>
        html, body {{ margin:0; padding:0; background:transparent; font-family:Arial,sans-serif; }}
        .viewer-card {{
          width:100%; overflow:hidden; border-radius:22px;
          background:radial-gradient(ellipse at 50% 35%, #263b55 0%, #101827 72%);
          border:1px solid #3b4d66; box-shadow:0 14px 35px rgba(0,0,0,.22);
        }}
        model-viewer {{
          display:block; width:100%; height:490px; background:transparent;
          --poster-color: transparent; --progress-bar-color:#60a5fa;
          --progress-bar-height:3px;
        }}
        .viewer-caption {{
          color:#dbeafe; font-size:13px; text-align:center;
          padding:10px 12px 15px; line-height:1.5;
        }}
        .viewer-caption span {{ display:inline-block; margin:0 7px; }}
      </style>
    </head>
    <body>
      <div class="viewer-card">
        <model-viewer
          src="{safe_url}"
          alt="Interactive 3D educational model of {safe_name}"
          camera-controls
          touch-action="pan-y"
          auto-rotate
          rotation-per-second="12deg"
          interaction-prompt="auto"
          shadow-intensity="1.1"
          shadow-softness="0.8"
          exposure="1.15"
          environment-image="neutral"
          tone-mapping="aces"
          camera-orbit="0deg 75deg auto"
          min-camera-orbit="auto 15deg auto"
          max-camera-orbit="auto 165deg auto"
          field-of-view="30deg"
          loading="eager"
          reveal="auto"
          style="width:100%;height:490px;">
          <div slot="progress-bar" style="height:3px;background:#60a5fa;"></div>
        </model-viewer>
                <div id="model-status" style="color:#dbeafe;text-align:center;padding:8px;">
          Loading 3D model...
        </div>

        <script>
          const viewer = document.querySelector("model-viewer");
          const status = document.getElementById("model-status");

viewer.addEventListener("load", () => {{
    status.textContent = "3D model loaded successfully";
}});

viewer.addEventListener("error", () => {{
    status.textContent = "Could not load the 3D model. Check WebGL and the model URL.";
}});
        </script>
        <div class="viewer-caption">
          <span>↔ {html.escape(tr("Drag to rotate"))}</span>
          <span>⌕ {html.escape(tr("Scroll or pinch to zoom"))}</span>
          <span>⟳ {html.escape(tr("Use two fingers to move"))}</span>
        </div>
      </div>
    </body>
    </html>
    """
    st.components.v1.html(viewer_html, height=550, scrolling=False)
    if model_note:
        st.info(tr(model_note))

def ask_gemini(organ, question):
    """Ask Gemini and request the answer in the selected app language."""

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return "Gemini API key is not configured."

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are the educational AI assistant in Smart Health Assistant.
Respond in clear English. Keep organ names and medical terminology accurate,
and explain unfamiliar terms simply.

Organ: {organ['name']}
Body system: {organ['system']}
Basic function: {organ['function']}
User question: {question}

Explain the topic clearly for a student. Use accurate, age-appropriate
medical education. Do not diagnose the user or prescribe treatment.
If the question describes urgent symptoms, advise seeking help from a
trusted adult and a qualified medical professional. Make clear that the
response is educational, not a diagnosis.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        if response.text:
            return response.text

        return tr("Gemini returned an empty answer. Please try again.")

    except Exception as e:
        st.error(f"Gemini error: {type(e).__name__}: {e}")
        return tr(
            "The AI request could not be completed. Check your Gemini API key, internet connection, and API settings."
        )

def render_body_explorer():
    st.title(tr("AI Body Explorer"))
    st.write(tr(
        "Explore human organs in 3D, rotate the models with your mouse, and learn how different body systems work."
    ))

    organ_keys = list(ORGANS.keys())
    selected = st.selectbox(
        tr("Choose an organ to explore"),
        organ_keys,
        format_func=_organ_label,
        key="body_explorer_organ",
    )
    organ = ORGANS[selected]

    left, right = st.columns([1.15, 1])

    with left:
        st.subheader(f"{_organ_label(selected)} — {tr('Interactive 3D model')}")
        render_3d_model(
            organ["model"],
            organ["name"],
            organ.get("model_note"),
        )

    with right:
        st.subheader(_organ_label(selected))
        st.caption(f"{tr('Body system')}: {tr(organ['system'])}")
        st.write(tr(organ["function"]))
        st.markdown(f"### {tr('Did you know?')}")
        for fact in organ["facts"]:
            st.markdown(f"- {tr(fact)}")

    st.divider()
    st.subheader(tr("Ask AI about this organ"))

    with st.form("body_explorer_question_form"):
        question = st.text_input(
            tr("What would you like to learn?"),
            placeholder=f"{tr('How does the')} {_organ_label(selected).lower()} {tr('work?')}",
        )
        submitted = st.form_submit_button(
            tr("Ask Gemini"),
            use_container_width=True,
        )

    if submitted:
        if not question.strip():
            st.warning(tr("Write a question first."))
        else:
            with st.spinner(tr("AI is preparing your explanation...")):
                answer = ask_gemini(organ, question.strip())
            st.markdown(f"### {tr('AI Explanation')}")
            st.write(answer)

    st.caption(tr(
        "Educational use only. 3D models are illustrative and should not be used to diagnose medical conditions."
    ))
