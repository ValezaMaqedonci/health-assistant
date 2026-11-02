import streamlit as st
import pandas as pd
import os
import datetime
import html
from abc import ABC, abstractmethod
from PIL import Image
from sklearn.linear_model import LinearRegression
from utils.ocr import extract_text
from utils.chatbot import symptom_response
import sqlite3
import hashlib
from geopy.geocoders import Nominatim
import folium
import osmnx as ox
from streamlit_folium import st_folium
from utils.body_explorer import render_body_explorer


# =================================================
# PAGE CONFIG
# =================================================
st.set_page_config(page_title="Smart Health Assistant", layout="wide")

# =================================================
# DATABASE
# =================================================
DB_FILE = "users.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


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
    c.execute(
        "SELECT id, password FROM users WHERE username=?",
        (username,)
    )
    result = c.fetchone()
    conn.close()

    if result:
        user_id, stored_hash = result
        if stored_hash == hash_password(password):
            return True, user_id, username

    return False, None, None


# =================================================
# SESSION STATE
# =================================================
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "theme" not in st.session_state:
    st.session_state.theme = "Black Mode"

if "page" not in st.session_state:
    st.session_state.page = "home"


def go(page):
    st.session_state.page = page


# =================================================
# THEME
# =================================================
def apply_theme(theme):
    if theme == "Black Mode":
        st.markdown("""
        <style>
        .stApp { background:#0F172A; color:white; }
        section[data-testid="stSidebar"] {
            background:#111827; border-right:1px solid #1F2937;
        }
        .card {
            background:linear-gradient(135deg,#1E293B,#334155);
            border-radius:22px; padding:22px; margin-bottom:20px;
            box-shadow:0 10px 30px rgba(0,0,0,.35); transition:.3s;
        }
        .card:hover { transform:translateY(-3px); }
        .stButton>button {
            width:100%; border:none; border-radius:16px; padding:14px;
            font-size:16px; font-weight:600;
            background:linear-gradient(90deg,#2f343d); color:white;
        }
        .stButton>button:hover {
            background:linear-gradient(90deg,#1C7BFF,#4098FF);
        }
        input,textarea { border-radius:14px !important; }
        [data-testid="metric-container"] {
            background:#1E293B; border-radius:18px; padding:18px;
            box-shadow:0 6px 20px rgba(0,0,0,.3);
        }
        h1,h2,h3,h4,h5,h6 { color:white; }
        .stProgress>div>div { background:#2E8BFF; }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        .stApp { background:#F4F7FC; color:#111827; }
        section[data-testid="stSidebar"] {
            background:white; border-right:1px solid #E5E7EB;
        }
        .card {
            background:white; border-radius:22px; padding:22px;
            margin-bottom:20px; box-shadow:0 8px 25px rgba(0,0,0,.08);
            transition:.3s;
        }
        .card:hover { transform:translateY(-3px); }
        .stButton>button {
            width:100%; border:none; border-radius:16px; padding:14px;
            font-size:16px; font-weight:600;
            background:linear-gradient(90deg,#2E8BFF,#4FA3FF); color:white;
        }
        .stButton>button:hover {
            background:linear-gradient(90deg,#1C7BFF,#4098FF);
        }
        input,textarea { border-radius:14px !important; }
        [data-testid="metric-container"] {
            background:white; border-radius:18px; padding:18px;
            box-shadow:0 6px 20px rgba(0,0,0,.08);
        }
        .stProgress>div>div { background:#2E8BFF; }
        h1,h2,h3,h4,h5,h6 { color:#111827; }
        </style>
        """, unsafe_allow_html=True)


apply_theme(st.session_state.theme)

# =================================================
# APP HEADER
# =================================================
st.markdown(
    f"""
    <h2 style='text-align:center;'>🩺 {("Smart Health Assistant")}</h2>
    <p style='text-align:center; opacity:0.7;'>
        {("Your personal AI-powered health companion")}
    </p>
    """,
    unsafe_allow_html=True
)

# =================================================
# HYDRATION TRACKER HELPERS
# =================================================
class WaterValue(ABC):
    def __init__(self, glasses=0, target_glasses=8):
        self.glasses = max(0, int(glasses))
        self.target_glasses = max(1, int(target_glasses))

    @abstractmethod
    def current_value(self):
        pass

    @abstractmethod
    def goal_progress(self):
        pass

    @abstractmethod
    def hydration_status(self):
        pass


