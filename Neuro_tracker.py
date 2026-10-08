import datetime
import io
import hashlib
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import libsql
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Streamlit Page Config
st.set_page_config(
    page_title="Neuro-Tracker | Dr. Ananda's Practice",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🧠"
)

# Helper function to hash passwords
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# Connect to Turso Cloud DB (or local fallback)
def get_connection():
    if "TURSO_URL" in st.secrets:
        return libsql.connect(
            database="neuro_health_tracker.db",
            sync_url=st.secrets["TURSO_URL"],
            auth_token=st.secrets["TURSO_TOKEN"]
        )
    else:
        import sqlite3
        return sqlite3.connect("neuro_health_tracker.db")

def init_db():
    conn = get_connection()
    if hasattr(conn, 'sync'):
        conn.sync()
    c = conn.cursor()
    
    # 1. Users Table (Authentication & Access Control)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            role TEXT, -- 'doctor' or 'patient'
            patient_id TEXT -- Stores Hospital MRN
        )
    ''')

    # 2. Patient Profiles Table (Indexed by MRN)
    c.execute('''
        CREATE TABLE IF NOT EXISTS patient_profiles (
            patient_id TEXT PRIMARY KEY, -- Hospital MRN Number
            patient_name TEXT,
            diagnosis TEXT,
            procedure_type TEXT,
            affected_cranial_nerves TEXT,
            created_date TEXT
        )
    ''')

    # 3. Daily Logs Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS multi_patient_logs (
            patient_id TEXT, -- Hospital MRN Number
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
            PRIMARY KEY (patient_id, date, time_of_day)
        )
    ''')
    
    # Pre-populate default accounts on initial launch using MRN format
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Create Doctor account (Default Pass: doc123)
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("drananda", hash_password("doc123"), "doctor", "ALL"))
        
        # Create Linda's Profile & Account (Default Pass: linda123)
        c.execute("INSERT INTO patient_profiles VALUES ('MRN-0010826', 'Linda Marcia Thomas', 'Trigeminal Neuralgia & SNHL', 'Right Retrosigmoid Craniotomy / MVD', 'CN V, CN VIII', '2026-10-08')")
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("linda", hash_password("linda123"), "patient", "MRN-0010826"))

    conn.commit()
    conn.close()

init_db()

# --- AUTHENTICATION SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['user_role'] = None
    st.session_state['assigned_patient_id'] = None
    st.session_state['username'] = None

if 'default_log_time' not in st.session_state:
    st.session_state['default_log_time'] = datetime.datetime.now().time()

# --- LOGIN FORM ---
if not st.session_state['authenticated']:
    st.title("🧠 Neuro-Tracker Portal Login")
    
    with st.form("login_form"):
        username = st.text_input("Username").strip().lower()
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", type="primary")
        
        if submit:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT password_hash, role, patient_id FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            conn.close()
            
            if user and user[0] == hash_password(password):
                st.session_state['authenticated'] = True
                st.session_state['username'] = username
                st.session_state['user_role'] = user[1]
                st.session_state['assigned_patient_id'] = user[2]
                st.success(f"Welcome, {username.title()}!")
                st.rerun()
            else:
                st.error("Invalid Username or Password.")
    st.stop()

# --- LOGGED-IN APPLICATION INTERFACE ---

st.sidebar.write(f"Logged in: **{st.session_state['username']}** ({st.session_state['user_role'].title()})")
if st.sidebar.button("Logout"):
    st.session_state['authenticated'] = False
    st.rerun()

st.title("🧠 Neuro-Tracker Platform")

# Fetch Profiles based on Role
conn = get_connection()

if st.session_state['user_role'] == 'doctor':
    profiles_df = pd.read_sql_query("SELECT * FROM patient_profiles", conn)
    selected_patient_id = st.sidebar.selectbox(
        "👤 Select Patient (Hospital MRN)",
        options=profiles_df['patient_id'].tolist(),
        format_func=lambda mrn: f"[{mrn}] - {profiles_df[profiles_df['patient_id'] == mrn]['patient_name'].values[0]}"
    )
else:
    profiles_df = pd.read_sql_query(
        "SELECT * FROM patient_profiles WHERE patient_id = ?", 
        conn, params=(st.session_state['assigned_patient_id'],)
    )
    selected_patient_id = st.session_state['assigned_patient_id']

conn.close()

active_profile = profiles_df[profiles_df['patient_id'] == selected_patient_id].iloc[0]
st.sidebar.info(f"**MRN:** {active_profile['patient_id']}\n\n**Patient:** {active_profile['patient_name']}\n\n**Procedure:** {active_profile['procedure_type']}\n\n**Nerves:** {active_profile['affected_cranial_nerves']}")

