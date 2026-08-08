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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx
import sys
import traceback
from PIL import Image
from bs4 import BeautifulSoup
import edge_tts
from google import genai
import chromadb
from pypdf import PdfReader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from apscheduler.schedulers.background import BackgroundScheduler
from duckduckgo_search import DDGS

# --- IMPORT FASTAPI & CORSMiddleware ---
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ==========================================
# KONFIGURASI UTAMA & STARK SECURITY STATE
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"
MODEL_NAME = "gemini-3.6-flash"

# Status Keamanan Stark Protocol
IS_LOCKDOWN = False

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

# ==========================================
# PROJECT T.A.C.H.I.: AUTO-JOURNALING ENGINE
# ==========================================
def generate_daily_journal_job():
    """Fungsi otomatis jam 23:59: Membaca aktivitas hari ini & membuat Jurnal Rekap"""
    if IS_LOCKDOWN: return

    print("🧠 [T.A.C.H.I.] Mengompilasi Jurnal Harian Aktivitas Proyek Bos...")
    today_str = datetime.datetime.now().strftime("%A, %d %B %Y")
    
    # Ambil memori terbaru dari SQLite
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
    
    # Simpan jurnal ini ke SQLite & ChromaDB
    save_memory("DAILY_JOURNAL", f"[{today_str}] {journal_result[:500]}")
    add_to_vector_db(journal_result, f"journal_{int(time.time())}", {"type": "daily_journal", "date": today_str})
    
    # Kirim Laporan Jurnal Malam ke Telegram Bos
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_CHAT_ID,
        "text": f"📖 *STARK INDUSTRIES DAILY JOURNAL ({today_str})*\n\n{journal_result}"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Gagal kirim Jurnal Harian: {e}")

# ==========================================
# STARK INTRUSION & SECURITY PROTOCOL
# ==========================================
def send_security_alert(intruder_id: str, message_text: str):
    """Mengirim peringatan penyusupan langsung ke HP Bos"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_CHAT_ID,
        "text": f"🚨 *STARK SECURITY ALERT: INTRUSION DETECTED!*\n\n"
                f"👤 *Intruder ID:* `{intruder_id}`\n"
                f"💬 *Pesan Penyusup:* {message_text}\n"
                f"🛡️ *Action:* Access Denied & Logged."
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Security Alert Error: {e}")

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
        return "🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Semua fungsi Jarvis sedang terkunci demi keamanan. Gunakan perintah `/unlock` untuk membuka kembali."

    now = datetime.datetime.now()
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

# ==========================================
# PROTOCOL "LEGION" (MULTI-AGENT SUB-TASKING)
# ==========================================
def legion_sub_agent_task(agent_type: str, task_prompt: str):
    """Menjalankan Sub-Agent secara mandiri di background thread"""
    print(f"🤖 [LEGION PROTOCOL] Sub-Agent ({agent_type}) mulai bekerja...")
    
    agent_instructions = {
        "research": "Kamu adalah Sub-Agent Riset. Lakukan analisis mendalam dan berikan laporan ringkas.",
        "coder": "Kamu adalah Sub-Agent Developer. Fokus buatkan kode program dan solusinya.",
        "guard": "Kamu adalah Sub-Agent Keamanan. Analisis risiko dan kesehatan sistem."
    }
    
    prefix = agent_instructions.get(agent_type, "Kamu adalah Sub-Agent Jarvis.")
    full_prompt = f"{prefix}\nTugas: {task_prompt}"
    
    result_text = ask_jarvis(full_prompt)
    
    # Laporkan hasil kerja Sub-Agent langsung ke Telegram Bos
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_CHAT_ID,
        "text": f"🤖 *PROTOCOL LEGION: SUB-AGENT ({agent_type.upper()}) FINISHED*\n\n{result_text}"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Gagal kirim laporan Sub-Agent: {e}")

def autonomous_research(query: str, max_results: int = 4) -> str:
    """Melakukan pencarian web mandiri dan menyusun ringkasan riset"""
    print(f"🛰️ [FRIDAY AGENT] Melakukan riset web mandiri untuk: '{query}'...")
    search_results = []
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            for r in results:
                title = r.get('title', '')
                snippet = r.get('body', '')
                link = r.get('href', '')
                search_results.append(f"• **{title}**\n  {snippet}\n  Link: {link}")
    except Exception as e:
        print(f"[!] DuckDuckGo Search Error: {e}")
        return f"Gagal melakukan pencarian web: {e}"

    if not search_results:
        return "Tidak ditemukan hasil yang relevan di web, Bos."

    raw_research_data = "\n\n".join(search_results)
    
    # Minta Gemini merangkum hasil riset web tersebut
    prompt = f"""
