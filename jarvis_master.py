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
import base64
import edge_tts
import cv2
from PIL import Image
from bs4 import BeautifulSoup
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
from playwright.async_api import async_playwright
# --- FASTAPI & MIDDLEWARE IMPORTS ---
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi import WebSocket, WebSocketDisconnect
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


# ==========================================
# PROJECT T.A.C.H.I.: AUTO-JOURNALING ENGINE
# ==========================================
def generate_daily_journal_job():
    """Fungsi otomatis jam 23:59: Membaca aktivitas hari ini & membuat Jurnal Rekap"""
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
    print(f"🤖 [LEGION PROTOCOL] Sub-Agent ({agent_type}) mulai bekerja...")
    
    agent_instructions = {
        "research": "Kamu adalah Sub-Agent Riset. Lakukan analisis mendalam dan berikan laporan ringkas.",
        "coder": "Kamu adalah Sub-Agent Developer. Fokus buatkan kode program dan solusinya.",
        "guard": "Kamu adalah Sub-Agent Keamanan. Analisis risiko dan kesehatan sistem."
    }
    
    prefix = agent_instructions.get(agent_type, "Kamu adalah Sub-Agent Jarvis.")
    full_prompt = f"{prefix}\nTugas: {task_prompt}"
    
    result_text = ask_jarvis(full_prompt)
    
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

async def computer_vision_snapshot_analysis(prompt_instruction: str = "Deskripsikan apa yang terlihat di depan kamera saat ini secara detail, Bos.") -> str:
    """Mengambil frame dari webcam lokal dan menganalisisnya dengan Gemini Multimodal"""
    print("👁️ [COMPUTER VISION] Mengakses lensa kamera lokal...")
    try:
        # Buka kamera default (0 = Webcam utama)
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

# ==========================================
# PROJECT E.D.I.T.H.: TERMINAL COMMANDER ENGINE
# ==========================================
def execute_terminal_command(command_str: str) -> str:
    blacklisted_keywords = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"]
    for kw in blacklisted_keywords:
        if kw in command_str.lower():
            return "🚨 *STARK SECURITY PROTOCOL:* Perintah ini diblokir demi keamanan sistem!"

    try:
        print(f"⚡ [E.D.I.T.H.] Executing Shell Command: '{command_str}'...")
        process = subprocess.run(
            command_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        stdout_text = process.stdout.strip()
        stderr_text = process.stderr.strip()

        output = ""
        if stdout_text:
            output += f"📤 *STDOUT:*\n`{stdout_text[:3000]}`"
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
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_CHAT_ID,
        "text": f"🛡️ *VERONICA BUG HUNTER ALERT: SYSTEM CRASH DETECTED!*\n\n{fix_suggestion}"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Gagal kirim Veronica alert: {e}")

def veronica_global_exception_handler(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"🚨 [CRASH DETECTED]:\n{error_msg}")
    threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()

sys.excepthook = veronica_global_exception_handler

async def execute_browser_automation(url: str, action: str = "screenshot", form_data: dict = None) -> tuple[bool, str, str]:
    """
    Mengeksekusi aksi browser headless otomatis menggunakan Playwright.
    action: 'screenshot' | 'extract_text' | 'click_and_capture'
    """
    print(f"🌐 [FRIDAY BROWSER] Starting headless session for: {url} (Action: {action})...")
    
    try:
        async with async_playwright() as p:
            # Jalankan browser Chromium tanpa GUI (Headless)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Buka URL target
            await page.goto(url, timeout=30000, wait_until="networkidle")
            
            if action == "screenshot":
                screenshot_path = f"web_snap_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                await browser.close()
                return True, "✅ Screenshot halaman web berhasil diambil, Bos!", screenshot_path
                
            elif action == "extract_text":
                content = await page.inner_text("body")
                await browser.close()
                clean_content = "\n".join([line.strip() for line in content.splitlines() if line.strip()])[:3000]
                return True, f"📄 *HASIL EKSTRAKSI TEKS WEB:*\n\n{clean_content}", ""

            elif action == "fill_form" and form_data:
                # Contoh pengisian form dinamis
                for selector, value in form_data.items():
                    await page.fill(selector, value)
                
                screenshot_path = f"form_filled_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path)
                await browser.close()
                return True, "✅ Form berhasil diisi otomatis, Bos!", screenshot_path

            await browser.close()
            return False, "Action tidak dikenal.", ""

    except Exception as e:
        print(f"🚨 [FRIDAY BROWSER ERROR]: {e}")
        return False, f"🚨 Error otomatisasi web: {e}", ""

# ==========================================
# PROJECT ULTRON-SENTINEL: UPTIME & HEALTH MONITOR
# ==========================================
# Daftar URL / Endpoint yang ingin dipantau 24/7 oleh Jarvis
MONITORED_TARGETS = [
    {"name": "Railway FastAPI Server", "url": "https://worker-production-792b.up.railway.app"}
]

def ultron_sentinel_ping_job():
    """Fungsi otomatis yang mengecek kesehatan server & API setiap 15 menit"""
    if IS_LOCKDOWN: return

    print("🛰️ [ULTRON-SENTINEL] Running 24/7 Uptime & Endpoint Health Check...")
    
    failed_services = []
    
    for target in MONITORED_TARGETS:
        name = target["name"]
        url = target["url"]
        
        # Abaikan jika URL masih placeholder
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

    # Jika ada server yang down, kirim Alert Alarm ke Telegram
    if failed_services:
        alert_body = "\n".join(failed_services)
        alarm_msg = f"🚨 *ULTRON-SENTINEL ALARM: SERVICE DOWN DETECTED!*\n\n{alert_body}\n\n*Action Required:* Mohon periksa server/koneksi Bos!"
        
        url_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ALLOWED_CHAT_ID,
            "text": alarm_msg,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url_api, json=payload)
        except Exception as e:
            print(f"[!] Gagal kirim Sentinel Alarm: {e}")

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

