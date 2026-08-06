import os
import json
import re
import shutil
import subprocess
import asyncio
import sqlite3
import datetime
import schedule
import time
import threading
import edge_tts
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Konfigurasi Utama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # Opsional untuk auto-push ke GitHub

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural"
MODEL_NAME = "gemini-2.5-flash"

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
    "4. Jawablah dengan akurat, lugas, dan penyampaian yang enak didengar, baik untuk teks maupun voice note."
)

# ==========================================
# LONG-TERM MEMORY & SCHEDULE DB (SQLITE)
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
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT,
                command TEXT,
                time_str TEXT
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
        cursor.execute("SELECT category, content FROM long_term_memory ORDER BY id DESC LIMIT 25")
        rows = cursor.fetchall()
        conn.close()
        if not rows: return "Belum ada catatan memori."
        return "\n".join([f"- [{cat}] {cont}" for cat, cont in rows])
    except Exception as e:
        return f"Error membaca memori: {e}"

# ==========================================
# HELPER FUNCTIONS & MULTILINGUAL VOICE
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

async def send_voice_response(update: Update, raw_text: str):
    temp_voice_out = os.path.join(BASE_DIR, "temp_voice_out.mp3")
    try:
        spoken_text = clean_text_for_speech(raw_text)
        english_keywords = ["hello", "hi", "the", "and", "is", "you", "to", "a", "of", "in", "for", "it", "with", "sir", "boss"]
        words = spoken_text.lower().split()
        is_english = sum(1 for word in words if word in english_keywords) >= 2
        
        chosen_voice = "en-US-AndrewNeural" if is_english else VOICE_ACTOR
        
        communicate = edge_tts.Communicate(spoken_text, chosen_voice, rate="+8%", pitch="+0Hz")
        await communicate.save(temp_voice_out)

        with open(temp_voice_out, 'rb') as audio_file:
            await update.message.reply_voice(voice=audio_file, caption=f"🎙️ Voice Response ({'EN' if is_english else 'ID'})")

        if os.path.exists(temp_voice_out): os.remove(temp_voice_out)
    except Exception as e:
        print(f"[!] Warning Gagal kirim voice response: {e}")
        if os.path.exists(temp_voice_out): os.remove(temp_voice_out)

async def safe_reply(update: Update, text: str):
    try:
        await update.message.reply_html(clean_markdown_to_html(text))
    except:
        await update.message.reply_text(text)

# ==========================================
# ADVANCED CAPABILITIES (GITHUB & SELF-HEALING)
# ==========================================

