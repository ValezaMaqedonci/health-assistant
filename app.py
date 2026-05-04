import streamlit as st
import pandas as pd
import datetime
import os
from PIL import Image
from sklearn.linear_model import LinearRegression
from utils.ocr import extract_text
from utils.chatbot import symptom_response
from deep_translator import GoogleTranslator
import sqlite3
import hashlib
from functools import lru_cache

# =================================================
# DATABASE SETUP
# =================================================
DB_FILE = "users.db"
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def signup(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        user_id = c.fetchone()[0]
        return True, user_id, username
    except sqlite3.IntegrityError:
        return False, None, None
    finally:
        conn.close()

def login(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        user_id, stored_hash = result
        if stored_hash == hash_password(password):
            return True, user_id, username
    return False, None, None

# =================================================
# PAGE CONFIG
# =================================================
st.set_page_config(page_title="Smart Health Assistant", layout="wide")
st.title("🩺 Smart Health Assistant")

# =================================================
# LANGUAGE SYSTEM (OPTIMIZED)
# =================================================

LANGUAGES = {
    "English": "en", "Spanish": "es", "French": "fr", "German": "de",
    "Italian": "it", "Albanian": "sq", "Arabic": "ar", "Turkish": "tr"
}

selected_language = st.sidebar.selectbox("🌍 Language", list(LANGUAGES.keys()))
lang_code = LANGUAGES[selected_language]

# Use Streamlit cache (much faster across reruns)
@st.cache_data(show_spinner=False)
def cached_translate(text, lang):
    if lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=lang).translate(text)
    except:
        return text

def t(text):
    return cached_translate(text, lang_code)

def translate_response(text):
    return cached_translate(text, lang_code)

# =================================================
# THEME SYSTEM
# =================================================
if "theme" not in st.session_state:
    st.session_state.theme = "Black Mode"

def apply_theme(theme):
    if theme == "Black Mode":
        st.markdown("""<style>
        .stApp { background:#0e1117; color:white; }
        section[data-testid="stSidebar"] { background:#1b1f2a; }
        label, span, p, div { color:white !important; }
        input, textarea, button { background:#1f2433 !important; color:white !important; }
        div[data-baseweb="select"] > div { background:#1f2433 !important; color:white !important; }
        ul[role="listbox"] { background:#1f2433 !important; color:white !important; }
        li[role="option"] { background:#2b2f3a !important; color:white !important; }
        li[role="option"]:hover { background:#3a3f4a !important; }
        .card { background:#1f2433; padding:14px; border-radius:12px; margin-bottom:12px; }
        </style>""", unsafe_allow_html=True)
    else:
        st.markdown("""<style>
        .stApp { background:white; color:black; }
        section[data-testid="stSidebar"] { background:#f4f4f4; }
        label, span, p, div { color:black !important; }
        input, textarea, button { background:#eaeaea !important; color:black !important; }
        div[data-baseweb="select"] > div { background:white !important; color:black !important; }
        ul[role="listbox"] { background:white !important; color:black !important; }
        li[role="option"] { background:white !important; color:black !important; }
        li[role="option"]:hover { background:#eaeaea !important; }
        .card { background:#f6f6f6; padding:14px; border-radius:12px; margin-bottom:12px; }
        </style>""", unsafe_allow_html=True)

apply_theme(st.session_state.theme)

# =================================================
# USER FILES
# =================================================
def get_user_files():
    uid = st.session_state.user_id
    if uid is None:
        return None, None, None
    return f"symptom_history_{uid}.csv", f"user_data_{uid}.csv", f"vitals_data_{uid}.csv"

# =================================================
# LOGIN / SIGNUP
# =================================================
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None

if st.session_state.user_id is None:
    st.sidebar.subheader(t("Login / Signup"))

    # KEEP INTERNAL VALUES IN ENGLISH (do not translate logic values)
    action = st.sidebar.radio(
        t("Action"),
        ["Login", "Signup"],
        format_func=lambda x: t(x)  # translate only for display
    )

    username = st.sidebar.text_input(t("Username"))
    password = st.sidebar.text_input(t("Password"), type="password")

    if st.sidebar.button(t(action)):
        if action == "Signup":
            success, user_id, uname = signup(username, password)
            if success:
                st.session_state.user_id = user_id
                st.session_state.username = uname
                st.rerun()
            else:
                st.sidebar.error(t("Username already exists."))
        else:  # Login
            success, user_id, uname = login(username, password)
            if success:
                st.session_state.user_id = user_id
                st.session_state.username = uname
                st.rerun()
            else:
                st.sidebar.error(t("Invalid credentials"))
else:
    st.sidebar.success(t(f"Logged in as {st.session_state.username}"))
    if st.sidebar.button(t("Logout")):
        st.session_state.user_id = None
        st.session_state.username = None
        st.rerun()
        
# =================================================
# TABS
# =================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    t("🤖 Symptom Chatbot"),
    t("💊 Medicine OCR"),
    t("📊 Health Tracker"),
    t("🏥 Find Help Nearby"),
    t("⚙️ Settings"),
    t("ℹ️ About Chatbot"),
])

