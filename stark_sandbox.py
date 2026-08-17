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
        """Menguji eksekusi kode (runtime) di dalam sandbox"""
        target_path = os.path.join(self.sandbox_dir, filename)
        if not os.path.exists(target_path):
            return False, f"File {filename} tidak ditemukan di sandbox."

        try:
            # 🚀 UBAH: Kita eksekusi langsung kodenya, bukan sekadar tes py_compile
            result = subprocess.run(
                ["python", target_path],
                capture_output=True,
                text=True,
                timeout=30  # Batas waktu 5 detik agar tidak nyangkut di infinite loop
            )
            
            # Jika return code 0, kode sukses berjalan dari awal sampai akhir
            if result.returncode == 0:
                output_msg = result.stdout.strip()
                if not output_msg:
                    output_msg = "(Kode berjalan sukses tapi tidak mencetak output apa-apa)"
                return True, f"✅ Lolos Uji Runtime! Output program:\n{output_msg}"
            else:
                # Menangkap error logika atau runtime (pembagian nol, module not found, dll)
                return False, f"🚨 Runtime Error terdeteksi:\n{result.stderr}"
                
        except subprocess.TimeoutExpired:
            # Pelindung ekstra: kalau agen AI berhalusinasi bikin "while True", proses langsung diputus
            return False, "⏳ Timeout Error: Kode berjalan lebih dari 5 detik. Kemungkinan terjebak infinite loop."
        except Exception as e:
            return False, f"🚨 Sandbox Execution Error: {e}"

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
    box.create_canvas_file("test_feature.py", "print('Stark Sandbox Uji Runtime Active!')")
    success, msg = box.test_sandbox_file("test_feature.py")
    print(f"Hasil Uji: {success}\nPesan:\n{msg}")