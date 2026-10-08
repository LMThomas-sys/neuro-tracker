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
    initial_sidebar_state="collapsed",
    page_icon="🧠"
)

# Connect to Turso Cloud DB (or fallback to local sqlite for offline testing)
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            date TEXT PRIMARY KEY,
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
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

st.title("🧠 Post-MVD Recovery Tracker")
st.caption("Patient Recovery Log for Dr. Ananda | Right Retrosigmoid Craniotomy / MVD")

# Sidebar - Daily Data Entry
st.sidebar.header("📝 Daily Log Entry")

log_date = st.sidebar.date_input("Log Date", datetime.date.today())
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

if st.sidebar.button("Save Daily Log", type="primary"):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO daily_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
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
        str(log_date), systolic, diastolic, pulse, temperature,
        incision_pain, hardware_sens, heat_weakness, hand_clumsy,
        right_ear_pain, ", ".join(auditory_noises), 1 if positional_palpitations else 0, notes
    ))
    conn.commit()
    if hasattr(conn, 'sync'):
        conn.sync()
    conn.close()
    st.sidebar.success(f"Saved entry for {log_date}")

# Main Dashboard
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM daily_logs ORDER BY date ASC", conn)
conn.close()

if df.empty:
    st.info("No logs recorded yet. Use the sidebar menu to enter your first day's vitals and symptoms.")
else:
    tab1, tab2, tab3 = st.tabs(["📊 Analytics & Trends", "📋 Raw Data", "📄 PDF Export for Dr. Ananda"])

    with tab1:
        df['whooshing_lying_flat'] = df['auditory_noises'].fillna('').apply(
            lambda x: 1 if "Whooshing Sound (when lying flat)" in x else 0
        )
        df['humming_wind'] = df['auditory_noises'].fillna('').apply(
            lambda x: 1 if "Straight Humming / Wind Blowing Sound (non-pulsating)" in x else 0
        )

        st.subheader("Vitals Overview")
        col1, col2, col3, col4 = st.columns(4)
        latest = df.iloc[-1]
        col1.metric("Latest Blood Pressure", f"{latest['systolic']}/{latest['diastolic']} mmHg")
        col2.metric("Latest Pulse", f"{latest['pulse']} bpm")
        col3.metric("Latest Temperature", f"{latest['temperature']} °C")
        
        total_whooshing = df['whooshing_lying_flat'].sum()
        total_palpitations = df['positional_palpitations'].sum()
        total_days = len(df)
        col4.metric(
            "Positional Symptoms",
            f"{total_whooshing + total_palpitations} Days Total",
            delta=f"Whooshing: {total_whooshing}/{total_days}d | Dubdub: {total_palpitations}/{total_days}d",
            delta_color="off"
        )

        st.subheader("🛌 Positional Symptoms Tracker (Lying Flat)")
        fig_positional = go.Figure()
        
        fig_positional.add_trace(go.Bar(
            x=df['date'], y=df['whooshing_lying_flat'],
            name="Whooshing Sound (Lying Flat)", marker_color="#8B5CF6"
        ))
        fig_positional.add_trace(go.Bar(
            x=df['date'], y=df['positional_palpitations'],
            name="Chest 'Dubdub' / Palpitations (Lying Flat)", marker_color="#EF4444"
        ))
        fig_positional.add_trace(go.Bar(
            x=df['date'], y=df['humming_wind'],
            name="Wind Humming Sound", marker_color="#06B6D4"
        ))

        fig_positional.update_layout(
            barmode='group',
            title="Daily Occurrence of Positional Auditory & Cardiac Symptoms",
            xaxis_title="Date",
            yaxis=dict(title="Occurrence", tickvals=[0, 1], ticktext=["Absent", "Present"]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_positional, use_container_width=True)

        fig_vitals = px.line(df, x="date", y=["systolic", "diastolic", "pulse"],
                             title="Blood Pressure & Pulse Trends")
        st.plotly_chart(fig_vitals, use_container_width=True)

        fig_temp = px.line(df, x="date", y="temperature", title="Daily Body Temperature (°C)")
        fig_temp.add_hline(y=38.0, line_dash="dash", line_color="red", annotation_text="Fever Threshold (38°C)")
        st.plotly_chart(fig_temp, use_container_width=True)

        st.subheader("Neurological & Incision Symptom Severity (0–10)")
        symptom_cols = ["incision_pain", "hardware_sensitivity", "heat_weakness_flare", "hand_clamsiness", "right_ear_pain"]
        fig_symptoms = px.line(df, x="date", y=symptom_cols,
                               title="Symptom Scores Over Time")
        st.plotly_chart(fig_symptoms, use_container_width=True)

    with tab2:
        st.dataframe(df, use_container_width=True)

    with tab3:
        st.subheader("Generate Clinical Summary PDF")

        def generate_pdf(dataframe):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()

            elements.append(Paragraph("<b>Post-MVD Recovery Summary (1-Month Log)</b>", styles['Title']))
            elements.append(Paragraph("<b>Patient:</b> Retrosigmoid Craniotomy / MVD Recovery Tracker", styles['Normal']))
            elements.append(Paragraph("<b>Attending Neurosurgeon:</b> Dr. Ananda", styles['Normal']))
            elements.append(Paragraph(f"<b>Report Generated:</b> {datetime.date.today()}", styles['Normal']))
            elements.append(Spacer(1, 10))

            headers = ["Date", "BP", "Pulse", "Temp", "Incision", "Hardware", "Heat/Weak", "Hand Clums", "R Ear", "Auditory Noises", "Chest 'Dubdub'"]
            table_data = [headers]

            for _, row in dataframe.iterrows():
                table_data.append([
                    str(row['date']),
                    f"{row['systolic']}/{row['diastolic']}",
                    str(row['pulse']),
                    f"{row['temperature']}°C",
                    str(row['incision_pain']),
                    str(row['hardware_sensitivity']),
                    str(row['heat_weakness_flare']),
                    str(row['hand_clamsiness']),
                    str(row['right_ear_pain']),
                    Paragraph(str(row['auditory_noises']), styles['Normal']),
                    "Yes" if row['positional_palpitations'] == 1 else "No"
                ])

            t = Table(table_data, colWidths=[55, 45, 35, 40, 40, 45, 50, 50, 35, 120, 55])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 6.5),
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
