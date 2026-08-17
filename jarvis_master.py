import os
import json
import re
import shutil
import subprocess
import asyncio
import sqlite3
import datetime
import requests
import psutil
import html
import threading
import time
import io
import pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx
import sys
import traceback
import base64
import numpy as np
import logging
from openwakeword.model import Model
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from gtts import gTTS
from PIL import Image
from bs4 import BeautifulSoup
from google import genai
import chromadb
from pypdf import PdfReader
from stark_sandbox import StarkSandboxManager
from apscheduler.schedulers.background import BackgroundScheduler
from duckduckgo_search import DDGS
from playwright.async_api import async_playwright

# --- FASTAPI & MIDDLEWARE IMPORTS ---
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
import uvicorn

# ==========================================
# KONFIGURASI UTAMA & STARK SECURITY STATE
# ==========================================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.getcwd()
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
MODEL_NAME = "gemini-3.6-flash"
sandbox_manager = StarkSandboxManager()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JarvisServer")
app = FastAPI()
IS_LOCKDOWN = False



def load_agentic_squad_orchestrator():
    """Load AgenticSquadOrchestrator without crashing when the module is unavailable."""
    try:
        module_name = "orchestrator"
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)

        module = __import__(module_name, fromlist=["AgenticSquadOrchestrator"])
        return getattr(module, "AgenticSquadOrchestrator", None)
    except Exception:
        return None

LOCAL_COMMAND_QUEUE = []
LOCAL_COMMAND_RESULT = None
CLIENT_SECRET_KEY = os.getenv("STARK_SECRET_KEY")
ACTIVE_HUD_CONNECTIONS = []

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {'tools': [{'google_search': {}}]}

JARVIS_PERSONA = """
Kamu adalah J.A.R.V.I.S., asisten AI pribadi super canggih, adaptif, cerdas, dan sangat loyal milik Bos (Mr. Stark).

GAYA BAHASA & KEPRIBADIAN:
1. BAHASA BILINGUAL & ADAPTIF:
   - Secara otomatis sesuaikan bahasa jawabanmu berdasarkan bahasa yang digunakan Bos atau konteks percakapan (Bahasa Indonesia atau Bahasa Inggris).
   - Jika Bos bertanya dalam Bahasa Indonesia, jawab dalam Bahasa Indonesia yang santai, luwes, dan alami.
   - Jika Bos bertanya dalam Bahasa Inggris, jawab dengan Bahasa Inggris yang lancar, presisi, dan natural ("At your service, Sir/Boss!").
2. PANGGILAN KHAS:
   - Panggil pengguna dengan sebutan "Bos" atau "Sir".
3. GAYA KOMUNIKASI:
   - Tampil cerdas, responsif, berkelas, dan miliki sedikit sentuhan kecerdasan/humor khas J.A.R.V.I.S.
4. ATURAN TAMPILAN TEKS:
   - JANGAN gunakan simbol pagar (#) untuk header.
   - JANGAN gunakan simbol bintang (*) berlebihan. Tulis jawaban dalam paragraf atau poin sederhana agar rapi di layar chat.
"""

# ==========================================
# DATABASE & MEMORY ENGINE
# ==========================================
MEMORY_DB_PATH = os.path.join(BASE_DIR, "jarvis_memory.db")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
vector_collection = chroma_client.get_or_create_collection(name="jarvis_knowledge")

def init_memory_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS long_term_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, status TEXT DEFAULT 'Pending', due TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e: 
        print(f"[!] Warning DB: {e}")

init_memory_db()

def save_memory(category: str, content: str):
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO long_term_memory (category, content) VALUES (?, ?)", (category, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Save Memory Error: {e}")

def add_to_vector_db(text: str, doc_id: str, metadata: dict = None):
    try:
        vector_collection.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[metadata or {"source": "user_chat"}]
        )
        return True
    except Exception as e:
        print(f"[!] Error ChromaDB Add: {e}")
        return False

def search_vector_db(query: str, n_results: int = 3) -> str:
    try:
        results = vector_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        docs = results.get('documents', [[]])[0]
        if docs:
            return "\n[PENGETAHUAN TERKAIT DARI CHROMADB]:\n" + "\n".join([f"• {d}" for d in docs])
        return ""
    except Exception as e:
        print(f"[!] Error ChromaDB Search: {e}")
        return ""

def process_pdf_document(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        extracted_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                extracted_text += f"\n--- Halaman {i+1} ---\n" + text
        
        doc_id = f"pdf_{os.path.basename(pdf_path)}_{int(time.time())}"
        add_to_vector_db(extracted_text[:4000], doc_id, {"source": os.path.basename(pdf_path)})
        return f"Dokumen `{os.path.basename(pdf_path)}` berhasil dipelajari dan disimpan ke memori ChromaDB!"
    except Exception as e:
        return f"Gagal membaca PDF: {e}"

def get_all_memories() -> str:
    if not os.path.exists(MEMORY_DB_PATH): return "Tidak ada memori."
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT category, content FROM long_term_memory ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        return "\n".join([f"- [{cat}] {cont}" for cat, cont in rows]) if rows else "Belum ada memori."
    except Exception as e: 
        return f"Error DB: {e}"

def handle_sandbox_command(user_input: str) -> str:
    global sandbox_manager
    if "buat file" in user_input.lower() and "sandbox" in user_input.lower():
        filename = "temp_fitur.py"
        content = "print('Halo dari Sandbox!')" 
        path = sandbox_manager.create_canvas_file(filename, content)
        return f"📦 File dibuat di sandbox: {path}"
    elif "tes sandbox" in user_input.lower():
        success, msg = sandbox_manager.test_sandbox_file("temp_fitur.py")
        return f"🧪 Status Uji: {msg}"
    return "Perintah sandbox tidak dikenali, Bos."

# ==========================================
# PROJECT T.A.C.H.I.: AUTO-JOURNALING ENGINE
# ==========================================
def generate_daily_journal_job():
    if IS_LOCKDOWN: return

    print("🧠 [T.A.C.H.I.] Mengompilasi Jurnal Harian Aktivitas Proyek Bos...")
    today_str = datetime.datetime.now().strftime("%A, %d %B %Y")
    recent_memories = get_all_memories()
    
    prompt = f"""
Kamu adalah T.A.C.H.I., sistem memori tingkat tinggi Jarvis.
Tugasmu adalah membuat Ringkasan Jurnal Harian untuk Bos (Mr. Stark) berdasarkan catatan memori & aktivitas hari ini.

Catatan Memori Terakhir:
{recent_memories}

Tuliskan Jurnal Harian untuk tanggal {today_str} yang berisi:
1. Ringkasan Progres Utama Hari Ini.
2. Fitur / Perubahan yang Berhasil Dideploy.
3. Rekomendasi/Catatan untuk Esok Hari.

Tulis dengan gaya bahasa Jarvis yang berkelas, padat, dan panggil "Bos".
"""
    journal_result = ask_jarvis(prompt)
    save_memory("DAILY_JOURNAL", f"[{today_str}] {journal_result[:500]}")
    add_to_vector_db(journal_result, f"journal_{int(time.time())}", {"type": "daily_journal", "date": today_str})
    
    # Broadcast jurnal harian langsung ke HUD HP aktif
    journal_alert = f"📖 *STARK INDUSTRIES DAILY JOURNAL ({today_str})*\n\n{journal_result}"
    for ws in ACTIVE_HUD_CONNECTIONS:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json({"type": "text_chunk", "content": journal_alert}), asyncio.get_event_loop())
        except:
            pass

