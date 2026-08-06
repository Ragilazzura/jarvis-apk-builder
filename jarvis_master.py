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

# Konfigurasi Utama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"
MODEL_NAME = "gemini-3.1-flash-lite"

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {'tools': [{'google_search': {}}]}

JARVIS_PERSONA = (
    "Kamu adalah JARVIS, asisten AI pribadi yang sangat cerdas, responsif, profesional, dan adaptif. "
    "Gunakan sapaan 'Bos' secara proporsional dan jawablah dengan akurat dan lugas."
)

# ==========================================
# FASTAPI SERVER ENGINE + CORS (UNTUK FLUTTER)
# ==========================================
web_app = FastAPI(title="Jarvis Mobile API")

# 🛑 IZINKAN KONEKSI DARI FLUTTER WEB / MOBILE (CORS)
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
    user_msg = request.message
    
    # 🕒 1. Suntikkan Waktu Real-Time Saat Ini
    now = datetime.datetime.now()
    time_context = now.strftime("%A, %d %B %Y - Jam %H:%M WIB")
    
    memories = get_all_memories()
    
    system_prompt = f"""
{JARVIS_PERSONA}

[KONTEKS WAKTU SISTEM REAL-TIME]:
Hari & Tanggal Sekarang: {time_context}

[MEMORI TERIMPAN]:
{memories}

Pesan Pengguna: {user_msg}
"""
    try:
        # 🌐 2. Aktifkan Google Search Grounding agar bisa cek cuaca/berita real-time
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=system_prompt,
            config=GROUNDING_CONFIG
        )
        return {"reply": response.text}
    except Exception as e:
        return {"reply": f"Maaf Bos, terjadi masalah pada server: {str(e)}"}

def run_fastapi():
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Menyalakan FastAPI Server di Port {port}...")
    uvicorn.run(web_app, host="0.0.0.0", port=port)

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
    except Exception as e: print(f"[!] Warning DB: {e}")

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
    except Exception as e: return f"Error DB: {e}"

# ==========================================
# TELEGRAM HANDLER
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
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID: return
    user_text = update.message.text or ""
    if not user_text: return
    
    try:
        c_res = client.models.generate_content(model=MODEL_NAME, contents=f"{JARVIS_PERSONA}\n\n{user_text}")
        await safe_reply(update, c_res.text)
    except Exception as e:
        await safe_reply(update, f"🚨 Error: {e}")

# ==========================================
# MAIN EXECUTION
# ==========================================
def run_telegram_bot():
    """Menjalankan Telegram Bot di thread terpisah secara aman"""
    while True:
        try:
            print("🤖 Memulai Telegram Bot...")
            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Telegram Error (Akan auto-restart dalam 5 detik): {e}")
            time.sleep(5)

if __name__ == "__main__":
    print("🤖 Jarvis Mega-Agent Running...")
    
    # 1. Jalankan Discord
    try:
        subprocess.Popen(["python", "jarvis_discord.py"])
    except Exception as e:
        print(f"⚠️ Discord error: {e}")
        
    # 2. Jalankan Telegram Bot di Background Thread (supaya conflict tidak mematikan server)
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    # 3. KUNCI UTAMA: Jalankan FastAPI di MAIN THREAD agar Railway Container selalu HIDUP
    run_fastapi()