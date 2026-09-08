import asyncio
import json
import requests
import websockets
from datetime import date

TOKEN = "Add your token here"
GUILD_ID = "ADD_YOUR_SERVER_ID_HERE"
CHANNEL_ID = "ADD_YOUR_CHANNEL_ID_HERE"

STATUS = "online"  # online / dnd / idle
SELF_MUTE = True
SELF_DEAF = False

API = "https://discord.com/api/v10"

res = requests.get(f"{API}/users/@me", headers={"Authorization": TOKEN})
if res.status_code != 200:
    print("Invalid token!")
    exit()

user = res.json()
print(f"Logged in as {user['username']} ({user['id']})!")

last_action_date = None  # Track if action performed today

async def heartbeat(ws, interval):
    while True:
        await asyncio.sleep(interval / 1000)
        await ws.send(json.dumps({"op": 1, "d": None}))

async def connect_voice():
    uri = "wss://gateway.discord.gg/?v=10&encoding=json"
    async with websockets.connect(uri, max_size=10 * 1024 * 1024) as ws:
        # Receive HELLO and start heartbeat
        hello = json.loads(await ws.recv())
        heartbeat_interval = hello["d"]["heartbeat_interval"]
        asyncio.create_task(heartbeat(ws, heartbeat_interval))

        # Identify and set presence
        await ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": TOKEN,
                "properties": {
                    "$os": "windows",
                    "$browser": "chrome",
                    "$device": "pc"
                },
                "presence": {
                    "status": STATUS,
                    "afk": False
                }
            }
        }))

        # Wait for READY event
        while True:
            event = json.loads(await ws.recv())
            if event.get("t") == "READY":
                break

        # Join the voice channel
        await ws.send(json.dumps({
            "op": 4,
            "d": {
                "guild_id": GUILD_ID,
                "channel_id": CHANNEL_ID,
                "self_mute": SELF_MUTE,
                "self_deaf": SELF_DEAF
            }
        }))

        print("Joined the voice channel!")

        # Monitor members and perform daily check
        await monitor_members(ws)

async def monitor_members(ws):
    global last_action_date
    # Retrieve voice channel object
    guild = None
    # We need to get guild info via API
    headers = {"Authorization": TOKEN}
    res_guild = requests.get(f"{API}/guilds/{GUILD_ID}", headers=headers)
    if res_guild.status_code != 200:
        print("Failed to get guild info")
        return
    guild_data = res_guild.json()

    # Find the voice channel
    voice_channel = None
    for channel in guild_data.get("channels", []):
        if str(channel["id"]) == CHANNEL_ID:
            voice_channel = channel
            break

    if not voice_channel:
        print("Voice channel not found")
        return

    while True:
        # Check members in the voice channel
        members_res = requests.get(f"{API}/guilds/{GUILD_ID}/channels/{CHANNEL_ID}/members", headers=headers)
        if members_res.status_code != 200:
            print("Failed to get channel members")
            await asyncio.sleep(3600)
            continue

        members = members_res.json()
        # Count non-bot members
        non_bot_members = [m for m in members if not m.get("user", {}).get("bot", False)]
        num_non_bot = len(non_bot_members)

        today = date.today()

        print(f"Non-bot members in voice: {num_non_bot}")

        # Perform the once-per-day check
        if last_action_date != today:
            if num_non_bot == 1:
                # Leave voice channel
                print("Only 1 other person today, leaving for 10 minutes...")
                await ws.send(json.dumps({
                    "op": 4,
                    "d": {
                        "guild_id": GUILD_ID,
                        "channel_id": None,  # Disconnect
                        "self_mute": SELF_MUTE,
                        "self_deaf": SELF_DEAF
                    }
                }))
                # Wait 10 minutes
                await asyncio.sleep(600)
                # Rejoin the voice channel
                await ws.send(json.dumps({
                    "op": 4,
                    "d": {
                        "guild_id": GUILD_ID,
                        "channel_id": CHANNEL_ID,
                        "self_mute": SELF_MUTE,
                        "self_deaf": SELF_DEAF
                    }
                }))
                print("Rejoined the voice channel.")
                last_action_date = today
            else:
                print("More than 1 person, no action taken.")
        else:
            print("Already performed today's check.")

        await asyncio.sleep(3600)  # Check every hour

async def main():
    while True:
        try:
            await connect_voice()
        except Exception as e:
            print("Error:", e)
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

asyncio.run(main())
