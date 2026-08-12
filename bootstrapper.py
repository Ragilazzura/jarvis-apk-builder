import sys
import os
import time
import subprocess
import re
import glob
import gc

# Config & Limits
MAX_CONSECUTIVE_CRASHES = 5
RESTART_DELAY = 3  # Detik

def clean_temporary_junk():
    """🧹 Pembersihan Otomatis Berkas Temporary & Cache Disk"""
    print("🧹 [VERONICA HOUSEKEEPING] Pembersihan berkas sampah temporary...", flush=True)
    patterns = ["*.png", "*.jpg", "*.ogg", "*.mp3", "temp_*"]
    removed_count = 0
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    removed_count += 1
            except Exception:
                pass
    gc.collect()
    print(f"✅ [HOUSEKEEPING COMPLETE] Berhasil membersihkan {removed_count} berkas temporary.", flush=True)

def extract_target_file_from_traceback(stderr_text):
    """🔍 Melacak berkas Python spesifik yang menjadi sumber utama crash"""
    matches = re.findall(r'File "([^"]+\.py)"', stderr_text)
    if matches:
        for filepath in reversed(matches):
            filename = os.path.basename(filepath)
            if os.path.exists(filename) and filename != "bootstrapper.py":
                return filename
    return "jarvis_master.py"

def run_veronica_outer_shield():
    print("🛡️ ==============================================================", flush=True)
    print("🛡️ [VERONICA & A.S.C.A.R. LEVEL 4 PRE-FLIGHT SHIELD ONLINE]", flush=True)
    print("🛡️ Multi-Module Watchdog & Real-Time Terminal Log Active", flush=True)
    print("🛡️ ==============================================================\n", flush=True)

    crash_count = 0

    while True:
        print("🚀 [BOOTSTRAPPER] Starting Child Process: jarvis_master.py ...\n", flush=True)
        
        # 🔥 GABUNGKAN STDOUT & STDERR (stderr=subprocess.STDOUT) AGAR SEMUA PRINT MUNCUL DI TERMINAL
        process = subprocess.Popen(
            [sys.executable, "-u", "jarvis_master.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output_lines = []

        # Stream SELURUH output (Print biasa + Crash Log) secara real-time ke Railway Terminal
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    output_lines.append(line)

        process.wait()
        return_code = process.returncode
        full_output = "".join(output_lines)

        # 1. PERHENTIAN NORMAL
        if return_code == 0:
            print("✅ [BOOTSTRAPPER] Application shut down cleanly.", flush=True)
            break

        crash_count += 1
        print(f"\n🚨 [CRASH DETECTED] Process exited with Return Code: {return_code}", flush=True)

        # 2. PENANGANAN CRASH OOM (OUT OF MEMORY - EXIT CODE 137)
        if return_code == 137 or "MemoryError" in full_output:
            print("⚠️ [VERONICA EMERGENCY] Out Of Memory (OOM / Code 137) terdeteksi!", flush=True)
            clean_temporary_junk()
            os.environ["LOW_MEMORY_MODE"] = "1"

        # 3. PENANGANAN RUNTIME / STARTUP / SYNTAX CRASH VIA A.S.C.A.R.
        else:
            target_file = extract_target_file_from_traceback(full_output)
            print(f"🎯 [VERONICA TARGETING] Melacak sumber error ke berkas: `{target_file}`", flush=True)
            print("🔧 [A.S.C.A.R.] Mengaktifkan Autonomous Hotpatch Engine...", flush=True)

            try:
                from ascar_engine import ASCARMaintenanceEngine
                engine = ASCARMaintenanceEngine()

                healed, heal_msg = engine.auto_repair_file(target_file, full_output)
                status_str = "SUCCESS" if healed else "FAILED/ROLLBACKED"
                print(f"🛠️ [A.S.C.A.R. RESULT - {status_str}]: {heal_msg}", flush=True)

            except Exception as e:
                print(f"🚨 [BOOTSTRAPPER ERROR] Gagal mengeksekusi A.S.C.A.R. Engine -> {e}", flush=True)

        # 4. SAFETY CIRCUIT BREAKER
        if crash_count >= MAX_CONSECUTIVE_CRASHES:
            print(f"\n🛑 [CIRCUIT BREAKER] Terjadi {MAX_CONSECUTIVE_CRASHES}x crash berturut-turut.", flush=True)
            sys.exit(1)

        print(f"🔄 [AUTO-RECOVERY] Me-restart sistem dalam {RESTART_DELAY} detik...\n", flush=True)
        time.sleep(RESTART_DELAY)

if __name__ == "__main__":
    run_veronica_outer_shield()