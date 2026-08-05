import os
import subprocess
import requests
from google import genai

# ==========================================
# CONFIGURATION
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6IxhTdXEg7BM0seNpek0rcF8iOmAe8Ndc5QFZpV6HbsLg"
TELEGRAM_BOT_TOKEN = "8716909256:AAHiaoc3IiDJqnlgVe8mmzUhYP4WrCMOh4A"
TELEGRAM_CHAT_ID = "5883853281"

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_notify(message):
    """Kirim notifikasi ke HP via Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Gagal kirim notif: {e}")

def test_code_execution(file_path):
    """Fungsi untuk mengecek apakah ada error sintaks pada kode"""
    print(f"🧪 Jarvis: Menguji kodingan '{file_path}'...")
    try:
        # Mengecek kompilasi sintaks Python
        result = subprocess.run(
            ["python", "-m", "py_compile", file_path],
            capture_output=True,
            text=True,
            check=True
        )
        return True, "Sukses! Tidak ada error sintaks."
    except subprocess.CalledProcessError as e:
        # Jika ada error sintaks pada kode
        return False, e.stderr

def run_agent_task(blueprint_file, target_output_file, max_attempts=3):
    print("🤖 Jarvis: Membaca blueprint...")
    
    if not os.path.exists(blueprint_file):
        print(f"[-] Error: File '{blueprint_file}' tidak ditemukan!")
        return

    with open(blueprint_file, "r", encoding="utf-8") as f:
        blueprint_content = f.read()

    send_telegram_notify(
        f"🚀 *JARVIS STARTING (PHASE 2)*\n\n"
        f"📄 Processing: `{blueprint_file}`\n"
        f"🛡️ Mode: Auto-Test & Self-Correction Enabled"
    )

    error_context = ""
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- PERCOBAAN KE-{attempt} ---")
        
        # Penanganan string error terpisah agar tidak memicu SyntaxError f-string
        error_instruction = ""
        if error_context:
            error_instruction = f"⚠️ PERBAIKAN ERROR (Percobaan sebelumnya gagal dengan error berikut):\n{error_context}"

        prompt = f"""
        Kamu adalah agen software developer otomatis.
        Tugasmu adalah membuat kode program Python lengkap berdasarkan blueprint berikut:

        --- BLUEPRINT ---
        {blueprint_content}
        --- END BLUEPRINT ---

        {error_instruction}

        Berikan HANYA kode programnya saja tanpa teks penjelasan tambahan maupun sintaks markdown ```python.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )

        code_result = response.text.replace("```python", "").replace("```", "").strip()

        # Simpan file
        with open(target_output_file, "w", encoding="utf-8") as f:
            f.write(code_result)

        # UJI KODE SECARA OTOMATIS
        is_success, log_message = test_code_execution(target_output_file)

        if is_success:
            print("✅ Kode berhasil diuji dan lolos tes sintaks!")
            send_telegram_notify(
                f"✅ *CHECKPOINT PASSED! (Percobaan {attempt})*\n\n"
                f"File `{target_output_file}` berhasil dibuat & lolos pengujian otomatis tanpa error!\n\n"
                f"Silakan cek laptop kamu, Bos! 😎"
            )
            return
        else:
            print(f"❌ Terdeteksi Error pada Percobaan {attempt}!")
            print(f"Error Log:\n{log_message}")
            error_context = log_message
            send_telegram_notify(
                f"⚠️ *Jarvis Menemukan Error (Attempt {attempt})*\n"
                f"Sedang mencoba *Auto-Fixing*..."
            )

    # Jika sudah mencapai batas percobaan tapi masih error
    send_telegram_notify(
        f"🚨 *JARVIS GAGAL SELESAI*\n\n"
        f"Sudah dicoba {max_attempts}x tapi masih ada error. Butuh bantuan manusia, Bos!"
    )

if __name__ == "__main__":
    run_agent_task(blueprint_file="blueprint.txt", target_output_file="hasil_app.py")