async def generate_tts_base64(text: str) -> str:
    try:
        clean_txt = re.sub(r'[*_`#~\[\]\(\)]', '', text)[:300]
        communicate = edge_tts.Communicate(clean_txt, "id-ID-ArdiNeural")
        
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
                
        return base64.b64encode(audio_bytes).decode('utf-8')
    except Exception as e:
        print(f"[!] TTS Base64 Generation Error: {e}")
        return ""

@web_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if IS_LOCKDOWN:
        return {
            "status": "error", 
            "reply": "🔒 STARK LOCKDOWN ACTIVE.",
            "audio_base64": ""
        }
    
    reply_text = ask_jarvis(request.message)
    msg_lower = request.message.lower()

    voice_triggers = ["pake suara", "pakai suara", "balas suara", "pake voice", "pakai voice", "pake vn", "bicaralah"]
    text_triggers = ["balas teks", "balas chat", "ketik aja", "tanpa suara", "tanpa voice", "gak usah suara"]

    wants_voice = any(kw in msg_lower for kw in voice_triggers)
    wants_text = any(kw in msg_lower for kw in text_triggers)

    # 🧠 STRICT LOGIC:
    if request.is_voice_input:
        if wants_text:
            return {"status": "success", "reply": reply_text, "audio_base64": "", "timestamp": str(datetime.datetime.now())}
        else:
            audio_b64 = await generate_tts_base64(reply_text)
            return {"status": "success", "reply": "", "audio_base64": audio_b64, "timestamp": str(datetime.datetime.now())}
    else:
        if wants_voice:
            audio_b64 = await generate_tts_base64(reply_text)
            return {"status": "success", "reply": "", "audio_base64": audio_b64, "timestamp": str(datetime.datetime.now())}
        else:
            return {"status": "success", "reply": reply_text, "audio_base64": "", "timestamp": str(datetime.datetime.now())}

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
            # Menerima chunk audio (bytes) dari klien (Flutter / Klien Audio)
            data = await websocket.receive_bytes()
            
            if not data:
                continue
                
            print(f"🎙️ [LIVE VOICE] Menerima data audio stream ({len(data)} bytes)...")
            
            # Simulasi / Proses Audio Stream dengan Gemini Multimodal / Edge-TTS
            # (Untuk tahap awal, kita kirim balik sinyal echo atau respons audio terproses)
            response_text = ask_jarvis("Halo Bos, saya mendengarkan stream suara Anda.")
            audio_b64 = await generate_tts_base64(response_text)
            
            # Kirim kembali respons audio base64 ke klien secara real-time
            await websocket.send_json({
                "status": "success",
                "reply": response_text,
                "audio_base64": audio_b64
            })
            
    except WebSocketDisconnect:
        print("🎙️ [LIVE VOICE] Klien terputus dari WebSocket.")
    except Exception as e:
        print(f"🚨 [LIVE VOICE ERROR] {e}")
        try:
            await websocket.close()
        except:
            pass

