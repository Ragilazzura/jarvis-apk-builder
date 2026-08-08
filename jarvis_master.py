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
from PIL import Image
from bs4 import BeautifulSoup
import edge_tts
from google import genai
import chromadb
from pypdf import PdfReader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORT FASTAPI & CORSMiddleware ---
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
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
scheduler.start()

# ==========================================
# FASTAPI SERVER ENGINE + IOT WEBHOOK BRIDGE
# ==========================================
web_app = FastAPI(title="Jarvis Mobile & IoT API")

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
    return {"status": "Jarvis Web & IoT Bridge Online", "lockdown": IS_LOCKDOWN}

@web_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    reply = ask_jarvis(request.message)
    return {"reply": reply}

@web_app.post("/iot/control")
async def iot_control_endpoint(request: IoTCommandRequest):
    """Bridge kontrol smart device / home automation"""
    if IS_LOCKDOWN:
        return {"status": "error", "message": "System is in Lockdown"}
    
    print(f"📡 [STARK IOT BRIDGE] Device: {request.device_id} | Action: {request.action}")
    # Kirim konfirmasi balasan ke Bos
    return {
        "status": "success",
        "device": request.device_id,
        "executed_action": request.action,
        "timestamp": str(datetime.datetime.now())
    }

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

def run_telegram_bot():
    while True:
        try:
            print("🤖 Memulai Telegram Bot...")
            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
            
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