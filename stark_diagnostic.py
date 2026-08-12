import os
import time
import sqlite3
import subprocess
import psutil
import gc
import traceback

class StarkDiagnosticSuite:
    def __init__():
        self.results = {}

    def log_result(self, feature_name: str, passed: bool, details: str):
        symbol = "✅ PASSED" if passed else "🚨 FAILED"
        self.results[feature_name] = {"status": symbol, "details": details}

    # 1. UJI OTAR UTAMA (GEMINI API)
    def test_gemini_api(self):
        try:
            from jarvis_master import ask_jarvis
            res = ask_jarvis("Tes diagnostik V.E.R.I.T.A.S. Jawab HANYA satu kata: 'ONLINE'")
            if res and len(res.strip()) > 0:
                self.log_result("Gemini AI Core Engine", True, f"API Responsif: '{res.strip()[:30]}...'")
            else:
                self.log_result("Gemini AI Core Engine", False, "Menerima respons kosong dari API.")
        except Exception as e:
            self.log_result("Gemini AI Core Engine", False, f"Error: {e}")

    # 2. UJI MEMORI SQLITE
    def test_sqlite_db(self):
        try:
            from jarvis_master import MEMORY_DB_PATH
            if os.path.exists(MEMORY_DB_PATH):
                conn = sqlite3.connect(MEMORY_DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()
                self.log_result("SQLite Long-Term Memory", True, f"Tabel DB terverifikasi ({len(tables)} tabel).")
            else:
                self.log_result("SQLite Long-Term Memory", False, "Berkas database SQLite tidak ditemukan.")
        except Exception as e:
            self.log_result("SQLite Long-Term Memory", False, f"Database Error: {e}")

    # 3. UJI MEMORI VEKTOR (CHROMADB)
    def test_chroma_vector_db(self):
        try:
            from jarvis_master import vector_collection
            count = vector_collection.count()
            self.log_result("ChromaDB Vector Palace", True, f"Koleksi aktif ({count} dokumen terindeks).")
        except Exception as e:
            self.log_result("ChromaDB Vector Palace", False, f"Vector Store Error: {e}")

    # 4. UJI SINTESIS AUDIO (gTTS)
    def test_tts_engine(self):
        try:
            from jarvis_master import generate_gtts_base64_sync
            audio_b64 = generate_gtts_base64_sync("V.E.R.I.T.A.S. Audio Test")
            if audio_b64 and len(audio_b64) > 100:
                self.log_result("gTTS Audio Synthesizer", True, f"Base64 stream berhasil dibangun ({len(audio_b64)} bytes).")
            else:
                self.log_result("gTTS Audio Synthesizer", False, "Ukuran buffer audio tidak sesuai.")
        except Exception as e:
            self.log_result("gTTS Audio Synthesizer", False, f"TTS Synthesis Error: {e}")

    # 5. UJI SENSOR HARDWARE (psutil)
    def test_hardware_metrics(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.log_result("Hardware Telemetry Sensor", True, f"CPU Usage: {cpu}% | RAM Usage: {ram}%")
        except Exception as e:
            self.log_result("Hardware Telemetry Sensor", False, f"Sensor Error: {e}")

    # 6. UJI HEPHAESTUS GIT ENGINE
    def test_git_pipeline(self):
        try:
            res = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                self.log_result("Hephaestus Git CLI Engine", True, "Git terhubung dengan repositori lokal.")
            else:
                self.log_result("Hephaestus Git CLI Engine", False, f"Git CLI Error: {res.stderr}")
        except Exception as e:
            self.log_result("Hephaestus Git CLI Engine", False, f"Git Execution Error: {e}")

    # 7. EXEKUSI AUDIT MENYELURUH
    def run_full_audit(self) -> str:
        print("\n🩺 [V.E.R.I.T.A.S.] Starting Full System Diagnostic...\n")

        self.test_gemini_api()
        self.test_sqlite_db()
        self.test_chroma_vector_db()
        self.test_tts_engine()
        self.test_hardware_metrics()
        self.test_git_pipeline()

        total_tests = len(self.results)
        passed_tests = sum(1 for v in self.results.values() if "PASSED" in v["status"])

        report_lines = [
            "🩺 **[PROJECT V.E.R.I.T.A.S. DIAGNOSTIC REPORT]**",
            f"📊 *System Integrity Rate:* `{passed_tests}/{total_tests} Modules Verified`\n"
        ]

        for feature, data in self.results.items():
            report_lines.append(f"• **{feature}**: {data['status']}\n  └ _{data['details']}_")

        return "\n".join(report_lines)

if __name__ == "__main__":
    suite = StarkDiagnosticSuite()
    print(suite.run_full_audit())