class DailyWaterTracker(WaterValue):
    def current_value(self):
        return self.glasses

    def goal_progress(self):
        return round(min(100.0, (self.glasses / self.target_glasses) * 100), 1)

    def hydration_status(self):
        if self.glasses >= self.target_glasses:
            return "Well hydrated"
        if self.glasses >= self.target_glasses * 0.75:
            return "On track"
        if self.glasses >= self.target_glasses * 0.5:
            return "Drink a little more"
        return "Dehydrated"


# =================================================
# USER FILES
# =================================================
def get_user_files():
    uid = st.session_state.user_id
    if uid is None:
        return None, None, None, None

    return (
        f"symptom_history_{uid}.csv",
        f"user_data_{uid}.csv",
        f"vitals_data_{uid}.csv",
        f"medications_{uid}.csv",
    )


# =================================================
# LOGIN / SIGNUP
# =================================================
if st.session_state.user_id is None:
    st.sidebar.subheader(("Login / Signup"))
    action = st.sidebar.radio(
        ("Action"),
        [("Login"), ("Signup")],
        key="login_action"
    )
    username = st.sidebar.text_input(("Username"))
    password = st.sidebar.text_input(("Password"), type="password")

    if st.sidebar.button(("Login") if action == ("Login") else ("Signup"), key="login_signup_button"):
        # The translated radio label is mapped back to the action.
        if action == ("Signup"):
            success, uid, uname = signup(username, password)
        else:
            success, uid, uname = login(username, password)

        if success:
            st.session_state.user_id = uid
            st.rerun()
        else:
            st.sidebar.error(("Invalid credentials"))
else:
    st.sidebar.markdown(f"### {('Logged In')}")
    if st.sidebar.button(("Logout")):
        st.session_state.user_id = None
        st.rerun()


# =================================================
# SIDEBAR NAVIGATION
# =================================================
st.sidebar.markdown(f"## {('Navigation')}")

navigation = [
    ("🏠", "Home", "home"),
    ("🤖", "Assistant", "assistant"),
    ("💊", "Scan", "scan"),
    ("🧍", "AI Body Explorer", "body_explorer"),
    ("📊", "Health", "health"),
    ("🏥", "Nearby", "nearby"),
    ("💊", "Reminders", "reminders"),
    ("⚙️", "Settings", "settings"),
]

for icon, label, page_name in navigation:
    if st.sidebar.button(f"{icon} {(label)}", key=f"nav_{page_name}"):
        go(page_name)

page = st.session_state.page

# =================================================
# AI BODY EXPLORER
# =================================================
if page == "body_explorer":
    render_body_explorer()


