import streamlit as st
import time
import datetime

# Initialize session state variables
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'elapsed_time' not in st.session_state:
    st.session_state.elapsed_time = 0
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'laps' not in st.session_state:
    st.session_state.laps = []
if 'last_lap_time' not in st.session_state:
    st.session_state.last_lap_time = 0

# Function to force refresh the page for real-time updates
def refresh():
    st.experimental_rerun()

def format_time(seconds):
    """Format seconds to HH:MM:SS format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def format_time_ms(seconds):
    """Format seconds to HH:MM:SS.ms format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 100)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:02d}"

# Streamlit app title
st.set_page_config(
    page_title="ГБУ ДО РД СШ 'САМУР'",
    page_icon="⏱️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("⏱️ Часы для тренера")
st.markdown("*Идеально подходят для отслеживания тренировочных сессий*")

# Display the current elapsed time
time_display = st.empty()
current_time = st.session_state.elapsed_time

if st.session_state.is_running:
    current_time += time.time() - st.session_state.start_time

time_display.subheader(f"`{format_time_ms(current_time)}`")

# Create buttons for controlling the stopwatch
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🟢 Старт"):
        if not st.session_state.is_running:
            st.session_state.start_time = time.time()
            st.session_state.is_running = True

with col2:
    if st.button("⏸️ Пауза"):
        if st.session_state.is_running:
            st.session_state.elapsed_time += time.time() - st.session_state.start_time
            st.session_state.is_running = False

with col3:
    if st.button("🔄 Сброс"):
        st.session_state.start_time = None
        st.session_state.elapsed_time = 0
        st.session_state.is_running = False
        st.session_state.laps = []
        st.session_state.last_lap_time = 0

with col4:
    if st.button("🏁 Круг"):
        if st.session_state.is_running:
            # Calculate lap time
            current_total = st.session_state.elapsed_time + (time.time() - st.session_state.start_time)
            lap_time = current_total - st.session_state.last_lap_time
            
            # Add lap to the list
            st.session_state.laps.append({
                'lap': len(st.session_state.laps) + 1,
                'time': format_time_ms(lap_time),
                'total': format_time_ms(current_total)
            })
            
            st.session_state.last_lap_time = current_total

# Show lap times
if st.session_state.laps:
    st.subheader("Времена кругов")
    # Reverse the list to show latest laps first
    for lap in reversed(st.session_state.laps):
        st.write(f"Круг {lap['lap']}: `{lap['time']}` | Всего: `{lap['total']}`")

# Auto-refresh every 0.1 seconds to update the timer in real-time when running
if st.session_state.is_running:
    time.sleep(0.1)
    st.rerun()

# Mobile-friendly styling
st.markdown("""
<style>
/* Mobile-friendly styles */
.stButton > button {
    font-size: 1.2rem;
    padding: 15px;
    margin: 5px;
    min-height: 3rem;
}
.subheader {
    font-size: 2.5rem !important;
    text-align: center;
    font-family: monospace;
}
/* Larger font for time display */
div[data-testid="stMarkdownContainer"] h3 {
    font-size: 3rem;
    text-align: center;
    font-family: monospace;
    letter-spacing: 2px;
}
</style>
""", unsafe_allow_html=True)

# Show instructions
st.markdown("---")
st.markdown("### Как пользоваться:")
st.markdown("- **Старт**: Начать секундомер")
st.markdown("- **Пауза**: Временно остановить тайминг")
st.markdown("- **Сброс**: Очистить все времена и круги")
st.markdown("- **Круг**: Записать промежуточное время во время работы")
