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
from bs4 import BeautifulSoup
import edge_tts
from google import genai
import chromadb
from pypdf import PdfReader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Konfigurasi Utama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"
MODEL_NAME = "gemini-3.1-flash-lite"

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {
    'tools': [{'google_search': {}}]
}

JARVIS_PERSONA = (
    "Kamu adalah JARVIS, asisten AI pribadi yang sangat cerdas, responsif, profesional, dan adaptif. "
    "Aturan Bahasa:\n"
    "1. Sesuaikan bahasa responmu secara otomatis dengan bahasa pengguna (Bahasa Indonesia atau Bahasa Inggris).\n"
    "2. Gunakan sapaan 'Bos' secara proporsional.\n"
    "3. Jawablah dengan akurat, lugas, dan penyampaian yang enak didengar."
)

# ==========================================
# LONG-TERM MEMORY & DATABASE ENGINE
# ==========================================

MEMORY_DB_PATH = os.path.join(BASE_DIR, "jarvis_memory.db")

def init_memory_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT,
                status TEXT DEFAULT 'Pending',
                due TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                summary TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Warning Gagal inisialisasi DB: {e}")

init_memory_db()

def save_memory(category: str, content: str):
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO long_term_memory (category, content) VALUES (?, ?)", (category, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Gagal simpan memori: {e}")

def get_all_memories() -> str:
    if not os.path.exists(MEMORY_DB_PATH):
        return "Tidak ada memori tersimpan."
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT category, content FROM long_term_memory ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return "Belum ada catatan memori."
        return "\n".join([f"- [{cat}] {cont}" for cat, cont in rows])
    except Exception as e:
        return f"Error membaca memori: {e}"

# ==========================================
# VECTOR DATABASE & RAG ENGINE (FASE 2)
# ==========================================

VECTOR_DB_PATH = os.path.join(BASE_DIR, "jarvis_vector_db")

# Inisialisasi ChromaDB secara lokal
try:
    chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    knowledge_collection = chroma_client.get_or_create_collection(name="jarvis_knowledge")
except Exception as e:
    print(f"[!] Gagal inisialisasi Vector DB: {e}")

def ingest_document_to_vector_db(file_path: str, doc_name: str) -> str:
    """Membaca dokumen PDF/TXT dan memasukkannya ke Vector DB"""
    try:
        text_content = ""
        if file_path.lower().endswith('.pdf'):
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text: text_content += text + "\n"
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()

        if not text_content.strip():
            return "Dokumen kosong atau tidak bisa dibaca teksnya."

        # Pecah teks menjadi "chunks" (potongan kecil) agar mudah diingat AI
        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        ids = [f"{doc_name}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": doc_name} for _ in chunks]

        # Masukkan ke dalam "Otak" ChromaDB
        knowledge_collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        return f"🧠 <b>KNOWLEDGE INGESTED:</b> Dokumen <code>{doc_name}</code> berhasil diserap ke dalam Otak Vector (Total: {len(chunks)} potongan memori)."
    except Exception as e:
        return f"🚨 Gagal menyerap dokumen: {str(e)}"

def search_vector_db(query: str) -> str:
    """Mencari informasi relevan dari dalam Vector DB"""
    try:
        if knowledge_collection.count() == 0:
            return ""
        
        results = knowledge_collection.query(
            query_texts=[query],
            n_results=3 # Ambil 3 potongan teks paling relevan
        )
        
        if results['documents'] and results['documents'][0]:
            context = "\n\n---\n".join(results['documents'][0])
            return f"\n\n[Konteks dari Vector DB Jarvis]:\n{context}"
        return ""
    except Exception as e:
        print(f"Error Vector Search: {e}")
        return ""
# ==========================================
# NEW MODULES: DEVOPS, SCRAPER, ORGANIZER, TASKS
# ==========================================

def get_server_stats() -> str:
    """Modul DevOps: Memantau kesehatan server"""
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return (
            f"🖥️ <b>SERVER HEALTH MONITOR</b>\n\n"
            f"• <b>CPU Usage:</b> {cpu}%\n"
            f"• <b>RAM Usage:</b> {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
            f"• <b>Disk Usage:</b> {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)\n"
            f"• <b>Status:</b> All systems operational ⚡"
        )
    except Exception as e:
        return f"Gagal mengecek stats server: {str(e)}"

