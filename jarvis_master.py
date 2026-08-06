os_env_check = True
import os
import json
import re
import shutil
import subprocess
import asyncio
import sqlite3
import threading
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import edge_tts
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Konfigurasi Utama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"
MODEL_NAME = "gemini-3.6-flash"

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {
    'tools': [{'google_search': {}}]
}

JARVIS_PERSONA = (
    "Kamu adalah JARVIS, asisten AI pribadi yang sangat cerdas, responsif, profesional, dan adaptif. "
    "Aturan Bahasa (Language Adaptation):\n"
    "1. Sesuaikan bahasa responmu secara otomatis dengan bahasa yang digunakan pengguna saat ini (Bahasa Indonesia atau Bahasa Inggris).\n"
    "2. Jika pengguna memberikan instruksi eksplisit untuk menggunakan bahasa tertentu, ikuti perintah tersebut.\n"
    "3. Gunakan sapaan 'Bos' secara proporsional.\n"
    "4. Jawablah dengan akurat, lugas, dan penyampaian yang enak didengar."
)

# ==========================================
# LONG-TERM MEMORY ENGINE (SQLITE)
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
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Warning Gagal inisialisasi DB memori: {e}")

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
        cursor.execute("SELECT category, content FROM long_term_memory ORDER BY id DESC LIMIT 25")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return "Belum ada catatan memori."
        return "\n".join([f"- [{cat}] {cont}" for cat, cont in rows])
    except Exception as e:
        return f"Error membaca memori: {e}"

# ==========================================
# HELPER FUNCTIONS & SELF-HEALING ENGINE
# ==========================================

def clean_markdown_to_html(text: str) -> str:
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

def clean_text_for_speech(text: str) -> str:
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    text = text.replace("*", "").replace("`", "").replace("_", "").replace("#", "")
    return text.strip()

async def run_with_self_healing(target_fp: str, max_retries: int = 3):
    file_dir = os.path.dirname(target_fp)
    file_name = os.path.basename(target_fp)
    
    for attempt in range(1, max_retries + 1):
        r_res = subprocess.run(["python", target_fp], capture_output=True, text=True, timeout=25, cwd=file_dir)
        if r_res.returncode == 0:
            return f"BERHASIL:\n{r_res.stdout}"
            
        error_output = r_res.stderr if r_res.stderr else r_res.stdout
        try:
            with open(target_fp, "r", encoding="utf-8") as f:
                current_code = f.read()
        except Exception as e:
            return f"Gagal membaca file: {str(e)}"
            
        fix_prompt = f"""
        Kamu adalah AI SENIOR DEBUGGER & SELF-HEALING AGENT. Script Python ini error:
        NAMA FILE: {file_name}
        KODE:
        ```python
        {current_code}
        ```
        ERROR:
        {error_output}
        Perbaiki kodenya. Output HARUS JSON MURNI tanpa markdown:
        {{"explanation": "penjelasan", "fixed_code": "kode lengkap baru"}}
        """
        try:
            fix_res = client.models.generate_content(model=MODEL_NAME, contents=fix_prompt)
            clean_json_str = fix_res.text.replace("```json", "").replace("```", "").strip()
            fix_data = json.loads(clean_json_str)
            fixed_code = fix_data.get("fixed_code", "")
            if fixed_code:
                with open(target_fp, "w", encoding="utf-8") as f:
                    f.write(fixed_code)
            else:
                return f"Gagal auto-fix pada percobaan {attempt}"
        except Exception as e:
            return f"Error Auto-Fix: {str(e)}"
    return f"Gagal diperbaiki setelah {max_retries} percobaan."

# ==========================================
# FASTAPI WEB INTERFACE & APP SERVER
# ==========================================

web_app = FastAPI()

@web_app.get("/", response_class=HTMLResponse)
async def web_ui():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JARVIS Mobile Interface</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background-color: #0b0f19; color: #e2e8f0; font-family: monospace; }
            .glow { text-shadow: 0 0 10px rgba(56, 189, 248, 0.5); }
        </style>
    </head>
    <body class="flex flex-col h-screen max-w-md mx-auto p-4">
        <header class="flex justify-between items-center pb-4 border-b border-gray-800">
            <div>
                <h1 class="text-xl font-bold text-sky-400 glow">J.A.R.V.I.S.</h1>
                <p class="text-xs text-gray-400">Autonomous Web Portal</p>
            </div>
            <span class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></span>
        </header>

        <div id="chat-container" class="flex-1 overflow-y-auto py-4 space-y-3">
            <div class="bg-gray-900 border border-gray-800 p-3 rounded-lg text-sm">
                <span class="text-sky-400 font-bold">JARVIS:</span> Online, Bos. Silakan masukkan perintah.
            </div>
        </div>

        <div class="pt-2 border-t border-gray-800 flex items-center gap-2">
            <input type="text" id="user-input" placeholder="Ketik pesan..." 
                class="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-sky-500"
                onkeypress="if(event.key === 'Enter') sendMessage()">
            <button onclick="sendMessage()" class="bg-sky-600 hover:bg-sky-500 px-4 py-2 rounded-lg text-sm font-bold transition">Kirim</button>
        </div>

        <script>
            async function sendMessage() {
                const inputField = document.getElementById('user-input');
                const container = document.getElementById('chat-container');
                const text = inputField.value.trim();
                if(!text) return;

                container.innerHTML += `<div class="bg-gray-800 p-3 rounded-lg text-sm text-right"><span class="text-emerald-400 font-bold">Bos:</span> ${text}</div>`;
                inputField.value = '';
                container.scrollTop = container.scrollHeight;

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text })
                    });
                    const data = await res.json();
                    container.innerHTML += `<div class="bg-gray-900 border border-gray-800 p-3 rounded-lg text-sm"><span class="text-sky-400 font-bold">JARVIS:</span> ${data.response}</div>`;
                } catch(e) {
                    container.innerHTML += `<div class="bg-red-900 p-3 rounded-lg text-sm text-white">Gagal terhubung ke server Jarvis.</div>`;
                }
                container.scrollTop = container.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

