import os
import json
import re
import shutil
import subprocess
import asyncio
import edge_tts
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# Membaca dari Railway Variables (Cloud) jika ada, atau menggunakan nilai default di bawah
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kbs37cggGinTX-5AW_9z-eJGPtggJa97dJCuJ-K7roYA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "5883853281")

BASE_DIR = "D:\\Jarvis-Agent"
VOICE_ACTOR = "id-ID-ArdiNeural" # Suara Laki-Laki Indonesia Neural
# Variabel Global untuk nama model agar mudah diganti di masa depan
MODEL_NAME = "gemini-3.6-flash"

# Memastikan API Key bersih dari spasi/karakter tersembunyi
CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

GROUNDING_CONFIG = {
    'tools': [{'google_search': {}}]
}

JARVIS_PERSONA = (
    "Kamu adalah JARVIS, asisten AI pribadi yang sangat cerdas, responsif, profesional, dan adaptif. "
    "Gunakan kemampuan 'read the room' untuk menyesuaikan nada bicaramu dengan konteks pengguna:\n"
    "1. Jika pengguna bertanya hal teknis, serius, atau memberikan perintah kerja (coding, dokumen, analisis): "
    "Berikan jawaban yang lugas, presisi, solutif, dan profesional tanpa terlalu banyak gurauan.\n"
    "2. Jika pengguna mengajak ngobrol santai atau bercanda: "
    "Responlah dengan santai, luwes, sedikit cerdas/humoris, namun tetap ramah dan sopan.\n"
    "3. Gunakan sebutan 'Bos' secara proporsional. Hindari bahasa yang terlalu gaul atau berlebihan. "
    "Jawablah dengan akurat, jelas, dan penyampaian yang enak didengar."
)

# ==========================================
# HELPER FUNCTIONS
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
    # Hilangkan koma sebelum panggilan "Bos" / "Bro" agar tidak ada jeda patah
    text = re.sub(r',\s*(Bos|Bro)', r' \1', text, flags=re.IGNORECASE)
    # Ganti koma yang terlalu kaku menjadi spasi biasa
    text = text.replace(" ,", " ").replace(", ", " ")
    if len(text) > 400:
        text = text[:400] + ". Detail lengkapnya sudah saya tampilkan di teks ya Bos."
    return text.strip()

