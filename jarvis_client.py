import os
import time
import json
import base64
import io
import subprocess
import requests
import psutil
from PIL import ImageGrab

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
    
    # 1. SCREEN VISION
    if cmd_type == "SCREEN_VISION":
        prompt_user = data.get("prompt", "Analisis layar PC ini, Bos.")
        print("👁️ [VISION] Mengambil screenshot layar...")
        img_b64 = take_screenshot_base64()
        return {"type": "VISION_RESPONSE", "image_base64": img_b64, "prompt": prompt_user}

    # 2. MEDIA CONTROL
    elif cmd_type == "MEDIA_CONTROL":
        action = data.get("action")
        keys = {"vol_up": 175, "vol_down": 174, "vol_mute": 173, "play_pause": 179}
        if action in keys:
            execute_windows_command(f"powershell -c \"(new-object -com wscript.shell).SendKeys([char]{keys[action]})\"")
        return {"output": f"Media Action '{action}' executed."}

    # 3. SHUTDOWN CONTROL
    elif cmd_type == "SHUTDOWN_TIMER":
        minutes = data.get("minutes", 1)
        execute_windows_command(f"shutdown /s /t {minutes * 60}")
        return {"output": f"PC dijadwalkan shutdown dalam {minutes} menit."}

    elif cmd_type == "SHUTDOWN_CANCEL":
        execute_windows_command("shutdown /a")
        return {"output": "Penjadwalan shutdown dibatalkan."}

    # 4. START DOCUMENT INDEXER
    elif cmd_type == "START_FILE_INDEXING":
        scan_and_index_documents()
        return {"output": "Pemindaian dan pengindeksan dokumen selesai."}

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

        # Laporkan rangkuman eksekusi kembali ke Telegram/Cloud
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

    return {"output": "Unknown command"}

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
            if job_data.get("command_data"):
                result_payload = process_command(job_data["command_data"])
                requests.post(
                    f"{RAILWAY_URL}/client/report",
                    headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                    json=result_payload
                )

    except Exception:
        pass
        
    time.sleep(3)