@web_app.post("/api/chat")
async def api_chat(request: Request):
    data = await request.json()
    msg = data.get("message", "")
    current_memories = get_all_memories()
    
    prompt = f"""
    {JARVIS_PERSONA}
    Catatan memori jangka panjang:
    {current_memories}
    Pertanyaan/Perintah: {msg}
    """
    try:
        res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return {"response": res.text}
    except Exception as e:
        return {"response": f"Error memproses: {str(e)}"}

def run_fastapi_server():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="warning")

# ==========================================
# TELEGRAM BOT HANDLER
# ==========================================

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    is_voice = bool(update.message.voice)
    user_input_text = ""

    if is_voice:
        await safe_reply(update, "🎙️ Mengolah pesan suara Bos...")
        temp_audio_path = os.path.join(BASE_DIR, "temp_voice_input.ogg")
        try:
            voice_file = await update.message.voice.get_file()
            await voice_file.download_to_drive(temp_audio_path)
            with open(temp_audio_path, "rb") as audio_f:
                audio_bytes = audio_f.read()
            
            t_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"inline_data": {"mime_type": "audio/ogg", "data": audio_bytes}}, "Transkripsikan pesan suara ini."]
            )
            user_input_text = t_res.text.strip()
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
        except Exception as e:
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
            await safe_reply(update, f"🚨 Gagal mendengarkan suara: {str(e)}")
            return
    else:
        user_input_text = update.message.text

    if not user_input_text: return

    existing_memories = get_all_memories()
    router_prompt = f"""
    Analisis kalimat: "{user_input_text}"
    Memori: {existing_memories}
    Tentukan intent: SEARCH, BUILD, CMD, RUN, REMEMBER, CHAT.
    Output JSON MURNI:
    {{
        "intent": "SEARCH/BUILD/CMD/RUN/REMEMBER/CHAT",
        "clean_query": "query rapi",
        "is_data_requested": true/false,
        "voice_summary": "ringkasan lisan",
        "memory_category": "kategori",
        "memory_content": "konten"
    }}
    """
    try:
        router_res = client.models.generate_content(model=MODEL_NAME, contents=router_prompt)
        parsed_intent = json.loads(router_res.text.replace("```json", "").replace("```", "").strip())
        intent = parsed_intent.get("intent", "CHAT")
        clean_query = parsed_intent.get("clean_query", user_input_text)
        is_data = parsed_intent.get("is_data_requested", False)
        voice_summary = parsed_intent.get("voice_summary", "Siap Bos.")

        if intent == "SEARCH":
            s_res = client.models.generate_content(model=MODEL_NAME, contents=f"{JARVIS_PERSONA}\nCari info terbaru: {clean_query}", config=GROUNDING_CONFIG)
            await safe_reply(update, f"🔍 <b>HASIL RISET:</b>\n\n{s_res.text}")
        elif intent == "RUN":
            target_fn = clean_query.replace("python", "").replace("run", "").strip()
            target_fp = None
            for root, dirs, files in os.walk(BASE_DIR):
                if target_fn in files:
                    target_fp = os.path.join(root, target_fn)
                    break
            if target_fp:
                res_msg = await run_with_self_healing(target_fp)
                await safe_reply(update, f"⚙️ <b>SELF-HEALING RUN:</b>\n<pre>{res_msg}</pre>")
            else:
                await safe_reply(update, f"❌ File <code>{target_fn}</code> tidak ditemukan.")
        elif intent == "REMEMBER":
            save_memory(parsed_intent.get("memory_category", "Umum"), parsed_intent.get("memory_content", clean_query))
            await safe_reply(update, "🧠 Memori berhasil dicatat ke jangka panjang!")
        else:
            c_res = client.models.generate_content(model=MODEL_NAME, contents=f"{JARVIS_PERSONA}\nMemori:\n{existing_memories}\nPesan:\n{clean_query}")
            await safe_reply(update, f"💬 <b>JARVIS:</b>\n\n{c_res.text}")
    except Exception as e:
        await safe_reply(update, f"🚨 Gagal: {str(e)}")

async def safe_reply(update: Update, text: str):
    try:
        await update.message.reply_html(clean_markdown_to_html(text))
    except:
        await update.message.reply_text(text)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID: return
    await safe_reply(update, "⚡ <b>JARVIS WEB & TELEGRAM AGENT ONLINE!</b> 🤖")

def main():
    # Jalankan FastAPI di Background Thread agar Web App dan Telegram bisa jalan bersamaan
    threading.Thread(target=run_fastapi_server, daemon=True).start()
    print("🌐 FastAPI Web Portal running...")

    print("🤖 Telegram Bot Polling running...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
    app.add_handler(MessageHandler(filters.VOICE, unified_handler))
    app.run_polling()

if __name__ == "__main__":
    main()