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
    print("🧹 [VERONICA HOUSEKEEPING] Pembersihan berkas sampah temporary...")
    patterns = ["*.png", "*.jpg", "*.ogg", "*.mp3", "temp_*"]
    removed_count = 0
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            try:
                # Jangan hapus assets permanen jika ada
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    removed_count += 1
            except Exception:
                pass
    gc.collect()
    print(f"✅ [HOUSEKEEPING COMPLETE] Berhasil membersihkan {removed_count} berkas temporary.")

def extract_target_file_from_traceback(stderr_text):
    """🔍 Melacak berkas Python spesifik yang menjadi sumber utama crash"""
    # Mencari pola Traceback Python: File "xxx.py", line yyy
    matches = re.findall(r'File "([^"]+\.py)"', stderr_text)
    if matches:
        # Ambil file lokal terakhir dalam stack trace (biasanya file sumber error)
        for filepath in reversed(matches):
            filename = os.path.basename(filepath)
            if os.path.exists(filename) and filename != "bootstrapper.py":
                return filename
    return "jarvis_master.py" # Fallback default

def run_veronica_outer_shield():
    print("🛡️ ==============================================================")
    print("🛡️ [VERONICA & A.S.C.A.R. LEVEL 4 PRE-FLIGHT SHIELD ONLINE]")
    print("🛡️ Multi-Module Watchdog & Out-Of-Memory Defense Active")
    print("🛡️ ==============================================================")

    crash_count = 0

    while True:
        print(f"\n🚀 [BOOTSTRAPPER] Starting Child Process: jarvis_master.py ...")
        
        # Jalankan master process tanpa buffering
        process = subprocess.Popen(
            [sys.executable, "-u", "jarvis_master.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        stderr_lines = []

        # Stream stderr secara real-time ke console Railway
        if process.stderr:
            for line in iter(process.stderr.readline, ''):
                if line:
                    sys.stderr.write(line)
                    sys.stderr.flush()
                    stderr_lines.append(line)

        process.wait()
        return_code = process.returncode
        full_stderr = "".join(stderr_lines)

        # 1. PERHENTIAN NORMAL
        if return_code == 0:
            print("✅ [BOOTSTRAPPER] Application shut down cleanly.")
            break

        crash_count += 1
        print(f"\n🚨 [CRASH DETECTED] Process exited with Return Code: {return_code}")

        # 2. PENANGANAN CRASH OOM (OUT OF MEMORY - EXIT CODE 137)
        if return_code == 137 or "MemoryError" in full_stderr:
            print("⚠️ [VERONICA EMERGENCY] Out Of Memory (OOM / Code 137) terdeteksi!")
            clean_temporary_junk()
            print("💡 Menyalakan LOW_MEMORY_MODE untuk proses berikutnya...")
            os.environ["LOW_MEMORY_MODE"] = "1"

        # 3. PENANGANAN RUNTIME / STARTUP / SYNTAX CRASH VIA A.S.C.A.R.
        else:
            target_file = extract_target_file_from_traceback(full_stderr)
            print(f"🎯 [VERONICA TARGETING] Melacak sumber error ke berkas: `{target_file}`")
            print("🔧 [A.S.C.A.R.] Mengaktifkan Autonomous Hotpatch Engine...")

            try:
                # Import A.S.C.A.R. secara dinamis dari outer shield
                from ascar_engine import ASCARMaintenanceEngine
                engine = ASCARMaintenanceEngine()

                healed, heal_msg = engine.auto_repair_file(target_file, full_stderr)
                status_str = "SUCCESS" if healed else "FAILED/ROLLBACKED"
                print(f"🛠️ [A.S.C.A.R. RESULT - {status_str}]: {heal_msg}")

            except Exception as e:
                print(f"🚨 [BOOTSTRAPPER ERROR] Gagal mengeksekusi A.S.C.A.R. Engine -> {e}")

        # 4. SAFETY CIRCUIT BREAKER
        if crash_count >= MAX_CONSECUTIVE_CRASHES:
            print(f"\n🛑 [CIRCUIT BREAKER] Terjadi {MAX_CONSECUTIVE_CRASHES}x crash berturut-turut.")
            print("Sistem membatalkan restart otomatis demi mencegah spamming loop.")
            sys.exit(1)

        print(f"🔄 [AUTO-RECOVERY] Me-restart sistem dalam {RESTART_DELAY} detik...\n")
        time.sleep(RESTART_DELAY)

if __name__ == "__main__":
    run_veronica_outer_shield()