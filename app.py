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
import altair as alt



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
        bg = "#0F172A"
        sidebar = "#111827"
        surface = "#1E293B"
        text = "#F8FAFC"
        border = "#334155"
        muted = "#CBD5E1"
        input_bg = "#1E293B"
    else:
        bg = "#F4F7FC"
        sidebar = "#FFFFFF"
        surface = "#FFFFFF"
        text = "#111827"
        border = "#E5E7EB"
        muted = "#64748B"
        input_bg = "#FFFFFF"

    st.markdown(f"""
    <style>
    /* Main application */
    .stApp {{
        background-color: {bg} !important;
        color: {text} !important;
    }}

    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {{
        background-color: {bg} !important;
        color: {text} !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {sidebar} !important;
        border-right: 1px solid {border};
    }}

    section[data-testid="stSidebar"] * {{
        color: {text};
    }}

    /* All text */
    .stApp h1, .stApp h2, .stApp h3,
    .stApp h4, .stApp h5, .stApp h6,
    .stApp p, .stApp label,
    .stApp li, .stApp span {{
        color: {text};
    }}

    .stApp small,
    [data-testid="stCaptionContainer"] {{
        color: {muted} !important;
    }}

    /* Cards */
    .card {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 22px;
        padding: 22px;
        margin-bottom: 20px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.06);
        transition: 0.3s;
    }}

    .card:hover {{
        transform: translateY(-3px);
    }}

    /* Metrics */
    [data-testid="stMetric"] {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 18px;
        padding: 18px;
    }}

    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] {{
        color: {text} !important;
    }}

    /* Input fields */
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input,
    .stDateInput input,
    .stTimeInput input {{
        background-color: {input_bg} !important;
        color: {text} !important;
        border: 1px solid {border} !important;
        border-radius: 12px !important;
    }}

    /* Select boxes and dropdowns */
    [data-baseweb="select"] > div,
    [data-baseweb="popover"],
    [data-baseweb="menu"] {{
        background-color: {surface} !important;
        color: {text} !important;
    }}

    /* Buttons */
    .stButton > button,
    .stFormSubmitButton > button {{
        background: linear-gradient(90deg, #042f69);
        color: white !important;
        border: none;
        border-radius: 14px;
        padding: 12px 18px;
        font-weight: 600;
    }}

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {{
        background: #1C7BFF;
        color: white !important;
    }}

    /* Forms and containers */
    [data-testid="stForm"],
    [data-testid="stExpander"] {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 16px;
    }}

    /* Dividers */
    hr {{
        border-color: {border} !important;
    }}

    /* Progress bars */
    .stProgress > div > div {{
        background-color: #2E8BFF;
    }}

    /* Radio buttons and checkboxes */
    [data-testid="stRadio"],
    [data-testid="stCheckbox"] {{
        color: {text} !important;
    }}

    /* Dataframes */
    [data-testid="stDataFrame"] {{
        background-color: {surface};
    }}
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
elif page == "scan":
    st.header("Medicine Scanner")

    if st.session_state.user_id is None:
        st.info("Please login first")
    else:
        option = st.radio(
            "Choose scanning method",
            ["Camera", "Upload Image"],
            horizontal=True
        )

        if option == "Camera":
            image_file = st.camera_input("Take a picture")
        else:
            image_file = st.file_uploader(
                "Upload medicine image",
                type=["png", "jpg", "jpeg"]
            )

        if image_file is not None:
            image = Image.open(image_file).convert("RGB")
            st.image(image, use_container_width=True)

            if st.button("Analyze Image"):
                with st.spinner("Gemini is analyzing..."):
                    result = extract_text(image)

                st.markdown(result)


# =================================================
# HEALTH TRACKER
# =================================================
elif page == "health":
    st.header("Health Tracker")

    if st.session_state.user_id is None:
        st.info("Please login to view your health tracker.")

    else:
        _, data_file, _, _ = get_user_files()

        if not os.path.exists(data_file):
            pd.DataFrame(
                columns=[
                    "date",
                    "steps",
                    "sleep_hours",
                    "water_glasses",
                    "mood"
                ]
            ).to_csv(data_file, index=False)

        df = pd.read_csv(data_file)

        # DAILY HEALTH INPUT
        st.subheader("Daily Health Information")

        with st.form("health_form"):
            steps = st.number_input("Steps", min_value=0, step=1)
            sleep = st.number_input(
                "Sleep hours",
                min_value=0.0,
                max_value=24.0,
                value=7.0,
                step=0.5
            )
            water = st.number_input(
                "Water glasses",
                min_value=0,
                max_value=20,
                value=5
            )
            mood = st.slider("Mood (1–10)", 1, 10, 7)

            submit = st.form_submit_button("Save")

        if submit:
            new_entry = {
                "date": datetime.date.today().isoformat(),
                "steps": steps,
                "sleep_hours": sleep,
                "water_glasses": water,
                "mood": mood
            }

            df = pd.concat(
                [df, pd.DataFrame([new_entry])],
                ignore_index=True
            )
            df.to_csv(data_file, index=False)

            st.success("Your health information was saved successfully!")
            st.rerun()

        st.divider()

        # WEEKLY TRENDS
        st.subheader("Weekly Trends")

        if not df.empty:
            chart_df = df.copy()

            chart_df["date"] = pd.to_datetime(
                chart_df["date"],
                errors="coerce"
            )

            columns = [
                "steps",
                "sleep_hours",
                "water_glasses",
                "mood"
            ]

            for column in columns:
                chart_df[column] = pd.to_numeric(
                    chart_df[column],
                    errors="coerce"
                )

            chart_df = chart_df.dropna(subset=["date"])
            chart_df = chart_df.sort_values("date").tail(7)

            chart = alt.Chart(
                chart_df
            ).transform_fold(
                columns,
                as_=["Metric", "Value"]
            ).mark_line(
                point=True,
                strokeWidth=3
            ).encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("Value:Q", title="Value"),
                color=alt.Color("Metric:N", title="Health Metrics"),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("Metric:N", title="Metric"),
                    alt.Tooltip("Value:Q", title="Value")
                ]
            ).properties(
                height=350,
                background="transparent"
            ).configure_view(
                fill="transparent",
                stroke=None
            ).configure(
                background="transparent"
            )

            st.altair_chart(
                chart,
                use_container_width=True,
                theme=None
            )

        else:
            st.info("No data to show trends yet.")

        st.divider()

        # STREAKS & BADGES
        st.subheader("Streaks & Badges")

        streak = 0

        if not df.empty:
            for value in reversed(df["steps"].tolist()):
                if pd.notna(value) and float(value) >= 5000:
                    streak += 1
                else:
                    break

        st.metric("Current Activity Streak", f"{streak} days")

        badges = {
            1: "🥉 1 Day Active",
            3: "🥈 3 Days Active",
            5: "🥇 5 Days Active",
            7: "🏆 7 Days Champion"
        }

        earned = False

        for days, badge_text in badges.items():
            if streak >= days:
                earned = True
                st.markdown(
                    f"""
                    <div class="card">
                        <h3>{html.escape(badge_text)}</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        if not earned:
            st.info("No badges yet. Keep building healthy habits!")

        st.divider()

        # DAILY TIPS
        st.subheader("Daily Tips")

        if not df.empty:
            latest = df.iloc[-1]

            latest_steps = int(latest["steps"])
            latest_water = int(latest["water_glasses"])
            latest_sleep = float(latest["sleep_hours"])
            latest_mood = int(latest["mood"])

            tips = []

            if latest_steps < 5000:
                tips.append("Try a short walk today.")

            if latest_water < 5:
                tips.append("Remember to drink water throughout the day.")

            if latest_sleep < 6:
                tips.append("Try to maintain a regular sleep schedule.")

            if latest_mood < 5:
                tips.append("Take a relaxing break and do something you enjoy.")

            if (
                latest_steps >= 5000
                and latest_water >= 5
                and latest_sleep >= 6
                and latest_mood >= 5
            ):
                tips.append("Great job maintaining healthy habits!")

            for tip in tips:
                st.markdown(
                    f"""
                    <div class="card">
                        {html.escape(tip)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # MOOD PREDICTION
            if len(df) >= 3:
                prediction_df = df[
                    ["steps", "sleep_hours", "water_glasses", "mood"]
                ].apply(
                    pd.to_numeric,
                    errors="coerce"
                ).dropna()

                if len(prediction_df) >= 3:
                    model = LinearRegression()

                    X = prediction_df[
                        ["steps", "sleep_hours", "water_glasses"]
                    ]
                    y = prediction_df["mood"]

                    model.fit(X, y)

                    last_entry = prediction_df.iloc[-1]

                    prediction = model.predict(
                        pd.DataFrame([{
                            "steps": last_entry["steps"],
                            "sleep_hours": last_entry["sleep_hours"],
                            "water_glasses": last_entry["water_glasses"]
                        }])
                    )[0]

                    prediction = max(1, min(10, prediction))

                    st.markdown(
                        f"""
                        <div class="card">
                            <h3>Predicted Mood Tomorrow</h3>
                            <h2>{prediction:.1f}/10</h2>
                            <p>
                                This is an experimental estimate based on
                                previous health entries, not a medical prediction.
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        else:
            st.info("Add your first health entry to see your daily tips.")


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
                unsafe_allow_html=True



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
