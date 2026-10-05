import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import os
import random
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# Setting Page
st.set_page_config(page_title="VISIONEST Dashboard", page_icon="visionest_logo.png", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# SUNTIKAN CSS "SYNAPSE" ENTERPRISE THEME
# ==========================================
st.markdown("""
<style>
    /* Reset & Font */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Background Utama Abu-Abu Sangat Muda */
    .stApp {
        background-color: #f4f7fe;
    }
    
    /* Hilangkan padding default Streamlit yang mengganggu */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }

    /* Sidebar Putih Bersih */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: none;
        box-shadow: 2px 0px 20px rgba(0, 0, 0, 0.03);
    }

    /* Sembunyikan Header bawaan Streamlit (Garis atas dan hamburger menu) */
    header[data-testid="stHeader"] {
        display: none;
    }

    /* CUSTOM ENTERPRISE CARD */
    .nexus-card {
        background-color: #ffffff;
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0px 10px 30px rgba(17, 38, 146, 0.05);
        margin-bottom: 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    /* Header Card */
    .nexus-card-title {
        font-size: 14px;
        font-weight: 700;
        color: #a3aed0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }

    /* Nilai Utama Metrik */
    .nexus-card-value {
        font-size: 38px;
        font-weight: 800;
        color: #1b254b;
        line-height: 1.2;
    }
    
    .nexus-card-value-small {
        font-size: 24px;
        font-weight: 800;
        color: #1b254b;
        line-height: 1.2;
    }

    .nexus-card-sub {
        font-size: 14px;
        font-weight: 600;
        color: #a3aed0;
        margin-top: 4px;
    }

    /* Badge Status */
    .badge-online {
        background-color: #e0f8e9;
        color: #05cd99;
        padding: 6px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 700;
        display: inline-block;
    }
    .badge-offline {
        background-color: #ffe5d3;
        color: #ff5b5b;
        padding: 6px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 700;
        display: inline-block;
    }
    .badge-running {
        background-color: #e2e8f0;
        color: #4318ff;
        padding: 6px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 700;
        display: inline-block;
    }
    
    /* Tombol Navigasi Radio Streamlit diakali biar mirip menu aplikasi */
    div.row-widget.stRadio > div {
        background: transparent;
    }
    div.row-widget.stRadio > div label {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 15px !important;
        font-weight: 700 !important;
        color: #a3aed0 !important;
        font-size: 15px !important;
    }
    div.row-widget.stRadio > div label[data-baseweb="radio"] > div:first-child {
        display: none; /* Sembunyikan bulatannya */
    }
    /* Sembunyikan divider bawaan */
    hr {
        border-color: #e2e8f0 !important;
        margin-top: 10px !important;
        margin-bottom: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# BACKEND MQTT & DATA
# ==========================================
DB_FILE = "visionest_logs.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"logs": [], "last_log_ts": None}

def save_db(logs_list, last_ts):
    with open(DB_FILE, "w") as f:
        json.dump({"logs": logs_list, "last_log_ts": last_ts}, f)

@st.cache_resource
def get_shared_data():
    db_data = load_db()
    return {
        "device_id": "NO CONNECTION",
        "operator": "Not Set",
        "shift": "-",
        "status": "OFFLINE",
        "target_qty": 0,
        "progress_pct": 0,
        "pos_x": 0.0,
        "pos_y": 0.0,
        "mat_p": 0.0,          
        "mat_l": 0.0,          
        "shape_name": "-",     
        "shape_poly": [],      
        "nested_polys": [],    
        "duration_sec": 0.0,
        "timestamp": time.strftime("%H:%M:%S"),
        "waste_pct": 100.0,
        "logs": db_data.get("logs", []),             
        "last_log_ts": db_data.get("last_log_ts", None),
        "ping_msgs": [] 
    }

data = get_shared_data()

@st.cache_resource
def start_mqtt():
    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe("advantech/wise/visionest/telemetry")
        client.subscribe("advantech/wise/visionest/ping") 

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            if msg.topic == "advantech/wise/visionest/ping":
                if payload.get("sender") == "GUI":
                    data.setdefault("ping_msgs", []).append(payload)
                    if len(data["ping_msgs"]) > 20: data["ping_msgs"].pop(0)
            else:
                for key, value in payload.items():
                    if key not in ["logs", "last_log_ts", "ping_msgs"]:
                        if key in ["shape_poly", "nested_polys"] and not value:
                            continue
                        data[key] = value
                
                if payload.get("status") == "CYCLE_COMPLETE":
                    data["progress_pct"] = 100
                    ts = payload.get("timestamp")
                    if ts != data["last_log_ts"]:
                        data["last_log_ts"] = ts
                        entry = {
                            "waktu": ts,
                            "operator": payload.get("operator", "Unknown"),
                            "shift": payload.get("shift", "Shift 1"),
                            "pcs": payload.get("target_qty", 0),
                            "ukuran": f"{payload.get('mat_p', 0)} x {payload.get('mat_l', 0)}",
                            "bentuk": payload.get("shape_name", "-"),
                            "waste": payload.get("waste_pct", 100.0),
                            "shape_poly": payload.get("shape_poly", []),
                            "nested_polys": payload.get("nested_polys", [])
                        }
                        data["logs"].insert(0, entry)
                        save_db(data["logs"], ts)
        except Exception: pass

    client_id = f"VISIONEST_WEB_{random.randint(10000, 99999)}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id, transport="websockets")
    client.on_connect = on_connect
    client.on_message = on_message
    client.tls_set() 
    client.connect("broker.hivemq.com", 8884, 60)
    client.loop_start()
    return client

mqtt_client = start_mqtt()


# ==========================================
# 1. SIDEBAR (Putih Bersih)
# ==========================================
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns([3, 7])
    with c1:
        st.markdown("<img src='https://raw.githubusercontent.com/alzak123/Textile-Nest/main/app/visionest_logo.png' width='55' style='margin-left: 10px;'>", unsafe_allow_html=True)
    with c2:
        st.markdown("<h3 style='color:#1b254b; margin:0; font-size: 20px; font-weight:800; padding-top:5px;'>VISIONEST</h3><p style='color:#a3aed0; margin:0; font-size:12px; font-weight:700;'>BY DEMIURGEN ✦</p>", unsafe_allow_html=True)
    
    st.markdown("<br><p style='color:#a3aed0; font-size:12px; font-weight:700; margin-left: 15px; margin-bottom: 5px;'>NAVIGATION</p>", unsafe_allow_html=True)
    
    page = st.radio("", ["📱 Live Dashboard", "📊 Analytics AI", "📝 Activity Log"], label_visibility="collapsed")
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    # Card Kecil Biru di bawah Sidebar (Mirip referensi WISE-IoT)
    st.markdown("""
    <div style="background: linear-gradient(135deg, #4318ff 0%, #3f08a6 100%); border-radius: 20px; padding: 20px; text-align: center; margin: 15px;">
        <p style="color: white; font-weight: 700; font-size: 14px; margin: 0;">VISIONEST - Advantech</p>
        <p style="color: #e2e8f0; font-weight: 500; font-size: 11px; margin-bottom: 15px;">by PENS & Efortech</p>
        <div style="background-color: white; color: #4318ff; border-radius: 10px; padding: 8px; font-weight: 800; font-size: 12px;">
            ● WISE-IoT Cloud
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 2. HEADER TOP BAR (Card Memanjang)
# ==========================================
waktu_skrg = time.strftime('%H:%M:%S')
status_badge = ""
stat = data['status']
if stat in ["MACHINE_RUNNING", "CUTTING_IN_PROGRESS"]:
    status_badge = f"<span class='badge-online'>● {stat.replace('_', ' ')}</span>"
elif stat == "EMERGENCY_STOP_TRIGGERED":
    status_badge = f"<span class='badge-offline'>● E-STOP TRIGGERED!</span>"
elif stat == "OFFLINE":
    status_badge = "<span class='badge-offline'>● NO CONNECTION</span>"
else:
    status_badge = f"<span class='badge-running'>● {stat.replace('_', ' ')}</span>"

st.markdown(f"""
<div class="nexus-card" style="flex-direction: row; justify-content: space-between; align-items: center; padding: 15px 25px; margin-bottom: 25px; border-radius: 100px;">
    <div style="display: flex; align-items: center; gap: 20px;">
        <span style="font-weight: 800; color: #1b254b; font-size: 15px;">VISIONEST Dashboard</span>
        <span style="color: #e2e8f0;">|</span>
        <span style="font-weight: 700; color: #a3aed0; font-size: 13px;">PARTNERS</span>
        <span style="color: #1b254b; font-weight: 800; font-size: 14px;">ADVANTECH <span style="color:#a3aed0; font-weight:500;">x</span> EFORTECH <span style="color:#a3aed0; font-weight:500;">x</span> PENS</span>
    </div>
    <div style="display: flex; align-items: center; gap: 15px;">
        {status_badge}
        <span style="background-color: #f4f7fe; padding: 8px 15px; border-radius: 12px; font-weight: 700; color: #1b254b; font-size: 14px;">⏱ {waktu_skrg}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ==========================================
# 3. KONTEN HALAMAN
# ==========================================
if page == "📱 Live Dashboard":
    
    # BARIS 1: PREVIEW (Kiri Besar) + DEVICE INFO (Kanan Kecil)
    col_kiri, col_kanan = st.columns([7, 3])
    
    with col_kanan:
        # Card Device ID & Operator
        st.markdown(f"""
        <div class="nexus-card">
            <div class="nexus-card-title">Machine Identity</div>
            <div class="nexus-card-value-small" style="margin-bottom: 15px;">{data['device_id']}</div>
            <div class="nexus-card-title">Active Operator</div>
            <div class="nexus-card-value-small">{data['operator']}</div>
            <div class="nexus-card-sub">Shift: {data['shift']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Card Progress
        st.markdown(f"""
        <div class="nexus-card">
            <div class="nexus-card-title">Cutting Progress</div>
            <div class="nexus-card-value" style="color: #4318ff;">{data['progress_pct']}<span style="font-size:20px;">%</span></div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(max(0.0, min(1.0, data['progress_pct'] / 100.0)))
        
    with col_kiri:
        # Card 2D Preview Nesting
        st.markdown(f"""
        <div class="nexus-card" style="padding-bottom: 0px;">
            <div style="display: flex; justify-content: space-between;">
                <div class="nexus-card-title">Live Production Layout</div>
                <div class="nexus-card-sub" style="margin-top:0;">{data.get('mat_p', 0)} x {data.get('mat_l', 0)} mm</div>
            </div>
        """, unsafe_allow_html=True)
        
        mat_p = data.get('mat_p', 0.0)
        mat_l = data.get('mat_l', 0.0)
        
        if mat_p > 0 and mat_l > 0 and data.get('nested_polys'):
            fig_nest = go.Figure()
            # Garis Batas Merah
            fig_nest.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode='lines', line=dict(color='#ff5b5b', width=3), hoverinfo='skip'))
            
            # Pola Kuning Emas
            for idx, poly in enumerate(data['nested_polys']):
                xs = [p[0] for p in poly] + [poly[0][0]]
                ys = [p[1] for p in poly] + [poly[0][1]]
                fig_nest.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#ffb547', width=2), fillcolor='rgba(255, 181, 71, 0.3)', name=f'Pcs {idx+1}'))
                
            # Laser Merah
            fig_nest.add_trace(go.Scatter(x=[data.get('pos_x', 0.0)], y=[abs(data.get('pos_y', 0.0))], mode='markers', marker=dict(color='#ff5b5b', size=14, symbol='circle'), name='Laser Tool'))
            
            fig_nest.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=10, b=10, l=10, r=10), height=340, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
            st.plotly_chart(fig_nest, use_container_width=True)
        else:
            st.markdown("<div style='height: 340px; display:flex; align-items:center; justify-content:center; color:#a3aed0; font-weight:600;'>NO PATTERN LOADED</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # BARIS 2: METRIK BAWAH (Berjejer)
    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px;">
    """, unsafe_allow_html=True)
    
    # Custom HTML Metric Cards
    metrics_data = [
        ("TARGET OUTPUT", f"{data['target_qty']}", "Pieces", "Total items layout"),
        ("CYCLE DURATION", f"{data['duration_sec']}", "Sec", "Current execution time"),
        ("MATERIAL WASTE", f"{data['waste_pct']}", "%", "Estimated scrap fabric"),
        ("SHAPE CLASS", f"{data['shape_name']}", "", "Detected pattern")
    ]
    
    cols = st.columns(4)
    for i, col in enumerate(cols):
        with col:
            st.markdown(f"""
            <div class="nexus-card" style="margin-bottom: 0;">
                <div class="nexus-card-title">{metrics_data[i][0]}</div>
                <div style="display:flex; align-items:baseline; gap:5px;">
                    <div class="nexus-card-value">{metrics_data[i][1]}</div>
                    <div style="font-size: 16px; font-weight:700; color:#a3aed0;">{metrics_data[i][2]}</div>
                </div>
                <div class="nexus-card-sub">{metrics_data[i][3]}</div>
            </div>
            """, unsafe_allow_html=True)

    # BARIS 3: SERIAL LOG CHAT
    st.markdown("""
    <div class="nexus-card" style="margin-top: 20px;">
        <div class="nexus-card-title">Communication Log (Web ↔ GUI)</div>
    </div>
    """, unsafe_allow_html=True)
    
    if "ping_input" not in st.session_state:
        st.session_state.ping_input = ""

    def send_web_ping():
        msg = st.session_state.ping_input_widget
        if msg:
            payload = {"sender": "WEB", "message": msg, "timestamp": time.strftime("%H:%M:%S")}
            mqtt_client.publish("advantech/wise/visionest/ping", json.dumps(payload), qos=1)
            shared_data.setdefault("ping_msgs", []).append(payload)
            st.session_state.ping_input_widget = "" 

    c_chat, c_input = st.columns([8, 2])
    with c_chat:
        chat_box = st.container(height=180)
        with chat_box:
            if not data.get("ping_msgs"):
                st.markdown("<p style='color:#a3aed0; font-weight:600;'>No messages yet.</p>", unsafe_allow_html=True)
            for p in data.get("ping_msgs", []):
                if p["sender"] == "WEB":
                    st.markdown(f"<div style='text-align: right; color: #4318ff; font-weight:700; font-size:15px;'>[WEB] {p['message']} <br><small style='color: #a3aed0;'>({p['timestamp']})</small></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align: left; color: #05cd99; font-weight:700; font-size:15px;'>[GUI] {p['message']} <br><small style='color: #a3aed0;'>({p['timestamp']})</small></div>", unsafe_allow_html=True)

    with c_input:
        st.text_input("Msg:", key="ping_input_widget", on_change=send_web_ping, label_visibility="collapsed", placeholder="Type message...")
        st.button("🚀 Send Ping", type="primary", on_click=send_web_ping, use_container_width=True)

elif page == "📊 Analytics AI":
    st.markdown("""<div class="nexus-card"><div class="nexus-card-value-small">Material Usage Trends</div></div>""", unsafe_allow_html=True)
    if data["logs"]:
        df = pd.DataFrame(data["logs"]).sort_values(by="waktu") 
        df['Terpakai'] = 100.0 - df['waste']
        df['Waste'] = df['waste']
        
        fig_group = go.Figure(data=[
            go.Bar(name='Used (Effective)', x=df['waktu'], y=df['Terpakai'], marker_color='#05cd99'),
            go.Bar(name='Fabric Waste (Scrap)', x=df['waktu'], y=df['Waste'], marker_color='#ff5b5b')
        ])
        fig_group.update_layout(barmode='group', bargroupgap=0.1, margin=dict(t=20, b=20, l=20, r=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#1b254b'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_group, use_container_width=True)

        st.markdown("""<div class="nexus-card"><div class="nexus-card-value-small">Production History (Qty)</div></div>""", unsafe_allow_html=True)
        fig_bar = px.bar(df, x="waktu", y="pcs", color="shift", text="pcs", color_discrete_sequence=['#4318ff', '#39b8ff'])
        fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#1b254b'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No data available for analytics yet.")

elif page == "📝 Activity Log":
    c_title, c_btn = st.columns([8, 2])
    with c_title:
        st.markdown("""<div class="nexus-card"><div class="nexus-card-value-small">Historical Production Logs</div></div>""", unsafe_allow_html=True)
    with c_btn:
        if st.button("🗑 Reset Data", type="primary", use_container_width=True):
            data["logs"] = []
            data["last_log_ts"] = None
            save_db([], None)
            st.rerun()

    if not data["logs"]:
        st.info("No cutting history yet.")
    else:
        for i, log in enumerate(data["logs"]):
            with st.expander(f"✅ Finished at {log['waktu']} (Op: {log['operator']})"):
                c_text, c_img = st.columns([6, 4])
                with c_text:
                    st.markdown(f"**Target Qty:** {log['pcs']} Pcs <br>**Dimensions:** {log['ukuran']} mm<br>**Waste:** {log['waste']:.1f}%", unsafe_allow_html=True)
                with c_img:
                    poly_data = log.get('shape_poly', [])
                    if poly_data:
                        xs = [p[0] for p in poly_data] + [poly_data[0][0]]
                        ys = [p[1] for p in poly_data] + [poly_data[0][1]]
                        fig_hist = go.Figure()
                        fig_hist.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#4318ff', width=3), fillcolor='rgba(67, 24, 255, 0.2)'))
                        fig_hist.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=0, b=0, l=0, r=0), height=100, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                        st.plotly_chart(fig_hist, use_container_width=True, key=f"hist_{i}")

# ==========================================
# AUTO REFRESH FOOTER
# ==========================================
is_auto_refresh = st.sidebar.toggle("🔄 Live Auto-Refresh", value=True)
if is_auto_refresh:
    st_autorefresh(interval=2000, limit=None, key="auto_refresh")