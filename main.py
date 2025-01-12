import discord
from discord.ext import commands
import os
import google.generativeai as genai
import json
from discord.ui import Button, View
import asyncio
from threading import Thread
from flask import Flask, request

# Intents setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    print('Bot is ready to receive commands!')
    bot.loop.create_task(ping_bot_every_minute())  # Start the background task
    bot.loop.create_task(self_ping_task())  # Start the self-pinging task

# Configuration
TARGET_CHANNEL_ID = 1327513737657188393  # Set the target channel ID
LEARNING_CHANNEL_ID = 1327877300036964403  # Set the learning channel ID
SELF_PING_CHANNEL_ID = 1327493040201269343  # Set the self-pinging channel ID
USER_DATA_FILE = "user_data.json"
GLOBAL_DATA_FILE = "global_data.json"
WIKIPEDIA_FILE = "wikipedia.txt"
DISCORD_TOKEN = "MTMyNzQ5NTg1NDM3Mzk5NDU3Nw.GxUs0p.ChIOE-vo5hcjuFqLbThq3fW0SgsptBTb8ZhxvU"  # Replace with your actual token
GEMINI_API_KEY = os.getenv("YOUR_GEMINI_API_KEY")  # Replace with your actual API key

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Bot prompt
PROMPT_PREFIX = """You are a helpful, friendly, and informative assistant named Cammie. You should respond in a conversational and natural style as much as possible, explaining things in detail and providing multi-sentence responses. Do not answer with code snippets unless you are explicitly requested to. If asked to rephrase something, do so without giving any special intro text. Do not mention that you are an assistant.
You are a bot created for the ComondoPlayz discord server. The members of that server are: Gloxie, Comondoplayz and Aquaplayz.
You should not say any bad words. You are a good person and should act like a human.
"""

# Teaching server ID
TEACHING_SERVER_ID = 1327877300036964403

# Load wikipedia content into memory.
def load_wikipedia(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read()
    return ""

wikipedia_content = load_wikipedia(WIKIPEDIA_FILE)

# --- Data Loading and Saving ---
def load_user_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

def save_user_data(data, file_path):
    with open(file_path, "w") as f:
        json.dump(data, f)

def load_global_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

def save_global_data(data, file_path):
    with open(file_path, "w") as f:
        json.dump(data, f)

# --- Initial Global Knowledge ---
async def load_initial_global_knowledge():
    global global_data
    global_data = load_global_data(GLOBAL_DATA_FILE)

# --- User Agreement Handling ---
async def check_user_agreement(message):
    global user_data
    user_id = message.author.id
    if user_id not in user_data:
        user_data[user_id] = {"agreed": False, "country": "unknown"}

    if not user_data[user_id]["agreed"]:
        view = View()
        agree_button = Button(label="Agree", style=discord.ButtonStyle.green)
        disagree_button = Button(label="Disagree", style=discord.ButtonStyle.red)

        async def agree_callback(interaction):
            user_data[user_id]["agreed"] = True
            save_user_data(user_data, USER_DATA_FILE)
            await interaction.response.send_message("Thank you for agreeing to our terms!", ephemeral=True)

        async def disagree_callback(interaction):
            await interaction.response.send_message("You must agree to our terms to continue.", ephemeral=True)

        agree_button.callback = agree_callback
        disagree_button.callback = disagree_callback

        view.add_item(agree_button)
        view.add_item(disagree_button)

        await message.reply("Please agree to our terms by clicking the 'Agree' button below.", view=view)
        return False

    return True

# --- Response Generation ---
async def generate_response(message_content):
    try:
        modified_prompt = f"""{PROMPT_PREFIX} The message is: {message_content}
        Please respond in a conversational and natural style as much as possible.
        """

        response = model.generate_content(modified_prompt)
        return response.text
    except Exception as e:
        print(f"Error during Gemini processing: {e}")
        return "Sorry, I'm having trouble processing your request."

# --- On Interaction ---
@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.application_command:
        await interaction.response.send_message("Sorry, I don't understand that command yet.", ephemeral=True)

# --- Learning Functions ---
async def learn_global_data(message_content):
    if "global_learning_data" not in global_data:
        global_data["global_learning_data"] = {} 

    # Gemini-based context understanding
    try:
        modified_prompt = f"""{PROMPT_PREFIX} The message is: {message_content}
        What are the topics that the message is talking about? Please respond with the topics in comma seperated format."""

        response = model.generate_content(modified_prompt)
        topics = [topic.strip() for topic in response.text.split(",")]
        # Only update if gemini can extract any key phrases.
        if len(topics) > 0:
            for topic in topics:
                if topic in global_data["global_learning_data"]:
                    global_data["global_learning_data"][topic] += 1
                else:
                    global_data["global_learning_data"][topic] = 1
    except Exception as e:
        print(f"Error during Gemini processing: {e}")

    save_global_data(global_data)  # Save updated global data

# --- Message Handling ---
@bot.event
async def on_message(message):
    # Skip if the message is from the bot itself
    if message.author == bot.user:
        return

    # Check if the message is in the learning channel
    if message.channel.id == LEARNING_CHANNEL_ID:
        await learn_global_data(message.content)  # Learn from the message in the learning channel
        # (Gemini response handling in the learning channel can be added here if needed)

    # Check if the message is in the target channel
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    # Handle user agreement
    if not await check_user_agreement(message):
        return

    # Generate response
    response = await generate_response(message.content)
    await message.reply(response)

    await bot.process_commands(message)

# --- Flask Web Server Setup ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bot is alive"

def run_flask_app():
    app.run(host='0.0.0.0', port=8080)

# --- Main Bot Logic ---
def run_bot():
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: Bot token not found")

# --- Background Task ---
async def ping_bot_every_minute():
    while True:
        await asyncio.sleep(60)  # Wait for 60 seconds
        print("Pinging bot...")

async def self_ping_task():
    while True:
        await asyncio.sleep(60)  # Wait for 5 seconds
        await bot.get_channel(SELF_PING_CHANNEL_ID).send("Ping!")

if __name__ == "__main__":
    # 1. Start Flask app in a separate thread
    web_thread = Thread(target=run_flask_app)
    web_thread.daemon = True  # Ensure the thread exits if the main thread exits
    web_thread.start()

    # 2. Run the bot
    run_bot()