Kamu adalah FRIDAY, Sub-Agent Riset Otonom milik Bos.
Berikut adalah data hasil pencarian web terbaru mengenai topik: "{query}"

--- DATA HASIL PENCARIAN WEB ---
{raw_research_data}
--- END DATA ---

Tugasmu:
1. Buatkan ringkasan riset yang sangat jelas, padat, profesional, dan langsung ke inti informasi.
2. Cantumkan poin-poin penting utama.
3. Sebutkan sumber link referensi jika relevan.
Jawab dengan gaya bahasa Jarvis yang luwes dan panggil "Bos".
"""
    return ask_jarvis(prompt)

# ==========================================
# VOICE & CODE AGENT ENGINES
# ==========================================
async def generate_voice_response(text: str, output_path: str = "voice_reply.ogg") -> str:
    try:
        clean_speech = re.sub(r'[^\w\s,?!.]', '', text)
        communicate = edge_tts.Communicate(clean_speech, VOICE_ACTOR)
        await communicate.save(output_path)
        return output_path
    except Exception as e:
        return ""

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

# ==========================================
# MARK-UI: DIAGRAM GENERATOR ENGINE
# ==========================================
def generate_system_diagram(nodes_and_edges: list, title: str = "System Architecture") -> str:
    """Mengubah struktur node/alur menjadi gambar diagram visual"""
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
    """Mengeksekusi workflow Git secara otomatis di repository lokal"""
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
            
            # 1. Git Add
            subprocess.run(["git", "add", "."], capture_output=True, text=True, check=True)
            
            # 2. Git Commit
            commit_res = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
            
            # 3. Git Push
            push_res = subprocess.run(["git", "push"], capture_output=True, text=True, check=True)
            
            return f"🚀 *HEPHAESTUS GIT PUSH SUCCESSFUL!*\n\n*Commit Message:* `{commit_msg}`\n\n*Log Output:*\n```\n{commit_res.stdout}\n{push_res.stdout}\n```"
            
        else:
            return "Action tidak dikenali, Bos. Gunakan `status`, `pull`, atau `push`."
            
    except subprocess.CalledProcessError as e:
        return f"🚨 *HEPHAESTUS GIT ERROR:*\n```\n{e.stderr or e.stdout}\n```"
    except Exception as e:
        return f"🚨 *EXECUTION ERROR:* {e}"

# ==========================================
# PROACTIVE SCHEDULER
# ==========================================
def daily_briefing_job():
    if IS_LOCKDOWN: return
    briefing_text = ask_jarvis("Berikan briefing pagi singkat dan motivasi untuk Bos memulai hari.")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": ALLOWED_CHAT_ID, "text": f"🌅 GOOD MORNING BRIEFING\n\n{briefing_text}"}
    try: requests.post(url, json=payload)
    except: pass

scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
scheduler.add_job(daily_briefing_job, 'cron', hour=7, minute=0)
scheduler.add_job(generate_daily_journal_job, 'cron', hour=23, minute=59)
scheduler.start()

# ==========================================
# PROJECT E.D.I.T.H.: TERMINAL COMMANDER ENGINE
# ==========================================
def execute_terminal_command(command_str: str) -> str:
    """Mengeksekusi perintah terminal/shell secara aman di host machine"""
    # Blacklist perintah berbahaya demi keamanan
    blacklisted_keywords = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"]
    for kw in blacklisted_keywords:
        if kw in command_str.lower():
            return "🚨 *STARK SECURITY PROTOCOL:* Perintah ini diblokir demi keamanan sistem!"

    try:
        print(f"⚡ [E.D.I.T.H.] Executing Shell Command: '{command_str}'...")
        # Jalankan perintah via subprocess
        process = subprocess.run(
            command_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30 # Timeout 30 detik
        )
        
        stdout_text = process.stdout.strip()
        stderr_text = process.stderr.strip()

        output = ""
        if stdout_text:
            output += f"📤 *STDOUT:*\n`{stdout_text[:3000]}`" # Limit output agar tidak spam chat
        if stderr_text:
            output += f"\n⚠️ *STDERR:*\n`{stderr_text[:1000]}`"

        return output if output else "✅ Perintah berhasil dieksekusi tanpa output."
    except subprocess.TimeoutExpired:
        return "⏳ *Execution Timeout:* Perintah memakan waktu lebih dari 30 detik."
    except Exception as e:
        return f"🚨 *Execution Error:* {e}"

# ==========================================
# PROJECT VERONICA: LIVE BUG HUNTER ENGINE
# ==========================================
def veronica_auto_fix_bug(error_traceback: str):
    """Menganalisis error crash secara otomatis dan mengirimkan patch perbaikannya ke Bos"""
    print("🛡️ [VERONICA] Fatal Error terdeteksi! Menganalisis penyebab crash...")
    
    prompt = f"""
