

import os
from dotenv import load_dotenv
from telegram_bot import TelegramBot

#!/usr/bin/env python3

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get the chat ID from the .env file
    chat_id = os.getenv("TELEGRAM_CHAT_ID_OR_PHONE")
    if not chat_id:
        print("Error: TELEGRAM_CHAT_ID_OR_PHONE not set in .env file. Please get your chat ID from @userinfobot on Telegram and set it in your .env file.")
        return
        
    # Get the Telegram token from the .env file
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("Error: TELEGRAM_TOKEN not set in .env file.")
        return

    # Define a log callback function
    def log_callback(message):
        print(f"Bot log: {message}")
    
    # Create the TelegramBot instance
    bot = TelegramBot(log_callback, token)

    print(bot.list_interacted_users())
    
    print(chat_id)
    # Prepare the message
    message = "hi"
    
    # Use the bot to send the message
    try:
        response = bot.send_message(chat_id, message)
        print("Message sent successfully!")
    except Exception as e:
        print("Failed to send message:", e)

if __name__ == '__main__':
    main()