def scrape_and_summarize(target_url: str) -> str:
    """Modul Scraper: Sedot data web & simpan pipeline"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.extract()
        
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        clean_text = '\n'.join(chunk for chunk in lines if chunk)[:3000]
        
        prompt = f"Rangkum dan ekstrak data paling penting dari hasil web scraping berikut:\n{clean_text}"
        res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        summary = res.text
        
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scraped_data (url, summary) VALUES (?, ?)", (target_url, summary))
        conn.commit()
        conn.close()
        
        return f"🕷️ <b>WEB SCRAPING SUCCESS:</b>\n<b>URL:</b> {target_url}\n\n<b>RINGKASAN:</b>\n{summary}"
    except Exception as e:
        return f"🚨 Scraping gagal: {str(e)}"

def organize_directory(target_path: str = BASE_DIR) -> str:
    """Modul Organizer: Merapikan folder berdasarkan ekstensi file"""
    if not os.path.exists(target_path):
        return f"Path <code>{target_path}</code> tidak ditemukan."
    
    categories = {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
        "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx"],
        "Code": [".py", ".js", ".html", ".css", ".json"],
        "Archives": [".zip", ".tar", ".gz", ".rar"],
        "Audio_Video": [".mp3", ".wav", ".mp4", ".mkv"]
    }
    
    moved_count = 0
    for item in os.listdir(target_path):
        item_path = os.path.join(target_path, item)
        if os.path.isfile(item_path):
            ext = os.path.splitext(item)[1].lower()
            for cat, exts in categories.items():
                if ext in exts:
                    cat_dir = os.path.join(target_path, cat)
                    os.makedirs(cat_dir, exist_ok=True)
                    shutil.move(item_path, os.path.join(cat_dir, item))
                    moved_count += 1
                    break
    return f"🧹 <b>FOLDER ORGANIZED:</b> Berhasil merapikan {moved_count} file di folder <code>{target_path}</code>."

def manage_tasks(action: str, task_desc: str = "") -> str:
    """Modul Productivity Task Hub"""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    cursor = conn.cursor()
    
    if action == "ADD":
        cursor.execute("INSERT INTO tasks (task, due) VALUES (?, ?)", (task_desc, "Hari ini"))
        conn.commit()
        conn.close()
        return f"📌 <b>TASK DICATAT:</b> '{task_desc}'"
    elif action == "LIST":
        cursor.execute("SELECT id, task, status FROM tasks WHERE status='Pending'")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return "📋 Tidak ada tugas pending, Bos!"
        return "📋 <b>DAFTAR TUGAS PENDING:</b>\n" + "\n".join([f"• [{r[0]}] {r[1]}" for r in rows])
    
    conn.close()
    return "Aksi task tidak dikenal."

# ==========================================
# HELPER FUNCTIONS & MULTILINGUAL VOICE
# ==========================================

def clean_markdown_to_html(text: str) -> str:
    if not text: return ""

    text = text.replace('<b>', '[[B_START]]').replace('</b>', '[[B_END]]')
    text = text.replace('<i>', '[[I_START]]').replace('</i>', '[[I_END]]')
    text = text.replace('<code>', '[[C_START]]').replace('</code>', '[[C_END]]')

    text = html.escape(text)

    text = re.sub(r'^#{1,4}\s+(.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    text = re.sub(r'^\s*[\*\-]\s+', r'• ', text, flags=re.MULTILINE)

    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\w)\*(.*?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

    text = text.replace('---', '──────────────')

    text = text.replace('[[B_START]]', '<b>').replace('[[B_END]]', '</b>')
    text = text.replace('[[I_START]]', '<i>').replace('[[I_END]]', '</i>')
    text = text.replace('[[C_START]]', '<code>').replace('[[C_END]]', '</code>')

    return text

def clean_text_for_speech(text: str) -> str:
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    return text.replace("*", "").replace("`", "").replace("_", "").replace("#", "").strip()

async def send_voice_response(update: Update, raw_text: str):
    temp_voice_out = os.path.join(BASE_DIR, "temp_voice_out.mp3")
    try:
        spoken_text = clean_text_for_speech(raw_text)
        words = spoken_text.lower().split()
        is_english = sum(1 for w in words if w in ["hello", "hi", "the", "is", "you", "to", "for", "sir", "boss"]) >= 2
        chosen_voice = "en-US-AndrewNeural" if is_english else VOICE_ACTOR
        
        communicate = edge_tts.Communicate(spoken_text, chosen_voice, rate="+8%")
        await communicate.save(temp_voice_out)

        with open(temp_voice_out, 'rb') as audio_file:
            await update.message.reply_voice(voice=audio_file, caption=f"🎙️ Voice Response ({'EN' if is_english else 'ID'})")

        if os.path.exists(temp_voice_out): os.remove(temp_voice_out)
    except Exception as e:
        print(f"[!] Gagal voice response: {e}")
        if os.path.exists(temp_voice_out): os.remove(temp_voice_out)

async def safe_reply(update: Update, text: str):
    try:
        await update.message.reply_html(clean_markdown_to_html(text))
    except:
        await update.message.reply_text(text)

# ==========================================
# SELF-HEALING & MULTI-AGENT ENGINE
# ==========================================

async def run_with_self_healing(update: Update, target_fp: str, max_retries: int = 3):
    file_dir = os.path.dirname(target_fp)
    file_name = os.path.basename(target_fp)
    
    for attempt in range(1, max_retries + 1):
        await safe_reply(update, f"⚙️ Menjalankan <code>{file_name}</code> ({attempt}/{max_retries})...")
        r_res = subprocess.run(["python", target_fp], capture_output=True, text=True, timeout=25, cwd=file_dir)
        
        if r_res.returncode == 0:
            out = r_res.stdout if r_res.stdout else "(Program selesai)"
            await safe_reply(update, f"✅ <b>BERHASIL:</b>\n\n{out}")
            return True
            
        error_output = r_res.stderr if r_res.stderr else r_res.stdout
        await safe_reply(update, f"⚠️ <b>ERROR DETECTED:</b>\n<pre>{error_output[:600]}</pre>\n🛡️ <i>Self-Healing in progress...</i>")
        
        try:
            with open(target_fp, "r", encoding="utf-8") as f: current_code = f.read()
            fix_prompt = f"Fix this error in Python code:\nCODE:\n{current_code}\nERROR:\n{error_output}\nOutput JSON MURNI: {{\"explanation\":\"...\", \"fixed_code\":\"...\"}}"
            fix_res = client.models.generate_content(model=MODEL_NAME, contents=fix_prompt)
            fix_data = json.loads(fix_res.text.replace("```json", "").replace("```", "").strip())
            fixed_code = fix_data.get("fixed_code", "")
            if fixed_code:
                with open(target_fp, "w", encoding="utf-8") as f: f.write(fixed_code)
                await safe_reply(update, f"🔧 <b>Fix Applied:</b> {fix_data.get('explanation')}")
            else: return False
        except Exception as e:
            await safe_reply(update, f"🚨 Auto-Fix Gagal: {str(e)}")
            return False
    return False

# ==========================================
# UNIFIED INTENT ROUTER ENGINE
# ==========================================

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    is_voice = bool(update.message.voice)
    is_photo = bool(update.message.photo)
    is_document = bool(update.message.document)
    user_input_text = update.message.caption or update.message.text or ""

    # 1. VISION (FOTO)
    if is_photo:
        await safe_reply(update, "👁️ Menganalisis gambar Bos...")
        photo_file = await update.message.photo[-1].get_file()
        photo_path = os.path.join(BASE_DIR, "temp_vision.jpg")
        await photo_file.download_to_drive(photo_path)
        with open(photo_path, "rb") as f: img_bytes = f.read()
        
        v_prompt = user_input_text if user_input_text else "Analisis gambar ini secara detail."
        try:
            v_res = client.models.generate_content(model=MODEL_NAME, contents=[{"inline_data": {"mime_type": "image/jpeg", "data": img_bytes}}, v_prompt])
            resp_txt = v_res.text
        except Exception as e: resp_txt = f"Gagal analisa gambar: {str(e)}"
        
        if os.path.exists(photo_path): os.remove(photo_path)
        await safe_reply(update, f"🖼️ <b>ANALISIS VISION:</b>\n\n{resp_txt}")
        return

    # 2. DOCUMENT / PDF (VECTOR DB INGESTION)
    if is_document:
        doc_file = await update.message.document.get_file()
        doc_name = update.message.document.file_name
        doc_path = os.path.join(BASE_DIR, doc_name)
        await doc_file.download_to_drive(doc_path)
        await safe_reply(update, f"📂 Menyerap pengetahuan dari <code>{doc_name}</code> ke dalam Vector DB...")
        
        # Masukkan ke Vector DB
        ingest_result = ingest_document_to_vector_db(doc_path, doc_name)
        
        if os.path.exists(doc_path): os.remove(doc_path)
        await safe_reply(update, ingest_result)
        return

    # 3. VOICE NOTE
    if is_voice:
        await safe_reply(update, "🎙️ Mengolah pesan suara...")
        temp_audio_path = os.path.join(BASE_DIR, "temp_voice_input.ogg")
        try:
            voice_file = await update.message.voice.get_file()
            await voice_file.download_to_drive(temp_audio_path)
            with open(temp_audio_path, "rb") as f: audio_bytes = f.read()
            t_res = client.models.generate_content(model=MODEL_NAME, contents=[{"inline_data": {"mime_type": "audio/ogg", "data": audio_bytes}}, "Transkripsikan audio ini."])
            user_input_text = t_res.text.strip()
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
        except Exception as e:
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
            await safe_reply(update, f"🚨 Gagal memproses suara: {str(e)}")
            return

    if not user_input_text: return

    memories = get_all_memories()
    router_prompt = f"""
    Analisis perintah: "{user_input_text}"
    Memori: {memories}
    Pilih intent: SEARCH, BUILD, CMD, RUN, REMEMBER, MONITOR, SCRAPE, ORGANIZE, TASK, CHAT.
    Output JSON MURNI:
    {{
        "intent": "SEARCH/BUILD/CMD/RUN/REMEMBER/MONITOR/SCRAPE/ORGANIZE/TASK/CHAT",
        "clean_query": "query rapi atau url jika scrape",
        "voice_summary": "ringkasan lisan pendek",
        "memory_category": "kategori",
        "memory_content": "konten"
    }}
    """
    try:
        router_res = client.models.generate_content(model=MODEL_NAME, contents=router_prompt)
        parsed = json.loads(router_res.text.replace("```json", "").replace("```", "").strip())
        
        intent = parsed.get("intent", "CHAT")
        clean_query = parsed.get("clean_query", user_input_text)
        voice_summary = parsed.get("voice_summary", "Siap Bos.")

        if intent == "MONITOR":
            stats = get_server_stats()
            await safe_reply(update, stats)

        elif intent == "SCRAPE":
            await safe_reply(update, f"🕷️ Menyedot data web dari <code>{clean_query}</code>...")
            res_scrape = scrape_and_summarize(clean_query)
            await safe_reply(update, res_scrape)

        elif intent == "ORGANIZE":
            res_org = organize_directory()
            await safe_reply(update, res_org)

        elif intent == "TASK":
            if "lihat" in clean_query.lower() or "list" in clean_query.lower():
                res_task = manage_tasks("LIST")
            else:
                res_task = manage_tasks("ADD", clean_query)
            await safe_reply(update, res_task)

        elif intent == "SEARCH":
            await safe_reply(update, f"🌐 Riset internet: '<i>{clean_query}</i>'...")
            s_res = client.models.generate_content(model=MODEL_NAME, contents=f"{JARVIS_PERSONA}\nRangkum: {clean_query}", config=GROUNDING_CONFIG)
            await safe_reply(update, f"🔍 <b>HASIL RISET:</b>\n\n{s_res.text}")

        elif intent == "CMD":
            cmd_res = subprocess.run(clean_query, shell=True, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
            await safe_reply(update, f"🖥️ <b>OUTPUT CMD:</b>\n\n{cmd_res.stdout or '(Selesai)'}")

        elif intent == "RUN":
            target_fn = clean_query.replace("python", "").replace("run", "").strip()
            target_fp = None
            for root, dirs, files in os.walk(BASE_DIR):
                if target_fn in files:
                    target_fp = os.path.join(root, target_fn)
                    break
            if target_fp:
                await run_with_self_healing(update, target_fp)
            else:
                await safe_reply(update, f"❌ File <code>{target_fn}</code> tidak ditemukan.")

        elif intent == "REMEMBER":
            save_memory(parsed.get("memory_category", "Umum"), parsed.get("memory_content", clean_query))
            await safe_reply(update, f"🧠 <b>MEMORI DICATAT!</b>")

        else:
            vector_context = search_vector_db(clean_query)
            final_prompt = f"{JARVIS_PERSONA}\n\nMemori Jangka Pendek:\n{memories}{vector_context}\n\nPertanyaan Bos:\n{clean_query}"
            
            c_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=final_prompt
            )
            await safe_reply(update, f"💬 <b>JARVIS:</b>\n\n{c_res.text}")

        if is_voice:
            await send_voice_response(update, voice_summary)

    except Exception as e:
        await safe_reply(update, f"🚨 Gagal memproses: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID: return
    msg = (
        "⚡ <b>JARVIS MEGA-AGENT ONLINE!</b> 🤖\n\n"
        "Seluruh 10 Sistem Utama Siap Dijalankan:\n"
        "• 🧠 Long-Term Memory\n"
        "• 🖥️ Server Health DevOps Monitor\n"
        "• 🕷️ Web Scraping & Data Pipeline\n"
        "• 🧹 Smart File Organizer\n"
        "• 📋 Task & Productivity Hub\n"
        "• 🛡️ Self-Healing Debugger\n"
        "• 👁️ Vision & PDF Analyzer\n"
        "• 🎙️ Bilingual Voice Note"
    )
    await safe_reply(update, msg)

# ==========================================
# PROACTIVE & AUTONOMOUS ENGINE (FASE 1)
# ==========================================

async def auto_server_alert(context: ContextTypes.DEFAULT_TYPE):
    """Mengecek CPU setiap beberapa menit, kirim alert jika kritis"""
    cpu = psutil.cpu_percent(interval=1)
    if cpu > 85.0: # Batas toleransi kritis
        alert_msg = f"🚨 <b>URGENT ALERT!</b> 🚨\n\nBos, penggunaan CPU server saat ini melonjak hingga <b>{cpu}%</b>! Mohon segera lakukan pengecekan sistem."
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=alert_msg, parse_mode='HTML')

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    """Memberikan laporan harian secara otomatis setiap pagi"""
    stats = get_server_stats()
    tasks = manage_tasks("LIST")
    
    prompt = (
        f"Buat sapaan selamat pagi yang profesional dan semangat untuk 'Bos'. "
        f"Lalu rangkumkan data ini dengan luwes: \nStatus Server: {stats}\nAgenda: {tasks}."
    )
    
    try:
        # Generate laporan via Gemini
        res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        briefing_text = res.text
        
        # Kirim teks
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=clean_markdown_to_html(briefing_text), parse_mode='HTML')
        
        # Generate & Kirim Voice Note otomatis
        temp_voice = os.path.join(BASE_DIR, "briefing_voice.mp3")
        spoken_text = clean_text_for_speech(briefing_text)
        communicate = edge_tts.Communicate(spoken_text, VOICE_ACTOR, rate="+8%")
        await communicate.save(temp_voice)
        
        with open(temp_voice, 'rb') as audio_file:
            await context.bot.send_voice(chat_id=ALLOWED_CHAT_ID, voice=audio_file, caption="🎙️ Morning Briefing Audio")
            
        if os.path.exists(temp_voice): os.remove(temp_voice)
    except Exception as e:
        print(f"Gagal mengirim briefing: {e}")

def main():
    print("🤖 Jarvis Mega-Agent (Proactive Mode) Running...")
    try:
        subprocess.Popen(["python", "jarvis_discord.py"])
        print("✅ Sub-sistem Discord berhasil dinyalakan.")
    except Exception as e:
        print(f"⚠️ Gagal menyalakan Discord: {e}")
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
    app.add_handler(MessageHandler(filters.VOICE, unified_handler))
    app.add_handler(MessageHandler(filters.PHOTO, unified_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, unified_handler))
    
    jq = app.job_queue
    jq.run_repeating(auto_server_alert, interval=600, first=10)
    
    import datetime
    target_time = datetime.time(hour=7, minute=0, second=0) 
    jq.run_daily(morning_briefing, time=target_time)
    
    app.run_polling()

if __name__ == "__main__":
    main()