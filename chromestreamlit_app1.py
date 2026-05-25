import streamlit as st
import threading
import uuid
import time
import pytz
import os
from datetime import datetime
import glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= STORAGE LIMITS =================
MAX_MEMORY_LOGS = 80       # RAM per TASK ID
MAX_DISK_LOG_LINES = 80     # Disk per TASK ID
MAX_TASKS_IN_MEMORY = 100   # Max active tasks in RAM

# ================= REAL GLOBAL STORAGE =================
TASK_COUNTER = {}
TASK_LOGS = {}
DRIVERS = {}
TASK_CREATED_AT = {}

# ================= FILE LOG STORAGE (CLOUD SAFE) =================
LOG_DIR = "task_logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ================= AUTO STORAGE CLEANER =================
MAX_LOG_AGE_HOURS = 6   # 6 ghante baad delete
CLEAN_INTERVAL = 300    # 5 min me run

def auto_cleanup():
    while True:
        now = time.time()

        for file in glob.glob(f"{LOG_DIR}/*"):
            try:
                file_age = now - os.path.getmtime(file)

                if file_age > MAX_LOG_AGE_HOURS * 3600:
                    os.remove(file)

            except:
                pass

        time.sleep(CLEAN_INTERVAL)

def stop_flag(task_id):
    return f"{LOG_DIR}/STOP_{task_id}.flag"

def stopped_flag(task_id):
    return f"{LOG_DIR}/STOPPED_{task_id}.done"

def is_stop_requested(task_id):
    return os.path.exists(stop_flag(task_id))

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="E2E Multi Tool",
    page_icon="🚀",
    layout="wide"
)

# 👇 YEH ALAG HOGA
if "cleanup_started" not in st.session_state:
    threading.Thread(target=auto_cleanup, daemon=True).start()
    st.session_state.cleanup_started = True

