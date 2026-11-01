import datetime
import io
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Streamlit Page Config
st.set_page_config(
    page_title="My Neuro-Recovery Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🧠"
)

# Connect to Local SQLite Database
def get_connection():
    return sqlite3.connect("my_personal_recovery.db")

def init_db(reset=False):
    conn = get_connection()
    c = conn.cursor()
    
    if reset:
        c.execute("DROP TABLE IF EXISTS my_daily_logs")

    # Single-User Daily Logs Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS my_daily_logs (
            date TEXT,
            time_of_day TEXT,
            entry_time TEXT,
            systolic INTEGER,
            diastolic INTEGER,
            pulse INTEGER,
            temperature REAL,
            incision_pain INTEGER,
            hardware_sensitivity INTEGER,
            trigeminal_pain INTEGER,
            facial_numbness INTEGER,
            facial_weakness INTEGER,
            jaw_stiffness INTEGER,
            snhl_hearing_clarity INTEGER,
            ear_fullness INTEGER,
            dizziness_vertigo INTEGER,
            heat_weakness_flare INTEGER,
            hand_clumsiness INTEGER,
            auditory_noises TEXT,
            positional_palpitations INTEGER,
            eye_dryness INTEGER,
            csf_fluid_drip INTEGER,
            notes TEXT,
            PRIMARY KEY (date, time_of_day)
        )
    ''')
    conn.commit()
    conn.close()

init_db(reset=False)

# Lock time input via Session State
if "logged_time" not in st.session_state:
    st.session_state["logged_time"] = datetime.datetime.now().time()

# App Header
st.title("🧠 My Recovery Tracker")

# --- SIDEBAR: DATA ENTRY FORM ---
st.sidebar.header("📝 New Entry")

log_date = st.sidebar.date_input("Log Date", datetime.date.today())
time_of_day = st.sidebar.selectbox("Session Slot", ["Morning (AM)", "Afternoon (PM)", "Evening / Night (PM)"])
exact_time = st.sidebar.time_input("Time Taken", key="logged_time")

st.sidebar.subheader("🩺 Vitals")
systolic = st.sidebar.number_input("Systolic BP (mmHg)", 80, 200, 120)
diastolic = st.sidebar.number_input("Diastolic BP (mmHg)", 50, 130, 80)
pulse = st.sidebar.number_input("Pulse (bpm)", 40, 180, 72)
temperature = st.sidebar.number_input("Temp (°C)", 35.0, 41.0, 36.8, step=0.1)

st.sidebar.subheader("⚡ Cranial Nerve Symptoms")
trigeminal_pain = st.sidebar.slider("CN V Trigeminal Zap / Pain (0-10)", 0, 10, 0)
facial_numbness = st.sidebar.slider("Facial Numbness (0-10)", 0, 10, 0)
facial_weakness = st.sidebar.slider("Facial Weakness (0-10)", 0, 10, 0)
jaw_stiffness = st.sidebar.slider("Jaw Stiffness (0-10)", 0, 10, 0)
eye_dryness = 1 if st.sidebar.checkbox("Surgical-Side Eye Dryness") else 0

snhl_hearing_clarity = st.sidebar.slider("CN VIII Hearing Muffledness (0-10)", 0, 10, 0)
ear_fullness = st.sidebar.slider("Ear Pressure / Fullness (0-10)", 0, 10, 0)
dizziness_vertigo = st.sidebar.slider("Dizziness / Vertigo (0-10)", 0, 10, 0)
auditory_noises = st.sidebar.multiselect(
    "Tinnitus Symptoms",
    ["None", "Whooshing Sound (lying flat)", "Straight Humming / Wind Blowing", "Washing Machine Sound", "High-Pitch Ringing", "Hyperacusis"]
)

st.sidebar.subheader("🤕 Post-Op & Surgical Site")
incision_pain = st.sidebar.slider("Incision Pain (0-10)", 0, 10, 0)
hardware_sens = st.sidebar.slider("Hardware Sensitivity (0-10)", 0, 10, 0)
heat_weakness = st.sidebar.slider("Heat Flare-up / Weakness (0-10)", 0, 10, 0)
hand_clumsy = st.sidebar.slider("Hand Clumsiness (0-10)", 0, 10, 0)

positional_palpitations = 1 if st.sidebar.checkbox("Chest Palpitations when Flat") else 0
csf_fluid_drip = 1 if st.sidebar.checkbox("Clear Fluid Drip (Nose/Ear)") else 0
notes = st.sidebar.text_area("Notes / Triggers")

if st.sidebar.button("Save Entry", type="primary"):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO my_daily_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, time_of_day) DO UPDATE SET
            entry_time=excluded.entry_time, systolic=excluded.systolic, diastolic=excluded.diastolic,
            pulse=excluded.pulse, temperature=excluded.temperature, incision_pain=excluded.incision_pain,
            hardware_sensitivity=excluded.hardware_sensitivity, trigeminal_pain=excluded.trigeminal_pain,
            facial_numbness=excluded.facial_numbness, facial_weakness=excluded.facial_weakness,
            jaw_stiffness=excluded.jaw_stiffness, snhl_hearing_clarity=excluded.snhl_hearing_clarity,
            ear_fullness=excluded.ear_fullness, dizziness_vertigo=excluded.dizziness_vertigo,
            heat_weakness_flare=excluded.heat_weakness_flare, hand_clumsiness=excluded.hand_clumsiness,
            auditory_noises=excluded.auditory_noises, positional_palpitations=excluded.positional_palpitations,
            eye_dryness=excluded.eye_dryness, csf_fluid_drip=excluded.csf_fluid_drip, notes=excluded.notes
    ''', (
        str(log_date), time_of_day, str(exact_time), systolic, diastolic, pulse, temperature,
        incision_pain, hardware_sens, trigeminal_pain, facial_numbness, facial_weakness, jaw_stiffness,
        snhl_hearing_clarity, ear_fullness, dizziness_vertigo, heat_weakness, hand_clumsy,
        ", ".join(auditory_noises), positional_palpitations, eye_dryness, csf_fluid_drip, notes
    ))
    conn.commit()
    conn.close()
    st.sidebar.success(f"Log saved for {log_date} ({time_of_day})!")
    st.rerun()

