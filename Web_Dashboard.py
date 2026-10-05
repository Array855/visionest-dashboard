"""VISIONEST Dashboard: monitoring mesin potong kain real-time lewat MQTT."""

import html
import json
import logging
import math
import os
import random
import threading
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

log = logging.getLogger("visionest")

# ───────────────────────── Konfigurasi ─────────────────────────
BROKER, PORT = "broker.hivemq.com", 8884
TOPIC_TELEMETRY = "advantech/wise/visionest/telemetry"
TOPIC_PING = "advantech/wise/visionest/ping"

DB_FILE = "visionest_logs.json"
LOGO = "visionest_logo.png"
LOGO_REMOTE = "https://raw.githubusercontent.com/alzak123/Textile-Nest/main/app/visionest_logo.png"
LOGO_PARTNER = "logo_pens_kanan.png"
LOGO_PARTNER_REMOTE = "https://raw.githubusercontent.com/alzak123/Textile-Nest/main/app/logo_pens_kanan.png"

WIB = timezone(timedelta(hours=7), "WIB")
STALE_AFTER_S = 60  
MAX_LOGS, MAX_PINGS, PAGE_SIZE = 500, 20, 25
DEMO = os.getenv("VISIONEST_DEMO") == "1"

# ---> WARNA THEME CLEAN ANALYTICS (LIGHT MODE) <---
INK = "#1e293b"         # Teks Utama (Dark Slate pekat)
MUTED = "#64748b"       # Teks Redup (Slate abu-abu)
GOLD = "#f59e0b"        # Orange Accent
ACCENT = "#3b82f6"      # Bright Blue (Warna utama khas dashboard SaaS)
PURPLE = "#8b5cf6"      # Vibrant Purple (Untuk grafik Donut/Area)
OK = "#0ea5e9"          # Sky Blue / Cyan
WARN = "#f97316"        # Bright Orange
BAD = "#ef4444"         # Merah
GRID = "#f1f5f9"        # Garis Grid sangat halus

st.set_page_config(
    page_title="VISIONEST Dashboard",
    page_icon=LOGO if os.path.exists(LOGO) else "✂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────── CSS CLEAN ANALYTICS ─────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
:root {
    --bg: #f8fafc;         
    --card: #ffffff;       
    --ink: #1e293b;        
    --muted: #64748b;      
    --line: #e2e8f0;       
    --gold: #f59e0b;       
    --navy: #0f172a;       
    --accent: #3b82f6;     
    --ok: #0ea5e9;         
}

html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; }

/* PAKSA BACKGROUND LIGHT MODE */
.stApp, [data-testid="stAppViewContainer"], .main {
    background-color: var(--bg) !important;
    color: var(--ink) !important;
}

/* Membasmi elemen bawaan Streamlit */
header[data-testid="stHeader"] { background: transparent !important; }
footer { display: none !important; }
.viewerBadge_container__1QSob, .viewerBadge_link__1S137, .viewerBadge_text__1JaDK, .stDeployButton { display: none !important; }
a[href^="https://streamlit.io/cloud"] { display: none !important; }
#Manage\\ app { display: none !important; }

/* Padding Layout */
.block-container, [data-testid="stMainBlockContainer"] {
    padding: 1.5rem 1.5rem 2rem !important;
    max-width: 100% !important;
}

/* Sidebar Putih Bersih */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid var(--line) !important;
    min-width: 250px !important;
    max-width: 250px !important;
}
[data-testid="stSidebarResizer"] { display: none !important; }
[data-testid="stSidebarCollapseButton"], button[kind="headerNoPadding"] { display: none !important; }

/* Navigasi Sidebar - Pill Shape Halus */
[data-testid="stSidebar"] div[role="radiogroup"] { gap: 8px; }
[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 12px 16px;
    border-radius: 8px;
    width: 100%;
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none; }
[data-testid="stSidebar"] div[role="radiogroup"] label p {
    font-size: 15px !important;
    font-weight: 600 !important;
    color: var(--muted) !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: #f1f5f9 !important; 
    border-radius: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
    color: var(--accent) !important; 
    font-weight: 800 !important;
}

