"""VISIONEST Dashboard: monitoring mesin potong kain real-time lewat MQTT."""

import html
import json
import logging
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

WIB = timezone(timedelta(hours=7), "WIB")  # WIB tidak pakai DST, offset tetap aman
STALE_AFTER_S = 60  # tanpa data lebih lama dari ini = mesin dianggap diam
MAX_LOGS, MAX_PINGS, PAGE_SIZE = 500, 20, 25
DEMO = os.getenv("VISIONEST_DEMO") == "1"  # preview tampilan tanpa mesin

INK, MUTED, GOLD = "#1b254b", "#64748b", "#d4af37"
ACCENT, OK, WARN, BAD, GRID = "#4318ff", "#05cd99", "#f59e0b", "#ff5b5b", "#e8edf9"

st.set_page_config(
    page_title="VISIONEST Dashboard",
    page_icon=LOGO if os.path.exists(LOGO) else "✂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────── CSS ─────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
:root{--bg:#f4f7fe;--card:#fff;--ink:#1b254b;--muted:#64748b;--line:#e3e9f6;
      --gold:#d4af37;--navy:#1e3a8a;--accent:#4318ff;--ok:#05cd99;}
.stApp{background:var(--bg);}
.stApp,.stApp :is(p,h1,h2,h3,h4,label,input,button,li,small){font-family:'Plus Jakarta Sans',sans-serif !important;}

/* Padding dipres biar compact dan muat 1 layar penuh */
.block-container,[data-testid="stMainBlockContainer"]{padding:1.5rem 1.5rem 1rem !important;max-width:100% !important;}

header[data-testid="stHeader"]{background:transparent;}  
footer{display:none !important;}

/* PEMBASMI WATERMARK POJOK KANAN BAWAH */
.viewerBadge_container__1QSob, .viewerBadge_link__1S137, .viewerBadge_text__1JaDK, .stDeployButton { display: none !important; }
a[href^="https://streamlit.io/cloud"] { display: none !important; }
#Manage\\ app { display: none !important; }

/* Sidebar */
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line);}
[data-testid="stSidebar"] div[role="radiogroup"]{gap:4px;}
[data-testid="stSidebar"] div[role="radiogroup"] label{padding:10px 14px;border-radius:10px;width:100%;}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child{display:none;}
[data-testid="stSidebar"] div[role="radiogroup"] label p{font-size:15px;font-weight:700;color:var(--navy);}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:#eaf0ff;}