@web_app.exception_handler(Exception)
async def global_fastapi_exception_handler(request: Request, exc: Exception):
    error_msg = f"FastAPI Endpoint Error on [{request.method}] {request.url}\nDetail: {str(exc)}"
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
    if chat_id != ALLOWED_CHAT_ID:
        user_msg = update.message.text or "[Non-Text Message]"
        send_security_alert(chat_id, user_msg)
        return

    user_text = update.message.text or ""
    if not user_text: return
    
    voice_triggers = ["pake suara", "pakai suara", "balas suara", "pake voice", "pakai voice", "pake vn"]
    if any(kw in user_text.lower() for kw in voice_triggers):
        reply = ask_jarvis(user_text)
        audio_path = await generate_voice_response(reply)
        if audio_path and os.path.exists(audio_path):
            with open(audio_path, 'rb') as v_out:
                await update.message.reply_voice(voice=v_out)
            os.remove(audio_path)
        else:
            await safe_reply(update, reply)
    else:
        reply_text = ask_jarvis(user_text)
        await safe_reply(update, reply_text)

async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pesan suara (Voice Note) otomatis dari Bos"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID:
        send_security_alert(chat_id, "[Voice Note Intrusion Attempt]")
        return

    voice_file = await update.message.voice.get_file()
    ogg_path = f"user_voice_{int(time.time())}.ogg"
    await voice_file.download_to_drive(ogg_path)

    try:
        with open(ogg_path, "rb") as f:
            audio_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                {"mime_type": "audio/ogg", "data": audio_bytes},
                f"{JARVIS_PERSONA}\n\nDengarkan suara Bos di atas, pahami pesannya, lalu berikan jawaban yang singkat, padat, dan luwes."
            ]
        )
        transcribed_reply = response.text
        clean_reply = re.sub(r'#+\s*', '', transcribed_reply).replace('**', '').replace('*', '')

        text_triggers = ["balas teks", "balas chat", "ketik aja", "tanpa suara", "tanpa voice"]
        if any(kw in clean_reply.lower() for kw in text_triggers):
            await safe_reply(update, clean_reply)
        else:
            voice_reply_path = await generate_voice_response(clean_reply)
            if voice_reply_path and os.path.exists(voice_reply_path):
                with open(voice_reply_path, 'rb') as v_out:
                    await update.message.reply_voice(voice=v_out)
                os.remove(voice_reply_path)
            else:
                await safe_reply(update, clean_reply)

    except Exception as e:
        print(f"❌ Error Voice Processing: {e}")
        await update.message.reply_text(f"🚨 Maaf Bos, gagal memproses suara: {e}")
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)

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
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if len(context.args) < 2:
        await update.message.reply_text("Format salah, Bos!\nContoh: `/legion research cari berita terbaru AI`")
        return

    agent_type = context.args[0].lower()
    task_prompt = " ".join(context.args[1:])

    await update.message.reply_text(f"🤖 Sub-Agent ({agent_type.upper()}) dikirim ke background!")
    threading.Thread(target=legion_sub_agent_task, args=(agent_type, task_prompt), daemon=True).start()

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

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
            await update.message.reply_voice(voice=voice_file)
        os.remove(voice_path)
    else:
        await safe_reply(update, reply_text)