/* Kartu Bersih & Soft Shadow */
.card, [class*="st-key-card"] {
    background: var(--card) !important;
    border: 1px solid #f1f5f9 !important;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03), 0 2px 4px -1px rgba(0, 0, 0, 0.02); 
    height: 100%;
}
.card-title { font-size: 15px; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
.card-value { font-size: 34px; font-weight: 800; color: var(--ink); line-height: 1.15; }
.card-value.sm { font-size: 22px; }
.unit { font-size: 16px; font-weight: 600; color: var(--muted); margin-left: 6px; }
.card-sub { font-size: 13px; font-weight: 500; color: var(--muted); margin-top: 6px; }

/* Grid & Layouts */
.row { display: flex; justify-content: space-between; align-items: baseline; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }
.stack { display: grid; gap: 16px; }

/* Badges & Bars */
.pill { display: inline-block; padding: 4px 12px; border-radius: 99px; font-size: 12px; font-weight: 700; background: #eff6ff; color: var(--accent); }
.bar { height: 6px; border-radius: 99px; background: #f1f5f9; overflow: hidden; margin-top: 12px; }
.bar > span { display: block; height: 100%; border-radius: 99px; background: var(--ok); transition: width 0.5s ease; }
.empty { display: flex; align-items: center; justify-content: center; min-height: 120px; color: var(--muted); font-weight: 600; }

/* Header & Text Globals */
.brand { font-size: 28px; font-weight: 800; color: var(--ink); }
.brand .gold { color: var(--accent); font-weight:400; } 
.status { text-align: center; font-size: 14px; font-weight: 600; color: var(--muted); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; background: var(--muted); }
.sep { display: inline-block; width: 1px; height: 14px; background: var(--line); margin: 0 16px; vertical-align: middle; }

[data-testid="stWidgetLabel"] p, [data-testid="stMetricValue"], [data-testid="stMetricLabel"], .stMarkdown p, h1, h2, h3, h4, h5, h6 {
    color: var(--ink) !important;
}

/* Warna input box */
.stTextInput input {
    background-color: #ffffff !important;
    color: var(--ink) !important;
    border: 1px solid var(--line) !important;
    font-weight: 500 !important;
    border-radius: 6px;
}

/* Chat */
.msg { font-size: 14px; font-weight: 500; margin: 6px 0; }
.msg small { color: var(--muted); font-weight: 400; }
.msg.web { text-align: right; color: var(--accent); }
.msg.gui { text-align: left; color: var(--ok); }

/* Expander/Logs */
[data-testid="stExpander"] details { background: var(--card); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }
hr { border-color: var(--line) !important; margin: 12px 0 !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ───────────────────────── Helper ─────────────────────────
def esc(value):
    return html.escape(str(value))

def num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def fmt(value, digits=1):
    v = num(value)
    if v is None:
        return "–"
    if digits == 0:
        return f"{v:.0f}"
    return f"{v:.{digits}f}".rstrip("0").rstrip(".")

def outline(poly):
    pts = [(float(p[0]), float(p[1])) for p in poly]
    return [p[0] for p in pts] + [pts[0][0]], [p[1] for p in pts] + [pts[0][1]]

def plot_layout(**kw):
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK),
        margin=dict(t=4, b=4, l=4, r=4),
    )
    base.update(kw)
    return base

PLOT_CONFIG = {"displayModeBar": False}


# ───────────────────────── Penyimpanan log ─────────────────────────
def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        return db.get("logs", []), db.get("last_log_ts")
    except (OSError, ValueError):
        return [], None

def save_db(logs, last_ts):
    tmp = DB_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"logs": logs, "last_log_ts": last_ts}, f)
        os.replace(tmp, DB_FILE)
    except OSError:
        log.exception("Gagal menyimpan log")