# ==========================================
# WEB SCRAPER HELPER
# ==========================================
def scrape_web_page(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.extract()
            text = soup.get_text(separator=' ')
            clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
            return ' '.join(clean_lines)[:4000]
        return f"Gagal mengambil halaman web (HTTP Status {resp.status_code})"
    except Exception as e:
        return f"Error scraping web: {e}"

# ==========================================
# OTAK UTAMA JARVIS
# ==========================================
def ask_jarvis(user_msg: str) -> str:
    global IS_LOCKDOWN
    if IS_LOCKDOWN:
        return "🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Semua fungsi Jarvis sedang terkunci demi keamanan. Kirim perintah unlock untuk membuka kembali."

    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    time_context = now.strftime("%A, %d %B %Y - Jam %H:%M WIB")
    memories = get_all_memories()
    vector_context = search_vector_db(user_msg)

    urls = re.findall(r'https?://[^\s]+', user_msg)
    web_context = ""
    if urls:
        target_url = urls[0]
        scraped_content = scrape_web_page(target_url)
        web_context = f"\n[HASIL BACAAN WEB DARI URL {target_url}]:\n{scraped_content}\n"

    system_prompt = f"""
{JARVIS_PERSONA}

[KONTEKS WAKTU SISTEM REAL-TIME]:
Hari & Tanggal Sekarang: {time_context}

[MEMORI TERSEMPAN]:
{memories}
{vector_context}
{web_context}

Pesan Pengguna: {user_msg}
"""
    MODEL_CANDIDATES = [
        "gemini-3.6-flash",
        "gemini-3.0",
        "gemini-3.1-lite",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite"
    ]

    for model_name in MODEL_CANDIDATES:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=system_prompt,
                config=GROUNDING_CONFIG
            )
            clean_text = response.text
            clean_text = re.sub(r'#+\s*', '', clean_text)
            clean_text = re.sub(r'^\*\s+', '• ', clean_text, flags=re.MULTILINE)
            clean_text = clean_text.replace('**', '').replace('*', '')
            return clean_text
        except Exception as e:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=system_prompt
                )
                clean_text = response.text
                clean_text = re.sub(r'#+\s*', '', clean_text)
                clean_text = re.sub(r'^\*\s+', '• ', clean_text, flags=re.MULTILINE)
                clean_text = clean_text.replace('**', '').replace('*', '')
                return clean_text
            except Exception as e2:
                continue

    return "Maaf Bos, server Google sedang membatasi kuota API di wilayah ini. Mohon tunggu 30 detik ya! ⏳"

def ask_jarvis_with_image(image_bytes: bytes, user_prompt: str = "") -> str:
    global IS_LOCKDOWN
    if IS_LOCKDOWN: return "🔒 STARK LOCKDOWN ACTIVE."
    try:
        image = Image.open(io.BytesIO(image_bytes))
        prompt = user_prompt if user_prompt else "Analisis foto/screenshot ini dan berikan penjelasan atau solusi secara detail, Bos."
        system_prompt = f"{JARVIS_PERSONA}\n\nInstruksi Analisis Gambar: {prompt}"

        MODEL_CANDIDATES = ["gemini-3.6-flash", "gemini-3.0", "gemini-3.5-flash"]
        for model_name in MODEL_CANDIDATES:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[image, system_prompt]
                )
                clean_text = response.text
                clean_text = re.sub(r'#+\s*', '', clean_text)
                clean_text = re.sub(r'^\*\s+', '• ', clean_text, flags=re.MULTILINE)
                clean_text = clean_text.replace('**', '').replace('*', '')
                return clean_text
            except Exception as e:
                continue
        return "Maaf Bos, gagal menganalisis foto tersebut."
    except Exception as e:
        return f"🚨 Error membaca gambar: {e}"

def detect_language(text: str) -> str:
    english_keywords = {"the", "is", "and", "to", "a", "of", "in", "for", "on", "that", "you", "it", "with", "as", "all", "have", "more"}
    indonesian_keywords = {"dan", "yang", "di", "ke", "dari", "ini", "itu", "untuk", "dengan", "adalah", "tidak", "pada", "dalam", "saya", "kamu", "bos"}
    
    words = set(re.findall(r'\b\w+\b', text.lower()))
    en_matches = len(words.intersection(english_keywords))
    id_matches = len(words.intersection(indonesian_keywords))
    
    return 'en' if en_matches > id_matches else 'id'

def generate_gtts_base64_sync(text: str) -> str:
    lang_code = detect_language(text)
    tts = gTTS(text=text, lang=lang_code)
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return base64.b64encode(mp3_fp.read()).decode('utf-8')