async def code_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Mohon sertakan instruksi kodingannya, Bos!")
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

async def diagram_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Sertakan alur/topik diagramnya ya, Bos!\nContoh: `/diagram Client -> FastAPI -> SQLite -> Gemini`")
        return

    raw_input = " ".join(context.args)
    await update.message.reply_text("🎨 Jarvis sedang menggambar diagram visual...")

    steps = [step.strip() for step in raw_input.split("->")]
    edges = [(steps[i], steps[i+1]) for i in range(len(steps)-1)] if len(steps) > 1 else []

    if edges:
        diagram_img = generate_system_diagram(edges, title="STARK SYSTEM WORKFLOW")
        if diagram_img and os.path.exists(diagram_img):
            with open(diagram_img, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=f"📊 *Diagram Visual Workflow*\n`{raw_input}`")
            os.remove(diagram_img)
            return

    await update.message.reply_text("🚨 Gagal menggambar diagram. Gunakan format panah `->`.")

async def research_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Sertakan topik yang mau diriset ya, Bos!")
        return

    topic = " ".join(context.args)
    await update.message.reply_text(f"🛰️ *FRIDAY Agent dikirim!* Sedang menjelajah web untuk meriset `{topic}`...")

    def run_async_research():
        report = autonomous_research(topic)
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
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Akses terminal ditutup.")
        return

    if not context.args:
        await update.message.reply_text("Sertakan perintah shell yang mau dijalankan ya, Bos!")
        return

    command_to_run = " ".join(context.args)
    await update.message.reply_text(f"⚡ *E.D.I.T.H. Executing:* `{command_to_run}`...")

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
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await update.message.reply_text("🧠 *T.A.C.H.I. sedang merangkum Jurnal Progres Hari Ini...*")
    threading.Thread(target=generate_daily_journal_job, daemon=True).start()

async def testbug_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await update.message.reply_text("🧪 *Memicu simulasi ZeroDivisionError untuk menguji VERONICA...*")
    try:
        _ = 100 / 0
    except Exception:
        error_msg = traceback.format_exc()
        threading.Thread(target=veronica_auto_fix_bug, args=(error_msg,), daemon=True).start()