# ───────────────────────── State bersama ─────────────────────────
class Store:
    def __init__(self):
        self._lock = threading.Lock()
        self.logs, self.last_log_ts = load_db()
        self.pings = []
        self.last_msg_at = None
        self.state = {
            "device_id": "No connection", "operator": "Not set", "shift": "-", "status": "OFFLINE",
            "target_qty": 0, "progress_pct": 0, "pos_x": 0.0, "pos_y": 0.0,
            "mat_p": 0.0, "mat_l": 0.0, "shape_name": "-", "shape_poly": [], "nested_polys": [],
            "duration_sec": None, "waste_pct": None, "timestamp": "",
        }
        if DEMO:
            self._seed_demo()

    def snapshot(self):
        with self._lock:
            return dict(self.state)

    def logs_copy(self):
        with self._lock:
            return list(self.logs)

    def pings_copy(self):
        with self._lock:
            return list(self.pings)

    def seconds_since_data(self):
        with self._lock:
            return None if self.last_msg_at is None else time.time() - self.last_msg_at

    def add_ping(self, ping):
        with self._lock:
            self.pings.append(ping)
            del self.pings[:-MAX_PINGS]

    def reset_logs(self):
        with self._lock:
            self.logs.clear()
            self.last_log_ts = None
            save_db([], None)

    def update(self, payload):
        with self._lock:
            for key, value in payload.items():
                if key not in self.state:
                    continue
                if key in ("shape_poly", "nested_polys") and not value:
                    continue
                self.state[key] = value
            self.last_msg_at = time.time()

            if payload.get("status") != "CYCLE_COMPLETE":
                return
            self.state["progress_pct"] = 100
            ts = payload.get("timestamp")
            if not ts or ts == self.last_log_ts:
                return
            self.last_log_ts = ts
            s = self.state
            self.logs.insert(0, {
                "waktu": ts, "operator": s["operator"], "shift": s["shift"], "pcs": s["target_qty"],
                "ukuran": f"{fmt(s['mat_p'])} x {fmt(s['mat_l'])}", "bentuk": s["shape_name"],
                "waste": num(s["waste_pct"]), "shape_poly": s["shape_poly"], "nested_polys": s["nested_polys"],
            })
            del self.logs[MAX_LOGS:]
            save_db(self.logs, ts)

    def _seed_demo(self):
        rects = [[[x, y], [x + 170, y], [x + 170, y + 170], [x, y + 170]] for y in (20, 210) for x in (20, 210, 400)]
        self.state.update(
            device_id="VISIONEST-01", operator="Rizky", shift="Shift 1", status="CUTTING", target_qty=6,
            progress_pct=62, pos_x=210.0, pos_y=-95.0, mat_p=600.0, mat_l=400.0, shape_name="Square",
            shape_poly=rects[0], nested_polys=rects, duration_sec=84.3, waste_pct=18.4,
        )
        self.last_msg_at = time.time()
        self.pings = [{"sender": "GUI", "message": "Cutting started", "timestamp": "09:12:03"}]
        if not self.logs:
            for i in range(8):
                self.logs.insert(0, {
                    "waktu": f"{9 + i:02d}:{i * 7 % 60:02d}:00", "operator": "Rizky" if i < 4 else "Dewi",
                    "shift": "Shift 1" if i < 4 else "Shift 2", "pcs": 4 + i % 5, "ukuran": "600 x 400",
                    "bentuk": "Square", "waste": 14 + (i * 5) % 13, "shape_poly": rects[0], "nested_polys": rects,
                })


@st.cache_resource
def get_store():
    return Store()

@st.cache_resource
def get_mqtt():
    store = get_store()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe([(TOPIC_TELEMETRY, 0), (TOPIC_PING, 1)])

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                return
            if msg.topic == TOPIC_PING:
                if payload.get("sender") == "GUI":
                    store.add_ping(payload)
            else:
                store.update(payload)
        except Exception:
            log.exception("Gagal memproses pesan MQTT")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"VISIONEST_WEB_{random.randint(10000, 99999)}",
        transport="websockets",
    )
    client.on_connect = on_connect
    client.on_message = on_message
    if not DEMO:
        client.tls_set()
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.connect_async(BROKER, PORT, keepalive=60)
        client.loop_start()
    return client


store = get_store()
client = get_mqtt()

def link_status():
    if DEMO:
        return "Demo mode", ACCENT
    if not client.is_connected():
        return "Broker offline", BAD
    age = store.seconds_since_data()
    if age is not None and age < STALE_AFTER_S:
        return "Machine online", ACCENT
    return "Waiting for machine", MUTED

def send_ping(text):
    ping = {"sender": "WEB", "message": text, "timestamp": datetime.now(WIB).strftime("%H:%M:%S")}
    if not DEMO:
        if not client.is_connected():
            st.toast("Broker offline, message not sent.", icon="⚠️")
            return
        client.publish(TOPIC_PING, json.dumps(ping), qos=1)
    store.add_ping(ping)


# ───────────────────────── Sidebar ─────────────────────────
HOME, SUMMARY, ANALYSIS, LOGS = "Dashboard", "Stats", "Reports", "Log Files"