def test_code_execution(file_path):
    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", file_path],
            capture_output=True, text=True, check=True
        )
        return True, "Syntax Valid!"
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def generate_and_test_code(prompt_request: str, target_filename: str = "generated_app.py") -> tuple[bool, str, str]:
    error_context = ""
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        full_prompt = f"Buatkan kode Python murni tanpa markdown berdasarkan instruksi: {prompt_request}\n{error_context}"
        code_result = ask_jarvis(full_prompt)
        code_result = re.sub(r'```python|```', '', code_result).strip()
        
        with open(target_filename, "w", encoding="utf-8") as f:
            f.write(code_result)
            
        is_success, log_msg = test_code_execution(target_filename)
        if is_success:
            return True, f"✅ Code Agent Success! File `{target_filename}` lolos tes sintaks.", target_filename
        else:
            error_context = f"PERBAIKAN ERROR PERCOBAAN SEBELUMNYA: {log_msg}"
            
    return False, f"🚨 Code Agent gagal setelah {max_attempts}x percobaan.", target_filename

async def computer_vision_snapshot_analysis(prompt_instruction: str = "Deskripsikan apa yang terlihat di depan kamera saat ini secara detail, Bos.") -> str:
    if not CV2_AVAILABLE:
        return "⚠️ Modul OpenCV tidak tersedia di environment server ini. Fitur /vision khusus untuk dijalankan di host PC lokal, Bos."

    print("👁️ [COMPUTER VISION] Mengakses lensa kamera lokal...")
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "🚨 Gagal mengakses lensa kamera (Webcam tidak ditemukan atau sedang digunakan aplikasi lain)."

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return "🚨 Gagal mengambil frame gambar dari kamera."

        snap_filename = f"vision_snap_{int(time.time())}.jpg"
        cv2.imwrite(snap_filename, frame)

        with open(snap_filename, "rb") as img_file:
            img_bytes = img_file.read()

        analysis_result = ask_jarvis_with_image(img_bytes, prompt_instruction)

        if os.path.exists(snap_filename):
            os.remove(snap_filename)

        return analysis_result

    except Exception as e:
        print(f"🚨 [COMPUTER VISION ERROR] {e}")
        return f"🚨 Terjadi kesalahan sistem penglihatan komputer: {e}"

# ==========================================
# MARK-UI: DIAGRAM GENERATOR ENGINE
# ==========================================
def generate_system_diagram(nodes_and_edges: list, title: str = "System Architecture") -> str:
    try:
        G = nx.DiGraph()
        for edge in nodes_and_edges:
            if len(edge) == 2:
                G.add_edge(edge[0], edge[1])

        plt.figure(figsize=(10, 6))
        pos = nx.spring_layout(G, k=0.9)
        
        nx.draw_networkx_nodes(G, pos, node_size=3000, node_color="#1f2937", alpha=0.9)
        nx.draw_networkx_edges(G, pos, width=2, alpha=0.7, edge_color="#3b82f6", arrowsize=20)
        nx.draw_networkx_labels(G, pos, font_size=10, font_color="white", font_weight="bold", font_family="sans-serif")

        plt.title(title, fontsize=14, fontweight='bold', color="#111827")
        plt.axis('off')
        plt.tight_layout()

        output_path = f"diagram_{int(time.time())}.png"
        plt.savefig(output_path, dpi=200, bbox_inches='tight')
        plt.close()
        return output_path
    except Exception as e:
        print(f"[!] Diagram Error: {e}")
        return ""

# ==========================================
# PROJECT HEPHAESTUS: DEVOPS & GIT ENGINE
# ==========================================
def execute_git_workflow(action: str, commit_msg: str = "") -> str:
    try:
        if action == "status":
            res = subprocess.run(["git", "status"], capture_output=True, text=True, check=True)
            return f"📋 *HEPHAESTUS GIT STATUS:*\n```\n{res.stdout}\n```"
        elif action == "pull":
            res = subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)
            return f"📥 *HEPHAESTUS GIT PULL:*\n```\n{res.stdout}\n```"
        elif action == "push":
            if not commit_msg:
                commit_msg = f"Auto-deploy by Jarvis HEPHAESTUS - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(["git", "add", "."], capture_output=True, text=True, check=True)
            commit_res = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
            push_res = subprocess.run(["git", "push"], capture_output=True, text=True, check=True)
            return f"🚀 *HEPHAESTUS GIT PUSH SUCCESSFUL!*\n\n*Commit Message:* `{commit_msg}`\n\n*Log Output:*\n```\n{commit_res.stdout}\n{push_res.stdout}\n```"
        else:
            return "Action tidak dikenali, Bos. Gunakan `status`, `pull`, atau `push`."
    except subprocess.CalledProcessError as e:
        return f"🚨 *HEPHAESTUS GIT ERROR:*\n```\n{e.stderr or e.stdout}\n```"
    except Exception as e:
        return f"🚨 *EXECUTION ERROR:* {e}"

def veronica_auto_fix_bug(error_traceback: str):
    print("🛡️ [VERONICA] Fatal Error terdeteksi! Mengaktifkan A.S.C.A.R. Auto-Hotpatch...")
    prompt = (
        f"[VERONICA PROTOCOL: RUNTIME CRASH ANALYSIS]\n"
        f"Terjadi crash pada sistem. Berikut stack trace error-nya:\n\n"
        f"{error_traceback}\n\n"
        f"Tugasmu:\n"
        f"1. Sebutkan NAMA FILE Python yang menjadi sumber error utama (contoh: jarvis_master.py) di baris paling pertama (HANYA nama file murni tanpa markdown atau tanda petik).\n"
        f"2. Di baris berikutnya, berikan penjelasan singkat dan ringkas mengapa error terjadi."
    )
    try:
        analysis = ask_jarvis(prompt)
        lines = [line.strip() for line in analysis.strip().split('\n') if line.strip()]
        target_file = ""
        if lines:
            target_file = lines[0].replace('`', '').replace("'", "").replace('"', '').strip()

        healed = False
        heal_msg = ""
        if target_file and os.path.exists(target_file) and target_file.endswith('.py'):
            from ascar_engine import ASCARMaintenanceEngine
            engine = ASCARMaintenanceEngine()
            healed, heal_msg = engine.auto_repair_file(target_file, error_traceback)
            status_symbol = "✅ HOTPATCH SUCCESS" if healed else "🚨 HOTPATCH FAILED (ROLLBACKED)"
            alert_text = (
                f"🛡️ **[VERONICA ➔ A.S.C.A.R. AUTONOMOUS HOTPATCH]**\n"
                f"*Status:* `{status_symbol}`\n"
                f"*File Target:* `{target_file}`\n"
                f"*Log:* `{heal_msg}`\n\n"
                f"📄 *Detail Error Trace:* `{error_traceback[-250:].strip()}`"
            )
        else:
            alert_text = f"🛡️ **[VERONICA BUG HUNTER ALERT: SYSTEM CRASH DETECTED]**\n\n{analysis}"

        try:
            local_port = os.getenv("PORT", 8080)
            requests.post(
                f"http://127.0.0.1:{local_port}/client/proactive_alert",
                headers={"Authorization": CLIENT_SECRET_KEY, "Content-Type": "application/json"},
                json={"alert_message": alert_text},
                timeout=5
            )
        except Exception as e:
            print(f"[!] Gagal mem-forward Veronica ke HUD: {e}")
    except Exception as e:
        print(f"🚨 [VERONICA HOTPATCH ERROR]: {e}")

