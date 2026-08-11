import os
import time
import json
import base64
import io
import subprocess
import requests
import psutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import ImageGrab
import docx
from pypdf import PdfReader, PdfWriter

# ==========================================
# KONFIGURASI JEMBATAN STARK HYBRID
# ==========================================
RAILWAY_URL = "https://worker-production-792b.up.railway.app"
CLIENT_SECRET = "STARK_OVERRIDE_SECRET_2026"

# Threshold Notifikasi Hardware
CPU_THRESHOLD = 90.0
RAM_THRESHOLD = 90.0
last_alert_time = 0

# Folder Lokal yang Akan Diindeks Otomatis ke ChromaDB
TARGET_INDEX_DIR = os.path.expanduser("~/Documents") # Sesuaikan dengan folder kodingan/dokumen Bos

print("⚡ [STARK HYBRID MASTER] E.D.I.T.H., Vision, Media & Indexer Active!")

def execute_windows_command(cmd_str):
    try:
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=15)
        return res.stdout if res.stdout else res.stderr
    except Exception as e:
        return f"Error: {e}"

def take_screenshot_base64():
    try:
        screenshot = ImageGrab.grab()
        buffered = io.BytesIO()
        screenshot.save(buffered, format="JPEG", quality=75)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[!] Error Screenshot: {e}")
        return ""

def check_hardware_health():
    """Modul 4: Proactive Alerting Engine"""
    global last_alert_time
    now = time.time()
    
    if now - last_alert_time < 300: # Jeda 5 menit per notifikasi
        return

    cpu_use = psutil.cpu_percent(interval=1)
    ram_use = psutil.virtual_memory().percent

    if cpu_use > CPU_THRESHOLD or ram_use > RAM_THRESHOLD:
        alert_msg = f"⚠️ *WARNING HARDWARE OVERLOAD!*\nCPU: {cpu_use}% | RAM: {ram_use}%\nWorkstation Bos sedang bekerja sangat berat!"
        try:
            requests.post(
                f"{RAILWAY_URL}/client/proactive_alert",
                headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                json={"alert_message": alert_msg}
            )
            last_alert_time = now
            print(f"🔔 [PROACTIVE ALERT SENT] CPU: {cpu_use}% | RAM: {ram_use}%")
        except Exception as e:
            print(f"[!] Gagal kirim alert: {e}")

def scan_and_index_documents():
    """Modul 2: Auto-Document & Code Indexer ke ChromaDB"""
    print("📂 [INDEXER] Memulai pemindaian file lokal...")
    valid_extensions = [".py", ".txt", ".md", ".json", ".dart"]
    indexed_count = 0

    for root, _, files in os.walk(TARGET_INDEX_DIR):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(3000) # Ambil 3000 karakter pertama
                    
                    if content.strip():
                        requests.post(
                            f"{RAILWAY_URL}/client/index_document",
                            headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                            json={"file_name": file, "content": content}
                        )
                        indexed_count += 1
                        time.sleep(0.2)
                except Exception as e:
                    print(f"[!] Skip file {file}: {e}")

    print(f"✅ [INDEXER COMPLETED] Berhasil mengindeks {indexed_count} file ke ChromaDB!")

