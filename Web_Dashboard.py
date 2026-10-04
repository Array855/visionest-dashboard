import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import os
import random
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="VISIONEST Dashboard", page_icon="⚙️", layout="wide")

# --- SISTEM DATABASE LOCAL UNTUK WEB ---
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
        "device_id": "MENUNGGU DATA...",
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
        "nested_polys": [],    # Variabel penampung layout
        "duration_sec": 0.0,
        "timestamp": "-",
        "waste_pct": 100.0,
        "logs": db_data.get("logs", []),             
        "last_log_ts": db_data.get("last_log_ts", None)     
    }

shared_data = get_shared_data()

@st.cache_resource
def start_mqtt():
    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe("advantech/wise/visionest/telemetry")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            for key, value in payload.items():
                if key not in ["logs", "last_log_ts"]:
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
                        "nested_polys": payload.get("nested_polys", []) # Simpan full layout ke log
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

start_mqtt()
data = shared_data

# ==========================================
# HEADER LOGO & TITLE
# ==========================================
col_title, col_logo1, col_logo2 = st.columns([6, 1, 1])
with col_title:
    st.title("🌐 VISIONEST - Production Enterprise Dashboard")
with col_logo1:
    if os.path.exists("pens_logo.png"): st.image("pens_logo.png", width=70)
with col_logo2:
    if os.path.exists("advantech_logo.png"): st.image("advantech_logo.png", width=120)
st.markdown("---")

# ==========================================
# METRICS & STATUS
# ==========================================
col1, col2, col3 = st.columns(3)
with col1: st.info(f"**🖥️ Device ID:**\n### {data['device_id']}")
with col2: st.info(f"**👷 Operator Aktif:**\n### {data['operator']} | {data['shift']}")
with col3:
    stat = data['status']
    if stat in ["MACHINE_RUNNING", "CUTTING_IN_PROGRESS", "CYCLE_COMPLETE"]:
        st.success(f"**🔄 Status:**\n### {stat}")
    elif stat == "EMERGENCY_STOP_TRIGGERED":
        st.error(f"**🚨 Status:**\n### {stat}")
    else:
        st.warning(f"**⏸ Status:**\n### {stat}")

st.markdown("### 📊 Live Telemetry")
m1, m2, m3, m4 = st.columns(4)
m1.metric("🎯 Target Qty", f"{data['target_qty']} Pcs")
m2.metric("⏱ Duration", f"{data['duration_sec']} Sec")
m3.metric("📏 Material (P x L)", f"{data['mat_p']} x {data['mat_l']} mm") 
m4.metric("📈 Progress", f"{data['progress_pct']} %")
st.progress(max(0.0, min(1.0, data['progress_pct'] / 100.0)))

if data["shape_poly"] and data["status"] != "SYSTEM_READY":
    col_v1, col_v2, col_v3 = st.columns([1, 2, 1]) 
    with col_v2:
        st.markdown(f"<p style='text-align: center; color: #94a3b8;'><b>Preview Benda Kerja:</b> {data['shape_name']}</p>", unsafe_allow_html=True)
        xs = [p[0] for p in data["shape_poly"]] + [data["shape_poly"][0][0]]
        ys = [p[1] for p in data["shape_poly"]] + [data["shape_poly"][0][1]]
        fig_shape = go.Figure()
        fig_shape.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#0ea5e9', width=3), fillcolor='rgba(14, 165, 233, 0.3)'))
        fig_shape.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=10, b=10, l=10, r=10), height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        st.plotly_chart(fig_shape, use_container_width=True)

st.markdown("---")

# ==========================================
# EXECUTIVE ANALYTICS
# ==========================================
st.markdown("### 📈 Executive Analytics")
if data["logs"]:
    df = pd.DataFrame(data["logs"])
    df = df.sort_values(by="waktu") 
    col_kiri, col_tengah, col_kanan = st.columns([1, 2, 1])
    with col_tengah:
        st.markdown("**1. Material Usage Efficiency (Historical Trend)**")
        df['Terpakai'] = 100.0 - df['waste']
        df['Waste'] = df['waste']
        fig_group = go.Figure(data=[
            go.Bar(name='Terpakai (Efektif)', x=df['waktu'], y=df['Terpakai'], marker_color='#10b981'),
            go.Bar(name='Sisa Kain (Waste)', x=df['waktu'], y=df['Waste'], marker_color='#ef4444')
        ])
        fig_group.update_layout(barmode='group', bargroupgap=0.1, margin=dict(t=20, b=20, l=20, r=20), height=320, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_group, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True) 

        st.markdown("**2. Production History (Pieces per Cycle)**")
        fig_bar = px.bar(df, x="waktu", y="pcs", color="shift", text="pcs", color_discrete_sequence=px.colors.qualitative.Set2)
        fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=320, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("Belum ada data produksi yang selesai (CYCLE_COMPLETE) untuk menampilkan grafik analitik.")

