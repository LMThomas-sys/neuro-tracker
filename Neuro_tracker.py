import datetime
import io
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
    page_title="Post-MVD Recovery Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🧠"
)

# Connect to Turso Cloud DB (or fallback to local sqlite for testing)
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
    # Updated primary key to composite (date, time_of_day) for 3x daily tracking
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs_v2 (
            date TEXT,
            time_of_day TEXT,
            entry_time TEXT,
            systolic INTEGER,
            diastolic INTEGER,
            pulse INTEGER,
            temperature REAL,
            incision_pain INTEGER,
            hardware_sensitivity INTEGER,
            heat_weakness_flare INTEGER,
            hand_clamsiness INTEGER,
            right_ear_pain INTEGER,
            auditory_noises TEXT,
            positional_palpitations INTEGER,
            notes TEXT,
            PRIMARY KEY (date, time_of_day)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

st.title("🧠 Post-MVD Recovery Tracker")
st.caption("Patient Recovery Log for Dr. Ananda | Right Retrosigmoid Craniotomy / MVD")

# Sidebar - Multi-Daily Entry Form
st.sidebar.header("📝 Daily Log Entry (3x Daily)")

log_date = st.sidebar.date_input("Log Date", datetime.date.today())

# Time Slot Selector
time_of_day = st.sidebar.selectbox(
    "Time Slot / Session",
    ["Morning (AM)", "Afternoon (PM)", "Evening / Night (PM)"]
)

# Exact Time Recording
exact_time = st.sidebar.time_input("Exact Time Taken", datetime.datetime.now().time())

st.sidebar.subheader("Vitals")
systolic = st.sidebar.number_input("Systolic BP (mmHg)", 80, 200, 120)
diastolic = st.sidebar.number_input("Diastolic BP (mmHg)", 50, 130, 80)
pulse = st.sidebar.number_input("Pulse Rate (bpm)", 40, 180, 72)
temperature = st.sidebar.number_input("Body Temp (°C)", 35.0, 41.0, 36.8, step=0.1)

st.sidebar.subheader("Symptom Severity (0–10)")
incision_pain = st.sidebar.slider("Incision Pain", 0, 10, 0)
hardware_sens = st.sidebar.slider("Hardware/Screw Sensitivity", 0, 10, 0)
heat_weakness = st.sidebar.slider("Heat Flare-up / Weakness", 0, 10, 0)
hand_clumsy = st.sidebar.slider("Hand Clumsiness / Dropping Objects", 0, 10, 0)
right_ear_pain = st.sidebar.slider("Right Ear Pain", 0, 10, 0)

st.sidebar.subheader("Ear & Chest Symptoms")
auditory_noises = st.sidebar.multiselect(
    "Auditory Tinnitus / Noises",
    [
        "None",
        "Whooshing Sound (when lying flat)",
        "Straight Humming / Wind Blowing Sound (non-pulsating)",
        "Washing Machine Sound",
        "High Pitch Ringing",
        "Fullness / Pressure"
    ]
)

positional_palpitations = st.sidebar.checkbox("Sudden Chest 'Dubdub' / Palpitations when Lying Flat")
notes = st.sidebar.text_area("Additional Notes / Specific Triggers")

if st.sidebar.button("Save Entry", type="primary"):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO daily_logs_v2 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, time_of_day) DO UPDATE SET
            entry_time=excluded.entry_time,
            systolic=excluded.systolic,
            diastolic=excluded.diastolic,
            pulse=excluded.pulse,
            temperature=excluded.temperature,
            incision_pain=excluded.incision_pain,
            hardware_sensitivity=excluded.hardware_sensitivity,
            heat_weakness_flare=excluded.heat_weakness_flare,
            hand_clamsiness=excluded.hand_clamsiness,
            right_ear_pain=excluded.right_ear_pain,
            auditory_noises=excluded.auditory_noises,
            positional_palpitations=excluded.positional_palpitations,
            notes=excluded.notes
    ''', (
        str(log_date), time_of_day, str(exact_time), systolic, diastolic, pulse, temperature,
        incision_pain, hardware_sens, heat_weakness, hand_clumsy,
        right_ear_pain, ", ".join(auditory_noises), 1 if positional_palpitations else 0, notes
    ))
    conn.commit()
    if hasattr(conn, 'sync'):
        conn.sync()
    conn.close()
    st.sidebar.success(f"Saved {time_of_day} entry for {log_date} ({exact_time.strftime('%I:%M %p')})")

# Main Dashboard
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM daily_logs_v2 ORDER BY date ASC, entry_time ASC", conn)
conn.close()

if df.empty:
    st.info("No logs recorded yet. Use the sidebar menu to enter your first reading.")
else:
    # Combine Date & Time of Day for display
    df['date_time_label'] = df['date'] + " (" + df['time_of_day'] + ")"

    tab1, tab2, tab3 = st.tabs(["📊 Analytics & Trends", "📋 Raw Data", "📄 PDF Export for Dr. Ananda"])

    with tab1:
        df['whooshing_lying_flat'] = df['auditory_noises'].fillna('').apply(
            lambda x: 1 if "Whooshing Sound (when lying flat)" in x else 0
        )
        df['humming_wind'] = df['auditory_noises'].fillna('').apply(
            lambda x: 1 if "Straight Humming / Wind Blowing Sound (non-pulsating)" in x else 0
        )

        st.subheader("Latest Reading Overview")
        col1, col2, col3, col4 = st.columns(4)
        latest = df.iloc[-1]
        col1.metric("Latest Blood Pressure", f"{latest['systolic']}/{latest['diastolic']} mmHg", delta=latest['time_of_day'], delta_color="off")
        col2.metric("Latest Pulse", f"{latest['pulse']} bpm")
        col3.metric("Latest Temperature", f"{latest['temperature']} °C")
        
        total_whooshing = df['whooshing_lying_flat'].sum()
        total_palpitations = df['positional_palpitations'].sum()
        col4.metric(
            "Positional Symptoms Recorded",
            f"{total_whooshing + total_palpitations} Sessions",
            delta=f"Whooshing: {total_whooshing} | Dubdub: {total_palpitations}",
            delta_color="off"
        )

        st.subheader("📈 Blood Pressure & Pulse Trends (3x Daily)")
        fig_vitals = px.line(df, x="date_time_label", y=["systolic", "diastolic", "pulse"],
                             title="Blood Pressure & Pulse Across Daily Sessions",
                             markers=True)
        fig_vitals.update_xaxes(title="Date & Session")
        st.plotly_chart(fig_vitals, use_container_width=True)

        st.subheader("🛌 Positional Symptoms (Lying Flat)")
        fig_positional = go.Figure()
        
        fig_positional.add_trace(go.Bar(
            x=df['date_time_label'], y=df['whooshing_lying_flat'],
            name="Whooshing Sound (Lying Flat)", marker_color="#8B5CF6"
        ))
        fig_positional.add_trace(go.Bar(
            x=df['date_time_label'], y=df['positional_palpitations'],
            name="Chest 'Dubdub' / Palpitations", marker_color="#EF4444"
        ))

        fig_positional.update_layout(
            barmode='group',
            title="Session-by-Session Positional Auditory & Cardiac Symptoms",
            xaxis_title="Date & Session",
            yaxis=dict(title="Occurrence", tickvals=[0, 1], ticktext=["Absent", "Present"]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_positional, use_container_width=True)

        st.subheader("Symptom Severity (0–10)")
        symptom_cols = ["incision_pain", "hardware_sensitivity", "heat_weakness_flare", "hand_clamsiness", "right_ear_pain"]
        fig_symptoms = px.line(df, x="date_time_label", y=symptom_cols,
                               title="Symptom Scores Across Daily Sessions", markers=True)
        fig_symptoms.update_xaxes(title="Date & Session")
        st.plotly_chart(fig_symptoms, use_container_width=True)

    with tab2:
        st.dataframe(df, use_container_width=True)

    with tab3:
        st.subheader("Generate Clinical Summary PDF")

        def generate_pdf(dataframe):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
            elements = []
            styles = getSampleStyleSheet()

            elements.append(Paragraph("<b>Post-MVD Recovery Summary (3x Daily Vitals Log)</b>", styles['Title']))
            elements.append(Paragraph("<b>Patient:</b> Retrosigmoid Craniotomy / MVD Recovery Tracker", styles['Normal']))
            elements.append(Paragraph("<b>Attending Neurosurgeon:</b> Dr. Ananda", styles['Normal']))
            elements.append(Paragraph(f"<b>Report Generated:</b> {datetime.date.today()}", styles['Normal']))
            elements.append(Spacer(1, 10))

            headers = ["Date", "Session", "Time", "BP", "Pulse", "Temp", "Incision", "Hardware", "Heat/Weak", "Hand Clums", "R Ear", "Auditory / Positional"]
            table_data = [headers]

            for _, row in dataframe.iterrows():
                notes_summary = str(row['auditory_noises']) if row['auditory_noises'] else "None"
                if row['positional_palpitations'] == 1:
                    notes_summary += " | Chest Dubdub"

                table_data.append([
                    str(row['date']),
                    str(row['time_of_day']),
                    str(row['entry_time'])[:5],
                    f"{row['systolic']}/{row['diastolic']}",
                    str(row['pulse']),
                    f"{row['temperature']}°C",
                    str(row['incision_pain']),
                    str(row['hardware_sensitivity']),
                    str(row['heat_weakness_flare']),
                    str(row['hand_clamsiness']),
                    str(row['right_ear_pain']),
                    Paragraph(notes_summary, styles['Normal'])
                ])

            t = Table(table_data, colWidths=[50, 55, 35, 45, 30, 35, 35, 40, 45, 45, 30, 130])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 6.5),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
            ]))
            elements.append(t)
            doc.build(elements)
            buffer.seek(0)
            return buffer

        if st.button("Build PDF Report"):
            pdf_data = generate_pdf(df)
            st.download_button(
                label="📥 Download PDF for Dr. Ananda",
                data=pdf_data,
                file_name=f"MVD_Recovery_Report_{datetime.date.today()}.pdf",
                mime="application/pdf"
            )