def push_to_github(project_dir: str, project_name: str) -> str:
    if not GITHUB_TOKEN:
        return "Token GitHub belum diatur di environment variables."
    try:
        os.chdir(project_dir)
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "Jarvis Agent"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "jarvis@ai.system"], capture_output=True)
        subprocess.run(["git", "add", "."], capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit by Jarvis Multi-Agent AI"], capture_output=True)
        # Catatan: Integrasi otomatis repo publik via GitHub API dapat dikembangkan lebih lanjut
        os.chdir(BASE_DIR)
        return f"Proyek berhasil di-git init dan di-commit secara lokal di {project_dir}."
    except Exception as e:
        os.chdir(BASE_DIR)
        return f"Gagal auto-git: {str(e)}"

async def run_with_self_healing(update: Update, target_fp: str, max_retries: int = 3):
    file_dir = os.path.dirname(target_fp)
    file_name = os.path.basename(target_fp)
    
    for attempt in range(1, max_retries + 1):
        await safe_reply(update, f"⚙️ Menjalankan <code>{file_name}</code> (Percobaan {attempt}/{max_retries})...")
        r_res = subprocess.run(["python", target_fp], capture_output=True, text=True, timeout=25, cwd=file_dir)
        
        if r_res.returncode == 0:
            out = r_res.stdout if r_res.stdout else "(Program selesai tanpa output)"
            await safe_reply(update, f"✅ <b>BERHASIL:</b>\n\n{out}")
            return True
            
        error_output = r_res.stderr if r_res.stderr else r_res.stdout
        await safe_reply(update, f"⚠️ <b>TERDETEKSI ERROR:</b>\n<pre>{error_output[:800]}</pre>\n🛡️ <i>Memperbaiki diri secara otonom...</i>")
        
        try:
            with open(target_fp, "r", encoding="utf-8") as f:
                current_code = f.read()
        except Exception as e:
            await safe_reply(update, f"❌ Gagal membaca file: {str(e)}")
            return False
            
        fix_prompt = f"""
        Kamu adalah SENIOR DEBUGGER & SELF-HEALING AGENT. Script ini error:
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
            fix_data = json.loads(fix_res.text.replace("```json", "").replace("```", "").strip())
            fixed_code = fix_data.get("fixed_code", "")
            if fixed_code:
                with open(target_fp, "w", encoding="utf-8") as f: f.write(fixed_code)
                await safe_reply(update, f"🔧 <b>Patch diterapkan:</b> {fix_data.get('explanation', 'Perbaikan bug')}")
            else:
                return False
        except Exception as e:
            await safe_reply(update, f"🚨 Gagal Auto-Fix: {str(e)}")
            return False
    return False

def run_architect_agent(user_instruction: str) -> dict:
    prompt = f"Sebagai Architect Agent, rancang proyek: '{user_instruction}'. Output JSON MURNI: {{\"project_name\": \"nama\", \"blueprint\": \"desc\", \"file_list\": [\"main.py\"]}}"
    res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return json.loads(res.text.replace("```json", "").replace("```", "").strip())

def run_coder_agent(user_instruction: str, blueprint_data: dict) -> dict:
    prompt = f"Sebagai Coder Agent, tulis kode lengkap untuk: '{user_instruction}'. Blueprint: {json.dumps(blueprint_data)}. Output JSON MURNI: {{\"files\": [{{\"filepath\": \"main.py\", \"content\": \"kode\"}}]}}"
    res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return json.loads(res.text.replace("```json", "").replace("```", "").strip())

def run_reviewer_agent(coder_output: dict) -> dict:
    prompt = f"As QA Agent, review code: {json.dumps(coder_output)}. Output JSON MURNI: {{\"review_summary\": \"ok\", \"files\": [{{\"filepath\": \"main.py\", \"content\": \"code\"}}]}}"
    res = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return json.loads(res.text.replace("```json", "").replace("```", "").strip())

# ==========================================
# UNIFIED INTENT ROUTER ENGINE (WITH VISION & DOCS)
# ==========================================

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    is_voice = bool(update.message.voice)
    is_photo = bool(update.message.photo)
    is_document = bool(update.message.document)
    user_input_text = update.message.caption or update.message.text or ""

    # 1. HANDLE VISION (FOTO / SCREENSHOT)
    # 1. HANDLE VISION (FOTO / SCREENSHOT)
    if is_photo:
        await safe_reply(update, "👁️ Menganalisis gambar/screenshot Bos...")
        photo_file = await update.message.photo[-1].get_file()
        photo_path = os.path.join(BASE_DIR, "temp_vision.jpg")
        await photo_file.download_to_drive(photo_path)
        
        with open(photo_path, "rb") as f:
            image_bytes = f.read()
            
        vision_prompt = user_input_text if user_input_text else "Analisis gambar ini secara detail dan berikan solusi jika ini adalah error atau pertanyaan teknis."
        try:
            v_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_bytes}},
                    vision_prompt
                ]
            )
            response_text = v_res.text
        except Exception as e:
            response_text = f"Gagal memproses gambar: {str(e)}"

        if os.path.exists(photo_path): 
            os.remove(photo_path)
            
        await safe_reply(update, f"🖼️ <b>ANALISIS VISION:</b>\n\n{response_text}")
        return

    # 2. HANDLE DOCUMENT / PDF ANALYZER
    if is_document:
        doc_file = await update.message.document.get_file()
        doc_name = update.message.document.file_name
        doc_path = os.path.join(BASE_DIR, doc_name)
        await doc_file.download_to_drive(doc_path)
        
        await safe_reply(update, f"📂 Menganalisis dokumen <code>{doc_name}</code>...")
        
        try:
            with open(doc_path, "rb") as f:
                doc_bytes = f.read()
            
            doc_prompt = user_input_text if user_input_text else "Rangkum isi dokumen ini dan berikan poin-poin pentingnya."
            d_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    {"inline_data": {"mime_type": "application/pdf", "data": doc_bytes}},
                    doc_prompt
                ]
            )
            response_text = d_res.text
        except Exception as e:
            response_text = f"Gagal membaca dokumen: {str(e)}"

        if os.path.exists(doc_path): 
            os.remove(doc_path)
            
        await safe_reply(update, f"📄 <b>HASIL ANALISIS DOKUMEN:</b>\n\n{response_text}")
        return

    # 3. HANDLE VOICE NOTE
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

    if not user_input_text: return

    existing_memories = get_all_memories()
    router_prompt = f"""
    Analisis kalimat: "{user_input_text}"
    Memori jangka panjang: {existing_memories}
    Tentukan intent: SEARCH, BUILD, CMD, RUN, REMEMBER, CHAT.
    Output JSON MURNI:
    {{
        "intent": "SEARCH/BUILD/CMD/RUN/REMEMBER/CHAT",
        "clean_query": "query rapi",
        "is_data_requested": true/false,
        "voice_summary": "ringkasan lisan pendek",
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
            await safe_reply(update, f"🌐 Mencari info: '<i>{clean_query}</i>'...")
            s_res = client.models.generate_content(model=MODEL_NAME, contents=f"{JARVIS_PERSONA}\nRangkum info terbaru: {clean_query}", config=GROUNDING_CONFIG)
            await safe_reply(update, f"🔍 <b>HASIL RISET:</b>\n\n{s_res.text}")
            if is_voice: await send_voice_response(update, voice_summary)

        elif intent == "BUILD":
            await safe_reply(update, f"🚀 <b>MULTI-AGENT BUILD & GITHUB INIT:</b> {clean_query}")
            arch_res = run_architect_agent(clean_query)
            p_name = arch_res.get("project_name", "proyek_jarvis")
            
            coder_res = run_coder_agent(clean_query, arch_res)
            final_res = run_reviewer_agent(coder_res)

            project_dir = os.path.join(BASE_DIR, p_name)
            os.makedirs(project_dir, exist_ok=True)
            for f_info in final_res.get("files", []):
                fp = os.path.join(project_dir, f_info["filepath"])
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, "w", encoding="utf-8") as f: f.write(f_info["content"])

            git_msg = push_to_github(project_dir, p_name)
            zip_path = shutil.make_archive(project_dir, 'zip', project_dir)
            await safe_reply(update, f"🎉 <b>PROYEK SELESAI:</b> <code>{p_name}</code>\n📦 Mengirim .ZIP...\n🐙 {git_msg}")
            with open(zip_path, 'rb') as doc:
                await update.message.reply_document(document=doc, filename=f"{p_name}.zip")
            if is_voice: await send_voice_response(update, f"Proyek {p_name} selesai dibuat Bos.")

        elif intent == "CMD":
            cmd_res = subprocess.run(clean_query, shell=True, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
            await safe_reply(update, f"🖥️ <b>OUTPUT CMD:</b>\n\n{cmd_res.stdout or '(Selesai)'}")
            if is_voice: await send_voice_response(update, voice_summary)

        elif intent == "RUN":
            target_fn = clean_query.replace("python", "").replace("run", "").strip()
            target_fp = None
            for root, dirs, files in os.walk(BASE_DIR):
                if target_fn in files:
                    target_fp = os.path.join(root, target_fn)
                    break
            if target_fp:
                await run_with_self_healing(update, target_fp)
                if is_voice: await send_voice_response(update, voice_summary)
            else:
                await safe_reply(update, f"❌ File <code>{target_fn}</code> tidak ditemukan.")

        elif intent == "REMEMBER":
            mem_cat = parsed_intent.get("memory_category", "Umum")
            mem_cont = parsed_intent.get("memory_content", clean_query)
            save_memory(mem_cat, mem_cont)
            await safe_reply(update, f"🧠 <b>MEMORI DISIMPAN:</b>\n<b>[{mem_cat}]</b> {mem_cont}")
            if is_voice: await send_voice_response(update, "Informasi sudah dicatat ke memori jangka panjang Bos.")

        else:
            c_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=f"{JARVIS_PERSONA}\n\nMemori Jangka Panjang:\n{existing_memories}\n\nPesan Bos:\n{clean_query}"
            )
            if is_voice:
                if is_data:
                    await safe_reply(update, f"💬 <b>JARVIS:</b>\n\n{c_res.text}")
                    await send_voice_response(update, voice_summary)
                else:
                    await send_voice_response(update, voice_summary)
            else:
                await safe_reply(update, f"💬 <b>JARVIS:</b>\n\n{c_res.text}")

    except Exception as e:
        await safe_reply(update, f"🚨 Gagal memproses: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID: return
    msg = (
        "⚡ <b>JARVIS ULTIMATE AGENT ONLINE!</b> 🤖\n\n"
        "Semua fitur penuh aktif:\n"
        "• 🧠 <b>Long-Term Memory (SQLite)</b>\n"
        "• 🛡️ <b>Self-Healing Debugger</b>\n"
        "• 🚀 <b>Multi-Agent Builder & Git Auto-Init</b>\n"
        "• 👁️ <b>Vision / Screenshot Analyzer</b>\n"
        "• 📄 <b>PDF / Document Analyzer</b>\n"
        "• 🎙️ <b>Multilingual Voice Note (ID/EN)</b>"
    )
    await safe_reply(update, msg)

def main():
    print("🤖 Jarvis Ultimate Agent Running...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
    app.add_handler(MessageHandler(filters.VOICE, unified_handler))
    app.add_handler(MessageHandler(filters.PHOTO, unified_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, unified_handler))
    app.run_polling()

if __name__ == "__main__":
    main()