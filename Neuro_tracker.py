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
    
    # Default initial accounts setup
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Create Primary Doctor Account (Default Pass: doc123)
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("drananda", hash_password("doc123"), "doctor", "ALL"))
        
        # Create Generic Starter Patient Profile (Default Pass: patient123)
        c.execute("INSERT INTO patient_profiles VALUES ('MRN-10001', 'Patient Sample A', 'Trigeminal Neuralgia', 'Retrosigmoid Craniotomy / MVD', 'CN V, CN VIII', '2026-10-08')")
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("patient1", hash_password("patient123"), "patient", "MRN-10001"))

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
    if not profiles_df.empty:
        selected_patient_id = st.sidebar.selectbox(
            "👤 Select Patient (Hospital MRN)",
            options=profiles_df['patient_id'].tolist(),
            format_func=lambda mrn: f"[{mrn}] - {profiles_df[profiles_df['patient_id'] == mrn]['patient_name'].values[0]}"
        )
    else:
        selected_patient_id = None
else:
    profiles_df = pd.read_sql_query(
        "SELECT * FROM patient_profiles WHERE patient_id = ?", 
        conn, params=(st.session_state['assigned_patient_id'],)
    )
    selected_patient_id = st.session_state['assigned_patient_id']

conn.close()

if selected_patient_id and not profiles_df.empty:
    active_profile = profiles_df[profiles_df['patient_id'] == selected_patient_id].iloc[0]
    st.sidebar.info(f"**MRN:** {active_profile['patient_id']}\n\n**Patient:** {active_profile['patient_name']}\n\n**Procedure:** {active_profile['procedure_type']}\n\n**Nerves:** {active_profile['affected_cranial_nerves']}")
else:
    active_profile = None

# --- DOCTOR-ONLY CONTROLS ---
if st.session_state['user_role'] == 'doctor':
    # 1. REGISTER NEW PATIENT
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

    # 2. UPDATE PATIENT MRN
    with st.sidebar.expander("✏️ Update Patient MRN"):
        with st.form("update_mrn_form"):
            conn = get_connection()
            all_profiles = pd.read_sql_query("SELECT patient_id, patient_name FROM patient_profiles", conn)
            conn.close()
            
            mrn_options = all_profiles['patient_id'].tolist() if not all_profiles.empty else []
            old_mrn = st.selectbox(
                "Select Patient to Update",
                mrn_options,
                format_func=lambda mrn: f"[{mrn}] - {all_profiles[all_profiles['patient_id'] == mrn]['patient_name'].values[0]}" if not all_profiles.empty else mrn
            )
            
            new_mrn_input = st.text_input("New Hospital MRN (e.g., MRN-0010826)").strip().upper()
            update_mrn_submit = st.form_submit_button("Update MRN")
            
            if update_mrn_submit and old_mrn and new_mrn_input:
                if old_mrn == new_mrn_input:
                    st.warning("New MRN is the same as current MRN.")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("UPDATE patient_profiles SET patient_id = ? WHERE patient_id = ?", (new_mrn_input, old_mrn))
                        c.execute("UPDATE users SET patient_id = ? WHERE patient_id = ?", (new_mrn_input, old_mrn))
                        c.execute("UPDATE multi_patient_logs SET patient_id = ? WHERE patient_id = ?", (new_mrn_input, old_mrn))
                        
                        conn.commit()
                        if hasattr(conn, 'sync'):
                            conn.sync()
                            
                        st.success(f"Updated MRN from {old_mrn} to {new_mrn_input}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating MRN: {e}")
                    finally:
                        conn.close()

    # 3. RESET PATIENT PASSWORD