async def git_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Akses Git ditutup.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚒️ *PROJECT HEPHAESTUS DEVOPS ENGINE*\n\n"
            "Format perintah:\n"
            "• `/git status`\n"
            "• `/git pull`\n"
            "• `/git push <pesan commit>`",
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
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

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
    global IS_LOCKDOWN

    query = update.callback_query
    chat_id = str(query.message.chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await query.answer()
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
        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="btn_main_menu")]]
        await query.edit_message_text(status_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "btn_journal":
        await query.edit_message_text("🧠 *T.A.C.H.I. sedang merangkum Jurnal Progres Hari Ini...*", parse_mode="Markdown")
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
        await query.edit_message_text("🎙️ *VOICE CONVERSATION MODE*\nTahan tombol Mic di Telegram untuk mengirim Voice Note. Jarvis akan merespons dengan Balasan Suara murni!", parse_mode="Markdown")

    elif data == "btn_diagram_info":
        await query.edit_message_text("🎨 *MARK-UI DIAGRAM GENERATOR*\nKetik perintah:\n`/diagram NodeA -> NodeB -> NodeC`", parse_mode="Markdown")

    elif data == "btn_main_menu":
        await menu_command_handler(update, context)

async def web_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /web <url> [action: snap/text]"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Akses browser ditutup.")
        return

    if not context.args:
        await update.message.reply_text(
            "🌐 *PROJECT FRIDAY BROWSER AUTOMATION*\n\n"
            "Format Perintah:\n"
            "• `/web <url>` - Mengambil screenshot full-page halaman web\n"
            "• `/web <url> text` - Ekstraksi seluruh teks tersembunyi/rendered dari web",
            parse_mode="Markdown"
        )
        return

    target_url = context.args[0]
    if not target_url.startswith("http"):
        target_url = "https://" + target_url

    action_type = "text" if len(context.args) > 1 and context.args[1].lower() == "text" else "screenshot"

    await update.message.reply_text(f"🌐 *FRIDAY Agent meluncur ke:* `{target_url}`...")

    def run_async_browser():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, message, file_path = loop.run_until_complete(
            execute_browser_automation(target_url, action=action_type)
        )
        loop.close()

        url_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        if success and file_path and os.path.exists(file_path):
            # Kirim foto screenshot ke Telegram
            photo_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(file_path, 'rb') as photo:
                requests.post(photo_url, data={"chat_id": ALLOWED_CHAT_ID, "caption": message}, files={"photo": photo})
            os.remove(file_path)
        else:
            payload = {"chat_id": ALLOWED_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(url_api, json=payload)

    threading.Thread(target=run_async_browser, daemon=True).start()

async def sentinel_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /sentinel untuk memicu tes kesehatan server secara langsung"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    await update.message.reply_text("🛰️ *ULTRON-SENTINEL sedang memindai kesehatan seluruh endpoint & server...*")

    def run_async_sentinel():
        ultron_sentinel_ping_job()
        
    threading.Thread(target=run_async_sentinel, daemon=True).start()

async def recall_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /recall <topik> untuk mencari kembali memori/pengetahuan masa lalu"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if not context.args:
        await update.message.reply_text("Sertakan kata kunci atau topik yang ingin diingat kembali, Bos!\nContoh: `/recall strategi deployment minggu lalu`")
        return

    query_topic = " ".join(context.args)
    await update.message.reply_text(f"🧠 *M.I.N.D. PALACE:* Memindai arsip memori untuk topik `{query_topic}`...")

    # Cari dari ChromaDB vector collection
    retrieved_memory = search_vector_db(query_topic, n_results=5)
    
    if not retrieved_memory or "PENGETAHUAN TERKAIT" not in retrieved_memory:
        await update.message.reply_text(f"🔍 Maaf Bos, tidak ditemukan arsip memori yang cocok dengan topik `{query_topic}`.")
        return

    # Minta Gemini merangkum hasil memori lama tersebut agar enak dibaca
    prompt = f"""
Kamu adalah M.I.N.D. PALACE Engine milik Jarvis.
Berikut adalah data arsip memori lama yang ditemukan dari database terkait topik "{query_topic}":

{retrieved_memory}

Tugasmu:
Rangkum dan jelaskan kembali informasi tersebut secara padat, jelas, dan bernada loyal kepada Bos. Beritahu Bos apa yang dulu pernah kita bahas mengenai hal ini.
"""
    summary_result = ask_jarvis(prompt)
    await safe_reply(update, f"📖 *M.I.N.D. PALACE MEMORY RECALL*\n\n{summary_result}")

async def pc_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /pc <aksi> untuk kontrol komputer lokal"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK PROTOCOL LOCKDOWN IS ACTIVE.* Kontrol PC dikunci.")
        return

    if not context.args:
        await update.message.reply_text(
            "💻 *PROJECT LOCAL-OVERRIDE (PC CONTROL)*\n\n"
            "Format Perintah:\n"
            "• `/pc lock` - Mengunci layar komputer (Lock Screen)\n"
            "• `/pc info` - Menampilkan spesifikasi & status hardware PC host\n"
            "• `/pc screenshot` - Mengambil tangkapan layar (screenshot) monitor PC saat ini",
            parse_mode="Markdown"
        )
        return

    action = context.args[0].lower()

    if action == "lock":
        try:
            # Perintah khusus Windows untuk mengunci layar
            if os.name == 'nt':
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
                await update.message.reply_text("🔒 Layar PC berhasil dikunci, Bos!")
            else:
                await update.message.reply_text("⚠️ Perintah lock screen saat ini hanya didukung pada host Windows.")
        except Exception as e:
            await update.message.reply_text(f"🚨 Gagal mengunci layar: {e}")

    elif action == "info":
        cpu_freq = psutil.cpu_freq().current if hasattr(psutil, "cpu_freq") else "N/A"
        battery = psutil.sensors_battery()
        battery_status = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'Discharging'})" if battery else "N/A (Desktop)"
        
        info_text = f"""
💻 *HOST PC STATUS OVERRIDE:*
• OS: `{sys.platform}`
• CPU Cores: `{psutil.cpu_count(logical=True)} Core`
• CPU Frequency: `{cpu_freq} MHz`
• RAM Total/Used: `{round(psutil.virtual_memory().total / (1024**3), 2)} GB` (`{psutil.virtual_memory().percent}%`)
• Disk Usage: `{psutil.disk_usage('/').percent}%`
• Power/Battery: `{battery_status}`
"""
        await update.message.reply_text(info_text, parse_mode="Markdown")

    elif action == "screenshot":
        try:
            import pyautogui
            snap_path = f"pc_snap_{int(time.time())}.png"
            pyautogui.screenshot(snap_path)
            
            with open(snap_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption="📸 *Live Host PC Screenshot*")
            os.remove(snap_path)
        except ImportError:
            await update.message.reply_text("⚠️ Library `pyautogui` belum terpasang di environment host. Ketik `pip install pyautogui` di terminal.")
        except Exception as e:
            await update.message.reply_text(f"🚨 Gagal mengambil screenshot PC: {e}")
    else:
        await update.message.reply_text("🚨 Aksi PC tidak dikenali. Ketik `/pc` untuk melihat daftar perintah.")