# =================================================
# TAB 1 — SYMPTOM CHATBOT
# =================================================
with tab1:
    st.header(t("Symptom Chatbot"))
    if st.session_state.user_id is None:
        st.info(t("Please log in to use the chatbot and save history."))
    else:
        history_file, _, _ = get_user_files()
        symptoms = st.text_input(t("Describe your symptoms"))
        if st.button(t("Get Info")) and symptoms.strip():
            response = symptom_response(symptoms)
            translated_response = translate_response(response)
            st.markdown(f"<div class='card'>{translated_response}</div>", unsafe_allow_html=True)

            df = pd.read_csv(history_file) if os.path.exists(history_file) else pd.DataFrame(columns=["date","symptoms","response"])
            df.loc[len(df)] = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), symptoms, translated_response]
            df.to_csv(history_file, index=False)

        st.subheader(t("Your Symptom History"))
        if os.path.exists(history_file):
            hist_df = pd.read_csv(history_file).tail(5)
            for _, row in hist_df.iterrows():
                st.markdown(
                    f"<div class='card'><b>{row['date']}</b><br>🩺 {row['symptoms']}<br>💬 {row['response']}</div><br>",
                    unsafe_allow_html=True
                )
        else:
            st.info(t("No history yet. Your recent symptom entries will appear here."))

# =================================================
# TAB 2 — MEDICINE OCR
# =================================================
with tab2:
    st.header(t("Medicine Image Identifier"))
    col1, col2 = st.columns(2)
    with col1: upload = st.file_uploader(t("Upload medicine image"), type=["jpg","png","jpeg"])
    with col2: camera = st.camera_input(t("Take a photo"), key="camera_input")

    img = None
    if upload: img = Image.open(upload).convert("RGB")
    elif camera: img = Image.open(camera).convert("RGB")

    if img:
        st.image(img, width=280)
        st.markdown(f"<div class='card'>{t(extract_text(img))}</div>", unsafe_allow_html=True)

