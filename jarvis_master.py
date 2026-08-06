import os
import json
import re
import shutil
import subprocess
import asyncio
import sqlite3
import edge_tts
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Membaca dari Railway Variables (Cloud) jika ada, atau menggunakan nilai default di bawah
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = os.getcwd()
VOICE_ACTOR = "id-ID-ArdiNeural" # Suara Laki-Laki Indonesia Neural

# Variabel Global untuk nama model stabil terbaru
MODEL_NAME = "gemini-3.6-flash"

# Memastikan API Key bersih dari spasi/karakter tersembunyi
CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {
    'tools': [{'google_search': {}}]
}

JARVIS_PERSONA = (
    "Kamu adalah JARVIS, asisten AI pribadi yang sangat cerdas, responsif, profesional, dan adaptif. "
    "Aturan Bahasa (Language Adaptation):\n"
    "1. Sesuaikan bahasa responmu secara otomatis dengan bahasa yang digunakan pengguna saat ini (misalnya jika pengguna menyapa atau bertanya dalam Bahasa Indonesia, balas dengan Bahasa Indonesia yang natural. Jika dalam Bahasa Inggris, balas dengan Bahasa Inggris yang natural).\n"
    "2. Jika pengguna memberikan instruksi eksplisit untuk menggunakan bahasa tertentu (misal: 'Jawab pakai bahasa Inggris ya'), ikuti perintah tersebut secara mutlak.\n"
    "3. Gunakan sapaan 'Bos' secara proporsional dalam bahasa apa pun (atau 'Sir' / 'Boss' jika menggunakan Bahasa Inggris).\n"
    "4. Jawablah dengan akurat, lugas, dan penyampaian yang enak didengar, baik untuk teks maupun voice note."
)

# ==========================================
# LONG-TERM MEMORY ENGINE (SQLITE)
# ==========================================

MEMORY_DB_PATH = os.path.join(BASE_DIR, "jarvis_memory.db")

def init_memory_db():
    """Inisialisasi tabel memori jangka panjang jika belum ada"""
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

# Jalankan inisialisasi memori
init_memory_db()

def save_memory(category: str, content: str):
    """Menyimpan ingatan baru ke database"""
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO long_term_memory (category, content) VALUES (?, ?)", (category, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Gagal simpan memori: {e}")

