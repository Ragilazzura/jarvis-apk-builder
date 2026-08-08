import os
import io
import discord
from discord.ext import commands

from jarvis_master import (
    client, MODEL_NAME, JARVIS_PERSONA, 
    get_all_memories, search_vector_db, ask_jarvis, ask_jarvis_with_image,
    generate_voice_response, generate_and_test_code
)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Jarvis Discord Agent Online sebagai {bot.user}")

@bot.command(name="status")
async def status_cmd(ctx):
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    await ctx.send(f"📊 **JARVIS DISCORD AGENT HEALTH**\n• CPU: {cpu}%\n• RAM: {ram}%\n• Status: Online 100%")

@bot.command(name="voice")
async def voice_cmd(ctx, *, prompt: str):
    async with ctx.typing():
        reply_text = ask_jarvis(prompt)
        voice_path = await generate_voice_response(reply_text)
        if voice_path and os.path.exists(voice_path):
            await ctx.send(content=f"💬 {reply_text[:200]}...", file=discord.File(voice_path))
            os.remove(voice_path)
        else:
            await ctx.send(reply_text)

@bot.command(name="code")
async def code_cmd(ctx, *, prompt: str):
    async with ctx.typing():
        await ctx.send("🤖 Jarvis Code Agent sedang memproses & menguji kodingan...")
        is_success, status_msg, file_path = generate_and_test_code(prompt)
        await ctx.send(status_msg)
        if is_success and os.path.exists(file_path):
            await ctx.send(file=discord.File(file_path))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if message.content.startswith("!"):
        return

    if bot.user.mentioned_in(message) or "jarvis" in message.content.lower():
        user_msg = message.content.replace(f"<@{bot.user.id}>", "").strip()
        
        async with message.channel.typing():
            try:
                # 👁️ Jika ada lampiran gambar/foto
                if message.attachments:
                    for att in message.attachments:
                        if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                            img_bytes = await att.read()
                            reply_text = ask_jarvis_with_image(img_bytes, user_msg)
                            await message.reply(reply_text)
                            return

                reply_text = ask_jarvis(user_msg)
                if len(reply_text) > 1999:
                    reply_text = reply_text[:1996] + "..."
                await message.reply(reply_text)
            except Exception as e:
                await message.reply(f"🚨 Gagal memproses data: {str(e)}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)