# =================================================
# TAB 3 — HEALTH TRACKER (TIPS TRANSLATED)
# =================================================
with tab3:
    st.header(t("Daily Health Tracker"))

    if st.session_state.user_id is None:
        st.info(t("Please log in to save and view your health data."))
    else:
        _, data_file, _ = get_user_files()

        if not os.path.exists(data_file):
            pd.DataFrame(
                columns=["date","steps","sleep_hours","water_glasses","mood"]
            ).to_csv(data_file, index=False)

        df = pd.read_csv(data_file)

        # =========================
        # INPUT FORM
        # =========================
        with st.form("health_form"):
            steps = st.number_input(t("Steps"), 0)
            sleep = st.number_input(t("Sleep hours"), 0.0, 24.0, 7.0)
            water = st.number_input(t("Water glasses"), 0, 20, 5)
            mood = st.slider(t("Mood (1–10)"), 1, 10, 7)
            submit = st.form_submit_button(t("Save"))

        if submit:
            df.loc[len(df)] = [
                datetime.date.today(),
                steps,
                sleep,
                water,
                mood
            ]
            df.to_csv(data_file, index=False)
            st.success(t("Saved successfully"))

        # =========================
        # WEEKLY TRENDS
        # =========================
        st.subheader(t("Weekly Trends"))

        if len(df) > 0:
            chart_df = df.copy()
            chart_df["date"] = pd.to_datetime(chart_df["date"])
            chart_df = chart_df.set_index("date")
            st.line_chart(chart_df[["steps","sleep_hours","water_glasses","mood"]])
        else:
            st.info(t("No data to show trends yet."))

        # =========================
        # STREAKS & BADGES
        # =========================
        st.subheader(t("Streaks & Badges"))

        streak = 0
        for s in reversed(df["steps"].tolist()):
            if s >= 5000:
                streak += 1
            else:
                break

        badges = {
            1: t("🥉 1 Day Active"),
            3: t("🥈 3 Days Active"),
            5: t("🥇 5 Days Active"),
            7: t("🏆 7 Days Champion"),
        }

        earned = False
        for days, badge in badges.items():
            if streak >= days:
                earned = True
                st.markdown(f"<div class='card'>{badge}</div>", unsafe_allow_html=True)

        if not earned:
            st.info(t("No badges yet. Keep moving! 💪"))

        # =========================
        # DAILY TIPS
        # =========================
        st.subheader(t("Daily Tips"))

        if steps < 5000:
            st.markdown(
                f"<div class='card'>🚶 {t('Try a short walk today')}</div>",
                unsafe_allow_html=True
            )

        if water < 5:
            st.markdown(
                f"<div class='card'>💧 {t('Drink more water')}</div>",
                unsafe_allow_html=True
            )

        if sleep < 6:
            st.markdown(
                f"<div class='card'>😴 {t('Try sleeping earlier tonight')}</div>",
                unsafe_allow_html=True
            )

        if mood  < 5:
            st.markdown(
                f"<div class='card'>😔 {t('Try to stay positive')}</div>",
                unsafe_allow_html=True
            )

        if steps >= 5000 and water >= 5 and sleep >= 6 and mood >= 5:
            st.markdown(
                f"<div class='card'>🎉 {t('Great job maintaining healthy habits!')}</div>",
                unsafe_allow_html=True
            )

        # =========================
        # MOOD PREDICTION
        # =========================
        if len(df) >= 3:
            model = LinearRegression()
            model.fit(
                df[["steps","sleep_hours","water_glasses"]],
                df["mood"]
            )
            last = df.iloc[-1]
            prediction = model.predict([[
                last["steps"],
                last["sleep_hours"],
                last["water_glasses"]
            ]])[0]

            st.markdown(
                f"<div class='card'><b>{t('Predicted mood tomorrow')}:</b> {prediction:.1f}/10</div>",
                unsafe_allow_html=True
            )