def veronica_global_exception_handler(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"🚨 [CRASH DETECTED]:\n{error_msg}")
    threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()

sys.excepthook = veronica_global_exception_handler

# ==========================================
# PROJECT ULTRON-SENTINEL: UPTIME & HEALTH MONITOR
# ==========================================
MONITORED_TARGETS = [
    {"name": "Railway FastAPI Server", "url": "https://worker-production-792b.up.railway.app"}
]

def ultron_sentinel_ping_job():
    if IS_LOCKDOWN: return
    print("🛰️ [ULTRON-SENTINEL] Running 24/7 Uptime & Endpoint Health Check...")
    failed_services = []
    
    for target in MONITORED_TARGETS:
        name = target["name"]
        url = target["url"]
        if "xxxx" in url: continue
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            latency = round((time.time() - start_time) * 1000, 2)
            if response.status_code >= 400:
                failed_services.append(f"• *{name}*: HTTP Status {response.status_code} ({url})")
            else:
                print(f"✅ [SENTINEL] {name} is OK ({latency}ms)")
        except Exception as e:
            failed_services.append(f"• *{name}*: Unreachable ({e})")

    if failed_services:
        alert_body = "\n".join(failed_services)
        alarm_msg = f"🚨 *ULTRON-SENTINEL ALARM: SERVICE DOWN DETECTED!*\n\n{alert_body}\n\n*Action Required:* Mohon periksa server/koneksi Bos!"
        for ws in ACTIVE_HUD_CONNECTIONS:
            try:
                asyncio.run_coroutine_threadsafe(ws.send_json({"type": "text_chunk", "content": alarm_msg}), asyncio.get_event_loop())
            except:
                pass

