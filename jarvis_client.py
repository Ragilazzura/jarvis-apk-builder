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

# Threshold Notifikasi Otomatis
CPU_THRESHOLD = 90.0  # Alert jika CPU > 90%
RAM_THRESHOLD = 90.0  # Alert jika RAM > 90%
last_alert_time = 0

print("⚡ [STARK HYBRID] Jembatan Lokal E.D.I.T.H. Active & Monitoring...")

def execute_windows_command(cmd_str):
    """Mengeksekusi perintah terminal Windows"""
    try:
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=15)
        return res.stdout if res.stdout else res.stderr
    except Exception as e:
        return f"Error executing command: {e}"

def take_screenshot_base64():
    """Mengambil screenshot layar dan mengubahnya ke Base64"""
    try:
        screenshot = ImageGrab.grab()
        buffered = io.BytesIO()
        screenshot.save(buffered, format="JPEG", quality=75)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[!] Error Screenshot: {e}")
        return ""

def check_hardware_health():
    """Monitoring background untuk Proactive Push Notification"""
    global last_alert_time
    now = time.time()
    
    # Beri jeda minimal 5 menit antar notifikasi agar tidak spamming
    if now - last_alert_time < 300:
        return

    cpu_use = psutil.cpu_percent(interval=1)
    ram_use = psutil.virtual_memory().percent

    if cpu_use > CPU_THRESHOLD or ram_use > RAM_THRESHOLD:
        alert_msg = f"⚠️ *WARNING HARDWARE OVERLOAD!*\nCPU: {cpu_use}% | RAM: {ram_use}%\nLaptop Bos sedang bekerja sangat berat!"
        try:
            requests.post(
                f"{RAILWAY_URL}/client/proactive_alert",
                headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                json={"alert_message": alert_msg}
            )
            last_alert_time = now
            print(f"🔔 [PROACTIVE ALERT SENT] CPU: {cpu_use}% | RAM: {ram_use}%")
        except Exception as e:
            print(f"[!] Gagal mengirim alert: {e}")

def process_command(data):
    """Memproses instruksi yang datang dari cloud Railway"""
    cmd_type = data.get("type")
    
    # 1. ANALISIS LAYAR (E.D.I.T.H. SCREEN VISION)
    if cmd_type == "SCREEN_VISION":
        prompt_user = data.get("prompt", "Analisis layar PC ini, Bos.")
        print("👁️ [E.D.I.T.H. VISION] Mengambil screenshot layar...")
        img_b64 = take_screenshot_base64()
        return {
            "type": "VISION_RESPONSE",
            "image_base64": img_b64,
            "prompt": prompt_user
        }

    # 2. MEDIA & SYSTEM CONTROL
    elif cmd_type == "MEDIA_CONTROL":
        action = data.get("action")
        if action == "vol_up":
            execute_windows_command("powershell -c \"(new-object -com wscript.shell).SendKeys([char]175)\"") # Vol Up
        elif action == "vol_down":
            execute_windows_command("powershell -c \"(new-object -com wscript.shell).SendKeys([char]174)\"") # Vol Down
        elif action == "vol_mute":
            execute_windows_command("powershell -c \"(new-object -com wscript.shell).SendKeys([char]173)\"") # Mute
        elif action == "play_pause":
            execute_windows_command("powershell -c \"(new-object -com wscript.shell).SendKeys([char]179)\"") # Play/Pause
        return {"output": f"Media Control '{action}' executed."}

    # 3. SHUTDOWN TIMER CONTROL
    elif cmd_type == "SHUTDOWN_TIMER":
        minutes = data.get("minutes", 30)
        seconds = minutes * 60
        execute_windows_command(f"shutdown /s /t {seconds}")
        return {"output": f"PC dijadwalkan shutdown dalam {minutes} menit."}

    elif cmd_type == "SHUTDOWN_CANCEL":
        execute_windows_command("shutdown /a")
        return {"output": "Penjadwalan shutdown dibatalkan."}

    # 4. SHELL COMMAND UMUM
    elif cmd_type == "SHELL":
        output = execute_windows_command(data.get("command", ""))
        return {"output": output}

    return {"output": "Unknown command type"}

# ==========================================
# LOOPING UTAMA (POLLING SERVER)
# ==========================================
while True:
    try:
        # Cek beban hardware untuk Proactive Alert
        check_hardware_health()

        # Polling antrean perintah dari server
        resp = requests.get(
            f"{RAILWAY_URL}/client/poll",
            headers={"Authorization": CLIENT_SECRET},
            timeout=10
        )
        
        if resp.status_code == 200:
            job_data = resp.json()
            if job_data.get("command_data"):
                result_payload = process_command(job_data["command_data"])
                
                # Kirim hasil eksekusi kembali ke server
                requests.post(
                    f"{RAILWAY_URL}/client/report",
                    headers={"Authorization": CLIENT_SECRET, "Content-Type": "application/json"},
                    json=result_payload
                )

    except Exception as e:
        pass  # Jaga agar skrip tidak crash jika koneksi sempat terputus
        
    time.sleep(3)