/* Kartu */
.card,[class*="st-key-card"]{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;}
.card-title{font-size:13px;font-weight:700;color:var(--muted);margin-bottom:4px;}
.card-value{font-size:28px;font-weight:800;color:var(--ink);line-height:1.15;}
.card-value.sm{font-size:19px;}
.unit{font-size:14px;font-weight:700;color:var(--muted);margin-left:4px;}
.card-sub{font-size:12.5px;font-weight:600;color:var(--muted);margin-top:2px;}
.row{display:flex;justify-content:space-between;align-items:baseline;}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;}
.stack{display:grid;gap:12px;}
.pill{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12.5px;font-weight:700;background:#eef2ff;color:var(--accent);}
.bar{height:8px;border-radius:99px;background:#e8edf9;overflow:hidden;margin-top:10px;}
.bar > span{display:block;height:100%;border-radius:99px;background:var(--ok); transition: width 0.5s ease;}
.empty{display:flex;align-items:center;justify-content:center;min-height:120px;color:var(--muted);font-weight:700;}

/* Header */
.brand{font-size:26px;font-weight:800;color:var(--ink);}
.brand .gold{color:var(--gold);}
.status{text-align:center;font-size:15px;font-weight:700;color:var(--muted);}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;}
.sep{display:inline-block;width:1px;height:14px;background:var(--line);margin:0 14px;vertical-align:middle;}

/* Chat */
.msg{font-size:13.5px;font-weight:600;margin:4px 0;}
.msg small{color:var(--muted);font-weight:500;}
.msg.web{text-align:right;color:var(--accent);}
.msg.gui{text-align:left;color:#059669;}

/* Form & expander */
[data-testid="stForm"]{padding:0;border:0;}
[data-testid="stFormSubmitButton"] button{width:100%;}
[data-testid="stExpander"] details{background:var(--card);border-color:var(--line);border-radius:12px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ───────────────────────── Helper ─────────────────────────
def esc(value):
    """Escape semua teks dari MQTT sebelum masuk HTML (broker publik = input tidak tepercaya)."""
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
    """Daftar titik [x, y] -> (xs, ys) dengan polygon tertutup."""
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


# ───────────────────────── State bersama (thread MQTT <-> Streamlit) ─────────────────────────
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
        return "Machine online", OK
    return "Waiting for machine", WARN

def send_ping(text):
    ping = {"sender": "WEB", "message": text, "timestamp": datetime.now(WIB).strftime("%H:%M:%S")}
    if not DEMO:
        if not client.is_connected():
            st.toast("Broker offline, message not sent.", icon="⚠️")
            return
        client.publish(TOPIC_PING, json.dumps(ping), qos=1)
    store.add_ping(ping)


# ───────────────────────── Sidebar ─────────────────────────
HOME, ANALYSIS, LOGS = "🏠 Home", "📈 Analysis", "📝 Production log"

with st.sidebar:
    c_logo, c_name = st.columns([3, 7], vertical_alignment="center")
    c_logo.image(LOGO if os.path.exists(LOGO) else LOGO_REMOTE, width=48)
    c_name.markdown(
        "<div style='font-size:16px;font-weight:800;color:#d4af37;line-height:1.2'>VISIONEST</div>"
        "<div style='font-size:11px;font-weight:700;color:#1e3a8a'>by DEMIURGEN</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    page = st.radio("Menu", [HOME, ANALYSIS, LOGS], label_visibility="collapsed")
    st.divider()
    live = st.toggle("Live refresh", value=True)

REFRESH = 2 if live else None


# ───────────────────────── Komponen HTML ─────────────────────────
def card(title, value, unit="", sub=""):
    unit_html = f'<span class="unit">{esc(unit)}</span>' if unit else ""
    sub_html = f'<div class="card-sub">{esc(sub)}</div>' if sub else ""
    return (f'<div class="card"><div class="card-title">{esc(title)}</div>'
            f'<div class="card-value">{esc(value)}{unit_html}</div>{sub_html}</div>')

def machine_cards(s):
    pct = max(0.0, min(100.0, num(s["progress_pct"], 0.0)))
    status = str(s["status"]).replace("_", " ").title()
    machine = (
        '<div class="card"><div class="card-title">Machine</div>'
        f'<div class="card-value sm">{esc(s["device_id"])}</div>'
        f'<div class="card-sub">Operator: {esc(s["operator"])}</div>'
        f'<div class="card-sub">Shift: {esc(s["shift"])}</div>'
        f'<div style="margin-top:12px"><span class="pill">{esc(status)}</span></div></div>'
    )
    progress = (
        '<div class="card"><div class="card-title">Cutting progress</div>'
        f'<div class="card-value" style="color:var(--ok)">{pct:.0f}<span class="unit">%</span></div>'
        f'<div class="bar"><span style="width:{pct:.0f}%"></span></div></div>'
    )
    return f'<div class="stack">{machine}{progress}</div>'

def metric_grid(s):
    items = [
        card("Target output", fmt(s["target_qty"], 0), "pcs", "Total items in layout"),
        card("Cycle duration", fmt(s["duration_sec"]), "s", "Current execution time"),
        card("Material waste", fmt(s["waste_pct"]), "%", "Estimated scrap fabric"),
        card("Shape class", s["shape_name"], "", "Detected pattern"),
    ]
    return f'<div class="grid">{"".join(items)}</div>'

def nest_figure(s, mat_p, mat_l):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode="lines",
                             line=dict(color=BAD, width=2), hoverinfo="skip"))
    for i, poly in enumerate(s["nested_polys"], 1):
        xs, ys = outline(poly)
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", mode="lines", name=f"Piece {i}", hoverinfo="name",
                                 line=dict(color=WARN, width=2), fillcolor="rgba(245,158,11,0.25)"))
    fig.add_trace(go.Scatter(x=[num(s["pos_x"], 0.0)], y=[abs(num(s["pos_y"], 0.0))], mode="markers",
                             marker=dict(color=BAD, size=12), name="Laser tool"))
    fig.update_layout(**plot_layout(
        height=320, showlegend=False, uirevision="nest",
        xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
    ))
    return fig

