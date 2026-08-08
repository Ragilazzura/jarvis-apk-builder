import os
import discord
from discord.ext import commands

# Mengimpor "Otak" dan fungsi utama dari Telegram Bot kita
from jarvis_master import (
    client, MODEL_NAME, JARVIS_PERSONA, 
    get_all_memories, search_vector_db, clean_markdown_to_html
)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Setup Intents Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Jarvis Discord Agent Online sebagai {bot.user}")

@bot.event
async def on_message(message):
    # Jangan balas pesan dari diri sendiri
    if message.author == bot.user:
        return

    # Hanya merespons jika bot di-mention atau dipanggil "jarvis"
    if bot.user.mentioned_in(message) or "jarvis" in message.content.lower():
        user_msg = message.content.replace(f"<@{bot.user.id}>", "").strip()
        
        async with message.channel.typing():
            try:
                # 1. Ambil Ingatan Jangka Pendek & Jangka Panjang
                memories = get_all_memories()
                vector_context = search_vector_db(user_msg)
                
                # 2. Rangkai Prompt ke Otak Gemini
                final_prompt = f"{JARVIS_PERSONA}\n\nMemori Bos:\n{memories}{vector_context}\n\nPesan dari Discord:\n{user_msg}"
                
                # 3. Generate Jawaban
                c_res = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=final_prompt
                )
                
                # Discord pakai Markdown asli, jadi kita tidak perlu ubah ke HTML
                reply_text = c_res.text
                
                # Batas pesan Discord adalah 2000 karakter, potong jika perlu
                if len(reply_text) > 1999:
                    reply_text = reply_text[:1996] + "..."
                    
                await message.reply(reply_text)
            
            except Exception as e:
                await message.reply(f"🚨 Gagal memproses data: {str(e)}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)