with st.sidebar:
    c_logo, c_name = st.columns([3, 7], vertical_alignment="center")
    c_logo.image(LOGO if os.path.exists(LOGO) else LOGO_REMOTE, width=48)
    c_name.markdown(
        "<div style='font-size:18px;font-weight:800;color:#1e293b;line-height:1.2'>VISIONEST</div>"
        "<div style='font-size:11px;font-weight:700;color:#3b82f6;text-transform:uppercase;'>by DEMIURGEN</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:11px; font-weight:700; color:#94a3b8; padding-left:15px; margin-bottom:5px; text-transform:uppercase; letter-spacing:0.5px;'>Directories</p>", unsafe_allow_html=True)
    page = st.radio("Menu", [HOME, SUMMARY, ANALYSIS, LOGS], label_visibility="collapsed")
    st.divider()
    live = st.toggle("Live refresh", value=True)

REFRESH = 2 if live else None


# ───────────────────────── Komponen HTML ─────────────────────────
def card(title, value, unit="", sub="", val_color="var(--ink)"):
    unit_html = f'<span class="unit">{esc(unit)}</span>' if unit else ""
    sub_html = f'<div class="card-sub">{esc(sub)}</div>' if sub else ""
    return (f'<div class="card" style="height:100%;"><div class="card-title">{esc(title)}</div>'
            f'<div class="card-value" style="color:{val_color};">{esc(value)}{unit_html}</div>{sub_html}</div>')

def machine_cards(s):
    pct = max(0.0, min(100.0, num(s["progress_pct"], 0.0)))
    status = str(s["status"]).replace("_", " ").title()
    machine = (
        '<div class="card"><div class="card-title">Machine Info</div>'
        f'<div class="card-value sm">{esc(s["device_id"])}</div>'
        f'<div class="card-sub">Operator: {esc(s["operator"])}</div>'
        f'<div class="card-sub">Shift: {esc(s["shift"])}</div>'
        f'<div style="margin-top:12px"><span class="pill">{esc(status)}</span></div></div>'
    )
    progress = (
        '<div class="card"><div class="card-title">Cutting Progress</div>'
        f'<div class="card-value" style="color:var(--ink)">{pct:.0f}<span class="unit">%</span></div>'
        f'<div class="bar"><span style="width:{pct:.0f}%"></span></div></div>'
    )
    
    dim_text = "0.0 × 0.0 mm"
    shape_nm = str(s.get("shape_name", "-"))
    nested = s.get("nested_polys", [])
    
    if nested and len(nested) > 0:
        poly_mm = nested[0] 
        xs = [float(p[0]) for p in poly_mm]
        ys = [float(p[1]) for p in poly_mm]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        
        if "lingkaran" in shape_nm.lower():
            diameter = max(w, h)
            dim_text = f"Ø {diameter:.1f} mm"
        else:
            panjang = max(w, h)
            lebar = min(w, h)
            dim_text = f"{panjang:.1f} × {lebar:.1f} mm"
    elif shape_nm != "-":
        dim_text = "Calculating..."
        
    shape_class = "Undefined" if shape_nm == "-" else shape_nm
        
    pattern_size = (
        '<div class="card"><div class="card-title">Pattern Details</div>'
        f'<div class="card-value sm" style="color:var(--ink)">{esc(dim_text)}</div>'
        f'<div class="card-sub">Class: {esc(shape_class)}</div></div>'
    )
    
    return f'<div class="stack">{machine}{progress}{pattern_size}</div>'

def metric_grid(s):
    target = int(num(s.get("target_qty"), 0))
    pct = float(num(s.get("progress_pct"), 0.0))
    
    if pct >= 100 or str(s.get("status")) == "CYCLE_COMPLETE":
        curr = target
    elif pct <= 0:
        curr = 0
    else:
        curr = math.ceil((pct / 100.0) * target)
        if curr == 0 and target > 0:
            curr = 1
            
    qty_text = f"{curr} / {target}" if target > 0 else "0"

    items = [
        card("Target Output", qty_text, "pcs", "Current vs Target", val_color=ACCENT),
        card("Cycle Duration", fmt(s["duration_sec"]), "s", "Execution time", val_color=INK),
        card("Material Waste", fmt(s["waste_pct"]), "%", "Scrap percentage", val_color=BAD),
        card("Shape Class", s["shape_name"], "", "Detected pattern", val_color=INK),
    ]
    return f'<div class="grid">{"".join(items)}</div>'

