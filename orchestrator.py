import os
import re
import requests
from google import genai
from stark_sandbox import StarkSandboxManager

class AgenticSquadOrchestrator:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.sandbox = StarkSandboxManager()
        port = os.getenv("PORT", 8080)
        self.hud_url = f"http://127.0.0.1:{port}/client/proactive_alert"
        self.secret_key = "STARK_OVERRIDE_SECRET_2026"

    def _send_to_hud(self, message: str):
        """Mengirim progres agen ke layar HUD HP Bos secara real-time"""
        try:
            requests.post(
                self.hud_url,
                headers={"Authorization": self.secret_key, "Content-Type": "application/json"},
                json={"alert_message": message},
                timeout=5
            )
        except Exception as e:
            print(f"[!] Gagal mengirim telemetri ke HUD: {e}")

    def orchestrate(self, goal: str, target_filename: str = "fitur_otonom.py") -> str:
        print(f"🚀 [ORCHESTRATOR] Memulai misi pembangunan: {goal}", flush=True)
        self._send_to_hud(f"🚀 **[MISSION START]**\nGoal: `{goal}`")
        
        # 1. ARCHITECT AGENT: Menganalisis dan Membuat Blueprint
        print("🏗️ [ARCHITECT] Menyusun cetak biru arsitektur kode...", flush=True)
        self._send_to_hud("🏗️ **[AGENT: ARCHITECT]**\nSedang menyusun blueprint arsitektur...")
        blueprint = self._architect_agent(goal)
        self._send_to_hud(f"🏗️ **[ARCHITECT REPORT]**\n{blueprint[:500]}")

        # 2. CODER AGENT: Menulis Kode Murni ke Sandbox
        print(f"💻 [CODER] Menulis kode ke kanvas sandbox ({target_filename})...", flush=True)
        self._send_to_hud("💻 **[AGENT: CODER]**\nMenulis kode murni ke sandbox...")
        code_content = self._coder_agent(goal, blueprint)
        file_path = self.sandbox.create_canvas_file(target_filename, code_content)

        # 3. QA & HEALER LOOP: Menguji dan Memperbaiki Otomatis (Max 3 Percobaan)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(f"🧪 [QA TESTER] Pengujian sintaks percobaan ke-{attempt}...", flush=True)
            self._send_to_hud(f"🧪 **[AGENT: QA TESTER]**\nPengujian sintaks percobaan ke-{attempt}...")
            success, msg = self.sandbox.test_sandbox_file(target_filename)

            if success:
                print(f"✅ [QA PASSED] Kode 100% valid pada percobaan ke-{attempt}!", flush=True)
                self.sandbox.promote_sandbox_file(target_filename)
                msg_final = f"✅ **[MISSION SUCCESS]** Fitur `{target_filename}` berhasil dibangun, diuji, dan dipromosikan ke direktori utama!"
                self._send_to_hud(msg_final)
                return msg_final
            else:
                print(f"⚠️ [HEALER ACTIVE] Terdeteksi error, meminta AI memperbaiki...", flush=True)
                self._send_to_hud(f"⚠️ **[AGENT: HEALER]**\nError terdeteksi pada percobaan {attempt}, memperbaiki kode secara mandiri...")
                code_content = self._healer_agent(code_content, msg)
                file_path = self.sandbox.create_canvas_file(target_filename, code_content)

        fail_msg = f"🚨 **[MISSION FAILED]** Gagal setelah {max_attempts}x percobaan perbaikan otomatis."
        self._send_to_hud(fail_msg)
        return fail_msg

    def _architect_agent(self, goal: str) -> str:
        prompt = f"Bertindaklah sebagai System Architect. Buat rencana teknis singkat untuk membuat fitur berikut: {goal}"
        response = self.client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        return response.text

    def _coder_agent(self, goal: str, blueprint: str) -> str:
        prompt = (
            f"Tugas: Buat kode program Python lengkap berdasarkan tujuan dan blueprint ini.\n"
            f"Tujuan: {goal}\nBlueprint: {blueprint}\n"
            f"Berikan HANYA kode program murni tanpa teks penjelasan dan tanpa markdown ```python."
        )
        response = self.client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        code = response.text
        return re.sub(r'```python|```', '', code).strip()

    def _healer_agent(self, old_code: str, error_msg: str) -> str:
        prompt = (
            f"Bertindaklah sebagai Code Healer/Debugger.\n"
            f"Kode sebelumnya mengalami error berikut:\n{error_msg}\n\n"
            f"KODE LAMA:\n{old_code}\n\n"
            f"Perbaiki error tersebut dan berikan HANYA kode Python murni hasil perbaikan tanpa markdown."
        )
        response = self.client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        code = response.text
        return re.sub(r'```python|```', '', code).strip()