# =================================================
# TAB 4 — FIND HELP NEARBY (FINAL COMPLETE)
# =================================================
with tab4:
    import folium
    from streamlit_folium import st_folium
    from geopy.geocoders import Nominatim
    import osmnx as ox

    st.header(t("Find Hospitals & Specialists"))

    st.markdown(
        f"<div class='card'>{t('Find nearby hospitals, doctors, pharmacies, or emergency services.')}</div>",
        unsafe_allow_html=True
    )

    # 🔹 INIT STATE
    if "map_data" not in st.session_state:
        st.session_state.map_data = None

    # 🔹 INPUTS
    location_input = st.text_input(
        t("Enter your city or area"),
        placeholder="e.g. Prishtina"
    )

    search_type = st.selectbox(
        t("What are you looking for?"),
        [t("Hospitals"), t("Doctors"), t("Pharmacy"), t("Emergency")]
    )

    # 🔹 SEARCH BUTTON
    if st.button(t("Search")):

        geolocator = Nominatim(user_agent="health_app")

        try:
            location = geolocator.geocode(location_input if location_input else "Prishtina")
            lat, lon = location.latitude, location.longitude
        except:
            st.error(t("Location not found"))
            st.stop()

        # 🔹 MAP
        m = folium.Map(location=[lat, lon], zoom_start=13)

        # 🔹 SELECT FILTER
        if search_type == t("Hospitals"):
            tags = {"amenity": "hospital"}
            query = "hospitals"
        elif search_type == t("Doctors"):
            tags = {"amenity": "clinic"}
            query = "doctors"
        elif search_type == t("Pharmacy"):
            tags = {"amenity": "pharmacy"}
            query = "pharmacy"
        else:  # Emergency
            tags = {"amenity": "hospital"}
            query = "emergency hospital"

        places_data = []

        try:
            places = ox.features_from_point((lat, lon), tags=tags, dist=3000)

            for _, row in places.iterrows():
                if "geometry" in row and row.geometry.geom_type == "Point":
                    name = row.get("name", "Unnamed")
                    lat_p = row.geometry.y
                    lon_p = row.geometry.x

                    places_data.append((name, lat_p, lon_p))

                    folium.Marker(
                        [lat_p, lon_p],
                        popup=f"🏥 {name}",
                        tooltip=name
                    ).add_to(m)

        except:
            st.warning(t("Could not load places"))

        # 🔹 GOOGLE MAPS LINK
        maps_url = f"https://www.google.com/maps/search/{query}+in+{location_input.replace(' ', '+')}"

        # 🔹 SAVE STATE
        st.session_state.map_data = {
            "map": m,
            "places": places_data,
            "location": location.address,
            "maps_url": maps_url,
            "type": search_type
        }

    # 🔥 DISPLAY RESULTS (PERSISTENT)
    if st.session_state.map_data:

        st.success(f"{t('Location')}: {st.session_state.map_data['location']}")

        # 🗺 MAP
        st_folium(st.session_state.map_data["map"], width=700, height=500)

        # 📍 GOOGLE MAPS LINK
        st.markdown(
            f"""
            <div class='card'>
            📍 <a href="{st.session_state.map_data['maps_url']}" target="_blank">
            {t('Open full results in Google Maps')}
            </a>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 🏥 LIST
        if st.session_state.map_data["places"]:
            st.subheader(t("Nearby places"))
            for name, _, _ in st.session_state.map_data["places"][:10]:
                st.markdown(f"- 🏥 {name}")

    # 🚑 EMERGENCY SECTION (ALWAYS)
    st.subheader(t("Emergency Help"))

    st.markdown(
        f"""
        <div class='card'>
        🚑 <b>{t('Emergency Number')}:</b> 112<br><br>
        📞 <a href="tel:112">{t('Call Now (Mobile only)')}</a><br><br>
        💻 {t('If you are on a computer, please call using your phone')}
        </div>
        """,
        unsafe_allow_html=True
    )
# =================================================
# TAB 5 — SETTINGS
# =================================================
with tab5:
    st.header(t("Settings"))
    theme = st.radio(t("Choose Theme"), ["Black Mode","White Mode"], index=0 if st.session_state.theme=="Black Mode" else 1)
    if theme != st.session_state.theme:
        st.session_state.theme = theme
        apply_theme(theme)
    feedback = st.text_area(t("Leave feedback"))
    if st.button(t("Submit Feedback")) and feedback.strip():
        st.success(t("Thank you for reviewing our chatbot!"))

# =================================================
# TAB 6 — ABOUT
# =================================================
with tab6:
    about_text = """
# 🩺 Smart Health Assistant

**Welcome to the Smart Health Assistant!**

This AI health assistant helps users:

1. **Symptom Chatbot** — Describe your symptoms and get helpful guidance, including a history of your last entries.
2. **Medicine OCR** — Upload or take a photo of medicines to extract readable text.
3. **Daily Health Tracker** — Log your steps, sleep, water, and mood, see trends, badges, tips, and predictions.
4. **Vitals & Measurements** — Log your weight, height, and body info to track calories, BMI, and more.
5. **Settings** — Change themes, leave feedback, and select your language.

⚠️ **Educational use only. Not a replacement for medical advice.**
"""
    st.markdown(translate_response(about_text))