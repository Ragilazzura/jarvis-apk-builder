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
from bs4 import BeautifulSoup
import edge_tts
from google import genai
import chromadb
from pypdf import PdfReader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORT FASTAPI & CORSMiddleware ---
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==========================================
# KONFIGURASI UTAMA & MODEL API
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"

# Model Utama Gemini
MODEL_NAME = "gemini-3.6-flash"

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {'tools': [{'google_search': {}}]}

JARVIS_PERSONA = """
Kamu adalah J.A.R.V.I.S., asisten AI pribadi yang sangat cerdas, adaptif, dan loyal milik Bos.

GAYA BAHASA & KEPRIBADIAN:
1. BAHASA BILINGUAL & ADAPTIF:
   - Secara otomatis sesuaikan bahasa jawabanmu berdasarkan bahasa yang digunakan Bos atau konteks percakapan (Bahasa Indonesia atau Bahasa Inggris).
   - Jika Bos bertanya dalam Bahasa Indonesia, jawab dalam Bahasa Indonesia yang santai, luwes, dan alami.
   - Jika Bos bertanya dalam Bahasa Inggris (atau topik teknis/koding yang lebih pas dijelaskan dalam Bahasa Inggris), jawab dengan Bahasa Inggris yang lancar, presisi, dan natural.
2. PANGGILAN KHAS:
   - Panggil pengguna dengan sebutan "Bos" (atau "Boss" / "Sir" jika sedang merespons dalam Bahasa Inggris).
3. GAYA KOMUNIKASI:
   - Tampil cerdas, responsif, langsung ke poin utama, dan miliki sedikit sentuhan kecerdasan/humor (witty) khas J.A.R.V.I.S.
4. ATURAN TAMPILAN TEKS:
   - JANGAN gunakan simbol pagar (#) untuk header.
   - JANGAN gunakan simbol bintang (*) atau (**) berlebihan. Tulis jawaban dalam paragraf atau poin sederhana agar rapi di layar chat.
"""

# ==========================================
# DATABASE & MEMORY ENGINE (SQLITE + CHROMADB)
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

def save_memory(category: str, content: str) -> str:
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO long_term_memory (category, content) VALUES (?, ?)", (category, content))
        conn.commit()
        conn.close()
        return "Memori berhasil disimpan!"
    except Exception as e:
        return f"Gagal menyimpan memori: {e}"

# ==========================================
# OTAK UTAMA JARVIS
# ==========================================
def ask_jarvis(user_msg: str) -> str:
    now = datetime.datetime.now()
    time_context = now.strftime("%A, %d %B %Y - Jam %H:%M WIB")
    memories = get_all_memories()
    vector_context = search_vector_db(user_msg)

    system_prompt = f"""
{JARVIS_PERSONA}

[KONTEKS WAKTU SISTEM REAL-TIME]:
Hari & Tanggal Sekarang: {time_context}

[MEMORI TERSEMPAN]:
{memories}
{vector_context}

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
            print(f"🔄 Mencoba menghubungi model: {model_name}...")
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
            err_str = str(e)
            print(f"❌ Gagal pada model {model_name} (with Grounding): {err_str}")
            try:
                print(f"🔄 Retry {model_name} TANPA Grounding Search...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=system_prompt
                )
                print(f"✅ Berhasil merespons (Tanpa Search) menggunakan model: {model_name}")
                clean_text = response.text
                clean_text = re.sub(r'#+\s*', '', clean_text)
                clean_text = re.sub(r'^\*\s+', '• ', clean_text, flags=re.MULTILINE)
                clean_text = clean_text.replace('**', '').replace('*', '')

                return clean_text
            except Exception as e2:
                print(f"❌ Gagal pada model {model_name} (Pure AI): {e2}")
                continue

    return "Maaf Bos, server Google sedang membatasi kuota API di wilayah ini. Mohon tunggu 30 detik ya! ⏳"

# ==========================================
# VOICE ENGINE (EDGE-TTS)
# ==========================================
async def generate_voice_response(text: str, output_path: str = "voice_reply.ogg") -> str:
    try:
        clean_speech = re.sub(r'[^\w\s,?!.]', '', text)
        communicate = edge_tts.Communicate(clean_speech, VOICE_ACTOR)
        await communicate.save(output_path)
        return output_path
    except Exception as e:
        print(f"[!] Voice generation error: {e}")
        return ""

# ==========================================
# AUTONOMOUS CODE AGENT ENGINE
# ==========================================
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
        full_prompt = f"""
Kamu adalah Software Developer Agent otomatis.
Buatkan kode program Python lengkap berdasarkan instruksi berikut:
{prompt_request}

{f'PERBAIKAN ERROR PERCOBAAN SEBELUMNYA: {error_context}' if error_context else ''}

Berikan HANYA kode program murni tanpa penjelasan atau markdown.
"""
        code_result = ask_jarvis(full_prompt)
        code_result = re.sub(r'```python|```', '', code_result).strip()
        
        with open(target_filename, "w", encoding="utf-8") as f:
            f.write(code_result)
            
        is_success, log_msg = test_code_execution(target_filename)
        if is_success:
            return True, f"✅ Code Agent Success! File `{target_filename}` berhasil dibuat & lolos tes sintaks (Percobaan {attempt}).", target_filename
        else:
            error_context = log_msg
            
    return False, f"🚨 Code Agent gagal setelah {max_attempts}x percobaan. Error:\n`{error_context}`", target_filename

# ==========================================
# PROACTIVE SCHEDULER
# ==========================================
def daily_briefing_job():
    briefing_prompt = "Berikan briefing pagi singkat, cuaca umum, dan motivasi untuk Bos memulai hari."
    briefing_text = ask_jarvis(briefing_prompt)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALLOWED_CHAT_ID,
        "text": f"🌅 GOOD MORNING BRIEFING\n\n{briefing_text}"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Gagal kirim briefing: {e}")

scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
scheduler.add_job(daily_briefing_job, 'cron', hour=7, minute=0)
scheduler.start()

# ==========================================
# FASTAPI SERVER ENGINE + CORS (FLUTTER)
# ==========================================
web_app = FastAPI(title="Jarvis Mobile API")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@web_app.get("/")
def read_root():
    return {"status": "Jarvis Web API Online", "time": str(datetime.datetime.now())}

@web_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    reply = ask_jarvis(request.message)
    return {"reply": reply}

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
    try: 
        await update.message.reply_html(clean_markdown_to_html(text))
    except: 
        await update.message.reply_text(text)

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    user_text = update.message.text or ""
    if not user_text: return
    
    reply_text = ask_jarvis(user_text)
    await safe_reply(update, reply_text)

async def voice_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler perintah /voice <pesan>"""
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
    """Handler perintah /code <instruksi>"""
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
    """Handler upload dokumen PDF"""
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

def run_telegram_bot():
    while True:
        try:
            print("🤖 Memulai Telegram Bot...")
            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Register Command Handlers
            app.add_handler(CommandHandler("voice", voice_command_handler))
            app.add_handler(CommandHandler("code", code_command_handler))
            
            # Register Message Handlers
            app.add_handler(MessageHandler(filters.Document.PDF, pdf_document_handler))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
            
            app.run_polling(drop_pending_updates=True, stop_signals=None)
        except Exception as e:
            print(f"⚠️ Telegram Error (Auto-restart 5 detik): {e}")
            time.sleep(5)

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🤖 Jarvis Mega-Agent Full Engine Running...")
    
    try:
        subprocess.Popen(["python", "jarvis_discord.py"])
    except Exception as e:
        print(f"⚠️ Discord error: {e}")
        
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    run_fastapi()