async def pc_advanced_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /pc advance untuk kontrol aplikasi dan file lokal dengan data presisi"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK LOCKDOWN ACTIVE.*")
        return

    if not context.args:
        await update.message.reply_text(
            "💻 *DEEP OS CONTROL (LOCAL-OVERRIDE)*\n\n"
            "Format Perintah:\n"
            "• `/pc info` - Status presisi Hardware PC\n"
            "• `/pc open <app>` - Membuka aplikasi\n"
            "• `/pc search <nama_file>` - Mencari file\n"
            "• `/pc screenshot` - Ambil screenshot layar PC",
            parse_mode="Markdown"
        )
        return

    sub_action = context.args[0].lower()
    param = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    if sub_action == "info":
        try:
            # Mengambil data RAM secara akurat
            mem = psutil.virtual_memory()
            total_ram = round(mem.total / (1024**3), 2)
            used_ram = round(mem.used / (1024**3), 2)
            
            # Mengambil data Disk utama
            disk = psutil.disk_usage('/')
            total_disk = round(disk.total / (1024**3), 2)
            used_disk = round(disk.used / (1024**3), 2)

            # Cek status baterai dengan aman
            battery = psutil.sensors_battery()
            if battery:
                plug_status = "Mengisi Daya (Charging)" if battery.power_plugged else "Menggunakan Baterai"
                battery_status = f"{battery.percent}% ({plug_status})"
            else:
                battery_status = "Desktop / Sumber Daya Listrik Langsung"

            info_text = f"""
💻 *HOST PC SYSTEM METRICS (VERIFIED):*
• OS Platform: `{sys.platform}`
• CPU Usage: `{psutil.cpu_percent(interval=0.5)}%`
• Logical Cores: `{psutil.cpu_count(logical=True)} Core`
• RAM Total / Terpakai: `{used_ram} GB / {total_ram} GB` (`{mem.percent}%`)
• Disk Utama C:/ Terpakai: `{used_disk} GB / {total_disk} GB` (`{disk.percent}%`)
• Power / Baterai: `{battery_status}`
"""
            await update.message.reply_text(info_text, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"🚨 Gagal membaca info hardware: {e}")

    elif sub_action == "open" and param:
        try:
            if os.name == 'nt':
                subprocess.Popen(f"start {param}", shell=True)
            else:
                subprocess.Popen([param])
            await update.message.reply_text(f"🚀 Perintah membuka `{param}` dieksekusi, Bos!")
        except Exception as e:
            await update.message.reply_text(f"🚨 Gagal membuka aplikasi: {e}")

    elif sub_action == "screenshot":
        try:
            import pyautogui
            snap_path = f"pc_snap_{int(time.time())}.png"
            pyautogui.screenshot(snap_path)
            with open(snap_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption="📸 *Live Host PC Screenshot*")
            os.remove(snap_path)
        except Exception as e:
            await update.message.reply_text(f"🚨 Gagal screenshot (Pastikan pyautogui terinstal): {e}")
    else:
        await update.message.reply_text("🚨 Argumen perintah `/pc` tidak valid.")