def get_all_memories() -> str:
    """Mengambil semua ringkasan ingatan untuk disuntikkan ke konteks AI"""
    if not os.path.exists(MEMORY_DB_PATH):
        return "Tidak ada memori tersimpan."
    try:
        conn = sqlite3.connect(MEMORY_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT category, content FROM long_term_memory ORDER BY id DESC LIMIT 25")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "Belum ada catatan memori."
        
        memory_str = "\n".join([f"- [{cat}] {cont}" for cat, cont in rows])
        return memory_str
    except Exception as e:
        return f"Error membaca memori: {e}"

# ==========================================
# HELPER FUNCTIONS & SELF-HEALING ENGINE
# ==========================================

def clean_markdown_to_html(text: str) -> str:
    """Mengubah format Markdown dari Gemini menjadi HTML ramah Telegram"""
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

def clean_text_for_speech(text: str) -> str:
    """Pembersih teks khusus audio agar alur bicara mulus tanpa jeda kaku"""
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    text = text.replace("*", "").replace("`", "").replace("_", "").replace("#", "")
    text = re.sub(r',\s*(Bos|Bro)', r' \1', text, flags=re.IGNORECASE)
    text = text.replace(" ,", " ").replace(", ", " ")
    if len(text) > 400:
        text = text[:400] + ". Detail lengkapnya sudah saya tampilkan di teks ya Bos."
    return text.strip()

async def send_voice_response(update: Update, raw_text: str):
    """Mengubah teks respon menjadi Voice Note dengan suara yang otomatis menyesuaikan bahasa (Indo/English)"""
    temp_voice_out = os.path.join(BASE_DIR, "temp_voice_out.mp3")
    try:
        spoken_text = clean_text_for_speech(raw_text)
        english_keywords = ["hello", "hi", "the", "and", "is", "you", "to", "a", "of", "in", "for", "it", "with", "sir", "boss"]
        words = spoken_text.lower().split()
        is_english = sum(1 for word in words if word in english_keywords) >= 2
        chosen_voice = "en-US-AndrewNeural" if is_english else VOICE_ACTOR
        communicate = edge_tts.Communicate(
            spoken_text, 
            chosen_voice,
            rate="+8%",
            pitch="+0Hz"
        )
        await communicate.save(temp_voice_out)

        with open(temp_voice_out, 'rb') as audio_file:
            await update.message.reply_voice(
                voice=audio_file, 
                caption=f"🎙️ Voice Response ({'EN' if is_english else 'ID'})"
            )

        if os.path.exists(temp_voice_out): os.remove(temp_voice_out)
    except Exception as e:
        print(f"[!] Warning Gagal kirim voice response: {e}")
        if os.path.exists(temp_voice_out): os.remove(temp_voice_out)

async def safe_reply(update: Update, text: str, is_html: bool = True):
    if is_html:
        formatted_text = clean_markdown_to_html(text)
        if len(formatted_text) > 4000:
            formatted_text = formatted_text[:4000] + "\n\n<i>... (Output dipotong)</i>"
        try:
            await update.message.reply_html(formatted_text)
            return
        except Exception as e:
            print(f"[!] Warning HTML send failed: {e}")

    clean_plain = re.sub(r'<[^>]*>', '', text)
    clean_plain = clean_plain.replace("*", "").replace("`", "").replace("_", "")
    if len(clean_plain) > 4000:
        clean_plain = clean_plain[:4000] + "\n\n... (Output dipotong)"
    await update.message.reply_text(clean_plain)

async def run_with_self_healing(update: Update, target_fp: str, max_retries: int = 3):
    """Fungsi otonom untuk menjalankan script, mendeteksi error, dan memperbaiki diri (self-healing)"""
    file_dir = os.path.dirname(target_fp)
    file_name = os.path.basename(target_fp)
    
    for attempt in range(1, max_retries + 1):
        await safe_reply(update, f"⚙️ Menjalankan <code>{file_name}</code> (Percobaan ke-{attempt}/{max_retries})...")
        
        r_res = subprocess.run(["python", target_fp], capture_output=True, text=True, timeout=25, cwd=file_dir)
        
        if r_res.returncode == 0:
            out = r_res.stdout if r_res.stdout else "(Program selesai tanpa output)"
            await safe_reply(update, f"✅ <b>BERHASIL (Sukses):</b>\n\n{out}")
            return True
            
        error_output = r_res.stderr if r_res.stderr else r_res.stdout
        await safe_reply(update, f"⚠️ <b>TERDETEKSI ERROR PADA PERCOBAAN {attempt}:</b>\n<pre>{error_output[:1000]}</pre>\n\n🛡️ <i>Memulai prosedur Self-Healing & Auto-Fixing...</i>")
        
        try:
            with open(target_fp, "r", encoding="utf-8") as f:
                current_code = f.read()
        except Exception as e:
            await safe_reply(update, f"❌ Gagal membaca file kode: {str(e)}")
            return False
            
        fix_prompt = f"""
        Kamu adalah AI SENIOR DEBUGGER & SELF-HEALING AGENT.
        Script Python ini mengalami error saat dieksekusi.
        
        NAMA FILE: {file_name}
        
        ISI KODE SAAT INI:
        ```python
        {current_code}
        ```
        
        PESAN ERROR / TRACEBACK:
        {error_output}
        
        Tugasmu:
        Perbaiki kode tersebut agar error di atas hilang dan program bisa berjalan normal.
        Output HARUS JSON MURNI tanpa markdown ```json:
        {{
            "explanation": "penjelasan singkat apa yang diperbaiki",
            "fixed_code": "isi kode python lengkap yang sudah diperbaiki"
        }}
        """
        
        try:
            fix_res = client.models.generate_content(model=MODEL_NAME, contents=fix_prompt)
            clean_json_str = fix_res.text.replace("```json", "").replace("```", "").strip()
            fix_data = json.loads(clean_json_str)
            
            explanation = fix_data.get("explanation", "Perbaikan bug otonom")
            fixed_code = fix_data.get("fixed_code", "")
            
            if fixed_code:
                with open(target_fp, "w", encoding="utf-8") as f:
                    f.write(fixed_code)
                await safe_reply(update, f"🔧 <b>Self-Healing Patch diterapkan:</b> {explanation}")
            else:
                await safe_reply(update, "❌ Gagal menghasilkan kode perbaikan.")
                return False
                
        except Exception as e:
            await safe_reply(update, f"🚨 Gagal memproses Auto-Fix: {str(e)}")
            return False
            
    await safe_reply(update, f"❌ Program <code>{file_name}</code> gagal diperbaiki setelah {max_retries} kali percobaan otonom.")
    return False

# ==========================================
# MULTI-AGENT ENGINE FUNCTIONS
# ==========================================

def run_architect_agent(user_instruction: str) -> dict:
    prompt = f"""
    Kamu adalah ARCHITECT AGENT di sistem Jarvis.
    Tugasmu merancang blueprint struktur proyek software berdasarkan instruksi: "{user_instruction}"
    Output HARUS JSON MURNI tanpa markdown ```json:
    {{
        "project_name": "nama_folder_proyek",
        "blueprint": "penjelasan singkat rancangan arsitektur",
        "file_list": ["main.py", "README.md"]
    }}
    """
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

def run_coder_agent(user_instruction: str, blueprint_data: dict) -> dict:
    prompt = f"""
    Kamu adalah CODER AGENT (Senior Developer) di sistem Jarvis.
    Instruksi: "{user_instruction}"
    Blueprint: {json.dumps(blueprint_data)}
    Tuliskan isi kode program lengkap untuk SETIAP file!
    TIDAK BOLEH MENGGUNAKAN input() INTERAKTIF!
    Output HARUS JSON MURNI tanpa markdown ```json:
    {{
        "files": [
            {{"filepath": "main.py", "content": "isi kode program"}}
        ]
    }}
    """
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

def run_reviewer_agent(coder_output: dict) -> dict:
    prompt = f"""
    Kamu adalah REVIEWER & QA AGENT di sistem Jarvis.
    Tinjau & perbaiki isi file kode berikut: {json.dumps(coder_output)}
    Output HARUS JSON MURNI tanpa markdown ```json:
    {{
        "review_summary": "rangkuman perbaikan singkat",
        "files": [
            {{"filepath": "main.py", "content": "isi kode program revisi"}}
        ]
    }}
    """
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

# ==========================================
# UNIFIED INTENT ROUTER ENGINE
# ==========================================

async def unified_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return

    is_voice = bool(update.message.voice)
    user_input_text = ""

    # 1. AMBIL INPUT DARI VOICE ATAU TEKS
    if is_voice:
        await safe_reply(update, "🎙️ Mengolah pesan suara Bos...")
        temp_audio_path = os.path.join(BASE_DIR, "temp_voice_input.ogg")
        try:
            voice_file = await update.message.voice.get_file()
            await voice_file.download_to_drive(temp_audio_path)
            with open(temp_audio_path, "rb") as audio_f:
                audio_bytes = audio_f.read()
            
            transcribe_prompt = "Transkripsikan pesan suara ini dengan tepat dalam Bahasa Indonesia."
            t_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=[{"inline_data": {"mime_type": "audio/ogg", "data": audio_bytes}}, transcribe_prompt]
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

    # 2. DETEKSI INTENT/KATEGORI PERINTAH DENGAN MEMORI JANGKA PANJANG
    existing_memories = get_all_memories()

    router_prompt = f"""
    Analisis kalimat input dari pengguna ini: "{user_input_text}"
    
    Berikut adalah memori jangka panjang yang sudah dicatat sebelumnya:
    {existing_memories}
    
    Tentukan kategori perintah di antara 6 pilihan berikut:
    - SEARCH (Jika pengguna meminta mencari berita, info internet, harga, atau topik terupdate)
    - BUILD (Jika pengguna meminta dibuatkan aplikasi, bot, program, atau proyek kodingan utuh)
    - CMD (Jika pengguna meminta eksekusi perintah terminal/sistem laptop)
    - RUN (Jika pengguna meminta menjalankan file python tertentu, misal: jalankan main.py)
    - REMEMBER (Jika pengguna secara eksplisit meminta Jarvis mengingat suatu informasi, preferensi, atau aturan baru)
    - CHAT (Untuk obrolan biasa, diskusi, pertanyaan umum, atau konsultasi)

    Output HARUS JSON MURNI tanpa markdown ```json:
    {{
        "intent": "SALAH_SATU_DARI_6_KATEGORI",
        "clean_query": "instruksi yang dirapikan",
        "is_data_requested": true_atau_false,
        "voice_summary": "kalimat jawaban lisan pendek dan natural jika diomongkan via suara",
        "memory_category": "kategori singkat jika intent REMEMBER, misal: Preferensi, Proyek, Aturan",
        "memory_content": "poin informasi penting yang harus diingat jika intent REMEMBER"
    }}
    """

    try:
        router_res = client.models.generate_content(model=MODEL_NAME, contents=router_prompt)
        clean_router_json = router_res.text.replace("```json", "").replace("```", "").strip()
        parsed_intent = json.loads(clean_router_json)

        intent = parsed_intent.get("intent", "CHAT")
        clean_query = parsed_intent.get("clean_query", user_input_text)
        is_data = parsed_intent.get("is_data_requested", False)
        voice_summary = parsed_intent.get("voice_summary", "Siap Bos.")

        # 3. EKSEKUSI SESUAI INTENT AUTOMATIS

        # A. INTENT: SEARCH
        if intent == "SEARCH":
            await safe_reply(update, f"🌐 Mencari info terbaru: '<i>{clean_query}</i>'...")
            s_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=f"{JARVIS_PERSONA}\n\nRangkumkan info paling baru dari internet untuk: {clean_query}",
                config=GROUNDING_CONFIG
            )
            await safe_reply(update, f"🔍 <b>HASIL RISET INTERNET:</b>\n\n{s_res.text}")
            if is_voice:
                await send_voice_response(update, voice_summary)

        # B. INTENT: BUILD (MULTI-AGENT)
        elif intent == "BUILD":
            await safe_reply(update, f"🚀 <b>PANGGIL TIM MULTI-AGENT!</b>\nTarget: {clean_query}")
            await safe_reply(update, "🏛️ <b>[1/3] Architect Agent:</b> Merancang arsitektur...")
            arch_res = run_architect_agent(clean_query)
            p_name = arch_res.get("project_name", "proyek_jarvis")
            
            await safe_reply(update, "💻 <b>[2/3] Coder Agent:</b> Menulis kode program...")
            coder_res = run_coder_agent(clean_query, arch_res)

            await safe_reply(update, "🛡️ <b>[3/3] QA Agent:</b> Memeriksa bug & keamanan...")
            final_res = run_reviewer_agent(coder_res)

            project_dir = os.path.join(BASE_DIR, p_name)
            os.makedirs(project_dir, exist_ok=True)
            for f_info in final_res.get("files", []):
                fp = os.path.join(project_dir, f_info["filepath"])
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, "w", encoding="utf-8") as f: f.write(f_info["content"])

            zip_path = shutil.make_archive(project_dir, 'zip', project_dir)
            await safe_reply(update, f"🎉 <b>PROYEK SELESAI:</b> <code>{p_name}</code>\n📦 Mengirim file .ZIP...")
            with open(zip_path, 'rb') as doc:
                await update.message.reply_document(document=doc, filename=f"{p_name}.zip")
            if is_voice:
                await send_voice_response(update, f"Proyek {p_name} sudah selesai dibuat dan dikirim file zip nya ya Bos.")

        # C. INTENT: CMD
        elif intent == "CMD":
            await safe_reply(update, f"⚡ Eksekusi CMD: <code>{clean_query}</code>...")
            cmd_res = subprocess.run(clean_query, shell=True, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
            out = cmd_res.stdout if cmd_res.stdout else "(Selesai)"
            await safe_reply(update, f"🖥️ <b>OUTPUT TERMINAL:</b>\n\n{out}")
            if is_voice:
                await send_voice_response(update, "Perintah terminal sudah selesai dieksekusi Bos.")

        # D. INTENT: RUN (DENGAN SELF-HEALING)
        elif intent == "RUN":
            target_fn = clean_query.replace("python", "").replace("run", "").strip()
            target_fp = None
            for root, dirs, files in os.walk(BASE_DIR):
                if target_fn in files:
                    target_fp = os.path.join(root, target_fn)
                    break
            if target_fp:
                success = await run_with_self_healing(update, target_fp)
                if success and is_voice:
                    await send_voice_response(update, f"Program {target_fn} berhasil dijalankan Bos.")
            else:
                await safe_reply(update, f"❌ File <code>{target_fn}</code> tidak ditemukan di D:\\Jarvis-Agent")

        # E. INTENT: REMEMBER (MENYIMPAN MEMORI JANGKA PANJANG)
        elif intent == "REMEMBER":
            mem_cat = parsed_intent.get("memory_category", "Umum")
            mem_cont = parsed_intent.get("memory_content", clean_query)
            
            save_memory(mem_cat, mem_cont)
            await safe_reply(update, f"🧠 <b>MEMORI DISIMPAN, BOS!</b>\n\n<b>[{mem_cat}]</b> {mem_cont}")
            if is_voice:
                await send_voice_response(update, "Siap Bos, informasinya sudah saya catat ke memori jangka panjang.")

        # F. INTENT: CHAT (OBROLAN STANDARD DENGAN MEMORI)
        else:
            current_memories = get_all_memories()
            chat_context = f"""
            {JARVIS_PERSONA}
            
            Berikut adalah catatan memori jangka panjang tentang Bos yang harus kamu ingat:
            {current_memories}
            
            Obrolan/Pertanyaan Bos saat ini:
            {clean_query}
            """
            
            c_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=chat_context
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
        await safe_reply(update, f"🚨 Gagal memproses perintah: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return
    msg = (
        "⚡ <b>YOO, JARVIS AGENT V2 (SELF-HEALING + MEMORY) ONLINE, BOS!</b> 🤖\n\n"
        "Sekarang Jarvis punya memori jangka panjang dan bisa memperbaiki kodenya sendiri secara otonom!\n\n"
        "Contoh perintah baru:\n"
        "• <i>'Ingat ya, project utamaku menggunakan framework Flask'</i>\n"
        "• <i>'Jalankan script test.py'</i> (jika error, Jarvis bakal auto-fix sendiri!)\n"
    )
    await safe_reply(update, msg, is_html=True)

def main():
    print("🤖 Jarvis Phase 14 (Self-Healing & Long-Term Memory) Running...")
    print("Menunggu perintah suara / teks dari Bos...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
    app.add_handler(MessageHandler(filters.VOICE, unified_handler))

    app.run_polling()

if __name__ == "__main__":
    main()