# ==========================================
# NATURAL LANGUAGE ROUTER TERPADU (ALL-IN-ONE)
# ==========================================
def route_natural_language_command(user_message: str) -> dict:
    global LOCAL_COMMAND_QUEUE
    msg_lower = user_message.lower()

    if any(k in msg_lower for k in ["baca layar", "lihat layar", "periksa layar", "layar pc", "screenshot pc", "layar laptop"]):
        payload = {"type": "SCREEN_VISION", "prompt": user_message}
        LOCAL_COMMAND_QUEUE.append(payload)
        return {"status": "EXECUTE", "reply": "Mengambil screenshot layar PC secara langsung..."}

    elif any(k in msg_lower for k in ["besarkan volume", "tambah volume", "volume naik"]):
        LOCAL_COMMAND_QUEUE.append({"type": "MEDIA_CONTROL", "action": "vol_up"})
        return {"status": "EXECUTE", "reply": "Volume PC dinaikkan, Bos."}

    elif any(k in msg_lower for k in ["kecilkan volume", "kurangi volume", "volume turun"]):
        LOCAL_COMMAND_QUEUE.append({"type": "MEDIA_CONTROL", "action": "vol_down"})
        return {"status": "EXECUTE", "reply": "Volume PC dikurangi, Bos."}

    elif any(k in msg_lower for k in ["mute pc", "matikan suara pc", "unmute pc"]):
        LOCAL_COMMAND_QUEUE.append({"type": "MEDIA_CONTROL", "action": "vol_mute"})
        return {"status": "EXECUTE", "reply": "Status mute audio PC diubah."}

    elif any(k in msg_lower for k in ["pause musik", "play musik", "pause lagu", "play lagu"]):
        LOCAL_COMMAND_QUEUE.append({"type": "MEDIA_CONTROL", "action": "play_pause"})
        return {"status": "EXECUTE", "reply": "Status pemutar media PC diperbarui."}

    elif "sandbox" in msg_lower:
        reply = handle_sandbox_command(user_message)
        return {"status": "EXECUTE", "reply": reply}

    elif "matikan pc" in msg_lower or "shutdown pc" in msg_lower:
        numbers = re.findall(r'\d+', msg_lower)
        minutes = int(numbers[0]) if numbers else 1
        LOCAL_COMMAND_QUEUE.append({"type": "SHUTDOWN_TIMER", "minutes": minutes})
        return {"status": "EXECUTE", "reply": f"Siap Bos. PC dijadwalkan akan mati otomatis dalam {minutes} menit."}

    elif "batal shutdown" in msg_lower or "batalkan mati" in msg_lower:
        LOCAL_COMMAND_QUEUE.append({"type": "SHUTDOWN_CANCEL"})
        return {"status": "EXECUTE", "reply": "Penjadwalan shutdown PC berhasil dibatalkan, Bos!"}

    elif any(k in msg_lower for k in ["indeks folder", "pindai kodingan", "indeks dokumen"]):
        LOCAL_COMMAND_QUEUE.append({"type": "START_FILE_INDEXING"})
        return {"status": "EXECUTE", "reply": "Memulai pemindaian folder kerja dan pengindeksan dokumen lokal ke ChromaDB..."}

    elif "kirim email" in msg_lower or "tulis email" in msg_lower:
        payload = {"type": "SEND_EMAIL", "raw_prompt": user_message}
        LOCAL_COMMAND_QUEUE.append(payload)
        return {"status": "EXECUTE", "reply": "Memproses pembuatan dan pengiriman email..."}

    elif "kirim wa" in msg_lower or "whatsapp ke" in msg_lower:
        payload = {"type": "SEND_WHATSAPP", "raw_prompt": user_message}
        LOCAL_COMMAND_QUEUE.append(payload)
        return {"status": "EXECUTE", "reply": "Instruksi pengiriman WhatsApp diterima, memproses pesan..."}

    elif "tulis word" in msg_lower or "buat dokumen" in msg_lower or "edit word" in msg_lower:
        payload = {"type": "WORD_ACTION", "raw_prompt": user_message}
        LOCAL_COMMAND_QUEUE.append(payload)
        return {"status": "EXECUTE", "reply": "Memproses perintah dokumen Word di PC lokal..."}

    elif "cek aplikasi" in msg_lower or "aplikasi terbuka" in msg_lower or "proses pc" in msg_lower:
        LOCAL_COMMAND_QUEUE.append({"type": "CHECK_RUNNING_APPS"})
        return {"status": "EXECUTE", "reply": "Memindai seluruh aplikasi dan jendela yang sedang terbuka di PC..."}

    elif "buat diagram" in msg_lower or "gambar diagram" in msg_lower:
        return {"status": "EXECUTE_DIAGRAM", "reply": "Memproses pembuatan diagram secara visual..."}

    elif any(k in msg_lower for k in ["cek hardware", "hardware metrics", "penggunaan pc", "status server"]):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        metrics_msg = (
            f"💻 STARK SYSTEM METRICS:\n"
            f"• CPU Usage: {cpu}%\n"
            f"• RAM Usage: {ram}%\n"
            f"• Disk Usage: {disk}%\n"
            f"• Status: All Systems Operational"
        )
        return {"status": "EXECUTE", "reply": metrics_msg}

    elif "git status" in msg_lower or "cek status git" in msg_lower:
        res = execute_git_workflow("status")
        return {"status": "EXECUTE", "reply": res}
        
    elif "git pull" in msg_lower or "tarik git" in msg_lower:
        res = execute_git_workflow("pull")
        return {"status": "EXECUTE", "reply": res}
        
    elif "git push" in msg_lower or "unggah ke git" in msg_lower:
        res = execute_git_workflow("push", "Auto-deploy via Voice/HUD Command")
        return {"status": "EXECUTE", "reply": res}

    elif "ingat kembali" in msg_lower or "recall memori" in msg_lower or "coba ingat" in msg_lower:
        topic = msg_lower.replace("ingat kembali", "").replace("recall memori", "").replace("coba ingat", "").strip()
        memories = search_vector_db(topic, n_results=3)
        if not memories:
            return {"status": "EXECUTE", "reply": f"Maaf Bos, tidak ada ingatan tentang '{topic}' di M.I.N.D Palace."}
        summary = ask_jarvis(f"Rangkum ingatan ini secara singkat dan padat untuk Bos tentang '{topic}': {memories}")
        return {"status": "EXECUTE", "reply": f"📖 [MEMORY RECALL]\n{summary}"}

    elif msg_lower.startswith("buatkan script") or msg_lower.startswith("tulis kode"):
        is_success, log_msg, file_path = generate_and_test_code(user_message)
        return {"status": "EXECUTE", "reply": f"📝 Code Agent Report: {log_msg}"}

    elif any(k in msg_lower for k in ["test bug", "simulasi bug", "pemicu crash", "testbug"]):
        def trigger_simulated_crash():
            try:
                _ = 100 / 0
            except Exception:
                error_msg = traceback.format_exc()
                veronica_auto_fix_bug(error_msg)
        threading.Thread(target=trigger_simulated_crash, daemon=True).start()
        return {
            "status": "EXECUTE", 
            "reply": "🧪 [SIMULASI CRASH DIPICU]: Memperhatikan respons otomatis V.E.R.O.N.I.C.A. & A.S.C.A.R. secara real-time..."
        }

    elif msg_lower.startswith("jalankan orchestrator") or msg_lower.startswith("buat fitur otonom"):
        task_goal = user_message.replace("jalankan orchestrator", "").replace("buat fitur otonom", "").strip()
        if not task_goal:
            task_goal = "Buat modul utilitas penguji sistem sederhana"
            
        def run_async_orchestration():
            orchestrator_cls = load_agentic_squad_orchestrator()
            if orchestrator_cls is None:
                local_port = os.getenv("PORT", 8080)
                requests.post(
                    f"http://127.0.0.1:{local_port}/client/proactive_alert",
                    headers={"Authorization": CLIENT_SECRET_KEY, "Content-Type": "application/json"},
                    json={"alert_message": "[AGENTIC SQUAD] Modul orchestrator tidak tersedia di lingkungan ini."},
                    timeout=10
                )
                return
            orch = orchestrator_cls(api_key=GEMINI_API_KEY)
            report = orch.orchestrate(task_goal)
            
            local_port = os.getenv("PORT", 8080)
            requests.post(
                f"http://127.0.0.1:{local_port}/client/proactive_alert",
                headers={"Authorization": CLIENT_SECRET_KEY, "Content-Type": "application/json"},
                json={"alert_message": report},
                timeout=10
            )

        threading.Thread(target=run_async_orchestration, daemon=True).start()
        return {"status": "EXECUTE", "reply": f"🤖 [AGENTIC SQUAD] Tim agen diaktifkan untuk misi: '{task_goal}'. Memulai proses di latar belakang..."}

    elif any(k in msg_lower for k in ["ascar", "audit sistem", "periksa kode", "cek repositori", "ascar run"]):
        payload = {"type": "RUN_ASCAR_DIAGNOSTIC"}
        LOCAL_COMMAND_QUEUE.append(payload)
        return {
            "status": "EXECUTE", 
            "reply": "🛡️ [A.S.C.A.R. INITIATED]: Memulai pemindaian mendalam seluruh repositori JARVIS-AGENT di PC lokal..."
        }    

    elif any(k in msg_lower for k in ["cek flutter", "inspeksi flutter", "cek dart", "ascar dart", "inspeksi dart", "scan dart"]):
        payload = {"type": "INSPECT_DART_FRONTEND"}
        LOCAL_COMMAND_QUEUE.append(payload)
        return {
            "status": "EXECUTE", 
            "reply": "🩺 **[A.S.C.A.R. DART INSPECTOR INITIATED]**\nMemeriksa & menambal seluruh berkas `.dart` di PC lokal, Sir..."
        }

    elif any(k in msg_lower for k in ["veritas", "audit sistem", "cek kesehatan", "system audit", "audit jarvis"]):
        payload = {"type": "RUN_VERITAS_DIAGNOSTIC"}
        LOCAL_COMMAND_QUEUE.append(payload)
        def run_async_veritas():
            from stark_diagnostic import StarkDiagnosticSuite
            suite = StarkDiagnosticSuite()
            report_text = suite.run_full_audit()
            local_port = os.getenv("PORT", 8080)
            requests.post(
                f"http://127.0.0.1:{local_port}/client/proactive_alert",
                headers={"Authorization": CLIENT_SECRET_KEY, "Content-Type": "application/json"},
                json={"alert_message": report_text},
                timeout=60
            )
        threading.Thread(target=run_async_veritas, daemon=True).start()
        return {
            "status": "EXECUTE", 
            "reply": "🩺 **[PROJECT V.E.R.I.T.A.S. INITIATED]**\nMemulai pemeriksaan total organ internal J.A.R.V.I.S. (Cloud & PC Lokal), Sir..."
        }

    return {"status": "CHAT_ONLY"}

