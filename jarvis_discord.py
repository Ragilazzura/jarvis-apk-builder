import os
import re
import discord
from google import genai

# ==========================================
# KONFIGURASI DISCORD BOT
# ==========================================
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

CLEAN_GEMINI_KEY = GEMINI_API_KEY.strip().strip('"').strip("'") if GEMINI_API_KEY else ""
client = genai.Client(api_key=CLEAN_GEMINI_KEY)

JARVIS_PERSONA = """
Kamu adalah J.A.R.V.I.S., asisten AI pribadi super canggih, adaptif, cerdas, dan sangat loyal milik Bos (Mr. Stark).

GAYA BAHASA & KEPRIBADIAN:
1. BAHASA BILINGUAL & ADAPTIF:
   - Secara otomatis sesuaikan bahasa jawabanmu berdasarkan bahasa yang digunakan.
   - Panggil pengguna dengan sebutan "Bos" atau "Sir".
2. GAYA KOMUNIKASI:
   - Tampil cerdas, responsif, berkelas, dan miliki sedikit sentuhan kecerdasan khas J.A.R.V.I.S.
3. TAMPILAN TEKS:
   - JANGAN gunakan simbol pagar (#) berlebihan. Gunakan poin atau teks murni agar rapi di Discord.
"""

# Setup Intents Discord
intents = discord.Intents.default()
intents.message_content = True  # Wajib diaktifkan agar bot bisa baca pesan chat
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f"🎮 [DISCORD-LINK] J.A.R.V.I.S. berhasil mengudara sebagai {discord_client.user}")
    await discord_client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="perintah Bos"))

@discord_client.event
async def on_message(message):
    # Cegah bot membalas pesannya sendiri
    if message.author == discord_client.user:
        return

    # Hanya merespons jika bot di-mention atau dipanggil di Direct Message (DM)
    if discord_client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        
        # Hapus tag mention dari teks pengguna
        user_msg = message.content.replace(f'<@{discord_client.user.id}>', '').strip()
        if not user_msg:
            user_msg = "Halo Jarvis, apa statusmu saat ini?"

        system_prompt = f"{JARVIS_PERSONA}\n\nPesan Pengguna (dari server Discord): {user_msg}"

        # Tampilkan efek "Jarvis is typing..." di Discord
        async with message.channel.typing():
            try:
                # Memanggil Otak Utama Gemini
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=system_prompt
                )
                
                # Pembersihan format Markdown berlebih
                clean_text = response.text
                clean_text = re.sub(r'#+\s*', '', clean_text)
                clean_text = clean_text.replace('**', '').replace('*', '')

                # Discord memiliki limit 2000 karakter per pesan, kita pecah jika kepanjangan
                if len(clean_text) > 2000:
                    for i in range(0, len(clean_text), 2000):
                        await message.reply(clean_text[i:i+2000])
                else:
                    await message.reply(clean_text)

            except Exception as e:
                print(f"🚨 Discord Gemini Error: {e}")
                await message.reply("🚨 Maaf Bos, saya mengalami gangguan sinyal komunikasi ke satelit utama.")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN:
        discord_client.run(DISCORD_BOT_TOKEN)
    else:
        print("⚠️ [DISCORD-LINK] Token Discord tidak ditemukan. Melewati aktivasi Discord Bot.")