# ================= SESSION INIT =================
for k, v in {
    "auth": False,
    "page": "login",
    "task_id": None,
    "view_tid": None,
    "task_details_auth": False   # 🔐 Task Details password flag
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ================= CSS =================
st.markdown("""
<style>

/* ====== HEADER GLOW (already discussed) ====== */
.main-header {
    font-size: 3rem;
    text-align: center;
    background: linear-gradient(45deg, #ff0096, #00ffff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: textGlow 2s ease-in-out infinite alternate;
}

@keyframes textGlow {
    from {
        filter: drop-shadow(0 0 10px rgba(255,0,150,.6));
    }
    to {
        filter: drop-shadow(0 0 20px rgba(0,255,255,.6));
    }
}

/* ====== ACCESS SYSTEM BUTTON (HTML STYLE) ====== */
.stButton > button {
    width: 100%;
    padding: 16px;
    border-radius: 50px;
    border: none;
    cursor: pointer;

    font-size: 1.05rem;
    font-weight: bold;
    text-transform: uppercase;
    color: white;

    background: linear-gradient(
        120deg,
        #ff2aa1,
        #00eaea,
        #ff2aa1
    );
    background-size: 220% 220%;
    animation: btnFlow 6s linear infinite;

    box-shadow: none;
    transition: transform .3s ease, box-shadow .3s ease;
}

/* gradient movement */
@keyframes btnFlow {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* hover movement + cyan glow */
.stButton > button:hover {
    transform: translateY(-3px) scale(1.03);
    box-shadow: 0 0 35px rgba(0,234,234,0.8);
}

/* click press */
.stButton > button:active {
    transform: scale(0.97);
}

</style>
""", unsafe_allow_html=True)

# ================= GLOBAL TASK LIMIT =================
def enforce_global_task_limit():
    if len(TASK_LOGS) > MAX_TASKS_IN_MEMORY:
        extra_tasks = list(TASK_LOGS.keys())[:-MAX_TASKS_IN_MEMORY]
        for tid in extra_tasks:
            TASK_LOGS.pop(tid, None)
            TASK_COUNTER.pop(tid, None)
            DRIVERS.pop(tid, None)

# ================= LOG FUNCTION =================
def log_message(task_id, uid, message, status, count=True):
    ist = pytz.timezone("Asia/Kolkata")
    ts = datetime.now(ist).strftime("%d-%m-%Y | %H:%M:%S IST")

    if count:
        TASK_COUNTER[task_id] = TASK_COUNTER.get(task_id, 0) + 1
    else:
        TASK_COUNTER.setdefault(task_id, 0)

    # 🔥 UPTIME CALCULATION (NO STORAGE USE)
    uptime_str = "N/A"
    try:
        if task_id in TASK_CREATED_AT:
            ist = pytz.timezone("Asia/Kolkata")
            start_time = datetime.strptime(
                TASK_CREATED_AT[task_id], "%d-%m-%Y | %H:%M:%S IST"
            )
            start_time = ist.localize(start_time)

            now_time = datetime.now(ist)
            diff = now_time - start_time

            days = diff.days
            seconds = diff.seconds

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            uptime_str = f"{days}d {hours}h {minutes}m {secs}s"
    except:
        pass

    log = f"""
[TASK ID] = {task_id}
[TIME]    = {ts}
[INBOX]   = {uid}
[MESSAGE] = {message}
[STATUS]  = {status}
[TOTAL]   = {TASK_COUNTER[task_id]}
[UPTIME]  = {uptime_str}
----------------------------------------------
"""

    # -------- MEMORY LOGS (ROTATION) --------
    TASK_LOGS.setdefault(task_id, []).append(log)

    if len(TASK_LOGS[task_id]) > MAX_MEMORY_LOGS:
        TASK_LOGS[task_id] = TASK_LOGS[task_id][-MAX_MEMORY_LOGS:]

    # -------- WRITE TO DISK --------
    log_path = f"{LOG_DIR}/{task_id}.log"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log)

    # -------- DISK LOG ROTATION --------
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) > MAX_DISK_LOG_LINES:
            lines = lines[-MAX_DISK_LOG_LINES:]

            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

    # -------- GLOBAL TASK LIMIT --------
    enforce_global_task_limit()

# ================= DRIVER =================
def create_driver():

    opt = Options()

    # ================= HEADLESS =================
    opt.add_argument("--headless=new")

    # ================= STABILITY =================
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--disable-gpu")

    # ================= RAM REDUCTION =================
    opt.add_argument("--disable-extensions")
    opt.add_argument("--disable-infobars")
    opt.add_argument("--disable-notifications")

    # ================= BACKGROUND FREEZE REDUCTION =================
    opt.add_argument("--disable-background-timer-throttling")
    opt.add_argument("--disable-backgrounding-occluded-windows")
    opt.add_argument("--disable-renderer-backgrounding")

    # ================= HIGH TRAFFIC MESSENGER STABILITY =================
    opt.add_argument("--process-per-site")
    opt.add_argument("--disable-site-isolation-trials")
    opt.add_argument("--memory-pressure-off")
    opt.add_argument("--max_old_space_size=4096")
    opt.add_argument("--disable-features=CalculateNativeWinOcclusion")

    # ================= MESSENGER STABILITY =================
    opt.add_argument("--window-size=1920,1080")

    # ================= ANTI AUTOMATION =================
    opt.add_argument("--disable-blink-features=AutomationControlled")

    # ================= CHROMIUM PATH =================
    opt.binary_location = "/usr/bin/chromium"

    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"),
        options=opt
    )

    driver.maximize_window()

    # ✅ IMPORTANT
    # implicit wait freeze issues avoid karega
    driver.implicitly_wait(0)

    # ✅ SLOW GROUP LOAD SUPPORT
    driver.set_page_load_timeout(300)

    return driver
    
