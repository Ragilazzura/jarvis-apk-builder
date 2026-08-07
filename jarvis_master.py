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

# --- IMPORT FASTAPI & CORSMiddleware ---
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==========================================
# KONFIGURASI UTAMA & MODEL API
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"

# 🟢 PENYESUAIAN NAMA MODEL RESMI GEMINI
MODEL_NAME = "gemini-2.5-flash"

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {'tools': [{'google_search': {}}]}

JARVIS_PERSONA = (
    "Kamu adalah JARVIS, asisten AI pribadi yang sangat cerdas, responsif, profesional, dan adaptif. "
    "Gunakan sapaan 'Bos' secara proporsional dan jawablah dengan akurat dan lugas."
)

# ==========================================
# DATABASE & MEMORY ENGINE
# ==========================================
MEMORY_DB_PATH = os.path.join(BASE_DIR, "jarvis_memory.db")

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
# OTAK UTAMA JARVIS (DIPAKAI WEBSERVER & TELEGRAM)
# ==========================================
def ask_jarvis(user_msg: str) -> str:
    """Fungsi terpusat untuk memproses jawaban Jarvis dengan Waktu, Search, & Memori"""
    now = datetime.datetime.now()
    time_context = now.strftime("%A, %d %B %Y - Jam %H:%M WIB")
    memories = get_all_memories()

    system_prompt = f"""
{JARVIS_PERSONA}

[KONTEKS WAKTU SISTEM REAL-TIME]:
Hari & Tanggal Sekarang: {time_context}

[MEMORI TERSEMPAN]:
{memories}

Pesan Pengguna: {user_msg}
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=system_prompt,
            config=GROUNDING_CONFIG
        )
        return response.text
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "ResourceExhausted" in err_str:
            return "Maaf Bos, kuota API Gemini sedang mencapai batas (Rate Limit 429). Mohon tunggu 1 menit ya! ⏳"
        return f"🚨 Terjadi kesalahan pada otak Jarvis: {err_str}"

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
# TELEGRAM BOT HANDLER
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
    
    # Debug log agar ketahuan jika Chat ID ditolak
    if chat_id != ALLOWED_CHAT_ID:
        print(f"⚠️ Ditolak: Pesan masuk dari Chat ID {chat_id} (Diberikan akses hanya ke {ALLOWED_CHAT_ID})")
        return

    user_text = update.message.text or ""
    if not user_text: return
    
    # Gunakan Otak Utama Jarvis
    reply_text = ask_jarvis(user_text)
    await safe_reply(update, reply_text)

def run_telegram_bot():
    """Menjalankan Telegram Bot di background thread"""
    while True:
        try:
            print("🤖 Memulai Telegram Bot...")
            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Telegram Error (Auto-restart 5 detik): {e}")
            time.sleep(5)

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🤖 Jarvis Mega-Agent Full Engine Running...")
    
    # 1. Jalankan Discord Subprocess
    try:
        subprocess.Popen(["python", "jarvis_discord.py"])
    except Exception as e:
        print(f"⚠️ Discord error: {e}")
        
    # 2. Jalankan Telegram Bot di Thread Terpisah
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    # 3. Jalankan FastAPI Web Server di Main Thread
    run_fastapi()