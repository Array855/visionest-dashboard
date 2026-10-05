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

# Mode 'Light' dan Sidebar default kebuka
st.set_page_config(page_title="VISIONEST Dashboard", page_icon="visionest_logo.png", layout="wide", initial_sidebar_state="expanded")

# SUNTIKAN CSS TERANG (Perbaikan Bug Teks Ngilang & Sidebar)
st.markdown("""
<style>
    /* Paksa background cerah */
    .stApp {
        background-color: #f1f5f9;
        color: #0f172a;
    }
    /* Paksa Sidebar cerah */
    [data-testid="stSidebar"] {
        background-color: #e2e8f0;
        border-right: 2px solid #cbd5e1;
    }
    /* PAKSA SEMUA TEKS METRIK & LABEL JADI GELAP BIAR GAK NGILANG */
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"], .stRadio p, .stMarkdown p, h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
    }
    /* Warna kotak expander dan kontainer */
    .st-emotion-cache-1y4p8pa {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
    }
    /* Garis pemisah */
    hr {
        border-color: #cbd5e1 !important;
    }
    /* Sembunyikan margin atas biar lebih rapi */
    .block-container {
        padding-top: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "visionest_logs.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"logs": [], "last_log_ts": None}

def save_db(logs_list, last_ts):
    with open(DB_FILE, "w") as f:
        json.dump({"logs": logs_list, "last_log_ts": last_ts}, f)

@st.cache_resource
def get_shared_data():
    db_data = load_db()
    return {
        "device_id": "WAITING FOR DATA...",
        "operator": "-",
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
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "waste_pct": 100.0,
        "logs": db_data.get("logs", []),             
        "last_log_ts": db_data.get("last_log_ts", None),
        "ping_msgs": [] 
    }

shared_data = get_shared_data()

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
                    shared_data.setdefault("ping_msgs", []).append(payload)
                    if len(shared_data["ping_msgs"]) > 20:
                        shared_data["ping_msgs"].pop(0)
            else:
                for key, value in payload.items():
                    if key not in ["logs", "last_log_ts", "ping_msgs"]:
                        shared_data[key] = value
                
                if payload.get("status") == "CYCLE_COMPLETE":
                    shared_data["progress_pct"] = 100
                    ts = payload.get("timestamp")
                    if ts != shared_data["last_log_ts"]:
                        shared_data["last_log_ts"] = ts
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
                        shared_data["logs"].insert(0, entry)
                        save_db(shared_data["logs"], ts)
        except Exception:
            pass

    client_id = f"VISIONEST_WEB_{random.randint(10000, 99999)}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id, transport="websockets")
    client.on_connect = on_connect
    client.on_message = on_message
    client.tls_set() 
    client.connect("broker.hivemq.com", 8884, 60)
    client.loop_start()
    return client

mqtt_client_instance = start_mqtt()
data = shared_data


# ==========================================
# 1. SIDEBAR / NAVBAR KIRI (Sesuai Sketsa)
# ==========================================
with st.sidebar:
    # --- LOGO & NAMA APP ---
    col_log1, col_log2 = st.columns([2, 8])
    with col_log1:
        st.markdown("<img src='https://raw.githubusercontent.com/alzak123/Textile-Nest/main/app/visionest_logo.png' width='50'>", unsafe_allow_html=True)
    with col_log2:
        st.markdown("<h3 style='color: #d4af37; margin:0; padding:0;'>VISIONEST</h3><p style='color: #1e3a8a; margin:0; font-weight:bold;'>by DEMIURGEN</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # --- NAVIGASI UTAMA ---
    page = st.radio("Navigation Menu", ["🏠 HOME", "📈 ANALYSIS", "📝 PRODUCTION LOG"], label_visibility="collapsed")
    

# ==========================================
# 2. HEADER ATAS (Online, Time, Logo PENS)
# ==========================================
c_stat, c_time, c_logo = st.columns([3, 4, 3])
with c_stat:
    st.markdown("<h4 style='color:#10b981; margin-top:15px;'>📶 ONLINE</h4>", unsafe_allow_html=True)

with c_time:
    # Waktu Realtime
    waktu_skrg = time.strftime('%d %B %Y - %H:%M:%S')
    st.markdown(f"<h4 style='text-align:center; color:#475569; margin-top:15px;'>{waktu_skrg}</h4>", unsafe_allow_html=True)

with c_logo:
    if os.path.exists("logo_pens_kanan.png"): 
        st.image("logo_pens_kanan.png", use_container_width=True)
    else:
        st.markdown("<h4 style='text-align:right; color:#1e3a8a; margin-top:15px;'>[LOGO PENS]</h4>", unsafe_allow_html=True)

st.markdown("---")


# ==========================================
# 3. KONTEN BERDASARKAN NAVIGASI
# ==========================================

if page == "🏠 HOME":
    
    # ---> BARIS 1: DEVICE ID, OPERATOR, STATUS <---
    info1, info2, info3 = st.columns(3)
    with info1:
        st.info(f"**🖥️ Device ID:**\n### {data['device_id']}")
    with info2:
        st.info(f"**👷 Operator:**\n### {data['operator']} ({data['shift']})")
    with info3:
        stat = data['status']
        if stat in ["MACHINE_RUNNING", "CUTTING_IN_PROGRESS", "CYCLE_COMPLETE", "SYSTEM_READY"]:
            st.success(f"**🔄 Status:**\n### {stat}")
        elif stat == "EMERGENCY_STOP_TRIGGERED":
            st.error(f"**🚨 Status:**\n### {stat}")
        elif stat == "OFFLINE":
            st.error(f"**⏸ Status:**\n### {stat}")
        else:
            st.warning(f"**⏸ Status:**\n### {stat}")

    st.markdown("---")
    
    # ---> BARIS 2: PREVIEW 2D (TOP-DOWN) PENGGANTI 3D YANG BERAT <---
    st.markdown(f"<h4 style='text-align: center;'>👁️ Live Nesting Preview - Material: {data.get('mat_p', 0)} x {data.get('mat_l', 0)} mm</h4>", unsafe_allow_html=True)
    
    mat_p = data.get('mat_p', 0.0)
    mat_l = data.get('mat_l', 0.0)
    
    if mat_p > 0 and mat_l > 0 and data.get('status') not in ["SYSTEM_READY", "OFFLINE"] and data.get('nested_polys'):
        
        # Bikin Figure 2D Flat (Sangat ringan dan jelas)
        fig_nest = go.Figure()
        
        # 1. Gambar Kotak Batas Material (Garis Merah)
        fig_nest.add_trace(go.Scatter(
            x=[0, mat_p, mat_p, 0, 0], 
            y=[0, 0, mat_l, mat_l, 0], 
            mode='lines', 
            line=dict(color='#ef4444', width=3), 
            hoverinfo='skip'
        ))
        
        # 2. Gambar Pola Sarang (Kuning Emas Transparan)
        for idx, poly in enumerate(data['nested_polys']):
            xs = [p[0] for p in poly] + [poly[0][0]]
            ys = [p[1] for p in poly] + [poly[0][1]]
            fig_nest.add_trace(go.Scatter(
                x=xs, y=ys, fill='toself', mode='lines', 
                line=dict(color='#eab308', width=1.5), 
                fillcolor='rgba(234, 179, 8, 0.4)', 
                name=f'Pcs {idx+1}'
            ))
            
        # 3. Gambar TITIK LASER MERAH (Posisi CNC Real-time)
        curr_x = data.get('pos_x', 0.0)
        curr_y = data.get('pos_y', 0.0)
        fig_nest.add_trace(go.Scatter(
            x=[curr_x], y=[abs(curr_y)], 
            mode='markers', 
            marker=dict(color='red', size=12, symbol='circle'), 
            name='Laser Tool'
        ))
        
        # Atur Layout 2D agar Presisi Skala 1:1
        fig_nest.update_layout(
            xaxis=dict(visible=False), 
            yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), 
            margin=dict(t=10, b=10, l=10, r=10), 
            height=400, 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)', 
            showlegend=False
        )
        
        # Tengahkan grafik biar rapi
        c_kiri, c_tengah, c_kanan = st.columns([1, 4, 1])
        with c_tengah:
            st.plotly_chart(fig_nest, use_container_width=True)
            
    else:
        st.info("NO PATTERN LOADED. Menunggu komputasi dari GUI / Mesin belum berjalan.")


    # ---> BARIS 3: METRIK DATA <---
    st.markdown("---")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("⏱ Duration", f"{data['duration_sec']} s")
    m2.metric("🎯 Target / Qty", f"{data['target_qty']} Pcs")
    m3.metric("📏 Dimension", f"{data['mat_p']} x {data['mat_l']} mm")
    m4.metric("📊 Presentase", f"{data['progress_pct']} %")
    m5.metric("💠 Bentuk Kerja", f"{data['shape_name']}")
    
    st.progress(max(0.0, min(1.0, data['progress_pct'] / 100.0)))
    st.markdown("---")
    
    
    # ---> BARIS 4: SERIAL LOG / CHAT <---
    st.markdown("### 📡 Serial Log (Web ↔ GUI)")
    if "ping_input" not in st.session_state:
        st.session_state.ping_input = ""

    def send_web_ping():
        msg = st.session_state.ping_input_widget
        if msg:
            payload = {"sender": "WEB", "message": msg, "timestamp": time.strftime("%H:%M:%S")}
            mqtt_client_instance.publish("advantech/wise/visionest/ping", json.dumps(payload), qos=1)
            shared_data.setdefault("ping_msgs", []).append(payload)
            st.session_state.ping_input_widget = "" 

    c_chat, c_input = st.columns([8, 2])
    with c_chat:
        chat_box = st.container(height=200)
        with chat_box:
            if not data.get("ping_msgs"):
                st.caption("No messages yet. Send ping to GUI desktop.")
            for p in data.get("ping_msgs", []):
                if p["sender"] == "WEB":
                    st.markdown(f"<div style='text-align: right; color: #0ea5e9; font-size:16px;'><b>[WEB]</b> {p['message']} <small style='color: #94a3b8;'>({p['timestamp']})</small></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align: left; color: #10b981; font-size:16px;'><b>[GUI]</b> {p['message']} <small style='color: #94a3b8;'>({p['timestamp']})</small></div>", unsafe_allow_html=True)

    with c_input:
        st.text_input("Type message:", key="ping_input_widget", on_change=send_web_ping, label_visibility="collapsed", placeholder="Tulis pesan...")
        st.button("🚀 Send", type="primary", on_click=send_web_ping, use_container_width=True)


elif page == "📈 ANALYSIS":
    st.markdown("### 📈 Executive Analytics")
    if data["logs"]:
        df = pd.DataFrame(data["logs"])
        df = df.sort_values(by="waktu") 
        
        st.markdown("**1. Material Usage Efficiency (Historical Trend)**")
        df['Terpakai'] = 100.0 - df['waste']
        df['Waste'] = df['waste']
        fig_group = go.Figure(data=[
            go.Bar(name='Used (Effective)', x=df['waktu'], y=df['Terpakai'], marker_color='#10b981'),
            go.Bar(name='Fabric Waste (Scrap)', x=df['waktu'], y=df['Waste'], marker_color='#ef4444')
        ])
        fig_group.update_layout(barmode='group', bargroupgap=0.1, margin=dict(t=20, b=20, l=20, r=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#0f172a'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_group, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True) 

        st.markdown("**2. Production History (Pieces per Cycle)**")
        fig_bar = px.bar(df, x="waktu", y="pcs", color="shift", text="pcs", color_discrete_sequence=px.colors.qualitative.Set2)
        fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#0f172a'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No completed production data (CYCLE_COMPLETE) to display analytical graphs yet.")


elif page == "📝 PRODUCTION LOG":
    col_log_1, col_log_2 = st.columns([8, 2])
    with col_log_1:
        st.markdown("### 📝 Daily Production Logs Data")
    with col_log_2:
        if st.button("🗑 Reset Web Data", type="primary", use_container_width=True):
            data["logs"] = []
            data["last_log_ts"] = None
            save_db([], None)
            st.rerun()

    if not data["logs"]:
        st.info("No cutting history yet. Please run the machine first.")
    else:
        for i, log in enumerate(data["logs"]):
            with st.expander(f"✅ Cutting Completed - {log['waktu']} (By: {log['operator']} | {log['shift']})"):
                
                c_text, c_img = st.columns([6, 4])
                show_layout = False
                
                with c_text:
                    st.markdown(f"""
                    - **Total Patterns (Qty):** {log['pcs']} Pcs
                    - **Material Dimensions:** `{log['ukuran']} mm`
                    - **Pattern Shape:** `{log.get('bentuk', '-')}`
                    - **Wasted Fabric (Scrap):** `{log['waste']:.1f}%`
                    """)
                    st.write("")
                    
                    if log.get('nested_polys'):
                        show_layout = st.toggle("👁️ Show Full Layout Simulation", key=f"tgl_modal_{i}")
                
                with c_img:
                    poly_data = log.get('shape_poly', [])
                    if poly_data:
                        xs = [p[0] for p in poly_data] + [poly_data[0][0]]
                        ys = [p[1] for p in poly_data] + [poly_data[0][1]]
                        fig_hist = go.Figure()
                        fig_hist.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#10b981', width=3), fillcolor='rgba(16, 185, 129, 0.3)'))
                        fig_hist.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=0, b=0, l=0, r=0), height=120, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                        st.plotly_chart(fig_hist, use_container_width=True, key=f"hist_{i}")

                if log.get('nested_polys') and show_layout:
                    st.markdown("---")
                    st.markdown(f"<p style='text-align: center; color: #d97706;'><b>Full Layout Simulation (Material: {log['ukuran']})</b></p>", unsafe_allow_html=True)
                    
                    mat_p, mat_l = 0, 0
                    try:
                        parts = log['ukuran'].split('x')
                        mat_p = float(parts[0].replace('mm', '').strip())
                        mat_l = float(parts[1].replace('mm', '').strip())
                    except: pass
                        
                    fig_nest = go.Figure()
                    
                    if mat_p > 0 and mat_l > 0:
                        fig_nest.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode='lines', line=dict(color='#ef4444', width=2), hoverinfo='skip'))
                        
                    for idx, poly in enumerate(log['nested_polys']):
                        xs = [p[0] for p in poly] + [poly[0][0]]
                        ys = [p[1] for p in poly] + [poly[0][1]]
                        fig_nest.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#eab308', width=1.5), fillcolor='rgba(234, 179, 8, 0.4)', name=f'Pcs {idx+1}'))
                        
                    fig_nest.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=10, b=10, l=10, r=10), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                    
                    st.plotly_chart(fig_nest, use_container_width=True, key=f"full_layout_{i}")

# ==========================================
# FOOTER & AUTO REFRESH
# ==========================================
st.sidebar.markdown("---")
is_auto_refresh = st.sidebar.toggle("🔄 Auto-Refresh", value=True, help="Disable this to analyze graphs without reloading.")

if is_auto_refresh:
    st_autorefresh(interval=2000, limit=None, key="auto_refresh_dasbor")