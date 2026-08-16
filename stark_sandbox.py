import os
import shutil
import subprocess

class StarkSandboxManager:
    def __init__(self, base_dir="."):
        self.base_dir = os.path.abspath(base_dir)
        self.sandbox_dir = os.path.join(self.base_dir, ".stark_sandbox")
        
        # Inisialisasi folder sandbox jika belum ada
        if not os.path.exists(self.sandbox_dir):
            os.makedirs(self.sandbox_dir)

    def create_canvas_file(self, filename: str, content: str) -> str:
        """Membuat file baru di dalam kanvas sandbox yang aman"""
        safe_path = os.path.join(self.sandbox_dir, filename)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📦 [SANDBOX] Kanvas file berhasil dibuat: {safe_path}")
        return safe_path

    def test_sandbox_file(self, filename: str) -> tuple[bool, str]:
        """Menguji kompilasi/sintaks file di dalam sandbox tanpa merusak sistem"""
        target_path = os.path.join(self.sandbox_dir, filename)
        if not os.path.exists(target_path):
            return False, f"File {filename} tidak ditemukan di sandbox."

        try:
            # Uji sintaks Python di dalam sandbox
            result = subprocess.run(
                ["python", "-m", "py_compile", target_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, "Uji sandbox lolos: Sintaks 100% valid."
            else:
                return False, result.stderr
        except Exception as e:
            return False, f"Sandbox Execution Error: {e}"

    def promote_sandbox_file(self, filename: str) -> bool:
        """Memindahkan file dari sandbox ke direktori utama jika sudah terbukti aman"""
        src_path = os.path.join(self.sandbox_dir, filename)
        dest_path = os.path.join(self.base_dir, filename)

        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            print(f"🚀 [SANDBOX PROMOTION] File '{filename}' dipromosikan ke direktori utama!")
            return True
        return False

    def clear_sandbox(self):
        """Membersihkan seluruh isi kanvas sandbox"""
        if os.path.exists(self.sandbox_dir):
            shutil.rmtree(self.sandbox_dir)
            os.makedirs(self.sandbox_dir)
        print("🧹 [SANDBOX] Kanvas dibersihkan.")

if __name__ == "__main__":
    # Tes mandiri modul sandbox
    box = StarkSandboxManager()
    box.create_canvas_file("test_feature.py", "print('Stark Sandbox Active!')")
    success, msg = box.test_sandbox_file("test_feature.py")
    print(f"Hasil Uji: {success} | Pesan: {msg}")