def keep_session_alive(driver):
    try:
        driver.execute_script("window.localStorage.length;")
        return True
    except:
        return False

def recover_messenger(driver, uid):

    for _ in range(3):

        try:

            driver.get(
                f"https://www.facebook.com/messages/t/{uid}"
            )

            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@role='textbox']")
                )
            )

            time.sleep(5)

            return True

        except:

            try:
                driver.refresh()
            except:
                pass

            time.sleep(10)

    return False

# ================= SAFE MESSAGE SEND =================
def safe_send_message(driver, wait, message):

    MAX_RETRIES = 5

    for attempt in range(MAX_RETRIES):

        try:

            wait.until(
                lambda d: d.execute_script(
                    "return document.readyState"
                ) == "complete"
            )

            box = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@role='textbox']")
                )
            )

            WebDriverWait(driver, 60).until(
                EC.visibility_of(box)
            )

            driver.execute_script("""
                arguments[0].scrollIntoView({
                    block:'center'
                });
            """, box)

            time.sleep(1)

            try:
                driver.execute_script(
                    "arguments[0].click();",
                    box
                )
            except:
                box.click()

            time.sleep(1)

            active = driver.switch_to.active_element

            if active != box:
                driver.execute_script(
                    "arguments[0].focus();",
                    box
                )
                time.sleep(1)

            box.send_keys(Keys.CONTROL, "a")
            time.sleep(0.5)
            box.send_keys(Keys.BACKSPACE)

            time.sleep(1)

            for ch in message:
                box.send_keys(ch)
                time.sleep(0.02)

            time.sleep(2)

            entered = box.text.strip()

            if message.strip() not in entered:
                raise Exception("TEXT NOT ENTERED PROPERLY")

            box.send_keys(Keys.ENTER)

            time.sleep(4)

            final_text = box.text.strip()

            if final_text != "":
                raise Exception("MESSAGE NOT SENT")

            return True

        except Exception:

            try:
                driver.execute_script("window.stop();")
            except:
                pass

            time.sleep(3)

    return False

def login_with_cookies(cookie_str):
    d = create_driver()
    d.get("https://www.facebook.com")
    time.sleep(3)

    for c in cookie_str.split(";"):
        if "=" in c:
            k, v = c.split("=", 1)
            d.add_cookie({"name": k.strip(), "value": v.strip(), "domain": ".facebook.com"})

    d.refresh()
    time.sleep(5)

    # ✅ YAHAN ADD KARNA HAI
    if "login" in d.current_url:
        print("❌ LOGIN FAILED - Cookies expired")

    return d

