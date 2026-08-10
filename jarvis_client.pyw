import os
import subprocess
import requests
import time
import psutil

# Konfigurasi Penghubung Stark Hybrid
SERVER_URL = "https://worker-production-792b.up.railway.app"
CLIENT_SECRET_KEY = "STARK_OVERRIDE_SECRET_2026"  # Kunci pengaman enkripsi lokal

print("🛡️ [STARK CLIENT COMPANION] Menghubungkan ke Stark Mainframe...")

def poll_server_commands():
    while True:
        try:
            # Mengecek apakah ada antrean perintah terminal / kontrol PC dari server Railway
            resp = requests.get(f"{SERVER_URL}/client/poll", headers={"Authorization": CLIENT_SECRET_KEY}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                command = data.get("command")
                
                if command:
                    print(f"⚡ Menerima perintah dari Mainframe: '{command}'")
                    # Eksekusi aman di terminal PC lokal Bos
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                    output_text = result.stdout if result.stdout else result.stderr
                    
                    # Kirim balik hasilnya ke Railway
                    requests.post(f"{SERVER_URL}/client/report", json={
                        "output": output_text[:3000],
                        "status": "success"
                    }, headers={"Authorization": CLIENT_SECRET_KEY})
        except Exception as e:
            # Koneksi aman, abaikan jika terputus sementara
            pass
        
        time.sleep(5) # Cek perintah setiap 5 detik

if __name__ == "__main__":
    print("🟢 [STARK CLIENT] Aktif dan berjaga di latar belakang PC lokal.")
    poll_server_commands()