# --- MAIN DASHBOARD VIEW ---
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM my_daily_logs ORDER BY date ASC, entry_time ASC", conn)
conn.close()

if df.empty:
    st.info("No recovery logs recorded yet. Fill in your current vitals and symptoms in the sidebar on the left and click **Save Entry**.")
else:
    df['date_time_label'] = df['date'] + " (" + df['time_of_day'] + ")"
    tab1, tab2, tab3 = st.tabs(["📊 Symptom & Vitals Analytics", "📋 Raw Data Log", "📄 Generate PDF Report"])

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        latest = df.iloc[-1]
        col1.metric("BP", f"{latest['systolic']}/{latest['diastolic']} mmHg")
        col2.metric("Pulse", f"{latest['pulse']} bpm")
        col3.metric("CN V Zap Pain", f"{latest['trigeminal_pain']}/10")
        col4.metric("CN VIII Muffledness", f"{latest['snhl_hearing_clarity']}/10")

        st.plotly_chart(px.line(df, x="date_time_label", y=["systolic", "diastolic", "pulse"], title="Vitals Trends", markers=True), use_container_width=True)
        st.plotly_chart(px.line(df, x="date_time_label", y=["trigeminal_pain", "facial_numbness", "snhl_hearing_clarity", "ear_fullness", "dizziness_vertigo"], title="Cranial Nerve Intensity Trends", markers=True), use_container_width=True)

    with tab2:
        st.dataframe(df, use_container_width=True)

    with tab3:
        def generate_pdf(dataframe):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
            elements = []
            styles = getSampleStyleSheet()

            elements.append(Paragraph("<b>Personal Post-Op Recovery Report (Clean Clinical Summary)</b>", styles['Title']))
            elements.append(Paragraph(f"<b>Report Generated On:</b> {datetime.date.today()} (Unrecorded zero-value symptom columns automatically omitted)", styles['Normal']))
            elements.append(Spacer(1, 10))