[VERONICA PROTOCOL: SYSTEM CRASH ANALYSIS]
Sistem telah mengalami fatal error. Berikut adalah DATA STACKTRACE ERROR RESMI:

--- STACKTRACE START ---
{error_traceback}
--- STACKTRACE END ---

Tugasmu sebagai VERONICA:
1. Jelaskan secara singkat dan tepat mengapa error di atas bisa terjadi.
2. Berikan potongan kode perbaikannya (Patch Code) yang siap dipasang.
3. Berikan saran pencegahan singkat.
4. JANGAN meminta data tambahan lagi. Langsung sajikan analisis dan Patch Code sekarang.
"""
    fix_suggestion = ask_jarvis(prompt)
    
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_CHAT_ID,
        "text": f"🛡️ *VERONICA BUG HUNTER ALERT: SYSTEM CRASH DETECTED!*\n\n{fix_suggestion}"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Gagal kirim Veronica alert: {e}")

def veronica_global_exception_handler(exctype, value, tb):
    """Global exception hook untuk menangkap crash di Python"""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"🚨 [CRASH DETECTED]:\n{error_msg}")
    
    # Trigger Veronica untuk analisa & bikinkan fix di background
    threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()

# Pasang Hook Global Exception
sys.excepthook = veronica_global_exception_handler

# ==========================================
# FASTAPI SERVER ENGINE + IOT & KINETIC-UI ENDPOINTS
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

class IoTCommandRequest(BaseModel):
    device_id: str
    action: str
    secret_key: str = ""

@web_app.get("/")
def read_root():
    return {
        "status": "Jarvis Web, IoT Bridge & KINETIC-UI Online",
        "lockdown": IS_LOCKDOWN,
        "time": str(datetime.datetime.now())
    }

# 🟢 ENDPOINT 1: Chat Interaktif (Flutter / Web)
@web_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if IS_LOCKDOWN:
        return {"status": "error", "reply": "🔒 STARK LOCKDOWN ACTIVE."}
    
    reply = ask_jarvis(request.message)
    return {
        "status": "success",
        "reply": reply,
        "timestamp": str(datetime.datetime.now())
    }

# 🟢 ENDPOINT 2: Real-time System Status Dashboard (KINETIC-UI)
@web_app.get("/status")
def status_endpoint():
    return {
        "status": "online",
        "lockdown": IS_LOCKDOWN,
        "cpu_usage": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent,
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# 🟢 ENDPOINT 3: Riwayat Memori Percakapan (KINETIC-UI)
@web_app.get("/history")
def history_endpoint():
    memories = get_all_memories()
    return {
        "status": "success",
        "memories": memories
    }

# 🟢 ENDPOINT 4: Smart Home / IoT Control Bridge
@web_app.post("/iot/control")
async def iot_control_endpoint(request: IoTCommandRequest):
    """Bridge kontrol smart device / home automation"""
    if IS_LOCKDOWN:
        return {"status": "error", "message": "System is in Lockdown"}
    
    print(f"📡 [STARK IOT BRIDGE] Device: {request.device_id} | Action: {request.action}")
    return {
        "status": "success",
        "device": request.device_id,
        "executed_action": request.action,
        "timestamp": str(datetime.datetime.now())
    }

# 🛡️ GLOBAL EXCEPTION HANDLER (VERONICA AUTO-FIXER)
@web_app.exception_handler(Exception)
async def global_fastapi_exception_handler(request: Request, exc: Exception):
    """Menangkap error HTTP 500 di FastAPI dan memicu VERONICA"""
    error_msg = f"FastAPI Endpoint Error on [{request.method}] {request.url}\nDetail: {str(exc)}"
    
    # Jalankan Veronica Auto-Fixer di background thread
    threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()
    
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal Server Error detected. VERONICA Auto-Fixer has been notified."}
    )

def run_fastapi():
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Menyalakan FastAPI Server di Port {port}...")
    uvicorn.run(web_app, host="0.0.0.0", port=port)

# ==========================================
# TELEGRAM BOT HANDLERS & COMMANDS
# ==========================================
def clean_markdown_to_html(text: str) -> str:
    if not text: return ""
    text = html.escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

async def safe_reply(update: Update, text: str):
    try: await update.message.reply_html(clean_markdown_to_html(text))
    except: await update.message.reply_text(text)

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    # 🛡️ STARK SECURITY CHECK (Deteksi Penyusup)
    if chat_id != ALLOWED_CHAT_ID:
        user_msg = update.message.text or "[Non-Text Message]"
        send_security_alert(chat_id, user_msg)
        return

    user_text = update.message.text or ""
    if not user_text: return
    
    reply_text = ask_jarvis(user_text)
    await safe_reply(update, reply_text)

async def lockdown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_LOCKDOWN
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    IS_LOCKDOWN = True
    await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN ACTIVATED!*\nSeluruh API dan sistem Jarvis sekarang dikunci.")

async def unlock_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_LOCKDOWN
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    IS_LOCKDOWN = False
    await update.message.reply_text("🔓 *STARK PROTOCOL UNLOCKED.* Sistem Jarvis kembali beroperasi normal, Bos!")

async def legion_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /legion <type> <tugas>"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if len(context.args) < 2:
        await update.message.reply_text("Format salah, Bos!\nContoh: `/legion research cari berita terbaru AI`\nType opsional: `research`, `coder`, `guard`")
        return

    agent_type = context.args[0].lower()
    task_prompt = " ".join(context.args[1:])

    await update.message.reply_text(f"🤖 Sub-Agent ({agent_type.upper()}) dikirim ke background! Hasilnya akan dikirim begitu selesai.")
    
    # Jalankan Legion Sub-Agent di Thread terpisah
    threading.Thread(target=legion_sub_agent_task, args=(agent_type, task_prompt), daemon=True).start()

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID:
        send_security_alert(chat_id, "[Photo Intrusion Attempt]")
        return

    await update.message.reply_text("👁️ Jarvis sedang menganalisis foto/screenshot...")
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    
    caption = update.message.caption or ""
    reply_text = ask_jarvis_with_image(bytes(image_bytes), caption)
    await safe_reply(update, reply_text)

async def status_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent
    
    status_msg = f"""
