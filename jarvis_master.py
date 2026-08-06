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
from bs4 import BeautifulSoup
import edge_tts
from google import genai
import chromadb
from pypdf import PdfReader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# --- IMPORT FASTAPI & UVICORN UNTUK FLUTTER ---
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

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
    "Aturan Bahasa Wajib:\n"
    "1. WAJIB mutlak menggunakan bahasa yang SAMA PERSIS dengan yang digunakan oleh pengguna pada pesan terakhirnya.\n"
    "2. Gunakan sapaan 'Bos' (atau 'Sir' jika berbahasa Inggris) secara proporsional.\n"
    "3. Jawablah dengan akurat, lugas, dan penyampaian yang enak didengar."
)

# ==========================================
# FASTAPI SERVER ENGINE (UNTUK FLUTTER)
# ==========================================
web_app = FastAPI(title="Jarvis Mobile API")

class ChatRequest(BaseModel):
    message: str

@web_app.get("/")
def read_root():
    return {"status": "Jarvis Web API Online", "time": str(datetime.datetime.now())}

@web_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_msg = request.message
    try:
        # Panggil Gemini langsung untuk respon Flutter
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"{JARVIS_PERSONA}\n\nPesan dari aplikasi HP Bos: {user_msg}"
        )
        return {"reply": response.text}
    except Exception as e:
        return {"reply": f"Maaf Bos, terjadi masalah pada server: {str(e)}"}

def run_fastapi():
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Menyalakan FastAPI Server di Port {port}...")
    uvicorn.run(web_app, host="0.0.0.0", port=port)

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
# VECTOR DATABASE & RAG ENGINE
# ==========================================

VECTOR_DB_PATH = os.path.join(BASE_DIR, "jarvis_vector_db")

try:
    chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    knowledge_collection = chroma_client.get_or_create_collection(name="jarvis_knowledge")
except Exception as e:
    print(f"[!] Gagal inisialisasi Vector DB: {e}")

def ingest_document_to_vector_db(file_path: str, doc_name: str) -> str:
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

        chunk_size = 1000
        chunks = [text_content[i:i+chunk_size] for i in range(0, len(text_content), chunk_size)]
        
        ids = [f"{doc_name}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": doc_name} for _ in chunks]

        knowledge_collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        return f"🧠 <b>KNOWLEDGE INGESTED:</b> Dokumen <code>{doc_name}</code> berhasil diserap ke dalam Otak Vector (Total: {len(chunks)} potongan memori)."
    except Exception as e:
        return f"🚨 Gagal menyerap dokumen: {str(e)}"

def search_vector_db(query: str) -> str:
    try:
        if knowledge_collection.count() == 0:
            return ""
        
        results = knowledge_collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if results['documents'] and results['documents'][0]:
            context = "\n\n---\n".join(results['documents'][0])
            return f"\n\n[Konteks dari Vector DB Jarvis]:\n{context}"
        return ""
    except Exception as e:
        print(f"Error Vector Search: {e}")
        return ""

# ==========================================
# MODULES: DEVOPS, SCRAPER, ORGANIZER, TASKS
# ==========================================

def get_server_stats() -> str:
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
# HELPER FUNCTIONS
# ==========================================

def clean_markdown_to_html(text: str) -> str:
    if not text: return ""

    text = html.escape(text)

    text = re.sub(r'^#{1,4}\s+(.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[\*\-]\s+', r'• ', text, flags=re.MULTILINE)

    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\w)\*(.*?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

    text = text.replace('---', '──────────────')

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
        english_indicators = ["the", "is", "you", "to", "and", "a", "of", "in", "it", "that", "sir", "hello", "hi", "what", "how", "can"]
        english_match_count = sum(1 for w in words if w in english_indicators)
        
        is_english = english_match_count >= 2 or (len(words) > 0 and words[0] in ["hello", "hi", "sure", "i", "here's", "certainly"])
        
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
# UNIFIED INTENT ROUTER ENGINE (TELEGRAM)
# ==========================================

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    is_voice = bool(update.message.voice)
    is_photo = bool(update.message.photo)
    is_document = bool(update.message.document)
    user_input_text = update.message.caption or update.message.text or ""

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

    if is_document:
        doc_file = await update.message.document.get_file()
        doc_name = update.message.document.file_name
        doc_path = os.path.join(BASE_DIR, doc_name)
        await doc_file.download_to_drive(doc_path)
        await safe_reply(update, f"📂 Menyerap pengetahuan dari <code>{doc_name}</code> ke dalam Vector DB...")
        
        ingest_result = ingest_document_to_vector_db(doc_path, doc_name)
        
        if os.path.exists(doc_path): os.remove(doc_path)
        await safe_reply(update, ingest_result)
        return

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

        elif intent == "REMEMBER":
            save_memory(parsed.get("memory_category", "Umum"), parsed.get("memory_content", clean_query))
            await safe_reply(update, f"🧠 <b>MEMORI DICATAT!</b>")

        else:
            vector_context = search_vector_db(clean_query)
            final_prompt = f"{JARVIS_PERSONA}\n\nMemori Jangka Pendek:\n{memories}{vector_context}\n\nPertanyaan Bos:\n{clean_query}"
            
            c_res = client.models.generate_content(model=MODEL_NAME, contents=final_prompt)
            await safe_reply(update, c_res.text)

        if is_voice:
            await send_voice_response(update, voice_summary)

    except Exception as e:
        await safe_reply(update, f"🚨 Gagal memproses: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID: return
    msg = "⚡ <b>JARVIS MEGA-AGENT ONLINE!</b> 🤖\n\nSeluruh Sistem Siap Dijalankan!"
    await safe_reply(update, msg)

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    print("🤖 Jarvis Mega-Agent (Proactive + Web API Mode) Running...")
    
    # 1. NYALAKAN FASTAPI DI THREAD TERPISAH (UNTUK FLUTTER)
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # 2. NYALAKAN SUB-SISTEM DISCORD
    try:
        subprocess.Popen(["python", "jarvis_discord.py"])
        print("✅ Sub-sistem Discord berhasil dinyalakan.")
    except Exception as e:
        print(f"⚠️ Gagal menyalakan Discord: {e}")
        
    # 3. NYALAKAN TELEGRAM BOT
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
    app.add_handler(MessageHandler(filters.VOICE, unified_handler))
    app.add_handler(MessageHandler(filters.PHOTO, unified_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, unified_handler))
    
    app.run_polling()

if __name__ == "__main__":
    main()