import io
import time

import streamlit as st


def init_state():
    """Initialize session state with default values."""
    defaults = {
        "start_time": None,
        "elapsed_time": 0.0,
        "is_running": False,
        "laps": [],
        "last_lap_time": 0.0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def format_time_ms(seconds: float) -> str:
    """Format seconds as HH:MM:SS.cc (centiseconds)."""
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def current_total_seconds() -> float:
    """Return the running total elapsed time in seconds."""
    total = st.session_state.elapsed_time
    if st.session_state.is_running and st.session_state.start_time is not None:
        total += time.time() - st.session_state.start_time
    return total


def start_or_resume():
    if not st.session_state.is_running:
        st.session_state.start_time = time.time()
        st.session_state.is_running = True


def pause():
    if st.session_state.is_running and st.session_state.start_time is not None:
        st.session_state.elapsed_time += time.time() - st.session_state.start_time
        st.session_state.is_running = False
        st.session_state.start_time = None


def reset():
    st.session_state.start_time = None
    st.session_state.elapsed_time = 0.0
    st.session_state.is_running = False
    st.session_state.laps = []
    st.session_state.last_lap_time = 0.0


def record_lap():
    if not st.session_state.is_running:
        return
    total = current_total_seconds()
    lap_seconds = total - st.session_state.last_lap_time
    st.session_state.laps.append(
        {
            "lap": len(st.session_state.laps) + 1,
            "lap_seconds": lap_seconds,
            "total_seconds": total,
        }
    )
    st.session_state.last_lap_time = total


def laps_to_csv(laps) -> str:
    buf = io.StringIO()
    buf.write("Круг,Время круга,Общее время\n")
    for lap in laps:
        buf.write(
            f"{lap['lap']},{format_time_ms(lap['lap_seconds'])},"
            f"{format_time_ms(lap['total_seconds'])}\n"
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="ГБУ ДО РД СШ «САМУР» — Секундомер",
    page_icon="⏱️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #0e1117 0%, #1a1f2e 100%); }
    .stButton > button {
        font-size: 1.1rem;
        font-weight: 600;
        padding: 0.75rem 0.5rem;
        width: 100%;
        border-radius: 0.6rem;
        border: 1px solid rgba(255,255,255,0.08);
        transition: transform 0.05s ease-in-out, box-shadow 0.15s ease-in-out;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .stButton > button:active { transform: translateY(0); }
    .stop-display {
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        font-variant-numeric: tabular-nums;
        font-weight: 700;
        font-size: clamp(2.8rem, 11vw, 5.5rem);
        text-align: center;
        letter-spacing: 0.06em;
        padding: 1.25rem 0.5rem;
        margin: 0.5rem 0 1rem 0;
        border-radius: 1rem;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        color: #e6edf3;
    }
    .status-pill {
        display: inline-block;
        padding: 0.25rem 0.9rem;
        border-radius: 999px;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .status-running { background: rgba(46, 204, 113, 0.18); color: #2ecc71; }
    .status-paused  { background: rgba(241, 196, 15, 0.18); color: #f1c40f; }
    .status-idle    { background: rgba(149, 165, 166, 0.18); color: #bdc3c7; }
    .lap-table { width: 100%; border-collapse: collapse; }
    .lap-table th, .lap-table td {
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        text-align: left;
        font-variant-numeric: tabular-nums;
    }
    .lap-table th { color: #8b949e; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
    .lap-best  td { color: #2ecc71; }
    .lap-worst td { color: #e74c3c; }
    @media (max-width: 480px) {
        .stButton > button { font-size: 1rem; padding: 0.6rem 0.3rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_state()

st.title("⏱️ ГБУ ДО РД СШ «САМУР»")
st.caption("Секундомер для отслеживания тренировочных сессий")

# Status pill
if st.session_state.is_running:
    status_html = '<span class="status-pill status-running">● Идёт отсчёт</span>'
elif st.session_state.elapsed_time > 0:
    status_html = '<span class="status-pill status-paused">⏸ Пауза</span>'
else:
    status_html = '<span class="status-pill status-idle">○ Готов к старту</span>'
st.markdown(f"<div style='text-align:center'>{status_html}</div>", unsafe_allow_html=True)

# Time display
total_seconds = current_total_seconds()
st.markdown(
    f"<div class='stop-display'>{format_time_ms(total_seconds)}</div>",
    unsafe_allow_html=True,
)

# Current (in-progress) lap
if st.session_state.is_running or st.session_state.laps:
    current_lap = total_seconds - st.session_state.last_lap_time
    st.markdown(
        f"<div style='text-align:center;color:#8b949e;margin-top:-0.5rem;'>"
        f"Текущий круг: <code>{format_time_ms(current_lap)}</code></div>",
        unsafe_allow_html=True,
    )

st.write("")

# Controls
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.session_state.is_running:
        st.button("⏸️ Пауза", on_click=pause, key="pause_btn", type="secondary")
    else:
        label = "▶️ Продолжить" if st.session_state.elapsed_time > 0 else "🟢 Старт"
        st.button(label, on_click=start_or_resume, key="start_btn", type="primary")

with col2:
    st.button(
        "🏁 Круг",
        on_click=record_lap,
        key="lap_btn",
        disabled=not st.session_state.is_running,
    )

with col3:
    st.button(
        "🔄 Сброс",
        on_click=reset,
        key="reset_btn",
        disabled=(
            not st.session_state.is_running
            and st.session_state.elapsed_time == 0
            and not st.session_state.laps
        ),
    )

with col4:
    if st.session_state.laps:
        st.download_button(
            "💾 CSV",
            data=laps_to_csv(st.session_state.laps).encode("utf-8-sig"),
            file_name="laps.csv",
            mime="text/csv",
            key="csv_btn",
        )
    else:
        st.button("💾 CSV", key="csv_btn", disabled=True)

# Lap statistics
if st.session_state.laps:
    lap_seconds_list = [lap["lap_seconds"] for lap in st.session_state.laps]
    best = min(lap_seconds_list)
    worst = max(lap_seconds_list)
    avg = sum(lap_seconds_list) / len(lap_seconds_list)

    st.subheader("📊 Статистика")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Кругов", len(st.session_state.laps))
    s2.metric("Лучший", format_time_ms(best))
    s3.metric("Худший", format_time_ms(worst))
    s4.metric("Средний", format_time_ms(avg))

    st.subheader("🏁 Круги")
    rows = ["<table class='lap-table'><thead><tr><th>#</th><th>Время круга</th><th>Общее</th></tr></thead><tbody>"]
    for lap in reversed(st.session_state.laps):
        cls = ""
        if len(lap_seconds_list) > 1:
            if lap["lap_seconds"] == best:
                cls = " class='lap-best'"
            elif lap["lap_seconds"] == worst:
                cls = " class='lap-worst'"
        rows.append(
            f"<tr{cls}><td>{lap['lap']}</td>"
            f"<td>{format_time_ms(lap['lap_seconds'])}</td>"
            f"<td>{format_time_ms(lap['total_seconds'])}</td></tr>"
        )
    rows.append("</tbody></table>")
    st.markdown("".join(rows), unsafe_allow_html=True)

with st.expander("ℹ️ Как пользоваться"):
    st.markdown(
        "- **Старт / Продолжить** — запускает или возобновляет отсчёт.\n"
        "- **Пауза** — приостанавливает таймер без сброса.\n"
        "- **Круг** — фиксирует промежуточное время (доступно во время отсчёта).\n"
        "- **Сброс** — обнуляет время и список кругов.\n"
        "- **CSV** — выгружает все круги в файл для отчёта."
    )

# Auto-refresh while running for live time updates
if st.session_state.is_running:
    time.sleep(0.1)
    st.rerun()