📊 JARVIS STARK SYSTEM HEALTH:
• Lockdown Status: {'🔒 LOCKED' if IS_LOCKDOWN else '🟢 NORMAL'}
• CPU Usage: {cpu_usage}%
• RAM Usage: {ram_usage}%
• Active Protocols: Security, Legion Sub-Agents, IoT Bridge
• Server Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB
"""
    await update.message.reply_text(status_msg)

async def voice_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    user_prompt = " ".join(context.args) if context.args else "Halo Bos, ada yang bisa Jarvis bantu?"
    reply_text = ask_jarvis(user_prompt)
    
    voice_path = await generate_voice_response(reply_text)
    if voice_path and os.path.exists(voice_path):
        with open(voice_path, 'rb') as voice_file:
            await update.message.reply_voice(voice=voice_file, caption=f"💬 {reply_text[:100]}...")
        os.remove(voice_path)
    else:
        await safe_reply(update, reply_text)

async def code_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Mohon sertakan instruksi kodingannya, Bos!\nContoh: `/code buatkan script scraper harga crypto`")
        return

    prompt_req = " ".join(context.args)
    await update.message.reply_text("🤖 Jarvis Code Agent sedang memproses & menguji kodingan...")

    is_success, status_msg, file_path = generate_and_test_code(prompt_req)
    await update.message.reply_text(status_msg)

    if is_success and os.path.exists(file_path):
        with open(file_path, 'rb') as doc:
            await update.message.reply_document(document=doc, filename=file_path)

async def pdf_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    document = update.message.document
    if document.mime_type == 'application/pdf':
        await update.message.reply_text("📥 Menerima file PDF, Jarvis sedang mempelajari isinya...")
        
        file = await context.bot.get_file(document.file_id)
        temp_pdf_path = f"temp_{document.file_name}"
        await file.download_to_drive(temp_pdf_path)

        res_msg = process_pdf_document(temp_pdf_path)
        await update.message.reply_text(res_msg)

        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pesan suara (Voice Note) otomatis dari Bos"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID:
        send_security_alert(chat_id, "[Voice Note Intrusion Attempt]")
        return

    await update.message.reply_text("🎙️ *Jarvis mendengarkan pesan suara Bos...*")

    # 1. Unduh Voice Note (.ogg) dari Telegram
    voice_file = await update.message.voice.get_file()
    ogg_path = f"user_voice_{int(time.time())}.ogg"
    await voice_file.download_to_drive(ogg_path)

    try:
        # 2. Kirim Audio langsung ke Otak Gemini Multimodal
        with open(ogg_path, "rb") as f:
            audio_bytes = f.read()

        print("🎙️ Memproses audio pesan suara Bos ke Gemini...")
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                {"mime_type": "audio/ogg", "data": audio_bytes},
                f"{JARVIS_PERSONA}\n\nDengarkan suara Bos di atas, pahami pesannya, lalu berikan jawaban yang singkat, padat, dan luwes."
            ]
        )
        reply_text = response.text
        clean_reply = re.sub(r'#+\s*', '', reply_text).replace('**', '').replace('*', '')

        # 3. Ubah Balasan Teks Jarvis menjadi Suara (Voice Note)
        voice_reply_path = await generate_voice_response(clean_reply)

        if voice_reply_path and os.path.exists(voice_reply_path):
            with open(voice_reply_path, 'rb') as v_out:
                await update.message.reply_voice(voice=v_out, caption=f"💬 {clean_reply[:150]}...")
            os.remove(voice_reply_path)
        else:
            await safe_reply(update, clean_reply)

    except Exception as e:
        print(f"❌ Error Voice Processing: {e}")
        await update.message.reply_text(f"🚨 Maaf Bos, gagal memproses suara: {e}")
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)

async def diagram_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /diagram <topik>"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Sertakan alur/topik diagramnya ya, Bos!\nContoh: `/diagram Client -> FastAPI -> SQLite -> Gemini`")
        return

    raw_input = " ".join(context.args)
    await update.message.reply_text("🎨 Jarvis sedang menggambar diagram visual...")

    # Parser sederhana alur yang dipisahkan panah '->'
    steps = [step.strip() for step in raw_input.split("->")]
    edges = [(steps[i], steps[i+1]) for i in range(len(steps)-1)] if len(steps) > 1 else []

    if edges:
        diagram_img = generate_system_diagram(edges, title="STARK SYSTEM WORKFLOW")
        if diagram_img and os.path.exists(diagram_img):
            with open(diagram_img, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=f"📊 *Diagram Visual Workflow*\n`{raw_input}`")
            os.remove(diagram_img)
            return

    await update.message.reply_text("🚨 Gagal menggambar diagram. Gunakan format panah `->`, contoh:\n`/diagram User -> Bot -> Gemini API`")

async def research_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /research <topik>"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Sertakan topik yang mau diriset ya, Bos!\nContoh: `/research perkembangan AI terbaru 2026`")
        return

    topic = " ".join(context.args)
    await update.message.reply_text(f"🛰️ *FRIDAY Agent dikirim!* Sedang menjelajah web untuk meriset `{topic}`...")

    # Jalankan riset di background thread agar bot tidak freeze
    def run_async_research():
        report = autonomous_research(topic)
        # Kirim hasil laporan riset ke Telegram Bos
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ALLOWED_CHAT_ID,
            "text": f"📊 *RESEARCH REPORT: {topic.upper()}*\n\n{report}"
        }
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"[!] Gagal kirim laporan riset: {e}")

    threading.Thread(target=run_async_research, daemon=True).start()

async def cmd_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /cmd <shell command>"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID:
        send_security_alert(chat_id, "[E.D.I.T.H. Terminal Intrusion Attempt]")
        return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Akses terminal ditutup.")
        return

    if not context.args:
        await update.message.reply_text("Sertakan perintah shell yang mau dijalankan ya, Bos!\nContoh:\n`/cmd dir` (di Windows)\n`/cmd git status`\n`/cmd free -m`")
        return

    command_to_run = " ".join(context.args)
    await update.message.reply_text(f"⚡ *E.D.I.T.H. Executing:* `{command_to_run}`...")

    # Eksekusi di thread terpisah agar bot tidak ngelag/freeze
    def run_async_cmd():
        result = execute_terminal_command(command_to_run)
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ALLOWED_CHAT_ID,
            "text": f"💻 *E.D.I.T.H. TERMINAL OUTPUT*\n\n{result}",
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"[!] Gagal kirim output terminal: {e}")

    threading.Thread(target=run_async_cmd, daemon=True).start()

async def journal_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /journal untuk memicu rekap jurnal T.A.C.H.I. secara instan"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await update.message.reply_text("🧠 *T.A.C.H.I. sedang merangkum Jurnal Progres Hari Ini...*")
    
    def run_async_journal():
        generate_daily_journal_job()

    threading.Thread(target=run_async_journal, daemon=True).start()

async def testbug_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulasi error untuk menguji respons VERONICA Auto-Fixer"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await update.message.reply_text("🧪 *Memicu simulasi ZeroDivisionError untuk menguji VERONICA...*")
    
    try:
        simulated_crash = 100 / 0
    except Exception as e:
        error_msg = traceback.format_exc()
        threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()

async def git_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /git <action> [commit message]"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID:
        send_security_alert(chat_id, "[HEPHAESTUS Git Access Attempt]")
        return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Akses Git ditutup.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚒️ *PROJECT HEPHAESTUS DEVOPS ENGINE*\n\n"
            "Format perintah:\n"
            "• `/git status` - Cek status perubahan file\n"
            "• `/git pull` - Tarik pembaruan dari GitHub\n"
            "• `/git push <pesan commit>` - Otomatis add, commit, & push ke Cloud",
            parse_mode="Markdown"
        )
        return

    action = context.args[0].lower()
    commit_msg = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    await update.message.reply_text(f"⚒️ *HEPHAESTUS sedang mengeksekusi Git {action.upper()}...*")

    def run_async_git():
        report = execute_git_workflow(action, commit_msg)
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ALLOWED_CHAT_ID,
            "text": report,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"[!] Gagal kirim output Git: {e}")

    threading.Thread(target=run_async_git, daemon=True).start()

# ==========================================
# PROJECT STARK-OVERSEER: INTERACTIVE MENU ENGINE
# ==========================================
async def menu_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /menu atau /start untuk menampilkan Control Center berbasis Tombol"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID:
        send_security_alert(chat_id, "[STARK-OVERSEER Menu Access Attempt]")
        return

    # Susun Tata Letak Tombol Interaktif (Inline Keyboard)
    keyboard = [
        [
            InlineKeyboardButton("📊 System Health", callback_data="btn_status"),
            InlineKeyboardButton("📖 Daily Journal", callback_data="btn_journal")
        ],
        [
            InlineKeyboardButton("🔒 Toggle Lockdown", callback_data="btn_lockdown"),
            InlineKeyboardButton("🧪 Test VERONICA Bug", callback_data="btn_testbug")
        ],
        [
            InlineKeyboardButton("🎙️ Voice Mode Info", callback_data="btn_voice_info"),
            InlineKeyboardButton("🎨 Diagram Help", callback_data="btn_diagram_info")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    status_indicator = "🔒 LOCKED" if IS_LOCKDOWN else "🟢 ONLINE"
    message_text = f"""
