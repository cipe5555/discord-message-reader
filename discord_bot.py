import discord
import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
import asyncio

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
APP_URL = os.getenv("https://discord-message-reader.onrender.com")  # Set this in your environment variables (Render URL)

# Setup FastAPI
app = FastAPI()

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # Required to fetch nickname
intents.messages = True

client = discord.Client(intents=intents)

@app.get("/read_messages/{thread_id}")
async def read_messages(thread_id: int):
    channel = client.get_channel(thread_id)  # Get the forum thread
    if not channel:
        return {"error": "Thread not found"}

    messages = [msg async for msg in channel.history(limit=None)]  # Get latest messages

    message_data = []
    for msg in messages:
        author = msg.author
        user_nickname = msg.guild.get_member(author.id).nick if msg.guild else None

        # Check if message contains text
        text_content = msg.content if msg.content else None
        
        # Check if message contains an image
        image_urls = [attachment.url for attachment in msg.attachments if attachment.url]

        message_data.append({
            "username": author.name,
            "nickname": user_nickname,
            "content": text_content,
            "image_urls": image_urls,
            "timestamp": msg.created_at.isoformat(),
        })

    return {"messages": message_data}

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

# Function to run FastAPI and Discord bot together
async def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

# Keep-alive function to prevent the server from sleeping
async def keep_alive():
    while True:
        if APP_URL:
            try:
                requests.get(APP_URL)  # Ping your Render app
                print("Pinged the server to keep it awake.")
            except requests.RequestException as e:
                print(f"Keep-alive request failed: {e}")
        await asyncio.sleep(1 * 60)  # Wait 14 minutes

async def main():
    # Start FastAPI server in background
    asyncio.create_task(run_fastapi())
    # Start keep-alive task
    asyncio.create_task(keep_alive())
    # Start Discord bot
    await client.start(API_TOKEN)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
