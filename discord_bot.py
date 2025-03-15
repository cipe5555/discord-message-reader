import discord
import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
import asyncio
from datetime import datetime, timedelta, timezone
from src.regear import RegearAgent

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # Ensure APP_URL is set in .env
FORUM_LINK = os.getenv("FORUM_LINK")

regear_agent = RegearAgent()

# Setup FastAPI
app = FastAPI()

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # Required to fetch nickname
intents.messages = True

client = discord.Client(intents=intents)

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

@app.get("/read_messages/{thread_id}")
async def read_messages(thread_id: int):
    """Fetch messages from a forum thread"""
    channel = client.get_channel(thread_id)
    if not channel:
        return {"error": "Thread not found"}

    messages = [msg async for msg in channel.history(limit=None)]  # Get all messages

    message_data = []
    for msg in messages:
        author = msg.author
        user_nickname = None
        if msg.guild:
            try:
                member = await msg.guild.fetch_member(author.id)
                user_nickname = member.nick
            except discord.NotFound:
                user_nickname = None  # Handle cases where the user is not found

        message_data.append({
            "username": author.name,
            "nickname": user_nickname,
            "content": msg.content if msg.content else None,
            "image_urls": [attachment.url for attachment in msg.attachments if attachment.url],
            "timestamp": msg.created_at.isoformat(),
        })

    return {"messages": message_data}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_thread_create(thread):
    """Detects new forum posts and sends a notification"""
    if thread.parent and thread.parent.type == discord.ChannelType.forum and str(thread.parent_id) == FORUM_LINK:
        print(f"📢 New forum post detected: {thread.name}")
        try:
            now_utc = datetime.now(timezone.utc)
            end_datetime = now_utc.replace(tzinfo=None)  # Convert to naive datetime
            start_datetime = (now_utc - timedelta(hours=4)).replace(tzinfo=None)  # Convert to naive datetime
            print(f"end_datetime: {end_datetime}")
            print(f"start_datetime: {start_datetime}")
            regear_agent.regear(start_datetime, end_datetime, thread.name)
            print("Regear Calculated Successfully!")
        except Exception as e:
                print(f"error: {e}")
        # notify_channel = client.get_channel(NOTIFY_CHANNEL_ID)
        # if notify_channel:
        #     await notify_channel.send(
        #         f"📢 **New Forum Post:** {thread.name}\n🔗 {thread.jump_url}"
        #     )

# Function to run FastAPI and Discord bot together
async def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def keep_alive():
    """Keep-alive function to prevent app from sleeping (useful for cloud hosting)"""
    while True:
        if APP_URL:
            try:
                response = requests.get(f"{APP_URL}/healthz", timeout=10)
                print(f"🔄 Keep-alive ping to {APP_URL}/healthz, Status Code: {response.status_code}")
            except requests.RequestException as e:
                print(f"⚠️ Keep-alive request failed: {e}")
        else:
            print("⚠️ APP_URL is not set! Keep-alive function won't work.")
        await asyncio.sleep(60)  # Ping every 1 minute

async def main():
    asyncio.create_task(run_fastapi())  # Start FastAPI server in background
    asyncio.create_task(keep_alive())   # Start keep-alive task
    await client.start(API_TOKEN)       # Start Discord bot

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