async def vision_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /vision [instruksi] untuk memicu mata AI Watcher"""
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    if IS_LOCKDOWN:
        await update.message.reply_text("🔒 *STARK LOCKDOWN ACTIVE.* Sistem mata komputer dikunci.")
        return

    custom_prompt = " ".join(context.args) if context.args else "Periksa ruangan di depan kamera, apakah ada hal penting atau aktivitas yang terlihat?"
    
    await update.message.reply_text("👁️ *COMPUTER VISION:* Mengaktifkan lensa pemantau...")

    def run_async_vision():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result_report = loop.run_until_complete(computer_vision_snapshot_analysis(custom_prompt))
        loop.close()

        url_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ALLOWED_CHAT_ID,
            "text": f"👁️ *AI WATCHER REPORT*\n\n{result_report}",
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url_api, json=payload)
        except Exception as e:
            print(f"[!] Gagal kirim laporan vision: {e}")

    threading.Thread(target=run_async_vision, daemon=True).start()

def run_telegram_bot():
    while True:
        try:
            print("🤖 Memulai Telegram Bot...")
            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

            app.add_handler(CommandHandler("start", menu_command_handler))
            app.add_handler(CommandHandler("menu", menu_command_handler))
            app.add_handler(CallbackQueryHandler(button_callback_handler))
            
            app.add_handler(CommandHandler("lockdown", lockdown_command_handler))
            app.add_handler(CommandHandler("unlock", unlock_command_handler))
            app.add_handler(CommandHandler("legion", legion_command_handler))
            
            app.add_handler(CommandHandler("voice", voice_command_handler))
            app.add_handler(CommandHandler("code", code_command_handler))
            app.add_handler(CommandHandler("status", status_command_handler))
            
            app.add_handler(MessageHandler(filters.VOICE, voice_message_handler))
            app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
            app.add_handler(MessageHandler(filters.Document.PDF, pdf_document_handler))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
            
            app.add_handler(CommandHandler("diagram", diagram_command_handler))
            app.add_handler(CommandHandler("research", research_command_handler))
            app.add_handler(CommandHandler("cmd", cmd_command_handler))
            app.add_handler(CommandHandler("journal", journal_command_handler))
            app.add_handler(CommandHandler("testbug", testbug_command_handler))
            app.add_handler(CommandHandler("git", git_command_handler))
            app.add_handler(CommandHandler("web", web_command_handler))
            app.add_handler(CommandHandler("sentinel", sentinel_command_handler))
            app.add_handler(CommandHandler("recall", recall_command_handler))
            app.add_handler(CommandHandler("pc", pc_command_handler))
            app.add_handler(CommandHandler("pc_advance", pc_advanced_command_handler))
            app.add_handler(CommandHandler("vision", vision_command_handler))

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