def layout_card(s):
    mat_p, mat_l = num(s["mat_p"], 0.0), num(s["mat_l"], 0.0)
    with st.container(key="card_layout"):
        st.markdown(
            '<div class="row"><span class="card-title">Live production layout</span>'
            f'<span class="card-sub">{fmt(mat_p)} × {fmt(mat_l)} mm</span></div>',
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
    c_brand, c_status, c_logo = st.columns([3, 5, 2.5], vertical_alignment="center")
    c_brand.markdown('<div class="brand"><span class="gold">VISIONEST</span> Dashboard</div>', unsafe_allow_html=True)
    c_status.markdown(
        f'<div class="status"><span class="dot" style="background:{color}"></span>{esc(label)}'
        f'<span class="sep"></span>{now}</div>',
        unsafe_allow_html=True,
    )
    if os.path.exists(LOGO_PARTNER):
        c_logo.image(LOGO_PARTNER, width=200)
    else:
        c_logo.image(LOGO_PARTNER_REMOTE, width=200)

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
        st.markdown('<div class="card-title">Communication log (web ↔ GUI)</div>', unsafe_allow_html=True)
        chat_messages()
        with st.form("ping_form", clear_on_submit=True, border=False): 
            c_in, c_btn = st.columns([5, 1], vertical_alignment="bottom")
            text = c_in.text_input("Message", placeholder="Type a message to the cutting GUI",
                                   label_visibility="collapsed")
            sent = c_btn.form_submit_button("Send", type="primary")
        if sent and text.strip():
            send_ping(text.strip())

def style_chart(fig):
    fig.update_layout(**plot_layout(
        height=300, margin=dict(t=30, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    ))
    fig.update_xaxes(type="category", showgrid=False)
    fig.update_yaxes(gridcolor=GRID)
    return fig

def page_analysis():
    logs = store.logs_copy()
    if not logs:
        st.markdown(card("Analysis", "No data yet", "", "Charts appear after the first completed cut."),
                    unsafe_allow_html=True)
        return

    wastes = [w for w in (num(entry.get("waste")) for entry in logs) if w is not None]
    pieces = sum(int(num(entry.get("pcs"), 0)) for entry in logs)
    st.markdown(
        '<div class="grid">'
        + card("Completed cycles", len(logs), "", "In the log")
        + card("Pieces cut", pieces, "pcs", "All cycles")
        + card("Average waste", fmt(sum(wastes) / len(wastes)) if wastes else "–", "%", "All cycles")
        + "</div>",
        unsafe_allow_html=True,
    )

    df = pd.DataFrame(logs[:30][::-1]).reindex(columns=["waktu", "operator", "shift", "pcs", "waste"]) 
    df["waste"] = pd.to_numeric(df["waste"], errors="coerce")
    df["pcs"] = pd.to_numeric(df["pcs"], errors="coerce")
    df["shift"] = df["shift"].fillna("-")

    with st.container(key="card_usage"):
        st.markdown('<div class="card-title">Material usage per cycle (last 30)</div>', unsafe_allow_html=True)
        fig = go.Figure([
            go.Bar(name="Used", x=df["waktu"], y=100 - df["waste"], marker_color=OK),
            go.Bar(name="Waste", x=df["waktu"], y=df["waste"], marker_color=BAD),
        ])
        
        # ---> FIX 1: GRAFIK DIBUAT BERDAMPINGAN (GROUP), BUKAN NUMPUK (STACK) <---
        style_chart(fig).update_layout(barmode="group", bargroupgap=0.1)
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig, key="usage_chart", config=PLOT_CONFIG)

    with st.container(key="card_qty"):
        st.markdown('<div class="card-title">Production output per cycle (last 30)</div>', unsafe_allow_html=True)
        fig = px.bar(df, x="waktu", y="pcs", color="shift", text="pcs",
                     color_discrete_sequence=[ACCENT, "#39b8ff", GOLD])
        style_chart(fig).update_traces(cliponaxis=False)
        fig.update_layout(legend_title_text="")
        st.plotly_chart(fig, key="qty_chart", config=PLOT_CONFIG)

def page_logs():
    logs = store.logs_copy()
    c_title, c_btn = st.columns([8, 2], vertical_alignment="center")
    c_title.markdown(card("Production log", f"{len(logs)} cycles", "", "Newest first"), unsafe_allow_html=True)
    with c_btn.popover("Reset data"):
        st.write("Delete all production logs? This can't be undone.")
        if st.button("Delete all logs", type="primary"):
            store.reset_logs()
            st.session_state.pop("log_limit", None)
            st.rerun()

    if not logs:
        st.markdown('<div class="empty">No cutting history yet.</div>', unsafe_allow_html=True)
        return

    limit = st.session_state.setdefault("log_limit", PAGE_SIZE)
    for i, entry in enumerate(logs[:limit]):
        title = f'{entry.get("waktu", "-")}, {entry.get("operator", "-")}, {entry.get("pcs", 0)} pcs'
        with st.expander(title):
            c_text, c_img = st.columns([6, 4])
            c_text.markdown(
                f'**Pieces:** {entry.get("pcs", 0)}  \n'
                f'**Material:** {entry.get("ukuran", "-")} mm  \n'
                f'**Shape:** {entry.get("bentuk", "-")}  \n'
                f'**Waste:** {fmt(entry.get("waste"))}%'
            )
            
            # ---> FIX 2: LOGIKA FULL LAYOUT (KOTAK BATAS MATERIAL + SEMUA POLA) DIKEMBALIKAN <---
            mat_p, mat_l = 0, 0
            try:
                parts = entry.get('ukuran', '').split('x')
                mat_p = float(parts[0].replace('mm', '').strip())
                mat_l = float(parts[1].replace('mm', '').strip())
            except: pass
                
            fig_nest = go.Figure()
            
            # Gambar Kotak Merah Batas Material (Kalau datanya ada)
            if mat_p > 0 and mat_l > 0:
                fig_nest.add_trace(go.Scatter(x=[0, mat_p, mat_p, 0, 0], y=[0, 0, mat_l, mat_l, 0], mode='lines', line=dict(color=BAD, width=2), hoverinfo='skip'))
                
            # Gambar Semua Pola Nested di dalamnya
            polys = entry.get("nested_polys") or []
            for idx, poly in enumerate(polys):
                try:
                    xs, ys = outline(poly)
                    fig_nest.add_trace(go.Scatter(x=xs, y=ys, fill="toself", mode="lines", name=f"Pcs {idx+1}", hoverinfo="name", line=dict(color=WARN, width=1.5), fillcolor="rgba(245,158,11,0.25)"))
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
elif page == ANALYSIS:
    page_analysis()
else:
    page_logs()