🎛️ *J.A.R.V.I.S. STARK-OVERSEER CONTROL CENTER*
Status Sistem: *{status_indicator}*

Silakan pilih protokol yang ingin dieksekusi, Bos:
"""

    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler aksi saat tombol interaktif diklik oleh Bos"""
    global IS_LOCKDOWN

    query = update.callback_query
    chat_id = str(query.message.chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await query.answer() # Beri konfirmasi klik tombol ke Telegram
    data = query.data

    if data == "btn_status":
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        status_msg = f"""
📊 *STARK SYSTEM HEALTH REPORT*
• Lockdown Status: {'🔒 LOCKED' if IS_LOCKDOWN else '🟢 NORMAL'}
• CPU Usage: {cpu_usage}%
• RAM Usage: {ram_usage}%
• Memory Engine: SQLite & ChromaDB Active
• Server Time: {datetime.datetime.now().strftime('%H:%M:%S')} WIB
"""
        # Tampilkan ulang menu utama beserta status
        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="btn_main_menu")]]
        await query.edit_message_text(status_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "btn_journal":
        await query.edit_message_text("🧠 *T.A.C.H.I. sedang merangkum Jurnal Progres Hari Ini...*\nLaporan akan dikirimkan ke chat dalam beberapa detik.", parse_mode="Markdown")
        threading.Thread(target=generate_daily_journal_job, daemon=True).start()

    elif data == "btn_lockdown":
        IS_LOCKDOWN = not IS_LOCKDOWN
        state_str = "🔒 *LOCKED*" if IS_LOCKDOWN else "🔓 *UNLOCKED*"
        await query.edit_message_text(f"🛡️ *STARK SECURITY:* Status Lockdown berhasil diubah menjadi {state_str}.", parse_mode="Markdown")

    elif data == "btn_testbug":
        await query.edit_message_text("🧪 *Memicu simulasi ZeroDivisionError untuk menguji VERONICA...*", parse_mode="Markdown")
        try:
            _ = 100 / 0
        except Exception:
            error_msg = traceback.format_exc()
            threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()

    elif data == "btn_voice_info":
        await query.edit_message_text("🎙️ *VOICE CONVERSATION MODE*\nTahan tombol Mic di Telegram untuk mengirim Voice Note. Jarvis akan langsung merespons dengan balasan suara Ardi Neural secara instan!", parse_mode="Markdown")

    elif data == "btn_diagram_info":
        await query.edit_message_text("🎨 *MARK-UI DIAGRAM GENERATOR*\nKetik perintah:\n`/diagram NodeA -> NodeB -> NodeC`\nJarvis akan langsung menggambar diagram alur visual secara instan!", parse_mode="Markdown")

    elif data == "btn_main_menu":
        await menu_command_handler(update, context)

def run_telegram_bot():
    while True:
        try:
            print("🤖 Memulai Telegram Bot...")
            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

            # 🟢 STARK-OVERSEER MENU COMMANDS
            app.add_handler(CommandHandler("start", menu_command_handler))
            app.add_handler(CommandHandler("menu", menu_command_handler))
            app.add_handler(CallbackQueryHandler(button_callback_handler))
            
            # Stark Commands
            app.add_handler(CommandHandler("lockdown", lockdown_command_handler))
            app.add_handler(CommandHandler("unlock", unlock_command_handler))
            app.add_handler(CommandHandler("legion", legion_command_handler))
            
            # Standard Commands
            app.add_handler(CommandHandler("voice", voice_command_handler))
            app.add_handler(CommandHandler("code", code_command_handler))
            app.add_handler(CommandHandler("status", status_command_handler))
            
            # Handlers (TAMBAHKAN FILTERS.VOICE DI SINI)
            app.add_handler(MessageHandler(filters.VOICE, voice_message_handler)) # 👈 BARU!
            app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
            app.add_handler(MessageHandler(filters.Document.PDF, pdf_document_handler))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
            app.add_handler(CommandHandler("diagram", diagram_command_handler))
            app.add_handler(CommandHandler("research", research_command_handler))
            app.add_handler(CommandHandler("cmd", cmd_command_handler))
            app.add_handler(CommandHandler("journal", journal_command_handler))
            app.add_handler(CommandHandler("testbug", testbug_command_handler))
            app.add_handler(CommandHandler("git", git_command_handler))

            app.run_polling(drop_pending_updates=True, stop_signals=None)
        except Exception as e:
            print(f"⚠️ Telegram Error (Auto-restart 5 detik): {e}")
            time.sleep(5)

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🤖 Jarvis Stark Mega-Engine Full Running...")
    
    try:
        subprocess.Popen(["python", "jarvis_discord.py"])
    except Exception as e:
        print(f"⚠️ Discord error: {e}")
        
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    run_fastapi()