# --- DOCTOR-ONLY: REGISTER PATIENT VIA HOSPITAL MRN & RESET PASSWORDS ---
if st.session_state['user_role'] == 'doctor':
    with st.sidebar.expander("➕ Register New Patient (MRN)"):
        with st.form("register_patient_form"):
            new_mrn = st.text_input("Hospital MRN (e.g., MRN-884012)").strip().upper()
            new_name = st.text_input("Patient Full Name")
            new_username = st.text_input("Patient Portal Username").strip().lower()
            new_pass = st.text_input("Initial Password", type="password")
            new_diag = st.text_input("Diagnosis")
            new_proc = st.text_input("Procedure")
            new_nerves = st.multiselect("Affected Nerves", ["CN V (Trigeminal)", "CN VII (Facial)", "CN VIII (Vestibulocochlear)", "CN IX/X"])
            reg_submit = st.form_submit_button("Register Patient")
            
            if reg_submit:
                if new_mrn and new_name and new_username and new_pass:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO patient_profiles VALUES (?, ?, ?, ?, ?, ?)", (
                            new_mrn, new_name, new_diag, new_proc, ", ".join(new_nerves), str(datetime.date.today())
                        ))
                        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (
                            new_username, hash_password(new_pass), "patient", new_mrn
                        ))
                        conn.commit()
                        if hasattr(conn, 'sync'):
                            conn.sync()
                        st.success(f"Registered {new_name} (MRN: {new_mrn}) successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error registering user (MRN or Username already exists): {e}")
                    finally:
                        conn.close()
                else:
                    st.warning("Please fill in all required fields.")

    with st.sidebar.expander("🛠️ Reset Patient Password"):
        with st.form("reset_patient_pass_form"):
            conn = get_connection()
            all_users = pd.read_sql_query("SELECT username, patient_id FROM users WHERE role = 'patient'", conn)
            conn.close()
            
            user_options = all_users['username'].tolist() if not all_users.empty else []
            target_user = st.selectbox(
                "Select Patient Account", 
                user_options,
                format_func=lambda u: f"{u} (MRN: {all_users[all_users['username'] == u]['patient_id'].values[0]})" if not all_users.empty else u
            )
            admin_new_pass = st.text_input("Set New Password", type="password")
            reset_submit = st.form_submit_button("Reset Password")
            
            if reset_submit and target_user and admin_new_pass:
                conn = get_connection()
                c = conn.cursor()
                c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(admin_new_pass), target_user))
                conn.commit()
                if hasattr(conn, 'sync'):
                    conn.sync()
                conn.close()
                st.success(f"Password reset successfully for {target_user}!")

# --- SELF-SERVICE: CHANGE MY PASSWORD ---
with st.sidebar.expander("🔑 Change My Password"):
    with st.form("change_my_password_form"):
        curr_pass = st.text_input("Current Password", type="password")
        new_pass_1 = st.text_input("New Password", type="password")
        new_pass_2 = st.text_input("Confirm New Password", type="password")
        change_submit = st.form_submit_button("Update Password")
        
        if change_submit:
            if new_pass_1 != new_pass_2:
                st.error("New passwords do not match.")
            elif len(new_pass_1) < 4:
                st.error("New password must be at least 4 characters long.")
            else:
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE username = ?", (st.session_state['username'],))
                current_hash = c.fetchone()[0]
                
                if current_hash == hash_password(curr_pass):
                    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(new_pass_1), st.session_state['username']))
                    conn.commit()
                    if hasattr(conn, 'sync'):
                        conn.sync()
                    conn.close()
                    st.success("Your password has been updated!")
                else:
                    conn.close()
                    st.error("Current password is incorrect.")

# --- DAILY LOG ENTRY FORM ---
st.sidebar.header(f"📝 Log Entry for {active_profile['patient_name']}")

log_date = st.sidebar.date_input("Log Date", datetime.date.today())
time_of_day = st.sidebar.selectbox("Session Slot", ["Morning (AM)", "Afternoon (PM)", "Evening / Night (PM)"])

exact_time = st.sidebar.time_input(
    "Time Taken", 
    value=st.session_state['default_log_time'], 
    key="log_exact_time"
)

st.sidebar.subheader("🩺 Vitals")
systolic = st.sidebar.number_input("Systolic BP (mmHg)", 80, 200, 120)
diastolic = st.sidebar.number_input("Diastolic BP (mmHg)", 50, 130, 80)
pulse = st.sidebar.number_input("Pulse (bpm)", 40, 180, 72)
temperature = st.sidebar.number_input("Temp (°C)", 35.0, 41.0, 36.8, step=0.1)

# Dynamic Symptoms
trigeminal_pain, facial_numbness, jaw_stiffness, eye_dryness = 0, 0, 0, 0
facial_weakness = 0
snhl_hearing_clarity, ear_fullness, dizziness_vertigo = 0, 0, 0
auditory_noises = []

if "CN V" in active_profile['affected_cranial_nerves']:
    st.sidebar.markdown("**CN V Indicators:**")
    trigeminal_pain = st.sidebar.slider("Trigeminal Pain / Zaps (0-10)", 0, 10, 0)
    facial_numbness = st.sidebar.slider("Facial Numbness (0-10)", 0, 10, 0)
    jaw_stiffness = st.sidebar.slider("Jaw Stiffness (0-10)", 0, 10, 0)
    eye_dryness = 1 if st.sidebar.checkbox("Surgical-Side Eye Dryness") else 0

