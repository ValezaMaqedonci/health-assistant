# utils/chatbot.py

def symptom_response(symptoms: str) -> str:
    """
    Returns AI-like friendly responses based on user-provided symptoms.
    Input: string of symptoms typed by the user.
    """

    symptoms_lower = symptoms.lower()

    # ----------------------------------
    # EMERGENCY CHECK
    # ----------------------------------
    emergency_keywords = ["chest pain", "difficulty breathing", "unconscious", "severe bleeding"]
    if any(word in symptoms_lower for word in emergency_keywords):
        return (
            "⚠️ **URGENT**\n\n"
            "Your symptoms may indicate a medical emergency.\n"
            "Please seek immediate medical attention or call emergency services."
        )

    # ----------------------------------
    # COMMON CONDITIONS
    # ----------------------------------
    conditions = {
        "headache": "Headaches are often linked to stress, dehydration, or lack of sleep.",
        "fever": "A fever usually indicates an infection or inflammation.",
        "cough": "Coughing may be caused by a cold, flu, allergies, or irritation.",
        "stomach pain": "Stomach discomfort can be related to digestion, stress, or infection.",
        "fatigue": "Fatigue is commonly caused by poor sleep, stress, or nutritional issues.",
        "dizziness": "Dizziness can be caused by dehydration, low blood sugar, or fatigue.",
        "back pain": "Back pain is often related to posture, muscle strain, or injury.",
        "nausea": "Nausea can occur due to digestive issues, infections, or mild food poisoning.",
        "sore throat": "A sore throat is usually caused by a cold, flu, or irritation.",
        "rash": "Skin rashes can be caused by allergies, irritation, or infections.",
        "shortness of breath": "This could indicate respiratory issues, allergies, or anxiety.",
        "chills": "Chills can be related to fever or viral infection.",
        "vomiting": "Vomiting may be caused by stomach infections, food poisoning, or medication side effects.",
        "diarrhea": "Diarrhea can result from digestive infections, food intolerance, or stress.",
        "muscle pain": "Muscle aches may be due to overexertion, tension, or viral infection.",
        "joint pain": "Joint discomfort can be caused by injury, inflammation, or arthritis.",
        "runny nose": "A runny nose is often caused by cold, flu, or allergies.",
        "bleeding": "Unexplained bleeding should be evaluated by a healthcare professional.",
        "congestion": "Nasal congestion may indicate allergies or respiratory infection.",
    }

    matched_responses = []
    for key, resp in conditions.items():
        if key in symptoms_lower:
            matched_responses.append(resp)

    if matched_responses:
        tips = "\n".join([f"- {r}" for r in matched_responses])
        return (
            f"🩺 **Your symptoms may mean:**\n\n"
            f"{tips}\n\n"
            "💡 **General tips**:\n- Stay hydrated\n- Rest well\n- Observe your symptoms\n\n"
            "🌱 You're doing the right thing by checking your health early."
            "💙 Take care of yourself, and don't hesitate to seek medical help if needed."
        )
    else:
        return (
            "🩺 **Thanks for sharing**\n\n"
            "Your symptoms are not immediately alarming, but it's important to observe them.\n\n"
            "💡 **Tips**:\n- Rest well\n- Eat balanced meals\n- If symptoms worsen, consult a doctor\n\n"
            "💙 Take care of yourself."
        )