def process_command(data):
    cmd_type = data.get("type")
    
    # 1. 👁️ SCREEN VISION
    if cmd_type == "SCREEN_VISION":
        prompt_user = data.get("prompt", "Analisis layar PC ini, Bos.")
        print("👁️ [VISION] Mengambil screenshot layar...")
        img_b64 = take_screenshot_base64()
        return {"type": "VISION_RESPONSE", "image_base64": img_b64, "prompt": prompt_user}

    # 2. 📻 MEDIA CONTROL
    elif cmd_type == "MEDIA_CONTROL":
        action = data.get("action")
        keys = {"vol_up": 175, "vol_down": 174, "vol_mute": 173, "play_pause": 179}
        if action in keys:
            execute_windows_command(f"powershell -c \"(new-object -com wscript.shell).SendKeys([char]{keys[action]})\"")
        return {"output": f"Media Action '{action}' executed."}

    # 3. ⏰ POWER & SECURITY CONTROL
    elif cmd_type == "SHUTDOWN_TIMER":
        minutes = data.get("minutes", 1)
        execute_windows_command(f"shutdown /s /t {minutes * 60}")
        return {"output": f"PC dijadwalkan shutdown dalam {minutes} menit."}

    elif cmd_type == "SHUTDOWN_CANCEL":
        execute_windows_command("shutdown /a")
        return {"output": "Penjadwalan shutdown dibatalkan."}
        
    elif cmd_type == "LOCK_SCREEN":
        print("🔒 [SECURITY] Mengunci layar PC...")
        execute_windows_command("rundll32.exe user32.dll,LockWorkStation")
        return {"output": "Layar PC berhasil dikunci oleh E.D.I.T.H."}

    # 4. 📂 DOCUMENT & APP ENGINE
    elif cmd_type == "START_FILE_INDEXING":
        scan_and_index_documents()
        return {"output": "Pemindaian dan pengindeksan dokumen selesai."}
        
    elif cmd_type == "WORD_ACTION":
        # Contoh eksekusi dummy, bisa dikembangkan menerima payload spesifik
        print("📝 [DOC ENGINE] Memproses dokumen Word...")
        res = handle_word_document("create_or_append", "jarvis_notes.docx", "Catatan otomatis dari Jarvis HUD.")
        return {"output": res}
        
    elif cmd_type == "CHECK_RUNNING_APPS":
        print("📊 [APP CHECKER] Memeriksa aplikasi aktif...")
        res = check_running_apps()
        return {"output": f"Aplikasi berjalan:\n{res[:1000]}"}

    # 5. 📧 COMMUNICATION ENGINE
    elif cmd_type == "SEND_EMAIL":
        print("📧 [COMMUNICATION] Menyiapkan transmisi email...")
        import re
        
        raw_prompt = data.get("raw_prompt", "")
        
        # Ekstrak alamat email otomatis dari kalimat perintah Bos
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_prompt)
        target = emails[0] if emails else "email_bos_disini@gmail.com" # Ganti dengan email cadanganmu
        
        # Ekstrak isi pesan (mengambil kalimat setelah kata "isi" atau "pesan")
        msg_body = raw_prompt
        if "isi " in raw_prompt.lower():
            msg_body = raw_prompt.lower().split("isi ", 1)[1]
        elif "pesan " in raw_prompt.lower():
            msg_body = raw_prompt.lower().split("pesan ", 1)[1]
            
        res = send_email_smtp(target, "J.A.R.V.I.S Automated Protocol", msg_body)
        return {"output": res}
        
    elif cmd_type == "SEND_WHATSAPP":
        print("💬 [COMMUNICATION] Menyiapkan transmisi WhatsApp...")
        target = data.get("target", "1234567890")
        msg = data.get("message", "Pesan dari Jarvis.")
        res = send_whatsapp_web(target, msg)
        return {"output": res}

    # 6. 🤖 AUTONOMOUS TASK FORCE
    elif cmd_type == "TASK_FORCE_CHAIN":
        chain = data.get("chain", [])
        task_name = data.get("task_name", "Autonomous Task")
        print(f"🤖 [TASK FORCE] Memulai rantai pekerjaan: '{task_name}' ({len(chain)} Langkah)...")
        
        execution_logs = []
        for item in chain:
            step_num = item.get("step")
            desc = item.get("description")
            cmd = item.get("command")
            
            print(f" └─ [Langkah {step_num}] {desc} -> Executing: `{cmd}`")
            out = execute_windows_command(cmd)
            execution_logs.append(f"Step {step_num} ({desc}):\n{out.strip()}\n")
            time.sleep(1)

        full_report = f"✅ *TASK FORCE COMPLETED: {task_name}*\n\n" + "\n".join(execution_logs)
        try:
            requests.post(
                f"{RAILWAY_URL}/client/proactive_alert",
                headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                json={"alert_message": full_report[:4000]}
            )
        except:
            pass
        return {"output": f"Rantai eksekusi '{task_name}' sukses diselesaikan."}
        
    elif cmd_type == "RUN_ASCAR_DIAGNOSTIC":
        from ascar_engine import ASCARMaintenanceEngine
        engine = ASCARMaintenanceEngine()
        report_msg = engine.run_full_diagnostic()
        try:
            requests.post(
                f"{RAILWAY_SERVER_URL}/api/push_hud_message",
                json={"sender": "ascar", "message": report_msg},
                timeout=10
            )
        except Exception as e:
            print(f"Gagal mengirim laporan ASCAR ke HUD: {e}")

    return {"output": f"Unknown command: {cmd_type}"}

