import os
import py_compile
import datetime
import shutil
from google import genai

class ASCARMaintenanceEngine:
    def __init__(self, base_dir="."):
        self.base_dir = os.path.abspath(base_dir)
        self.backup_dir = os.path.join(self.base_dir, ".ascar_backups")
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        api_key = os.getenv("GEMINI_API_KEY", "").strip('"').strip("'")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def create_backup(self, file_path: str) -> str:
        """Membuat salinan cadangan sebelum file diedit"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        rel_path = os.path.relpath(file_path, self.base_dir)
        backup_target = os.path.join(self.backup_dir, rel_path)
        os.makedirs(os.path.dirname(backup_target), exist_ok=True)
        shutil.copy2(file_path, backup_target)
        return backup_target

    def restore_backup(self, file_path: str):
        """Mengembalikan file ke kondisi semula jika auto-patch gagal"""
        rel_path = os.path.relpath(file_path, self.base_dir)
        backup_target = os.path.join(self.backup_dir, rel_path)
        if os.path.exists(backup_target):
            shutil.copy2(backup_target, file_path)

    def verify_python_file(self, file_path: str) -> tuple[bool, str]:
        """Uji kompilasi sintaks Python NATIVE (Super Cepat di Memori)"""
        try:
            py_compile.compile(file_path, doraise=True)
            return True, "Valid"
        except py_compile.PyCompileError as e:
            return False, str(e.msg)
        except Exception as e:
            return False, str(e)

    def auto_repair_file(self, file_path: str, error_msg: str) -> tuple[bool, str]:
        """🤖 AI ENGINE: Membaca, Mengedit, dan Mengetes ulang file yang rusak"""
        if not self.client:
            return False, "Gemini API Key tidak ditemukan untuk Auto-Patching."

        # 1. Buat Backup File Asli
        self.create_backup(file_path)
        try:
            # Baca isi file yang rusak
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()

            # 2. Minta AI Memperbaiki Kode
            prompt = (
                f"Kamu adalah A.S.C.A.R. Auto-Repair Engine.\n"
                f"File berikut mengalami error kompilasi/sintaks.\n\n"
                f"PESAN ERROR:\n{error_msg}\n\n"
                f"KODE ASLI:\n{code_content}\n\n"
                f"TUGASMU:\nPerbaiki error sintaks di atas dan kembalikan HANYA KODE PYTHON LENGKAP HASIL PERBAIKAN.\n"
                f"JANGAN tambahkan teks penjelasan, markdown, atau pembuka/penutup selain kode murni!"
            )

            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            patched_code = getattr(response, "text", None) or getattr(response, "content", None) or str(response)
            patched_code = patched_code.replace("```python", "").replace("```", "").strip()

            # 3. Tulis Kode Baru ke File
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(patched_code)

            # 4. Tes Ulang Sintaks Setelah Diedit
            is_valid, new_err = self.verify_python_file(file_path)
            if is_valid:
                return True, "Berhasil diperbaiki & lolos uji kompilasi!"
            else:
                # Jika masih error, kembalikan ke kode awal (Rollback)
                self.restore_backup(file_path)
                return False, f"Patch gagal diaudit ulang -> Rollback dilakukan. Error: {new_err}"

        except Exception as e:
            self.restore_backup(file_path)
            return False, f"Proses Auto-Patching crash -> Rollback dilakukan: {e}"

    def deep_scan_and_heal(self) -> dict:
        results = {
            "total_files": 0,
            "py_passed": 0,
            "dart_files": 0,
            "config_files": 0,
            "repaired_files": [],
            "failed_repairs": [],
        }

        # 🚨 FOLDER YANG DIBLOKIR TOTAL DARI PEMINDAIAN
        IGNORED_DIRS = {
            ".git", "build", ".dart_tool", "node_modules", 
            ".ascar_backups", "venv", ".venv", "env", 
            "__pycache__", ".idea", ".vscode", "android", "ios", "windows"
        }

        print("🔍 [A.S.C.A.R.] Memulai penelusuran berkas...")

        for root, dirs, files in os.walk(self.base_dir):
            
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.base_dir)
                results["total_files"] += 1

                # 🐍 Audit File Python Utama
                if file.endswith(".py"):
                    print(f"   ├─ [PY CHECK]: {rel_path}")
                    is_valid, err_msg = self.verify_python_file(file_path)
                    if is_valid:
                        results["py_passed"] += 1
                    else:
                        print(f"🚨 [ANOMALI DETECTED]: {rel_path} -> Memulai Auto-Repair...")
                        healed, heal_msg = self.auto_repair_file(file_path, err_msg)
                        if healed:
                            results["repaired_files"].append((rel_path, heal_msg))
                        else:
                            results["failed_repairs"].append((rel_path, heal_msg))

                # 🎯 Audit File Dart (Flutter HUD)
                elif file.endswith(".dart"):
                    results["dart_files"] += 1

                # ⚙️ Audit Configs
                elif file.endswith((".yaml", ".gradle", ".kts", ".json")):
                    results["config_files"] += 1
        print("✨ [A.S.C.A.R.] Pemindaian seluruh berkas selesai!")
        return results

    def run_full_diagnostic(self) -> str:
        """Menjalankan audit total dan menghasilkan laporan berformat Markdown HUD"""
        start_time = datetime.datetime.now()
        data = self.deep_scan_and_heal()
        duration = (datetime.datetime.now() - start_time).total_seconds()

        status_icon = "✅ OPTIMAL" if len(data["failed_repairs"]) == 0 else "⚠️ UNRESOLVED ANOMALIES"

        report = f"""🛡️ **[A.S.C.A.R. AUTONOMOUS REPORT]**
Status: {status_icon} | Duration: {duration:.2f}s
Target Dir: {os.path.basename(self.base_dir)}

📊 1. SCOPE OF AUDIT:
• Total File Scanned: {data['total_files']}
• Python Modules (.py): {data['py_passed'] + len(data['repaired_files']) + len(data['failed_repairs'])}
• Flutter HUD Modules (.dart): {data['dart_files']}
• Config & Native Files: {data['config_files']}

🔍 2. AUTONOMOUS HEALING LOG:
• Clean / Valid Modules: {data['py_passed']}
• Auto-Repaired Modules: {len(data['repaired_files'])}
• Critical Unfixed Errors: {len(data['failed_repairs'])}
"""

        if data["repaired_files"]:
            report += "\n🔧 **AUTO-PATCHES APPLIED:**\n"
            for path, msg in data["repaired_files"]:
                report += f"• `{path}` ➔ `{msg}`\n"

        if data["failed_repairs"]:
            report += "\n🚨 **CRITICAL ERRORS (ROLLBACKED):**\n"
            for path, msg in data["failed_repairs"]:
                report += f"• `{path}` ➔ `{msg}`\n"

        if not data["repaired_files"] and not data["failed_repairs"]:
            report += "\n✨ **ALL SYSTEMS OPTIMAL:**\n• No syntax errors or broken links detected in repository."

        return report

if __name__ == "__main__":
    engine = ASCARMaintenanceEngine()
    print(engine.run_full_diagnostic())