# ==========================================
# PROACTIVE SCHEDULER
# ==========================================
def daily_briefing_job():
    if IS_LOCKDOWN: return
    briefing_text = ask_jarvis("Berikan briefing pagi singkat dan motivasi untuk Bos memulai hari.")
    briefing_msg = f"🌅 GOOD MORNING BRIEFING\n\n{briefing_text}"
    for ws in ACTIVE_HUD_CONNECTIONS:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json({"type": "text_chunk", "content": briefing_msg}), asyncio.get_event_loop())
        except:
            pass

scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
scheduler.add_job(daily_briefing_job, 'cron', hour=7, minute=0)
scheduler.add_job(generate_daily_journal_job, 'cron', hour=23, minute=59)
scheduler.add_job(ultron_sentinel_ping_job, 'interval', minutes=15)
scheduler.start()

# ==========================================
# FASTAPI SERVER ENGINE + SMART RESPONSE MODE
# ==========================================
web_app = FastAPI(title="Jarvis Mobile, IoT & KINETIC-UI API")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    is_voice_input: bool = False
    image_base64: Optional[str] = None

class IoTCommandRequest(BaseModel):
    device_id: str
    action: str
    secret_key: str = ""

class ProactiveAlertRequest(BaseModel):
    alert_message: str

@web_app.get("/")
def read_root():
    return {
        "status": "Jarvis Web, IoT Bridge & KINETIC-UI Online (Telegram-Free Edition)",
        "lockdown": IS_LOCKDOWN,
        "time": str(datetime.datetime.now())
    }

class AutonomousTaskRequest(BaseModel):
    task_description: str

# 1. Tambahkan struktur data Pydantic baru
class MobileErrorReport(BaseModel):
    feature: str
    error_message: str
    stack_trace: str
    platform: str

try:
    oww_model = Model(wakeword_models=["hey_jarvis_v0.1.onnx"])
    logger.info("🛡️ Model Wake Word berhasil dimuat di Server!")
except Exception as e:
    logger.error(f"🚨 Gagal memuat model: {e}")

@web_app.websocket("/ws/audio_stream")
async def audio_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("📡 Klien terhubung: Streaming audio dimulai.")
    
    try:
        while True:
            data = await websocket.receive_bytes()
            audio_array = np.frombuffer(data, dtype=np.int16)
            prediction = oww_model.predict(audio_array)
            
            if prediction["hey_jarvis_v0.1"] > 0.5:
                logger.info("🚨 'Hey Jarvis' terdeteksi di Server!")
                await websocket.send_json({
                    "event": "wake_word_triggered",
                    "status": "active"
                })
                oww_model.reset() 

    except WebSocketDisconnect:
        logger.info("🔌 Klien terputus.")
    except Exception as e:
        logger.error(f"❌ Error pada stream audio: {e}")

# 2. Tambahkan Endpoint penerima laporan
@web_app.post("/client/mobile_error_report")
async def receive_mobile_error(req: MobileErrorReport, authorization: str = Header(None)):
    if authorization != CLIENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access Denied")
    
    print(f"📱 [HUD ERROR DETECTED] Fitur: {req.feature}")
    
    # Minta J.A.R.V.I.S (LLM) menganalisis akar masalahnya
    prompt = f"""
    [A.S.C.A.R MOBILE DIAGNOSTIC PROTOCOL]
    Aplikasi Android HUD Bos mengalami kegagalan saat mencoba menjalankan fitur: '{req.feature}'.
    
    Pesan Error dari Flutter/Android: 
    {req.error_message}
    
    Stack Trace: 
    {req.stack_trace[:1500]}
    
    Tugasmu:
    Berikan analisis teknis yang tajam namun ringkas (maksimal 3-4 kalimat) mengenai kemungkinan penyebabnya (misal: kurang izin di AndroidManifest, package usang, fungsi native tidak didukung HP, dll) beserta saran perbaikannya. Gunakan gaya bahasa J.A.R.V.I.S.
    """
    
    analysis_result = ask_jarvis(prompt)
    alert_msg = f"📱 **[MOBILE HUD ERROR: {req.feature}]**\n\n{analysis_result}"
    
    # Broadcast hasil analisis langsung ke layar chat aplikasi HP
    for ws in ACTIVE_HUD_CONNECTIONS:
        try:
            await ws.send_json({"type": "text_chunk", "content": alert_msg})
            # Buat suara notifikasi
            audio_b64 = generate_gtts_base64_sync(f"Laporan kegagalan sistem pada fitur {req.feature} diterima. Saya telah mengirimkan hasil analisisnya ke layar, Bos.")
            await ws.send_json({"type": "stream_end", "audio_base64": audio_b64})
        except:
            pass
            
    return {"status": "analyzed_by_ascar"}