def nest_figure(s, mat_p, mat_l):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode="lines",
                             line=dict(color="#cbd5e1", width=2), hoverinfo="skip"))
    for i, poly in enumerate(s["nested_polys"], 1):
        xs, ys = outline(poly)
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", mode="lines", name=f"Piece {i}", hoverinfo="name",
                                 line=dict(color=ACCENT, width=2), fillcolor="rgba(59, 130, 246, 0.1)"))
        if len(xs) > 1:
            avg_x = sum(xs[:-1]) / len(xs[:-1])
            avg_y = sum(ys[:-1]) / len(ys[:-1])
            fig.add_annotation(
                x=avg_x, y=avg_y, text=f"<b>{i}</b>", showarrow=False, font=dict(color=INK, size=14)
            )
    fig.add_trace(go.Scatter(x=[num(s["pos_x"], 0.0)], y=[abs(num(s["pos_y"], 0.0))], mode="markers",
                             marker=dict(color=BAD, size=10), name="Laser tool"))
    fig.update_layout(**plot_layout(
        height=320, showlegend=False, uirevision="nest",
        xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
    ))
    return fig

def layout_card(s):
    mat_p, mat_l = num(s["mat_p"], 0.0), num(s["mat_l"], 0.0)
    with st.container(key="card_layout"):
        st.markdown(
            '<div class="row"><span class="card-title">Live Layout View</span>'
            f'<span class="card-sub" style="color:var(--muted); border:1px solid #e2e8f0; padding:2px 8px; border-radius:6px; font-size:12px;">{fmt(mat_p)} × {fmt(mat_l)} mm</span></div>',
            unsafe_allow_html=True,
        )
        if mat_p > 0 and mat_l > 0 and s["nested_polys"]:
            try:
                st.plotly_chart(nest_figure(s, mat_p, mat_l), key="nest_chart", config=PLOT_CONFIG)
            except (TypeError, ValueError, IndexError):
                st.markdown('<div class="empty">Layout data is malformed.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty" style="min-height:320px">No pattern loaded</div>', unsafe_allow_html=True)


# ───────────────────────── Fragment ─────────────────────────
@st.fragment(run_every=1 if live else None)
def header():
    label, color = link_status()
    now = datetime.now(WIB).strftime("%d %B %Y, %H:%M:%S")
    # ----> FIX: LOGO PARTNER KANAN DIPERBESAR BIAR SEIMBANG SAMA JUDUL <----
    c_brand, c_status, c_logo = st.columns([3, 4.5, 3], vertical_alignment="center")
    c_brand.markdown('<div class="brand">VISIONEST <span class="gold" style="font-weight:400;">Dashboard</span></div>', unsafe_allow_html=True)
    c_status.markdown(
        f'<div class="status"><span class="dot" style="background:{color};"></span><span style="color:var(--muted); font-weight:500;">{esc(label)}</span>'
        f'<span class="sep"></span><span style="color:var(--muted); font-weight:500;">{now}</span></div>',
        unsafe_allow_html=True,
    )
    if os.path.exists(LOGO_PARTNER):
        c_logo.image(LOGO_PARTNER, width=280) # Logo diperbesar ke 280px
    else:
        c_logo.image(LOGO_PARTNER_REMOTE, width=280)

@st.fragment(run_every=REFRESH)
def live_panel():
    s = store.snapshot()
    col_layout, col_info = st.columns([7, 3])
    with col_layout:
        layout_card(s)
    col_info.markdown(machine_cards(s), unsafe_allow_html=True)
    st.markdown(metric_grid(s), unsafe_allow_html=True)

@st.fragment(run_every=REFRESH)
def chat_messages():
    pings = store.pings_copy()
    with st.container(height=160, border=False):
        if not pings:
            st.markdown('<div class="empty" style="min-height:100px">No messages yet.</div>', unsafe_allow_html=True)
        for p in reversed(pings): 
            who = "web" if p.get("sender") == "WEB" else "gui"
            st.markdown(
                f'<div class="msg {who}">[{who.upper()}] {esc(p.get("message", ""))} '
                f'<small>({esc(p.get("timestamp", ""))})</small></div>',
                unsafe_allow_html=True,
            )


# ───────────────────────── Halaman ─────────────────────────
def chat_card():
    with st.container(key="card_chat"):
        st.markdown('<div class="card-title">Communication Log</div>', unsafe_allow_html=True)
        chat_messages()
        with st.form("ping_form", clear_on_submit=True, border=False): 
            c_in, c_btn = st.columns([8, 1], vertical_alignment="bottom")
            text = c_in.text_input("Message", placeholder="Type a message to GUI...",
                                   label_visibility="collapsed")
            sent = c_btn.form_submit_button("Send", type="primary", use_container_width=True)
        if sent and text.strip():
            send_ping(text.strip())