# ================= TASK THREAD (SAFE SEQUENTIAL MODE) =================
def send_messages(task_id, driver, uid, msgs, haters, delay):

    wait = WebDriverWait(driver, 60)

    driver.get(f"https://www.facebook.com/messages/t/{uid}")

    log_message(
        task_id,
        uid,
        f"LOGIN URL: {driver.current_url}",
        "INFO",
        count=False
    )

    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@role='main']")
        )
    )

    time.sleep(5)

    log_message(
        task_id,
        uid,
        "Task Started",
        "STARTED",
        count=False
    )

    i = 0

    # ✅ AUTO REFRESH TIMER
    last_refresh = time.time()

    # ✅ LAST SUCCESS TIMER
    last_sent_time = time.time()

    import random

    while True:

        # ================= STOP CHECK =================
        if is_stop_requested(task_id):
            break

        # ================= AUTO REFRESH =================
        if time.time() - last_refresh > 900:

            log_message(
                task_id,
                uid,
                "AUTO REFRESH FOR STABILITY",
                "INFO",
                count=False
            )

            recover_messenger(driver, uid)

            last_refresh = time.time()

        # ================= FREEZE DETECTION =================
        if time.time() - last_sent_time > 300:

            log_message(
                task_id,
                uid,
                "FREEZE DETECTED -> RECOVERING",
                "INFO",
                count=False
            )

            recover_messenger(driver, uid)

            last_sent_time = time.time()

        try:

            # ================= MESSAGE BUILD =================
            msg = msgs[i % len(msgs)]

            full = (
                f"{haters} {msg}"
                if haters else msg
            )

            # ================= SAFE SEND =================
            success = safe_send_message(
                driver,
                wait,
                full
            )

            # ================= SUCCESS =================
            if success:

                log_message(
                    task_id,
                    uid,
                    full,
                    "SENT"
                )

                # ✅ UPDATE LAST SUCCESS TIME
                last_sent_time = time.time()

                i += 1

                # ================= MEMORY REFRESH =================
                if i % 40 == 0 and i != 0:

                    log_message(
                        task_id,
                        uid,
                        "MEMORY REFRESH",
                        "INFO",
                        count=False
                    )

                    recover_messenger(driver, uid)

                # ================= SAFE RANDOM DELAY =================
                wait_time = random.randint(
                    delay,
                    delay + 20
                )

                for _ in range(wait_time):

                    if is_stop_requested(task_id):
                        break

                    time.sleep(1)

            # ================= FAILED =================
            else:

                log_message(
                    task_id,
                    uid,
                    "MESSAGE SEND FAILED AFTER RETRIES",
                    "FAILED"
                )

                recover_messenger(driver, uid)

                time.sleep(10)

                continue

        except Exception as e:

            err = str(e)

            log_message(
                task_id,
                uid,
                f"ERROR: {err}",
                "FAILED"
            )

            # ================= SESSION CHECK =================
            if not keep_session_alive(driver):

                log_message(
                    task_id,
                    uid,
                    "SESSION DEAD -> RELOGIN",
                    "INFO",
                    count=False
                )

                try:
                    driver.refresh()
                    time.sleep(10)

                except:
                    pass

            # ================= RECOVER =================
            recover_messenger(driver, uid)

            time.sleep(5)

    # ================= STOP CLEANUP =================
    log_message(
        task_id,
        uid,
        "Task Stopped",
        "STOPPED"
    )

    try:
        driver.quit()

    except:
        pass

    with open(stopped_flag(task_id), "w") as f:
        f.write("STOPPED")
        