if "CN VII" in active_profile['affected_cranial_nerves']:
    st.sidebar.markdown("**CN VII Indicators:**")
    facial_weakness = st.sidebar.slider("Facial Weakness (0-10)", 0, 10, 0)

if "CN VIII" in active_profile['affected_cranial_nerves']:
    st.sidebar.markdown("**CN VIII Indicators:**")
    snhl_hearing_clarity = st.sidebar.slider("Hearing Muffledness (0-10)", 0, 10, 0)
    ear_fullness = st.sidebar.slider("Ear Pressure (0-10)", 0, 10, 0)
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

if st.sidebar.button("Save Daily Log", type="primary"):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO multi_patient_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(patient_id, date, time_of_day) DO UPDATE SET
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
        selected_patient_id, str(log_date), time_of_day, str(exact_time), systolic, diastolic, pulse, temperature,
        incision_pain, hardware_sens, trigeminal_pain, facial_numbness, facial_weakness, jaw_stiffness,
        snhl_hearing_clarity, ear_fullness, dizziness_vertigo, heat_weakness, hand_clumsy,
        ", ".join(auditory_noises), positional_palpitations, eye_dryness, csf_fluid_drip, notes
    ))
    conn.commit()
    if hasattr(conn, 'sync'):
        conn.sync()
    conn.close()
    st.sidebar.success(f"Saved {time_of_day} entry for MRN {selected_patient_id}!")

# --- MAIN DASHBOARD ---
conn = get_connection()
df = pd.read_sql_query(
    "SELECT * FROM multi_patient_logs WHERE patient_id = ? ORDER BY date ASC, entry_time ASC",
    conn, params=(selected_patient_id,)
)
conn.close()

st.subheader(f"Recovery Dashboard: {active_profile['patient_name']} (MRN: {selected_patient_id})")

if df.empty:
    st.info("No logs recorded yet for this profile.")
else:
    df['date_time_label'] = df['date'] + " (" + df['time_of_day'] + ")"
    tab1, tab2, tab3 = st.tabs(["📊 Analytics", "📋 Raw Data", "📄 PDF Clinical Report"])

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        latest = df.iloc[-1]
        col1.metric("BP", f"{latest['systolic']}/{latest['diastolic']} mmHg")
        col2.metric("Pulse", f"{latest['pulse']} bpm")
        col3.metric("CN V Zap Pain", f"{latest['trigeminal_pain']}/10")
        col4.metric("Hearing Muffledness", f"{latest['snhl_hearing_clarity']}/10")

        st.plotly_chart(px.line(df, x="date_time_label", y=["systolic", "diastolic", "pulse"], title="Vitals Trend", markers=True), use_container_width=True)
        st.plotly_chart(px.line(df, x="date_time_label", y=["trigeminal_pain", "facial_numbness", "snhl_hearing_clarity", "ear_fullness", "dizziness_vertigo"], title="Cranial Nerve Trends", markers=True), use_container_width=True)

    with tab2:
        st.dataframe(df, use_container_width=True)

    with tab3:
        def generate_pdf(dataframe, profile):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
            elements = []
            styles = getSampleStyleSheet()

            elements.append(Paragraph(f"<b>Post-Op Clinical Summary: {profile['patient_name']} (MRN: {profile['patient_id']})</b>", styles['Title']))
            elements.append(Paragraph(f"<b>Attending Neurosurgeon:</b> Dr. Ananda | <b>Procedure:</b> {profile['procedure_type']}", styles['Normal']))
            elements.append(Paragraph(f"<b>Affected Nerves:</b> {profile['affected_cranial_nerves']} | <b>Report Date:</b> {datetime.date.today()}", styles['Normal']))
            elements.append(Spacer(1, 10))

            headers = ["Date", "Session", "BP", "Pulse", "CN V", "Numbness", "CN VIII", "Ear Fullness", "Dizziness", "Auditory/Notes"]
            table_data = [headers]

            for _, row in dataframe.iterrows():
                table_data.append([
                    str(row['date']), str(row['time_of_day']), f"{row['systolic']}/{row['diastolic']}",
                    str(row['pulse']), f"{row['trigeminal_pain']}/10", f"{row['facial_numbness']}/10",
                    f"{row['snhl_hearing_clarity']}/10", f"{row['ear_fullness']}/10", f"{row['dizziness_vertigo']}/10",
                    Paragraph(str(row['auditory_noises']) if row['auditory_noises'] else "None", styles['Normal'])
                ])

            t = Table(table_data, colWidths=[55, 60, 45, 35, 45, 50, 55, 45, 40, 110])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 6.5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
            ]))
            elements.append(t)
            doc.build(elements)
            buffer.seek(0)
            return buffer

        if st.button("Build Patient PDF Report"):
            pdf_data = generate_pdf(df, active_profile)
            st.download_button(
                label=f"📥 Download PDF for {active_profile['patient_name']}",
                data=pdf_data,
                file_name=f"Neuro_Report_MRN_{active_profile['patient_id']}_{datetime.date.today()}.pdf",
                mime="application/pdf"
            )