# =================================================
# HOME
# =================================================
elif page == "home":
    steps_value = 0
    water_value = 0
    sleep_value = 0.0
    mood_value = 0
    steps_change = 0
    water_change = 0
    sleep_change = 0
    df_home = pd.DataFrame()

    if st.session_state.user_id is not None:
        _, data_file, _, _ = get_user_files()
        if data_file and os.path.exists(data_file):
            df_home = pd.read_csv(data_file)
            if not df_home.empty:
                latest = df_home.iloc[-1]
                steps_value = int(latest["steps"])
                water_value = int(latest["water_glasses"])
                sleep_value = float(latest["sleep_hours"])
                mood_value = int(latest["mood"])

                if len(df_home) >= 2:
                    previous = df_home.iloc[-2]
                    steps_change = steps_value - int(previous["steps"])
                    water_change = water_value - int(previous["water_glasses"])
                    sleep_change = round(
                        sleep_value - float(previous["sleep_hours"]), 1
                    )

    st.markdown(
        f"""
        <div class="card">
            <h1>❤️ {("Smart Health Assistant")}</h1>
            <h3>{("Welcome back!")}</h3>
            <p style="opacity:.8;">
                {("Stay healthy today and keep tracking your progress.")}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(("🚶 Steps"), steps_value, steps_change)
    with col2:
        st.metric(("💧 Water"), f"{water_value} {('Glasses')}", water_change)
    with col3:
        st.metric(("😴 Sleep"), f"{sleep_value} {('hrs')}", sleep_change)
    with col4:
        score = min(
            100,
            int(
                (steps_value / 10000) * 40
                + (water_value / 8) * 20
                + (sleep_value / 8) * 20
                + (mood_value / 10) * 20
            )
        )
        st.metric(("❤️ Health Score"), f"{score}/100")

    st.markdown(
        f"""
        <div class='card'>
            <h3>🩺 {("Health Status")}</h3>
            <p>{("Track your habits, scan medicines and receive AI-powered health guidance.")}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


# =================================================
# ASSISTANT
# =================================================
elif page == "assistant":
    st.header(("AI Assistant"))

    if st.session_state.user_id is None:
        st.info(("Please login first"))
    else:
        user_text = st.text_input(("How are you feeling?"))
        if st.button(("Send")) and user_text.strip():
            with st.spinner(("Preparing your response...")):
                result = symptom_response(user_text)
                result = (result)
            st.markdown(
                f"<div class='card'>{html.escape(str(result)).replace(chr(10), '<br>')}</div>",
                unsafe_allow_html=True
            )


# =================================================
# MEDICINE SCANNER
# =================================================
elif page == "assistant":

    st.header(("AI Assistant"))

    if st.session_state.user_id is None:
        st.info(("Please login first"))

    else:
        user_text = st.text_input(
            ("How are you feeling?")
        )

        if st.button(("Send")) and user_text.strip():

            with st.spinner(("Preparing your response...")):

                # Get original AI response
                result = symptom_response(user_text)

                # Translate the complete response using Gemini
                result = (result)

            st.markdown(
                f"<div class='card'>{result}</div>",
                unsafe_allow_html=True
            )


# =================================================
# HEALTH TRACKER
# =================================================
elif page == "health":
    st.header(("📊 Health Tracker"))

    if st.session_state.user_id is None:
        st.info(("Please login to view health tracker"))
    else:
        _, data_file, _, _ = get_user_files()

        if not os.path.exists(data_file):
            pd.DataFrame(
                columns=["date", "steps", "sleep_hours", "water_glasses", "mood"]
            ).to_csv(data_file, index=False)

        df = pd.read_csv(data_file)

        with st.form("health_form"):
            steps = st.number_input(("Steps"), min_value=0, step=1)
            sleep = st.number_input(
                ("Sleep hours"), min_value=0.0, max_value=24.0, value=7.0
            )
            water = st.number_input(
                ("Water glasses"), min_value=0, max_value=20, value=5
            )
            mood = st.slider(("Mood (1–10)"), 1, 10, 7)
            submit = st.form_submit_button(("Save"))

        if submit:
            df.loc[len(df)] = [
                datetime.date.today().isoformat(),
                steps,
                sleep,
                water,
                mood,
            ]
            df.to_csv(data_file, index=False)
            st.success(("Saved successfully"))
            st.rerun()

        st.subheader(("Weekly Trends"))
        if not df.empty:
            chart_df = df.copy()
            chart_df["date"] = pd.to_datetime(chart_df["date"])
            chart_df = chart_df.set_index("date")
            st.line_chart(
                chart_df[["steps", "sleep_hours", "water_glasses", "mood"]]
            )
        else:
            st.info(("No data to show trends yet."))

        st.subheader(("Streaks & Badges"))
        streak = 0
        for value in reversed(df["steps"].tolist()):
            if value >= 5000:
                streak += 1
            else:
                break

        badges = {
            1: ("🥉 1 Day Active"),
            3: ("🥈 3 Days Active"),
            5: ("🥇 5 Days Active"),
            7: ("🏆 7 Days Champion"),
        }

        earned = False
        for days, badge_text in badges.items():
            if streak >= days:
                earned = True
                st.markdown(
                    f"<div class='card'>{html.escape(badge_text)}</div>",
                    unsafe_allow_html=True
                )

        if not earned:
            st.info(("No badges yet. Keep moving! 💪"))

        st.subheader(("Daily Tips"))
        if len(df) > 0:
            latest = df.iloc[-1]
            steps = int(latest["steps"])
            water = int(latest["water_glasses"])
            sleep = float(latest["sleep_hours"])
            mood = int(latest["mood"])

            tips = []
            if steps < 5000:
                tips.append(("🚶", "Try a short walk today"))
            if water < 5:
                tips.append(("💧", "Drink more water"))
            if sleep < 6:
                tips.append(("😴", "Try sleeping earlier tonight"))
            if mood < 5:
                tips.append(("😔", "Try to stay positive"))
            if steps >= 5000 and water >= 5 and sleep >= 6 and mood >= 5:
                tips.append(("🎉", "Great job maintaining healthy habits!"))

            for icon, tip in tips:
                st.markdown(
                    f"<div class='card'>{icon} {(tip)}</div>",
                    unsafe_allow_html=True
                )

            if len(df) >= 3:
                model = LinearRegression()
                model.fit(
                    df[["steps", "sleep_hours", "water_glasses"]],
                    df["mood"]
                )
                last = df.iloc[-1]
                prediction = model.predict([[
                    last["steps"],
                    last["sleep_hours"],
                    last["water_glasses"],
                ]])[0]
                st.markdown(
                    f"<div class='card'><b>{('Predicted mood tomorrow')}:</b> "
                    f"{prediction:.1f}/10</div>",
                    unsafe_allow_html=True
                )
        else:
            st.info(("Add your first health entry to see your daily tips."))


# =================================================
# NEARBY HELP
# =================================================
elif page == "nearby":
    st.header(("🏥 Nearby Help"))
    st.write(
        ("Find hospitals, doctors, pharmacies and emergency services near you.")
    )

    location_input = st.text_input(("City or Area"), value="Prishtina")
    search_type = st.selectbox(
        ("Type"),
        ["Hospital", "Doctor", "Pharmacy", "Emergency"]
    )

    if "nearby_results" not in st.session_state:
        st.session_state.nearby_results = None

    if st.button(("Search")):
        with st.spinner(("Searching nearby locations...")):
            geolocator = Nominatim(user_agent="smart_health_assistant")
            loc = geolocator.geocode(location_input)

            if loc is None:
                st.session_state.nearby_results = {
                    "error": "Location not found"
                }
            else:
                maps_query = search_type.lower()
                maps_url = (
                    "https://www.google.com/maps/search/"
                    f"{maps_query}+near+{location_input.replace(' ', '+')}"
                )

                if search_type == "Hospital" or search_type == "Emergency":
                    tags = {"amenity": "hospital"}
                elif search_type == "Doctor":
                    tags = {"amenity": "clinic"}
                else:
                    tags = {"amenity": "pharmacy"}

                places = []
                try:
                    data = ox.features_from_point(
                        (loc.latitude, loc.longitude),
                        tags=tags,
                        dist=3000
                    )
                    for _, row in data.iterrows():
                        geometry = row.geometry
                        if geometry is not None and geometry.geom_type == "Point":
                            places.append({
                                "name": row.get("name", "Unknown"),
                                "lat": geometry.y,
                                "lon": geometry.x,
                            })
                except Exception as e:
                    print("NEARBY SEARCH ERROR:", e)

                st.session_state.nearby_results = {
                    "lat": loc.latitude,
                    "lon": loc.longitude,
                    "places": places,
                    "maps_url": maps_url,
                    "location": location_input,
                }

    if st.session_state.nearby_results:
        results = st.session_state.nearby_results

        if "error" in results:
            st.error(("Error: " + results["error"]))
        else:
            map_object = folium.Map(
                location=[results["lat"], results["lon"]],
                zoom_start=13
            )
            folium.Marker(
                [results["lat"], results["lon"]],
                popup=("Selected Location"),
                tooltip=results["location"],
                icon=folium.Icon(color="red")
            ).add_to(map_object)

            for place in results["places"]:
                folium.Marker(
                    [place["lat"], place["lon"]],
                    popup=place["name"],
                    tooltip=place["name"]
                ).add_to(map_object)

            st_folium(
                map_object,
                use_container_width=True,
                height=500
            )

            st.link_button(
                ("🌍 Open in Google Maps"),
                results["maps_url"]
            )
            st.subheader(("Nearby Results"))

            if results["places"]:
                for place in results["places"][:15]:
                    st.write(f"🏥 {place['name']}")
            else:
                st.info(("No nearby locations found."))

            st.markdown(
                f"""
                <div class='card'>
                    🚑 <b>{('Emergency Number')}:</b> 112
                </div>
                """,
                unsafe_allow_html=True
            )


# =================================================
# MEDICATION REMINDER CHECK
# =================================================
if st.session_state.user_id is not None:
    _, _, _, meds_file = get_user_files()

    if meds_file and os.path.exists(meds_file):
        meds_df = pd.read_csv(meds_file)
        current_time = datetime.datetime.now().strftime("%H:%M")

        if "taken" in meds_df.columns:
            pending = int((meds_df["taken"] == False).sum())
            st.sidebar.metric(("💊 Pending"), pending)

            for _, row in meds_df.iterrows():
                if (
                    "time" in meds_df.columns
                    and "medicine" in meds_df.columns
                    and row["time"] <= current_time
                    and not bool(row["taken"])
                ):
                    st.toast(
                        ("Time to take") + f" {row['medicine']}",
                        icon="⏰"
                    )
                    st.warning(
                        ("Time to take") + f" {row['medicine']} "
                        f"({row.get('dosage', '')})"
                    )


# =================================================
# REMINDERS
# =================================================
if page == "reminders":
    st.header(("💊 Medication Reminders"))

    if st.session_state.user_id is None:
        st.info(("Please login first."))
    else:
        _, _, _, meds_file = get_user_files()

        if not os.path.exists(meds_file):
            pd.DataFrame(
                columns=["medicine", "dosage", "time", "taken"]
            ).to_csv(meds_file, index=False)

        meds_df = pd.read_csv(meds_file)

        with st.form("add_reminder"):
            medicine = st.text_input(("Medicine"))
            dosage = st.text_input(("Dosage"))
            reminder_time = st.time_input(("Reminder Time"))
            add = st.form_submit_button(("➕ Add Reminder"))

        if add:
            if medicine.strip():
                meds_df.loc[len(meds_df)] = [
                    medicine,
                    dosage,
                    reminder_time.strftime("%H:%M"),
                    False,
                ]
                meds_df.to_csv(meds_file, index=False)
                st.success(("Reminder added!"))
                st.rerun()
            else:
                st.warning(("Please enter a medicine name."))

        st.divider()
        st.subheader(("Today's Reminders"))

        if meds_df.empty:
            st.info(("No reminders yet."))
        else:
            for index, row in meds_df.iterrows():
                col1, col2, col3 = st.columns([6, 1, 1])

                with col1:
                    status = ("Taken") if bool(row["taken"]) else ("Pending")
                    st.markdown(
                        f"""
                        ### 💊 {html.escape(str(row['medicine']))}

                        **{("Dosage")}:** {html.escape(str(row['dosage']))}

                        **{("Time")}:** {html.escape(str(row['time']))}

                        **{("Status")}:** {html.escape(str(status))}
                        """
                    )

                with col2:
                    if not bool(row["taken"]):
                        if st.button("✔", key=f"take_{index}"):
                            meds_df.at[index, "taken"] = True
                            meds_df.to_csv(meds_file, index=False)
                            st.success(("Medicine marked as taken!"))
                            st.rerun()

                with col3:
                    if st.button("🗑", key=f"delete_{index}"):
                        meds_df = meds_df.drop(index).reset_index(drop=True)
                        meds_df.to_csv(meds_file, index=False)
                        st.rerun()

                st.divider()


# =================================================
# SETTINGS
# =================================================
if page == "settings":
    st.header(("⚙️ Settings"))

    theme_options = ["Black Mode", "White Mode"]
    selected_theme = st.radio(
        ("Theme"),
        theme_options,
        index=theme_options.index(st.session_state.theme)
    )

    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme
        st.rerun()

    feedback = st.text_area(
        ("Feedback"),
        placeholder=("Tell us about your experience...")
    )

    if st.button(("Submit Feedback")):
        if feedback.strip():
            with open("feedback.txt", "a", encoding="utf-8") as file:
                file.write(
                    f"{datetime.datetime.now()} | "
                    f"User: {st.session_state.user_id}\n"
                    f"{feedback}\n\n"
                )

            st.success(("Feedback submitted successfully!"))
            st.markdown(
                f"""
                <div class='card'>
                    💬 {("Thank you for reviewing our chatbot!")}
                    {("We appreciate your suggestions.")}
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.warning(("Please enter feedback first."))

    st.markdown("---")
    st.caption(
        ("🩺 Smart Health Assistant • AI-powered health companion • Educational use only")
    )