def plan_autonomous_task_chain(task_description: str) -> list:
    planner_prompt = f"""
Kamu adalah Chief Task Planner dari J.A.R.V.I.S.
Pecah instruksi kompleks berikut menjadi rantai langkah eksekusi terminal/shell yang logis dan aman untuk OS Windows.

Instruksi Bos: "{task_description}"

Kembalikan HANYA format JSON valid bertipe list of objects seperti contoh berikut (tanpa markdown ```json):
[
    {{"step": 1, "description": "Memeriksa status git", "command": "git status"}},
    {{"step": 2, "description": "Menjalankan tes sintaks", "command": "python -m py_compile main.py"}}
]
"""
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=planner_prompt
        )
        clean_json = re.sub(r'```json|```', '', response.text).strip()
        task_chain = json.loads(clean_json)
        return task_chain
    except Exception as e:
        print(f"[!] Planning Error: {e}")
        return [{"step": 1, "description": "Fallback Execution", "command": "echo Task planning failed"}]

@web_app.post("/agent/task_force")
def trigger_task_force(req: AutonomousTaskRequest):
    global LOCAL_COMMAND_QUEUE
    chain = plan_autonomous_task_chain(req.task_description)
    LOCAL_COMMAND_QUEUE.append({
        "type": "TASK_FORCE_CHAIN",
        "chain": chain,
        "task_name": req.task_description
    })
    return {
        "status": "planned",
        "message": f"Task Force diaktifkan. {len(chain)} langkah eksekusi dikirim ke PC lokal, Bos!",
        "planned_steps": chain
    }

@web_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if IS_LOCKDOWN:
        return {"status": "error", "reply": "🔒 STARK LOCKDOWN ACTIVE.", "audio_base64": ""}
    
    reply_text = ""
    diag_b64 = None

    if request.image_base64:
        try:
            img_bytes = base64.b64decode(request.image_base64)
            prompt_msg = request.message.strip() if request.message else "Tolong analisis gambar ini, Bos."
            reply_text = ask_jarvis_with_image(img_bytes, prompt_msg)
            if not reply_text:
                reply_text = "⚠️ Gemini Vision tidak memberikan tanggapan untuk gambar ini."
        except Exception as e:
            reply_text = f"🚨 [A.S.C.A.R. VISION ERROR]: Gagal memproses lampiran gambar -> {str(e)}"
    else:
        try:
            intent = route_natural_language_command(request.message)
            if intent.get("status") == "EXECUTE":
                reply_text = intent.get("reply")
            elif intent.get("status") == "EXECUTE_DIAGRAM":
                steps = [s.strip() for s in request.message.split("->")]
                if len(steps) > 1:
                    edges = [(steps[i], steps[i+1]) for i in range(len(steps)-1)]
                    diagram_path = generate_system_diagram(edges)
                    if diagram_path and os.path.exists(diagram_path):
                        with open(diagram_path, "rb") as f:
                            diag_b64 = base64.b64encode(f.read()).decode('utf-8')
                        os.remove(diagram_path)
                        reply_text = "Diagram berhasil di-render, Bos."
                if not reply_text:
                    reply_text = "Gagal render diagram. Gunakan format panah (->)"
            else:
                reply_text = ask_jarvis(request.message)
        except Exception as e:
            reply_text = f"🚨 [A.S.C.A.R. CORE ERROR]: Gangguan pada alur instruksi -> {str(e)}"

    audio_b64 = ""
    if request.is_voice_input and reply_text:
        try:
            audio_b64 = generate_gtts_base64_sync(reply_text)
        except Exception as e:
            print(f"[TTS WARNING] Gagal membangkitkan audio: {e}")
            audio_b64 = ""

    response_data = {
        "status": "success", 
        "reply": reply_text, 
        "audio_base64": audio_b64
    }
    if diag_b64:
        response_data["image_base64"] = diag_b64

    return response_data