st.markdown("---")

# ==========================================
# LOGGER BAWAH (DENGAN INLINE TOGGLE)
# ==========================================
col_log_1, col_log_2 = st.columns([8, 2])
with col_log_1:
    st.markdown("### 📝 Daily Production Logs Data")
with col_log_2:
    if st.button("🗑 Reset Data Web", use_container_width=True):
        data["logs"] = []
        data["last_log_ts"] = None
        save_db([], None)
        st.rerun()

if not data["logs"]:
    st.info("Belum ada riwayat pemotongan. Silakan jalankan mesin terlebih dahulu.")
else:
    for i, log in enumerate(data["logs"]):
        with st.expander(f"✅ Pemotongan Selesai - {log['waktu']} (Oleh: {log['operator']} | {log['shift']})", expanded=(i==0)):
            
            c_text, c_img = st.columns([6, 4])
            show_layout = False
            
            with c_text:
                st.markdown(f"""
                - **Total Pola (Qty):** {log['pcs']} Pcs
                - **Dimensi Material:** `{log['ukuran']} mm`
                - **Bentuk Pola:** `{log.get('bentuk', '-')}`
                - **Kain Terbuang (Scrap):** `{log['waste']:.1f}%`
                """)
                st.write("")
                
                # SAKLAR UNTUK MEMUNCULKAN DIGITAL TWIN FULL LAYOUT
                if log.get('nested_polys'):
                    show_layout = st.toggle("👁️ Tampilkan Full Layout (Digital Twin)", key=f"tgl_modal_{i}")
            
            with c_img:
                poly_data = log.get('shape_poly', [])
                if poly_data:
                    xs = [p[0] for p in poly_data] + [poly_data[0][0]]
                    ys = [p[1] for p in poly_data] + [poly_data[0][1]]
                    fig_hist = go.Figure()
                    fig_hist.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#10b981', width=3), fillcolor='rgba(16, 185, 129, 0.3)'))
                    fig_hist.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=0, b=0, l=0, r=0), height=120, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                    st.plotly_chart(fig_hist, use_container_width=True, key=f"hist_{i}")

            # RENDER FULL LAYOUT JIKA SAKLAR DINYALAKAN (INLINE, NO GLITCH)
            if log.get('nested_polys') and show_layout:
                st.markdown("---")
                st.markdown(f"<p style='text-align: center; color: #eab308;'><b>Simulasi Full Layout (Material: {log['ukuran']})</b></p>", unsafe_allow_html=True)
                
                mat_p, mat_l = 0, 0
                try:
                    parts = log['ukuran'].split('x')
                    mat_p = float(parts[0].replace('mm', '').strip())
                    mat_l = float(parts[1].replace('mm', '').strip())
                except: pass
                    
                fig_nest = go.Figure()
                
                # Batas Material Merah
                if mat_p > 0 and mat_l > 0:
                    fig_nest.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode='lines', line=dict(color='#ef4444', width=2), hoverinfo='skip'))
                    
                # Susunan Pola Kuning
                for idx, poly in enumerate(log['nested_polys']):
                    xs = [p[0] for p in poly] + [poly[0][0]]
                    ys = [p[1] for p in poly] + [poly[0][1]]
                    fig_nest.add_trace(go.Scatter(x=xs, y=ys, fill='toself', mode='lines', line=dict(color='#eab308', width=1.5), fillcolor='rgba(234, 179, 8, 0.4)', name=f'Pcs {idx+1}'))
                    
                fig_nest.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=10, b=10, l=10, r=10), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                
                # Ditengahkan
                c_kiri, c_tengah, c_kanan = st.columns([1, 4, 1])
                with c_tengah:
                    st.plotly_chart(fig_nest, use_container_width=True, key=f"full_layout_{i}")

# ==========================================
# FOOTER & SAKLAR AUTO-REFRESH
# ==========================================
st.markdown("---")
col_foot1, col_foot2 = st.columns([8, 2])
with col_foot1:
    st.caption(f"⏱ Terakhir update: **{data['timestamp']}**")
with col_foot2:
    is_auto_refresh = st.toggle("🔄 Live Auto-Refresh", value=True, help="Matikan ini agar web tidak merefresh otomatis saat menganalisa grafik.")

if is_auto_refresh:
    time.sleep(2)
    st.rerun()