# ==========================================
# 1. OFFICE & DOCUMENT ENGINE (WORD & PDF)
# ==========================================
def handle_word_document(action, file_path, content=""):
    """Membaca, menulis, atau mengedit file .docx"""
    try:
        if action == "read":
            doc = docx.Document(file_path)
            full_text = [p.text for p in doc.paragraphs]
            return "\n".join(full_text)[:3000]

        elif action == "create_or_append":
            if os.path.exists(file_path):
                doc = docx.Document(file_path)
            else:
                doc = docx.Document()
            doc.add_paragraph(content)
            doc.save(file_path)
            return f"Dokumen Word '{os.path.basename(file_path)}' berhasil diperbarui, Bos!"
            
    except Exception as e:
        return f"Error Word Document: {e}"

def handle_pdf_document(action, file_path, content=""):
    """Membaca isi file PDF"""
    try:
        if action == "read":
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages[:5]:  # Ambil 5 halaman pertama
                text += page.extract_text() or ""
            return text[:3000]
    except Exception as e:
        return f"Error PDF Document: {e}"

# ==========================================
# 2. COMMUNICATION ENGINE (EMAIL & WHATSAPP)
# ==========================================
def send_email_smtp(to_email, subject, body_text):
    """Mengirim Email otomatis via SMTP"""
    sender_email = os.getenv("STARK_EMAIL_USER", "your_email@gmail.com")
    sender_password = os.getenv("STARK_EMAIL_PASS", "your_app_password")

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return f"Email berhasil dikirim ke {to_email}, Bos!"
    except Exception as e:
        return f"Gagal mengirim email: {e}"

def send_whatsapp_web(phone_number, message):
    """Mengirim pesan WhatsApp via Web/Protocol"""
    try:
        import pywhatkit as pwk
        # Mengirim WA instant
        pwk.sendwhatmsg_instantly(f"+{phone_number}", message, wait_time=10, tab_close=True)
        return f"Pesan WhatsApp terkirim ke {phone_number}!"
    except Exception as e:
        return f"Error WA Sender: {e}"

# ==========================================
# 3. APP & SYSTEM CONTROLLER (PC)
# ==========================================
def check_running_apps():
    """Memeriksa aplikasi yang sedang berjalan di PC"""
    try:
        cmd = 'powershell -Command "Get-Process | Where-Object {$_.MainWindowTitle -ne \'\'} | Select-Object ProcessName, MainWindowTitle"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.stdout if res.stdout else "Tidak ada aplikasi aktif terdeteksi."
    except Exception as e:
        return f"Error checking apps: {e}"

# ==========================================
# MAIN LOOPING
# ==========================================
while True:
    try:
        check_hardware_health()

        resp = requests.get(
            f"{RAILWAY_URL}/client/poll",
            headers={"Authorization": CLIENT_SECRET},
            timeout=10
        )
        
        if resp.status_code == 200:
            job_data = resp.json()
            if job_data.get("command"):
                print(f"📥 [POLL] Menerima instruksi dari Cloud: {job_data['command']}")
                
                result_payload = process_command(job_data["command"])
                
                requests.post(
                    f"{RAILWAY_URL}/client/report",
                    headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                    json=result_payload
                )

    except Exception as e:
        print(f"🚨 [KONEKSI ERROR]: {e}")
        
    time.sleep(3)