# ================= LOGIN PAGE =================
if not st.session_state.auth:

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    .block-container {
        padding-top: 6rem;
    }

    /* Hide default label */
    label[data-testid="stWidgetLabel"] {
        display: none;
    }

    /* Custom Access Key text */
    .access-key-text {
        text-align: center;
        color: white;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 8px;
        text-shadow: 0 0 10px rgba(255,255,255,0.6);
    }

    /* Center password input */
    div[data-baseweb="input"] {
        display: flex;
        justify-content: center;
    }

    div[data-baseweb="input"] input {
        text-align: center;
        border-radius: 50px;
        height: 52px;
        font-size: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

    #  Heading
    st.markdown('<h1 class="main-header">🐦‍🔥 E2E Multi Tool</h1>', unsafe_allow_html=True)

    #  Access Key text
    st.markdown('<div class="access-key-text">Advance Automation Platform</div>', unsafe_allow_html=True)

    #  Password input (FIXED )
    pwd = st.text_input(
        "Access Key",
        type="password",
        label_visibility="collapsed"
    )

    if st.button("🧑‍💻 Access System"):
        if pwd == "VIKRAMXWD":
            st.session_state.auth = True
            st.session_state.page = "dashboard"
            st.rerun()
        else:
            st.error("Wrong Key")

    st.stop()

# ================= DASHBOARD =================
if st.session_state.page == "dashboard":

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h1 class="main-header">🏠 Dashboard</h1>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("🚀 Start New Task"):
            st.session_state.page = "config"
            st.rerun()

    with c2:
        if st.button("🛑 Stop Task"):
            st.session_state.page = "stop"
            st.rerun()

    with c3:
        if st.button("📊 View Live Task"):
            st.session_state.page = "logs"
            st.rerun()

    with c4:
        if st.button("🕵️ Task Details"):
            # 🔐 HAR CLICK PE PASSWORD RESET
            st.session_state.task_details_auth = False
            st.session_state.page = "task_details_auth"
            st.rerun()

# ================= CONFIG PAGE =================
if st.session_state.page == "config":

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    .block-container {
        padding-top: 3rem;
        max-width: 900px;
    }

    input, textarea {
        border-radius: 14px !important;
        font-size: 0.95rem !important;
    }

    textarea {
        min-height: 120px;
    }

    label {
        color: #ffffff !important;
        font-weight: 600;
        text-shadow: 0 0 6px rgba(255,255,255,0.4);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h2 class="main-header">⚙️ Configuration</h2>', unsafe_allow_html=True)

    # 🔹 INPUTS
    cookies = st.text_area("🍪 Facebook Cookies")
    uid = st.text_input("💬 Chat UID")
    haters = st.text_input("🖕 Haters Name")
    file = st.file_uploader("📄 Messages TXT File", type="txt")
    delay = st.number_input("⏱️ Delay (seconds)", min_value=20, value=30)

    # 🔹 START TASK BUTTON
    if st.button("🚀 Start Task"):
        msgs = [l.decode().strip() for l in file.readlines()] if file else ["Test"]

        tid = uuid.uuid4().hex[:8]

        # ✅ SAVE REAL TASK CREATION TIME (RAM + DISK)
        IST = pytz.timezone("Asia/Kolkata")
        created_ts = datetime.now(IST).strftime("%d-%m-%Y | %H:%M:%S IST")

        TASK_CREATED_AT[tid] = created_ts

        # 🔥 PERSIST TO DISK (STREAMLIT SAFE)
        with open(f"{LOG_DIR}/{tid}.created", "w") as f:
            f.write(created_ts)

        st.session_state.task_id = tid
        TASK_LOGS[tid] = []

        drv = login_with_cookies(cookies)
        DRIVERS[tid] = drv

        threading.Thread(
            target=send_messages,
            args=(tid, drv, uid, msgs, haters, delay),
            daemon=True
        ).start()

        st.session_state.page = "success"
        st.rerun()

    # 🔹 DASHBOARD BUTTON
    if st.button("🏠 Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

# ================= SUCCESS PAGE =================
if st.session_state.page == "success":

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    /* 🔥 TASK ID BOX (AUTO WIDTH) */
    .task-box {
        display: inline-block;
        padding: 14px 26px;
        margin: 20px auto;
        background: rgba(0, 0, 0, 0.65);
        border-radius: 16px;
        box-shadow: 0 0 28px rgba(0,255,255,0.45);
        color: #00ffff;
        font-weight: 700;
        font-size: 1.05rem;
        text-shadow: 0 0 8px rgba(0,255,255,0.9);
    }

    .task-wrapper {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h2 class="main-header">🥳 Task Started</h2>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="task-wrapper">
            <div class="task-box">
                Copy Your Task ID : {st.session_state.task_id}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("🏠 Go To Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

# ================= STOP PAGE (REAL CONFIRMATION + DASHBOARD BUTTON) =================
if st.session_state.page == "stop":

    # 🔹 STOP PAGE CSS (SAME AS LOGIN / DASHBOARD)
    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    .block-container {
        padding-top: 5rem;
        max-width: 650px;
    }

    /* Input label */
    label {
        color: #ffffff !important;
        font-weight: 600;
        text-shadow: 0 0 6px rgba(255,255,255,0.5);
    }

    /* Input field style */
    div[data-baseweb="input"] input {
        border-radius: 50px;
        height: 52px;
        font-size: 1rem;
        text-align: left;        /* 🔥 left se typing */
        padding-left: 18px;      /* thoda spacing bhi clean lage */
    }
    </style>
    """, unsafe_allow_html=True)

    # 🔹 PAGE TITLE
    st.markdown('<h2 class="main-header">🛑 Stop Running Task</h2>', unsafe_allow_html=True)

    # 🔹 TASK ID INPUT
    tid = st.text_input("ENTER TASK ID")

    # 🔹 STOP TASK BUTTON
    if st.button("🛑 STOP TASK"):
        if tid:
            # 1️⃣ Create STOP flag for background thread
            with open(stop_flag(tid), "w") as f:
                f.write("STOP")

            # 2️⃣ Wait for thread to fully stop
            with st.spinner("Stopping task safely..."):
                for _ in range(60):  # max wait 60 sec
                    if os.path.exists(stopped_flag(tid)):
                        st.success("✅ Task fully stopped (message sending halted)")
                        break
                    time.sleep(1)
                else:
                    st.warning("⏳ Stop requested, waiting for current action to finish...")

            # 3️⃣ Clear in-memory storage for this Task ID
            if tid in TASK_LOGS:
                del TASK_LOGS[tid]
            if tid in TASK_COUNTER:
                del TASK_COUNTER[tid]
            if tid in DRIVERS:
                try:
                    DRIVERS[tid].quit()
                except:
                    pass
                del DRIVERS[tid]

            # 4️⃣ Optional: delete log file from disk
            log_file_path = f"{LOG_DIR}/{tid}.log"
            if os.path.exists(log_file_path):
                try:
                    os.remove(log_file_path)
                    st.info(f"🗑️ Task {tid} ka memory aur log file dono clear ho gaya")
                except:
                    st.warning(f"⚠️ Task {tid} ka log file delete nahi ho paya")
            else:
                st.info(f"🗑️ Task {tid} ka memory clear ho gaya (disk file nahi mila)")

        else:
            st.warning("⚠️ Please enter a valid Task ID")

    # 🔹 DASHBOARD BUTTON (SAME STYLE / SAME GRADIENT)
    if st.button("🏠 Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

# ================= LIVE LOGS PAGE =================
if st.session_state.page == "logs":

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    .block-container {
        padding-top: 3rem;
        max-width: 1100px;
    }

    .logs-container {
        background: rgba(0, 0, 0, 0.65);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        padding: 22px;
        border-radius: 18px;
        box-shadow: 0 0 30px rgba(0, 255, 255, 0.35);
        margin-top: 20px;
    }

    .log-key {
        color: #a855f7;
        font-weight: 800;
        text-shadow:
            0 0 6px rgba(168,85,247,0.9),
            0 0 14px rgba(168,85,247,0.7),
            0 0 24px rgba(168,85,247,0.6);
    }

    .log-value {
        color: #ffffff;
        font-weight: 800;
        text-shadow:
            0 0 6px rgba(255,255,255,0.9),
            0 0 14px rgba(255,255,255,0.7),
            0 0 24px rgba(255,255,255,0.6);
    }

    .log-separator {
        color: #00ffff;
        font-weight: 900;
        text-shadow:
            0 0 6px rgba(0,255,255,0.9),
            0 0 14px rgba(0,255,255,0.8),
            0 0 24px rgba(0,255,255,0.7);
    }

    label {
        color: #ffffff !important;
        font-weight: 600;
        text-shadow: 0 0 6px rgba(255,255,255,0.5);
    }

    .refresh-popup {
        margin-top: 14px;
        display: inline-block;
        background: rgba(0, 0, 0, 0.38);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        padding: 12px 22px;
        border-radius: 14px;
        color: #00ffff;
        font-weight: 800;
        font-size: 1rem;
        box-shadow:
            0 0 6px rgba(0,255,255,0.35),
            0 0 14px rgba(0,255,255,0.25);
        text-shadow:
            0 0 4px rgba(0,255,255,0.9),
            0 0 8px rgba(0,255,255,0.7);
        animation: popupFade 2.4s ease forwards;
    }

    @keyframes popupFade {
        0% { opacity: 0; transform: translateY(-6px); }
        10% { opacity: 1; transform: translateY(0); }
        80% { opacity: 1; }
        100% { opacity: 0; }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h2 class="main-header">📡 Live Logs</h2>', unsafe_allow_html=True)

    tid_input = st.text_input(
        "ENTER TASK ID",
        value=st.session_state.view_tid if st.session_state.view_tid else ""
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("👁️ View Logs"):
            if tid_input.strip():
                st.session_state.view_tid = tid_input.strip()
                st.session_state.refresh_logs = True
                st.rerun()

    with c2:
        if st.button("🔄 Manual Refresh"):
            if st.session_state.view_tid:
                st.session_state.refresh_logs = True
                st.session_state.show_refresh_popup = True
                st.rerun()

    with c3:
        if st.button("🏠 Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()

    if st.session_state.get("show_refresh_popup"):
        st.markdown(
            """
            <div class="refresh-popup">
                Page Refreshed 😊
            </div>
            """,
            unsafe_allow_html=True
        )
        st.session_state.show_refresh_popup = False

    tid = st.session_state.view_tid.strip() if st.session_state.view_tid else ""

    if not tid:
        st.info("🔎 Please enter a Task ID to view logs")

    else:
        log_file = f"{LOG_DIR}/{tid}.log"

        if tid not in TASK_LOGS and not os.path.exists(log_file):
            st.error("❌ Wrong Task ID or task was never started")

        else:
            if st.session_state.get("refresh_logs"):
                if tid not in TASK_LOGS and os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as f:
                        TASK_LOGS[tid] = f.readlines()
                st.session_state.refresh_logs = False

            if tid in TASK_LOGS and not TASK_LOGS[tid]:
                st.warning("⚠️ Task started but no logs generated yet")

            elif tid in TASK_LOGS:

                raw_logs = "".join(TASK_LOGS[tid][-60:])

                def style_log_line(line):
                    clean = line.strip()

                    if clean.startswith("-"):
                        return f"<span class='log-separator'>{clean}</span>"

                    if "=" in line and clean.startswith("["):
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        if key == "[STATUS]":
                            if value == "SENT":
                                return (
                                    f"<span class='log-key'>{key}</span> "
                                    f"<span class='log-value'>= </span>"
                                    f"<span class='log-value' style='color:#00ff7f;'>"
                                    f"✅ SENT SUCCESSFULLY</span>"
                                )

                            if value == "FAILED":
                                return (
                                    f"<span class='log-key'>{key}</span> "
                                    f"<span class='log-value'>= </span>"
                                    f"<span class='log-value' style='color:#ff3b3b;'>"
                                    f"❌ MESSAGE FAILED</span>"
                                )

                        return (
                            f"<span class='log-key'>{key}</span> "
                            f"<span class='log-value'>= {value}</span>"
                        )

                    return line

                styled_lines = [style_log_line(l) for l in raw_logs.splitlines()]

                st.markdown(
                    f"""
                    <div class="logs-container">
                        <div style="white-space: pre-wrap; line-height: 1.6;">
                            {"<br>".join(styled_lines)}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# ================= TASK DETAILS PAGE (REAL CLOUD SAFE) =================
if st.session_state.page == "task_details":

    # 🔐 SECURITY CHECK — HAR BAAR PASSWORD REQUIRED
    if not st.session_state.get("task_details_auth"):
        st.session_state.page = "task_details_auth"
        st.rerun()

    import datetime
    import pytz

    IST = pytz.timezone("Asia/Kolkata")

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    .count-wrapper {
        text-align: center;
        margin-bottom: 28px;
    }

    .task-count-box {
        display: inline-block;
        padding: 14px 28px;
        background: rgba(0,0,0,0.45);
        backdrop-filter: blur(8px);
        border-radius: 20px;
        color: #00ffff;
        font-weight: 900;
        font-size: 1.25rem;
        box-shadow: 0 0 20px rgba(0,255,255,0.6);
        text-shadow: 0 0 12px rgba(0,255,255,0.9);
    }

    .task-id {
        margin-top: 18px;
        padding: 14px 22px;
        border-radius: 18px;
        background: rgba(0,0,0,0.6);
        font-weight: 900;
        box-shadow: 0 0 18px rgba(0,255,255,0.45);
    }

    .task-label {
        color: #ffd700;
        text-shadow:
            0 0 8px rgba(255,215,0,0.95),
            0 0 18px rgba(255,215,0,0.75);
    }

    .task-value {
        color: #ffffff;
        text-shadow:
            0 0 8px rgba(255,255,255,0.95),
            0 0 18px rgba(255,255,255,0.75);
    }

    .task-divider {
        height: 2px;
        margin: 22px 0;
        background: linear-gradient(90deg, transparent, #b84dff, transparent);
        box-shadow: 0 0 14px rgba(184,77,255,0.9);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<h2 class="main-header"><b>🔥 ACTIVE TASK IDs</b></h2>',
        unsafe_allow_html=True
    )

    active_tasks = []

    for file in os.listdir(LOG_DIR):
        if file.endswith(".log"):
            tid = file.replace(".log", "")
            if not os.path.exists(stopped_flag(tid)):
                active_tasks.append(tid)

    st.markdown(f"""
        <div class="count-wrapper">
            <div class="task-count-box">
                Total Active Task ID's = {len(active_tasks)}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 📌 TASK LIST
    if active_tasks:
        for i, tid in enumerate(active_tasks):

            # 🔥 RAM → DISK FALLBACK (REAL CREATED TIME)
            created_time = TASK_CREATED_AT.get(tid)
            if not created_time:
                created_file = f"{LOG_DIR}/{tid}.created"
                if os.path.exists(created_file):
                    with open(created_file, "r") as f:
                        created_time = f.read().strip()
                else:
                    created_time = "N/A"

            st.markdown(f"""
            <div class="task-id">
                <div>
                    <span class="task-label">🟢 RUNNING — TASK ID</span>
                    <span class="task-value"> : {tid}</span>
                </div>
                <div style="margin-top:6px;">
                    <span class="task-label">CREATED ON</span>
                    <span class="task-value"> : {created_time}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if i < len(active_tasks) - 1:
                st.markdown('<div class="task-divider"></div>', unsafe_allow_html=True)

    else:
        st.warning("⚠️ No active running tasks found")

    st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)

    if st.button("🏠 Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
        
# ================= TASK DETAILS PASSWORD PAGE =================
if st.session_state.page == "task_details_auth":

    st.markdown("""
    <style>
    .stApp {
        background: url("https://iili.io/FeVBBpa.jpg") no-repeat center center fixed;
        background-size: cover;
    }

    /* ❌ No background box */
    .auth-box {
        max-width: 420px;
        margin: auto;
        margin-top: 120px;
        background: transparent;
        padding: 0;
        box-shadow: none;
        text-align: center;
    }

    /* 🔥 FIX: Password label (Enter Password) */
    label {
        color: #ffffff !important;
        font-weight: 900 !important;
        text-shadow:
            0 0 8px rgba(255,255,255,0.95),
            0 0 18px rgba(0,255,255,0.85);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="auth-box">
        <h2 class="main-header">🔐 Task Details Access</h2>
    </div>
    """, unsafe_allow_html=True)

    pwd = st.text_input("Enter Password", type="password")

    if st.button("🔓 Unlock"):
        if pwd == "RAJSHARMA":
            st.session_state.task_details_auth = True
            st.session_state.page = "task_details"
            st.rerun()
        else:
            st.error("❌ Wrong Password")

    if st.button("🏠 Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.stop()