async def send_voice_response(update: Update, raw_text: str):
    """Mengubah teks respon menjadi Voice Note Laki-Laki yang mengalir lancar"""
    temp_voice_out = os.path.join(BASE_DIR, "temp_voice_out.mp3")
    try:
        spoken_text = clean_text_for_speech(raw_text)
        communicate = edge_tts.Communicate(
            spoken_text, 
            VOICE_ACTOR,
            rate="+8%",
            pitch="+0Hz"
        )
        await communicate.save(temp_voice_out)

        with open(temp_voice_out, 'rb') as audio_file:
            await update.message.reply_voice(
                voice=audio_file, 
                caption="🎙️ Voice Response Jarvis"
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
            
            # Transkripsi suara ke teks menggunakan Gemini
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

    # 2. DETEKSI INTENT/KATEGORI PERINTAH DENGAN GEMINI
    router_prompt = f"""
    Analisis kalimat input dari pengguna ini: "{user_input_text}"
    Tentukan kategori perintah yang paling cocok di antara 5 pilihan berikut:
    - SEARCH (Jika pengguna meminta mencari berita, info internet, harga, atau topik terupdate)
    - BUILD (Jika pengguna meminta dibuatkan aplikasi, bot, program, atau proyek kodingan utuh)
    - CMD (Jika pengguna meminta eksekusi perintah terminal/sistem laptop seperti list file, dir, ipconfig, dll)
    - RUN (Jika pengguna meminta menjalankan file python tertentu, misal: jalankan main.py)
    - CHAT (Untuk obrolan biasa, diskusi, pertanyaan umum, atau konsultasi)

    Juga tentukan apakah respons butuh menyertakan data teks panjang/kodingan atau cukup obrolan lisan.

    Output HARUS JSON MURNI tanpa markdown ```json:
    {{
        "intent": "SALAH_SATU_DARI_5_KATEGORI_DIATAS",
        "clean_query": "instruksi yang dirapikan",
        "is_data_requested": true_atau_false,
        "voice_summary": "kalimat jawaban lisan pendek dan natural jika diomongkan via suara"
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
            # Step 1
            await safe_reply(update, "🏛️ <b>[1/3] Architect Agent:</b> Merancang arsitektur...")
            arch_res = run_architect_agent(clean_query)
            p_name = arch_res.get("project_name", "proyek_jarvis")
            
            # Step 2
            await safe_reply(update, "💻 <b>[2/3] Coder Agent:</b> Menulis kode program...")
            coder_res = run_coder_agent(clean_query, arch_res)

            # Step 3
            await safe_reply(update, "🛡️ <b>[3/3] QA Agent:</b> Memeriksa bug & keamanan...")
            final_res = run_reviewer_agent(coder_res)

            # Save Files
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

        # D. INTENT: RUN (Dengan Self-Healing)
        elif intent == "RUN":
            target_fn = clean_query.replace("python", "").replace("run", "").strip()
            target_fp = None
            for root, dirs, files in os.walk(BASE_DIR):
                if target_fn in files:
                    target_fp = os.path.join(root, target_fn)
                    break
            if target_fp:
                # Jalankan menggunakan fungsi self-healing otonom
                success = await run_with_self_healing(update, target_fp)
                if success and is_voice:
                    await send_voice_response(update, f"Program {target_fn} berhasil diperbaiki dan dijalankan Bos.")
            else:
                await safe_reply(update, f"❌ File <code>{target_fn}</code> tidak ditemukan di D:\\Jarvis-Agent")

        # E. INTENT: CHAT (OBROLAN STANDARD)
        else:
            c_res = client.models.generate_content(
                model=MODEL_NAME,
                contents=f"{JARVIS_PERSONA}\n\nObrolan/Pertanyaan Bos:\n{clean_query}"
            )
            
            # ATURAN BALASAN SUARA VS TEKS
            if is_voice:
                if is_data:
                    # Kirim Teks Detail + Voice Note Ringkas
                    await safe_reply(update, f"💬 <b>JARVIS:</b>\n\n{c_res.text}")
                    await send_voice_response(update, voice_summary)
                else:
                    # HANYA BALAS VOICE NOTE! (Chat tidak dipenuhi teks)
                    await send_voice_response(update, voice_summary)
            else:
                # Jika Pengguna mengetik via teks -> Balas via Teks
                await safe_reply(update, f"💬 <b>JARVIS:</b>\n\n{c_res.text}")

    except Exception as e:
        await safe_reply(update, f"🚨 Gagal memproses perintah: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != ALLOWED_CHAT_ID: return
    msg = (
        "⚡ <b>YOO, JARVIS INTENT-AWARE IS ONLINE, BOS!</b> 🤖\n\n"
        "Sekarang kamu gak perlu pakai kode/prefix kaku lagi!\n"
        "Tinggal **ketik langsung** atau **kirim pesan suara (Voice Note)** secara bebas.\n\n"
        "Contoh yang bisa kamu katakan:\n"
        "• <i>'Cariin harga GPU RTX 4060 hari ini'</i>\n"
        "• <i>'Buatkan bot telegram pengingat jadwal'</i>\n"
        "• <i>'Jalankan script main.py'</i>\n"
        "• <i>'Halo Jarvis, hari ini ceritain lelucon dong'</i>"
    )
    await safe_reply(update, msg, is_html=True)

async def run_with_self_healing(update: Update, target_fp: str, max_retries: int = 3):
    """Fungsi otonom untuk menjalankan script, mendeteksi error, dan memperbaiki diri (self-healing)"""
    file_dir = os.path.dirname(target_fp)
    file_name = os.path.basename(target_fp)
    
    for attempt in range(1, max_retries + 1):
        await safe_reply(update, f"⚙️ Menjalankan <code>{file_name}</code> (Percobaan ke-{attempt}/{max_retries})...")
        
        # Eksekusi script python
        r_res = subprocess.run(["python", target_fp], capture_output=True, text=True, timeout=25, cwd=file_dir)
        
        # Jika BERHASIL (Exit code 0)
        if r_res.returncode == 0:
            out = r_res.stdout if r_res.stdout else "(Program selesai tanpa output)"
            await safe_reply(update, f"✅ <b>BERHASIL (Sukses):</b>\n\n{out}")
            return True
            
        # Jika GAGAL (Ada error traceback)
        error_output = r_res.stderr if r_res.stderr else r_res.stdout
        await safe_reply(update, f"⚠️ <b>TERDETEKSI ERROR PADA PERCOBAAN {attempt}:</b>\n<pre>{error_output[:1000]}</pre>\n\n🛡️ <i>Memulai prosedur Self-Healing & Auto-Fixing...</i>")
        
        # Baca isi file kode yang error saat ini
        try:
            with open(target_fp, "r", encoding="utf-8") as f:
                current_code = f.read()
        except Exception as e:
            await safe_reply(update, f"❌ Gagal membaca file kode: {str(e)}")
            return False
            
        # Panggil Gemini untuk memperbaiki kode yang error
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
                # Timpa file lama dengan kode hasil perbaikan mandiri
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

def main():
    print("🤖 Jarvis Phase 12 (Unified Intent Engine) Running...")
    print("Menunggu perintah suara / teks dari Bos...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    
    # SATU PINTU: Menangani Teks & Voice Note Otomatis tanpa command /
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unified_handler))
    app.add_handler(MessageHandler(filters.VOICE, unified_handler))

    app.run_polling()

if __name__ == "__main__":
    main()