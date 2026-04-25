import base64
import io
import math
import struct
import time
import wave

import streamlit as st
import streamlit.components.v1 as components


# ---------------------------------------------------------------------------
# Time formatting helpers
# ---------------------------------------------------------------------------


def format_time_full(seconds: float) -> str:
    """HH:MM:SS.cc — used in lap rows."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h:02d}:{m:02d}:{s:02d}.{cs:02d}"


def format_time_compact(seconds: float) -> str:
    """Compact time: drops hours when 0 → MM:SS.cc, otherwise H:MM:SS."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}.{cs:02d}"


def format_delta(seconds: float) -> str:
    sign = "+" if seconds >= 0 else "−"
    return f"{sign}{format_time_compact(abs(seconds))}"


# ---------------------------------------------------------------------------
# Beep generation (cached) — small WAV files encoded as data URIs
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def make_beep_data_uri(freq: float = 880.0, duration: float = 0.15, volume: float = 0.35) -> str:
    rate = 22050
    n = int(duration * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(n):
            # simple linear fade-out to avoid click
            fade = 1.0 - (i / n) * 0.6
            sample = int(volume * fade * 32767 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", sample))
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


def play_beep_if_pending():
    """Render a hidden <audio autoplay> if a beep was queued this run."""
    pending = st.session_state.get("_pending_beep")
    if not pending:
        return
    freq, duration = pending
    st.session_state["_pending_beep"] = None
    st.session_state["_beep_counter"] = st.session_state.get("_beep_counter", 0) + 1
    src = make_beep_data_uri(freq=freq, duration=duration)
    # Use components.html with a unique key so the autoplay element re-renders
    components.html(
        f"<audio src='{src}' autoplay></audio>"
        f"<!-- {st.session_state['_beep_counter']} -->",
        height=0,
    )


def queue_beep(freq: float = 880.0, duration: float = 0.15):
    if st.session_state.get("sound_enabled", True):
        st.session_state["_pending_beep"] = (freq, duration)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


def init_state():
    defaults = {
        # stopwatch
        "sw_start_time": None,
        "sw_elapsed": 0.0,
        "sw_running": False,
        "sw_laps": [],  # list of dicts: lap, lap_seconds, total_seconds, label
        "sw_last_lap_time": 0.0,
        "sw_lap_label": "",
        # interval timer
        "it_running": False,
        "it_phase": "idle",  # idle | prep | work | rest | done
        "it_phase_end": None,  # epoch when current phase ends
        "it_phase_remaining_paused": None,  # seconds remaining if paused
        "it_round": 0,  # 1-based current round
        "it_total_rounds": 8,
        "it_work": 30,
        "it_rest": 15,
        "it_prep": 5,
        "it_last_tick_count": None,  # last integer second remaining we beeped at
        # sound
        "sound_enabled": True,
        # beep plumbing
        "_pending_beep": None,
        "_beep_counter": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Stopwatch logic
# ---------------------------------------------------------------------------


def sw_total_seconds() -> float:
    total = st.session_state.sw_elapsed
    if st.session_state.sw_running and st.session_state.sw_start_time is not None:
        total += time.time() - st.session_state.sw_start_time
    return total


def sw_start_or_resume():
    if not st.session_state.sw_running:
        st.session_state.sw_start_time = time.time()
        st.session_state.sw_running = True


def sw_pause():
    if st.session_state.sw_running and st.session_state.sw_start_time is not None:
        st.session_state.sw_elapsed += time.time() - st.session_state.sw_start_time
        st.session_state.sw_running = False
        st.session_state.sw_start_time = None


def sw_reset():
    st.session_state.sw_start_time = None
    st.session_state.sw_elapsed = 0.0
    st.session_state.sw_running = False
    st.session_state.sw_laps = []
    st.session_state.sw_last_lap_time = 0.0


def sw_lap():
    if not st.session_state.sw_running:
        return
    total = sw_total_seconds()
    lap_seconds = total - st.session_state.sw_last_lap_time
    st.session_state.sw_laps.append(
        {
            "lap": len(st.session_state.sw_laps) + 1,
            "lap_seconds": lap_seconds,
            "total_seconds": total,
            "label": st.session_state.sw_lap_label.strip(),
        }
    )
    st.session_state.sw_last_lap_time = total
    queue_beep(880, 0.12)


def sw_undo_last_lap():
    if not st.session_state.sw_laps:
        return
    st.session_state.sw_laps.pop()
    if st.session_state.sw_laps:
        st.session_state.sw_last_lap_time = st.session_state.sw_laps[-1]["total_seconds"]
    else:
        st.session_state.sw_last_lap_time = 0.0


def laps_to_csv(laps) -> str:
    buf = io.StringIO()
    buf.write("Круг,Метка,Время круга,Дельта,Общее\n")
    prev = None
    for lap in laps:
        delta = "" if prev is None else format_delta(lap["lap_seconds"] - prev)
        label = (lap.get("label") or "").replace(",", ";")
        buf.write(
            f"{lap['lap']},{label},{format_time_full(lap['lap_seconds'])},{delta},"
            f"{format_time_full(lap['total_seconds'])}\n"
        )
        prev = lap["lap_seconds"]
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Interval timer logic
# ---------------------------------------------------------------------------

PHASE_LABELS = {
    "idle": "Готов",
    "prep": "Подготовка",
    "work": "Работа",
    "rest": "Отдых",
    "done": "Готово",
}

PHASE_COLORS = {
    "idle": "#bdc3c7",
    "prep": "#3498db",
    "work": "#2ecc71",
    "rest": "#f1c40f",
    "done": "#9b59b6",
}


def it_phase_duration(phase: str) -> int:
    return {
        "prep": st.session_state.it_prep,
        "work": st.session_state.it_work,
        "rest": st.session_state.it_rest,
    }.get(phase, 0)


def it_remaining() -> float:
    if st.session_state.it_phase in ("idle", "done"):
        return 0.0
    if not st.session_state.it_running:
        return float(st.session_state.it_phase_remaining_paused or 0.0)
    if st.session_state.it_phase_end is None:
        return 0.0
    return max(0.0, st.session_state.it_phase_end - time.time())


def it_start_phase(phase: str):
    st.session_state.it_phase = phase
    duration = it_phase_duration(phase)
    st.session_state.it_phase_end = time.time() + duration
    st.session_state.it_last_tick_count = duration + 1  # so first tick beep can fire
    if phase == "work":
        queue_beep(880, 0.25)
    elif phase == "rest":
        queue_beep(440, 0.25)
    elif phase == "prep":
        queue_beep(660, 0.18)


def it_start():
    if st.session_state.it_phase in ("idle", "done"):
        st.session_state.it_round = 1
        if st.session_state.it_prep > 0:
            it_start_phase("prep")
        else:
            it_start_phase("work")
        st.session_state.it_running = True
    else:
        # resume
        remaining = st.session_state.it_phase_remaining_paused or 0.0
        st.session_state.it_phase_end = time.time() + remaining
        st.session_state.it_phase_remaining_paused = None
        st.session_state.it_running = True


def it_pause():
    if st.session_state.it_running:
        st.session_state.it_phase_remaining_paused = it_remaining()
        st.session_state.it_running = False


def it_reset():
    st.session_state.it_running = False
    st.session_state.it_phase = "idle"
    st.session_state.it_phase_end = None
    st.session_state.it_phase_remaining_paused = None
    st.session_state.it_round = 0
    st.session_state.it_last_tick_count = None


def apply_preset_tabata():
    st.session_state.it_work = 20
    st.session_state.it_rest = 10
    st.session_state.it_total_rounds = 8
    st.session_state.it_prep = 5


def apply_preset_emom():
    st.session_state.it_work = 60
    st.session_state.it_rest = 0
    st.session_state.it_total_rounds = 10
    st.session_state.it_prep = 5


def apply_preset_3030():
    st.session_state.it_work = 30
    st.session_state.it_rest = 30
    st.session_state.it_total_rounds = 6
    st.session_state.it_prep = 5


def it_skip_phase():
    if st.session_state.it_phase in ("prep", "work", "rest"):
        st.session_state.it_phase_end = time.time()


def it_advance_if_needed():
    """Move to next phase when remaining hits zero."""
    if not st.session_state.it_running:
        return
    if st.session_state.it_phase in ("idle", "done"):
        return
    remaining = it_remaining()

    # Countdown beeps for the last 3 seconds of any phase
    int_remaining = int(math.ceil(remaining))
    last = st.session_state.it_last_tick_count
    if last is not None and int_remaining < last and 0 < int_remaining <= 3:
        queue_beep(1100, 0.08)
    st.session_state.it_last_tick_count = int_remaining

    if remaining > 0:
        return

    # Transition
    phase = st.session_state.it_phase
    if phase == "prep":
        it_start_phase("work")
    elif phase == "work":
        if st.session_state.it_round >= st.session_state.it_total_rounds:
            st.session_state.it_phase = "done"
            st.session_state.it_running = False
            queue_beep(523, 0.5)
        else:
            it_start_phase("rest")
    elif phase == "rest":
        st.session_state.it_round += 1
        it_start_phase("work")


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
        font-size: 1.1rem; font-weight: 600;
        padding: 0.7rem 0.4rem; width: 100%;
        border-radius: 0.6rem;
        border: 1px solid rgba(255,255,255,0.08);
        transition: transform 0.05s ease-in-out, box-shadow 0.15s ease-in-out;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
    .stButton > button:active { transform: translateY(0); }
    .clock {
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        font-variant-numeric: tabular-nums;
        font-weight: 700;
        text-align: center;
        letter-spacing: 0.05em;
        padding: 1.1rem 0.4rem;
        margin: 0.4rem 0 0.8rem 0;
        border-radius: 1rem;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        color: #e6edf3;
        font-size: clamp(2rem, 9vw, 4rem);
        white-space: nowrap;
        overflow: hidden;
    }
    .clock-big {
        font-size: clamp(2.6rem, 12vw, 5.2rem);
    }
    .pill {
        display: inline-block; padding: 0.25rem 0.9rem;
        border-radius: 999px; font-size: 0.9rem; font-weight: 700;
        letter-spacing: 0.02em;
    }
    .stat-grid {
        display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.5rem; margin: 0.5rem 0;
    }
    .stat-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 0.7rem; padding: 0.6rem 0.5rem; text-align: center;
        min-width: 0;
    }
    .stat-card .label {
        font-size: 0.72rem; color: #8b949e; text-transform: uppercase;
        letter-spacing: 0.05em; margin-bottom: 0.25rem;
    }
    .stat-card .value {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-weight: 700; font-size: clamp(0.95rem, 3.5vw, 1.4rem);
        color: #e6edf3; white-space: nowrap;
    }
    .lap-table { width: 100%; border-collapse: collapse; }
    .lap-table th, .lap-table td {
        padding: 0.45rem 0.6rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        text-align: left; font-variant-numeric: tabular-nums;
    }
    .lap-table th {
        color: #8b949e; font-weight: 600; font-size: 0.78rem;
        text-transform: uppercase; letter-spacing: 0.04em;
    }
    .lap-best  td { color: #2ecc71; font-weight: 600; }
    .lap-worst td { color: #e74c3c; }
    .delta-pos { color: #e74c3c; }
    .delta-neg { color: #2ecc71; }
    @media (max-width: 480px) {
        .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .stButton > button { font-size: 1rem; padding: 0.55rem 0.3rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_state()

st.title("⏱️ ГБУ ДО РД СШ «САМУР»")
st.caption("Секундомер и интервальный таймер для тренировок")

# Sound toggle (top-right)
top_l, top_r = st.columns([4, 1])
with top_r:
    st.session_state.sound_enabled = st.toggle("🔊 Звук", value=st.session_state.sound_enabled)

tab_sw, tab_it = st.tabs(["⏱️ Секундомер", "⏲️ Интервальный таймер"])

# ---------------------------------------------------------------------------
# Stopwatch tab
# ---------------------------------------------------------------------------
with tab_sw:
    if st.session_state.sw_running:
        pill = '<span class="pill" style="background:rgba(46,204,113,0.18);color:#2ecc71;">● Идёт отсчёт</span>'
    elif st.session_state.sw_elapsed > 0:
        pill = '<span class="pill" style="background:rgba(241,196,15,0.18);color:#f1c40f;">⏸ Пауза</span>'
    else:
        pill = '<span class="pill" style="background:rgba(149,165,166,0.18);color:#bdc3c7;">○ Готов к старту</span>'
    st.markdown(f"<div style='text-align:center'>{pill}</div>", unsafe_allow_html=True)

    total_seconds = sw_total_seconds()
    main_display = (
        format_time_full(total_seconds)
        if total_seconds >= 3600
        else format_time_compact(total_seconds)
    )
    st.markdown(
        f"<div class='clock clock-big'>{main_display}</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.sw_running or st.session_state.sw_laps:
        cur = total_seconds - st.session_state.sw_last_lap_time
        st.markdown(
            f"<div style='text-align:center;color:#8b949e;margin-top:-0.4rem;'>"
            f"Текущий круг: <code>{format_time_compact(cur)}</code></div>",
            unsafe_allow_html=True,
        )

    st.text_input(
        "Метка для следующего круга (необязательно)",
        key="sw_lap_label",
        placeholder="Например: имя спортсмена или упражнение",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.session_state.sw_running:
            st.button("⏸️ Пауза", on_click=sw_pause, key="sw_pause", type="secondary")
        else:
            label = "▶️ Продолжить" if st.session_state.sw_elapsed > 0 else "🟢 Старт"
            st.button(label, on_click=sw_start_or_resume, key="sw_start", type="primary")
    with c2:
        st.button("🏁 Круг", on_click=sw_lap, key="sw_lap", disabled=not st.session_state.sw_running)
    with c3:
        st.button(
            "🔄 Сброс",
            on_click=sw_reset,
            key="sw_reset",
            disabled=(
                not st.session_state.sw_running
                and st.session_state.sw_elapsed == 0
                and not st.session_state.sw_laps
            ),
        )
    with c4:
        if st.session_state.sw_laps:
            st.download_button(
                "💾 CSV",
                data=laps_to_csv(st.session_state.sw_laps).encode("utf-8-sig"),
                file_name="laps.csv",
                mime="text/csv",
                key="sw_csv",
            )
        else:
            st.button("💾 CSV", key="sw_csv_disabled", disabled=True)

    if st.session_state.sw_laps:
        lap_seconds_list = [lap["lap_seconds"] for lap in st.session_state.sw_laps]
        best = min(lap_seconds_list)
        worst = max(lap_seconds_list)
        avg = sum(lap_seconds_list) / len(lap_seconds_list)

        st.markdown(
            f"""
            <div class='stat-grid'>
              <div class='stat-card'><div class='label'>Кругов</div>
                <div class='value'>{len(st.session_state.sw_laps)}</div></div>
              <div class='stat-card'><div class='label'>Лучший</div>
                <div class='value' style='color:#2ecc71'>{format_time_compact(best)}</div></div>
              <div class='stat-card'><div class='label'>Худший</div>
                <div class='value' style='color:#e74c3c'>{format_time_compact(worst)}</div></div>
              <div class='stat-card'><div class='label'>Средний</div>
                <div class='value'>{format_time_compact(avg)}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        u1, _ = st.columns([1, 3])
        with u1:
            st.button("↩️ Удалить последний круг", on_click=sw_undo_last_lap, key="sw_undo")

        st.subheader("🏁 Круги")
        rows = [
            "<table class='lap-table'><thead><tr>"
            "<th>#</th><th>Метка</th><th>Время</th><th>Δ</th><th>Общее</th>"
            "</tr></thead><tbody>"
        ]
        for idx, lap in enumerate(reversed(st.session_state.sw_laps)):
            real_idx = len(st.session_state.sw_laps) - 1 - idx
            cls = ""
            if len(lap_seconds_list) > 1:
                if lap["lap_seconds"] == best:
                    cls = " class='lap-best'"
                elif lap["lap_seconds"] == worst:
                    cls = " class='lap-worst'"
            if real_idx > 0:
                prev = st.session_state.sw_laps[real_idx - 1]["lap_seconds"]
                d = lap["lap_seconds"] - prev
                d_cls = "delta-pos" if d > 0 else ("delta-neg" if d < 0 else "")
                delta_html = f"<span class='{d_cls}'>{format_delta(d)}</span>"
            else:
                delta_html = "<span style='color:#586069'>—</span>"
            label_html = lap.get("label") or ""
            rows.append(
                f"<tr{cls}><td>{lap['lap']}</td>"
                f"<td>{label_html}</td>"
                f"<td>{format_time_full(lap['lap_seconds'])}</td>"
                f"<td>{delta_html}</td>"
                f"<td>{format_time_full(lap['total_seconds'])}</td></tr>"
            )
        rows.append("</tbody></table>")
        st.markdown("".join(rows), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Interval timer tab
# ---------------------------------------------------------------------------
with tab_it:
    st.markdown("**Настройка раундов** (Tabata: 20 / 10 / 8)")
    ic1, ic2, ic3, ic4 = st.columns(4)
    with ic1:
        st.number_input("Подготовка, с", min_value=0, max_value=60, step=1, key="it_prep")
    with ic2:
        st.number_input("Работа, с", min_value=1, max_value=600, step=1, key="it_work")
    with ic3:
        st.number_input("Отдых, с", min_value=0, max_value=600, step=1, key="it_rest")
    with ic4:
        st.number_input("Раундов", min_value=1, max_value=99, step=1, key="it_total_rounds")

    p1, p2, p3 = st.columns(3)
    with p1:
        st.button("🥊 Tabata 20/10×8", key="preset_tabata", on_click=apply_preset_tabata)
    with p2:
        st.button("💪 EMOM 60×10", key="preset_emom", on_click=apply_preset_emom)
    with p3:
        st.button("🏃 30/30×6", key="preset_3030", on_click=apply_preset_3030)

    it_advance_if_needed()

    phase = st.session_state.it_phase
    phase_label = PHASE_LABELS[phase]
    phase_color = PHASE_COLORS[phase]

    pill_html = (
        f'<span class="pill" style="background:{phase_color}26;color:{phase_color};">'
        f'{phase_label}</span>'
    )
    if phase in ("prep", "work", "rest"):
        round_html = (
            f'<span style="margin-left:0.6rem;color:#8b949e;font-weight:600;">'
            f'Раунд {st.session_state.it_round} / {st.session_state.it_total_rounds}</span>'
        )
    else:
        round_html = ""
    st.markdown(
        f"<div style='text-align:center;margin-top:0.4rem'>{pill_html}{round_html}</div>",
        unsafe_allow_html=True,
    )

    rem = it_remaining()
    if phase == "idle":
        rem_display = format_time_compact(st.session_state.it_work)
    elif phase == "done":
        rem_display = "00:00"
    else:
        rem_display = format_time_compact(math.ceil(rem))
    st.markdown(
        f"<div class='clock clock-big' style='color:{phase_color}'>{rem_display}</div>",
        unsafe_allow_html=True,
    )

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        if st.session_state.it_running:
            st.button("⏸️ Пауза", on_click=it_pause, key="it_pause", type="secondary")
        else:
            label = "▶️ Продолжить" if phase in ("prep", "work", "rest") else "🟢 Старт"
            st.button(label, on_click=it_start, key="it_start", type="primary")
    with cc2:
        st.button(
            "⏭️ Пропустить",
            on_click=it_skip_phase,
            key="it_skip",
            disabled=phase in ("idle", "done"),
        )
    with cc3:
        st.button("🔄 Сброс", on_click=it_reset, key="it_reset")

    st.caption(
        "Звуковые сигналы: переход фазы и три коротких бипа за 3 секунды до конца. "
        "Если звука нет — браузер блокирует автоплей до первого клика по странице."
    )

# Play any queued beep
play_beep_if_pending()

# Auto-refresh while either timer is active
if st.session_state.sw_running or st.session_state.it_running:
    time.sleep(0.1)
    st.rerun()

with st.expander("ℹ️ Как пользоваться"):
    st.markdown(
        "**Секундомер:** Старт/Пауза, Круг (с опциональной меткой), Сброс. "
        "В таблице — лучший круг зелёный, худший красный, колонка Δ — разница с предыдущим кругом. "
        "Кнопка «Удалить последний круг» откатывает ошибочный клик. Все круги выгружаются в CSV.\n\n"
        "**Интервальный таймер:** задайте подготовку, работу, отдых и количество раундов "
        "(или нажмите пресет). Старт запустит цикл с подсчётом раундов и звуковыми сигналами. "
        "Кнопка «Пропустить» переходит к следующей фазе досрочно."
    )