def style_chart(fig):
    fig.update_layout(**plot_layout(
        height=300, margin=dict(t=30, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=INK)),
    ))
    fig.update_xaxes(type="category", showgrid=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, tickfont=dict(color=MUTED))
    return fig


# ─── HALAMAN STATS (YANG DI-UPGRADE JADI SUPER INFORMATIF) ───
def page_summary():
    logs = store.logs_copy()
    
    if not logs:
        st.markdown('<div class="card-title" style="font-size:22px; margin-bottom:15px; color:var(--ink);">Stats Overview</div>', unsafe_allow_html=True)
        st.markdown(card("Overview", "No data available", "", "Data will appear once production logs are recorded."), unsafe_allow_html=True)
        return

    # Kalkulasi Metrik Utama
    total_cycles = len(logs)
    total_pieces = sum(int(num(e.get("pcs"), 0)) for e in logs)
    
    wastes = [num(e.get("waste")) for e in logs if num(e.get("waste")) is not None]
    avg_waste = (sum(wastes) / len(wastes)) if wastes else 0.0
    avg_used = 100.0 - avg_waste
    
    avg_pcs_cycle = total_pieces / total_cycles if total_cycles > 0 else 0

    op_counts = {}
    shift_counts = {}
    shape_counts = {}
    for e in logs:
        op = e.get("operator", "Unknown")
        sh = e.get("shift", "Shift 1")
        shp = e.get("bentuk", "Undefined")
        op_counts[op] = op_counts.get(op, 0) + int(num(e.get("pcs"), 0))
        shift_counts[sh] = shift_counts.get(sh, 0) + 1
        shape_counts[shp] = shape_counts.get(shp, 0) + 1
        
    top_operator = max(op_counts, key=op_counts.get) if op_counts else "-"
    top_operator_val = op_counts.get(top_operator, 0)

    c_head1, c_head2 = st.columns([7, 3], vertical_alignment="center")
    c_head1.markdown('<div class="card-title" style="font-size:24px; margin-bottom:15px; color:var(--ink);">Stats Overview</div>', unsafe_allow_html=True)
    c_head2.markdown(f'<div style="text-align:right;"><span style="font-size:12px; font-weight:600; background:#f1f5f9; padding:6px 12px; border-radius:6px; color:var(--muted); border:1px solid #e2e8f0;">Data per: {datetime.now(WIB).strftime("%d %b %Y")}</span></div>', unsafe_allow_html=True)

    # 1. KARTU BARIS ATAS (DIPECAH JADI 4 BIAR INFORMATIF MAKSIMAL)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(card("Avg Utilization", f"{avg_used:.1f}", "%", f"Overall material efficiency", val_color=INK), unsafe_allow_html=True)
    with c2:
        st.markdown(card("Total Pieces", f"{total_pieces}", "pcs", f"From {total_cycles} complete cycles", val_color=INK), unsafe_allow_html=True)
    with c3:
        st.markdown(card("Avg Pcs / Cycle", f"{avg_pcs_cycle:.1f}", "pcs", f"Machine productivity rate", val_color=INK), unsafe_allow_html=True)
    with c4:
        st.markdown(card("Top Operator", top_operator, "", f"Highest yield ({top_operator_val} pcs)", val_color=ACCENT), unsafe_allow_html=True)

    st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)

    # 2. BARIS KEDUA: TREN & SHIFT SHARE
    c_a, c_d = st.columns([7, 3])
    
    with c_a:
        st.markdown('<div class="card" style="height:100%;"><div class="row"><span class="card-title" style="font-size:18px; color:var(--ink);">Production Trend</span><span style="font-size:12px; color:var(--muted); border:1px solid #e2e8f0; padding:2px 8px; border-radius:6px;">Last 7 Cycles</span></div>', unsafe_allow_html=True)
        df_trend = pd.DataFrame(logs[:7][::-1])
        if not df_trend.empty:
            df_trend["waktu_short"] = df_trend["waktu"].str.split(" ").str[-1] 
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=df_trend["waktu_short"], y=df_trend["pcs"],
                fill='tozeroy', mode='lines+markers', name='Pieces Cut',
                line=dict(color=OK, width=3, shape='spline'),
                marker=dict(size=6, color=OK),
                fillcolor='rgba(14, 165, 233, 0.15)' 
            ))
            fig_trend.update_layout(**plot_layout(height=260, margin=dict(t=10, b=30, l=10, r=10)))
            fig_trend.update_xaxes(showgrid=False, tickfont=dict(color=MUTED))
            fig_trend.update_yaxes(showgrid=True, gridcolor=GRID, tickfont=dict(color=MUTED))
            st.plotly_chart(fig_trend, key="summary_trend", config=PLOT_CONFIG, use_container_width=True)
        else:
            st.markdown('<div class="empty">Not enough data.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c_d:
        st.markdown('<div class="card" style="height:100%;"><div class="row"><span class="card-title" style="font-size:18px; color:var(--ink);">Shift Share</span></div>', unsafe_allow_html=True)
        fig_shift = px.pie(
            names=list(shift_counts.keys()), 
            values=list(shift_counts.values()), 
            hole=0.65,
            color_discrete_sequence=[ACCENT, OK, PURPLE]
        )
        fig_shift.update_layout(**plot_layout(height=260, margin=dict(t=10, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1)))
        fig_shift.update_traces(textinfo='none') 
        fig_shift.add_annotation(text=f"Total<br><span style='font-size:24px; font-weight:bold; color:#1e293b;'>{total_cycles}</span><br><span style='font-size:12px; color:#64748b;'>Cycles</span>", x=0.5, y=0.5, font_size=14, font_color=MUTED, showarrow=False)
        st.plotly_chart(fig_shift, key="summary_shift_pie", config=PLOT_CONFIG, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)

    # 3. BARIS KETIGA: OPERATOR PERFORMANCE & SHAPE DISTRIBUTION
    c_op, c_sh = st.columns(2)
    with c_op:
        st.markdown('<div class="card" style="height:100%;"><div class="row"><span class="card-title" style="font-size:18px; color:var(--ink);">Operator Performance</span><span style="font-size:12px; color:var(--muted); border:1px solid #e2e8f0; padding:2px 8px; border-radius:6px;">Total Pieces</span></div>', unsafe_allow_html=True)
        df_op = pd.DataFrame(list(op_counts.items()), columns=['Operator', 'Pieces']).sort_values('Pieces', ascending=True)
        fig_op = px.bar(df_op, x='Pieces', y='Operator', orientation='h', text='Pieces', color_discrete_sequence=[ACCENT])
        fig_op.update_layout(**plot_layout(height=240, margin=dict(t=20, b=10, l=10, r=10)))
        fig_op.update_traces(textposition='outside', cliponaxis=False)
        fig_op.update_xaxes(showgrid=True, gridcolor=GRID, title="")
        fig_op.update_yaxes(title="")
        st.plotly_chart(fig_op, key="op_perf_bar", config=PLOT_CONFIG, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with c_sh:
        st.markdown('<div class="card" style="height:100%;"><div class="row"><span class="card-title" style="font-size:18px; color:var(--ink);">Shape Class Breakdown</span><span style="font-size:12px; color:var(--muted); border:1px solid #e2e8f0; padding:2px 8px; border-radius:6px;">Frequency</span></div>', unsafe_allow_html=True)
        df_sh = pd.DataFrame(list(shape_counts.items()), columns=['Shape', 'Count'])
        fig_sh = px.pie(df_sh, names='Shape', values='Count', hole=0.4, color_discrete_sequence=[PURPLE, OK, ACCENT, GOLD])
        fig_sh.update_layout(**plot_layout(height=240, margin=dict(t=20, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1)))
        fig_sh.update_traces(textinfo='percent', textposition='inside')
        st.plotly_chart(fig_sh, key="shape_dist_pie", config=PLOT_CONFIG, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


def page_analysis():
    logs = store.logs_copy()
    if not logs:
        st.markdown(card("Reports", "No data yet", "", "Charts appear after the first completed cut."),
                    unsafe_allow_html=True)
        return

    df = pd.DataFrame(logs[:30][::-1]).reindex(columns=["waktu", "operator", "shift", "pcs", "waste"]) 
    df["waste"] = pd.to_numeric(df["waste"], errors="coerce")
    df["pcs"] = pd.to_numeric(df["pcs"], errors="coerce")
    df["shift"] = df["shift"].fillna("-")

    with st.container(key="card_usage"):
        st.markdown('<div class="card-title">Material Usage (Last 30)</div>', unsafe_allow_html=True)
        fig = go.Figure([
            go.Bar(name="Used", x=df["waktu"], y=100 - df["waste"], marker_color=OK),
            go.Bar(name="Waste", x=df["waktu"], y=df["waste"], marker_color=BAD),
        ])
        style_chart(fig).update_layout(barmode="group", bargroupgap=0.1)
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig, key="usage_chart", config=PLOT_CONFIG)

    with st.container(key="card_qty"):
        st.markdown('<div class="card-title">Output Volume (Last 30)</div>', unsafe_allow_html=True)
        fig = px.bar(df, x="waktu", y="pcs", color="shift", text="pcs",
                     color_discrete_sequence=[ACCENT, PURPLE, WARN])
        style_chart(fig).update_traces(cliponaxis=False)
        fig.update_layout(legend_title_text="")
        st.plotly_chart(fig, key="qty_chart", config=PLOT_CONFIG)


def page_logs():
    logs = store.logs_copy()
    c_title, c_btn = st.columns([8, 2], vertical_alignment="center")
    c_title.markdown(card("Log Files", f"{len(logs)} records", "", "Newest first"), unsafe_allow_html=True)
    with c_btn.popover("Reset data"):
        st.write("Delete all production logs? This can't be undone.")
        if st.button("Delete all logs", type="primary"):
            store.reset_logs()
            st.session_state.pop("log_limit", None)
            st.rerun()

    if not logs:
        st.markdown('<div class="empty">No history yet.</div>', unsafe_allow_html=True)
        return

    limit = st.session_state.setdefault("log_limit", PAGE_SIZE)
    for i, entry in enumerate(logs[:limit]):
        title = f'📄 {entry.get("waktu", "-")} | Op: {entry.get("operator", "-")} | {entry.get("pcs", 0)} pcs'
        with st.expander(title):
            c_text, c_img = st.columns([6, 4])
            c_text.markdown(
                f'<span style="color:var(--ink);">**Pieces:** {entry.get("pcs", 0)}</span>  \n'
                f'<span style="color:var(--ink);">**Material:** {entry.get("ukuran", "-")} mm</span>  \n'
                f'<span style="color:var(--ink);">**Shape:** {entry.get("bentuk", "-")}</span>  \n'
                f'<span style="color:var(--bad);">**Waste:** {fmt(entry.get("waste"))}%</span>',
                unsafe_allow_html=True
            )
            
            mat_p, mat_l = 0, 0
            try:
                parts = entry.get('ukuran', '').split('x')
                mat_p = float(parts[0].replace('mm', '').strip())
                mat_l = float(parts[1].replace('mm', '').strip())
            except: pass
                
            fig_nest = go.Figure()
            if mat_p > 0 and mat_l > 0:
                fig_nest.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode='lines', line=dict(color="#cbd5e1", width=2), hoverinfo='skip'))
                
            polys = entry.get("nested_polys") or []
            for idx, poly in enumerate(polys, 1):
                try:
                    xs, ys = outline(poly)
                    fig_nest.add_trace(go.Scatter(x=xs, y=ys, fill="toself", mode="lines", name=f"Pcs {idx}", hoverinfo="name", line=dict(color=ACCENT, width=1.5), fillcolor="rgba(59, 130, 246, 0.1)"))
                    if len(xs) > 1:
                        avg_x = sum(xs[:-1]) / len(xs[:-1])
                        avg_y = sum(ys[:-1]) / len(ys[:-1])
                        fig_nest.add_annotation(
                            x=avg_x, y=avg_y, text=f"<b>{idx}</b>", showarrow=False, font=dict(color=INK, size=12)
                        )
                except (TypeError, ValueError, IndexError):
                    continue
                    
            if polys:
                fig_nest.update_layout(**plot_layout(
                    height=180, showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
                    xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
                ))
                c_img.plotly_chart(fig_nest, key=f"full_layout_{i}", config=PLOT_CONFIG)

    if len(logs) > limit and st.button("Load older"):
        st.session_state.log_limit = limit + PAGE_SIZE
        st.rerun()


# ───────────────────────── Render ─────────────────────────
header()
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

if page == HOME:
    live_panel()
    chat_card()
elif page == SUMMARY:
    page_summary()
elif page == ANALYSIS:
    page_analysis()
else:
    page_logs()