@web_app.get("/status")
def status_endpoint():
    return {
        "status": "online",
        "lockdown": IS_LOCKDOWN,
        "cpu_usage": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent,
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@web_app.get("/history")
def history_endpoint():
    memories = get_all_memories()
    return {
        "status": "success",
        "memories": memories
    }

@web_app.post("/iot/control")
async def iot_control_endpoint(request: IoTCommandRequest):
    if IS_LOCKDOWN:
        return {"status": "error", "message": "System is in Lockdown"}
    print(f"📡 [STARK IOT BRIDGE] Device: {request.device_id} | Action: {request.action}")
    return {
        "status": "success",
        "device": request.device_id,
        "executed_action": request.action,
        "timestamp": str(datetime.datetime.now())
    }

@web_app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🎙️ [LIVE VOICE] Klien terhubung via WebSocket Audio Stream.")
    try:
        while True:
            data = await websocket.receive_bytes()
            if not data: continue
            response_text = ask_jarvis("Halo Bos, saya mendengarkan stream suara Anda.")
            audio_b64 = generate_gtts_base64_sync(response_text)
            await websocket.send_json({
                "status": "success",
                "reply": response_text,
                "audio_base64": audio_b64
            })
    except WebSocketDisconnect:
        print("🎙️ [LIVE VOICE] Klien terputus dari WebSocket.")
    except Exception as e:
        print(f"🚨 [LIVE VOICE ERROR] {e}")
        try: await websocket.close()
        except: pass

class DocumentIndexRequest(BaseModel):
    file_name: str
    content: str

@web_app.post("/client/index_document")
def receive_document_index(req: DocumentIndexRequest, authorization: str = Header(None)):
    if authorization != CLIENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access Denied")
    doc_id = f"local_doc_{req.file_name}_{int(time.time())}"
    success = add_to_vector_db(req.content[:4000], doc_id, {"source": req.file_name, "type": "local_code"})
    if success:
        return {"status": "indexed", "file": req.file_name}
    return {"status": "failed"}

@web_app.get("/client/poll")
def client_poll_command(authorization: str = Header(None)):
    global LOCAL_COMMAND_QUEUE
    if authorization != CLIENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access Denied: Invalid Stark Key")
    if LOCAL_COMMAND_QUEUE:
        cmd = LOCAL_COMMAND_QUEUE.pop(0)
        return {"command": cmd}
    return {"command": None}

class ClientReportRequest(BaseModel):
    output: str
    status: str

@web_app.post("/client/report")
def client_report_result(request: ClientReportRequest, authorization: str = Header(None)):
    global LOCAL_COMMAND_RESULT
    if authorization != CLIENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access Denied: Invalid Stark Key")
    LOCAL_COMMAND_RESULT = request.output
    print(f"💻 [STARK HYBRID] Laporan dari PC Lokal diterima: {request.output[:100]}...")
    return {"status": "received"}

class TelemetryRequest(BaseModel):
    location: Optional[str] = "Tidak diketahui"
    temperature: Optional[str] = "--"
    weather: Optional[str] = "Cerah"
    battery_level: Optional[int] = 0
    is_charging: Optional[bool] = False
    events: Optional[list] = []

@web_app.post("/client/telemetry_briefing")
async def client_telemetry_briefing(req: TelemetryRequest, authorization: str = Header(None)):
    if authorization != CLIENT_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        location_name = req.location
        temperature = req.temperature
        weather_condition = req.weather
        battery_level = req.battery_level
        is_charging = req.is_charging
        calendar_events = req.events or []
        
        charging_status = "sedang diisi daya" if is_charging else "menggunakan baterai"
        events_str = ", ".join(calendar_events) if calendar_events else "Tidak ada agenda khusus tercatat."

        prompt = f"""
[SYSTEM PROTOCOL: MOBILE-FIRST GOOD MORNING BRIEFING]
Kamu adalah J.A.R.V.I.S., asisten pribadi canggih. Susun Good Morning Briefing untuk Bos dalam gaya bahasa yang elegan, efisien, dan siap tempur.

DATA REAL LOKAL HP BOS SAAT INI:
- Lokasi: {location_name}
- Cuaca & Suhu: {weather_condition}, {temperature}°C
- Baterai HP: {battery_level}% ({charging_status})
- Agenda Hari Ini: {events_str}

TUGAS:
1. Sapa Bos dengan hangat dan profesional.
2. Laporkan kondisi lingkungan lokal (lokasi, cuaca) & status baterai HP secara alami.
3. Ingatkan agenda hari ini jika ada.
4. Berikan pesan motivasi singkat khas kesiapan J.A.R.V.I.S.
JANGAN meminta data tambahan lagi.
"""
        briefing_text = ask_jarvis(prompt)
        return {
            "status": "SUCCESS",
            "briefing_message": f"🌅 **[GOOD MORNING BRIEFING - MOBILE INTEL]**\n\n{briefing_text}"
        }
    except Exception as e:
        print(f"🚨 [TELEMETRY ERROR]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@web_app.post("/client/proactive_alert")
async def receive_proactive_alert(req: ProactiveAlertRequest, authorization: str = Header(None)):
    if authorization != CLIENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access Denied")
    
    # Broadcast eksklusif ke Jarvis HUD
    for ws in ACTIVE_HUD_CONNECTIONS:
        try:
            await ws.send_json({"type": "text_chunk", "content": f"\n🚨 *SYSTEM ALERT*\n{req.alert_message}\n"})
            audio_b64 = generate_gtts_base64_sync("Peringatan, Bos. Ada sistem yang memerlukan perhatian.")
            await ws.send_json({"type": "stream_end", "audio_base64": audio_b64})
        except:
            pass
            
    return {"status": "alert_delivered"}

@web_app.get("/client/audit")
def client_veritas_audit():
    try:
        from stark_diagnostic import StarkDiagnosticSuite
        suite = StarkDiagnosticSuite()
        report_text = suite.run_full_audit()
        return {"status": "SUCCESS", "report": report_text}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@web_app.exception_handler(Exception)
async def global_fastapi_exception_handler(request: Request, exc: Exception):
    error_msg = f"FastAPI Endpoint Error on [{request.method}] {request.url}\nDetail: {str(exc)}"
    threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal Server Error detected. VERONICA Auto-Fixer has been notified."}
    )

@web_app.websocket("/ws/stream_chat")
async def websocket_stream_chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    ACTIVE_HUD_CONNECTIONS.append(websocket)
    print("⚡ [LOW-LATENCY STREAM] HUD Client connected.")
    try:
        while True:
            data = await websocket.receive_text()
            if not data: continue

            intent = route_natural_language_command(data)
            if intent.get("status") == "EXECUTE":
                reply_text = intent.get("reply")
                await websocket.send_json({"type": "text_chunk", "content": reply_text})
                audio_b64 = generate_gtts_base64_sync(reply_text)
                await websocket.send_json({"type": "stream_end", "audio_base64": audio_b64})
                continue
            elif intent.get("status") == "EXECUTE_DIAGRAM":
                await websocket.send_json({"type": "text_chunk", "content": "Mohon gunakan Tab FRIDAY atau ketik tanpa streaming untuk render diagram via HTTP, Bos."})
                await websocket.send_json({"type": "stream_end"})
                continue

            wib = pytz.timezone('Asia/Jakarta')
            time_now = datetime.datetime.now(wib).strftime("%H:%M WIB")
            prompt = f"Waktu sekarang {time_now}. Jawab secara singkat, cepat, berkelas: {data}"

            response_stream = client.models.generate_content_stream(model="gemini-3.6-flash", contents=prompt)
            full_reply = ""

            for chunk in response_stream:
                if chunk.text:
                    full_reply += chunk.text
                    await websocket.send_json({"type": "text_chunk", "content": chunk.text})
                    await asyncio.sleep(0.01)

            audio_b64 = generate_gtts_base64_sync(full_reply)
            await websocket.send_json({"type": "stream_end", "audio_base64": audio_b64})

    except WebSocketDisconnect:
        print("⚡ [LOW-LATENCY STREAM] Client disconnected.")
    except Exception as e:
        print(f"🚨 [STREAM ERROR]: {e}")
    finally:
        ACTIVE_HUD_CONNECTIONS.remove(websocket)
        try: await websocket.close()
        except: pass

def run_fastapi():
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Menyalakan FastAPI Server di Port {port}...")
    uvicorn.run(web_app, host="0.0.0.0", port=port)

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🤖 Jarvis Stark HUD-Core Engine Full Running...")
    run_fastapi()