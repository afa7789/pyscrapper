import requests
from logging_config import get_logger

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.logger = get_logger()
        self.MAX_MESSAGE_LENGTH = 4096  # Telegram's character limit

    def send_message(self, identifier, text):
        """Sends message to a chat ID, phone number, or username (if valid).
           Splits long messages into multiple messages."""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        if isinstance(identifier, (int, str)) and str(identifier).isdigit():
            chat_id = identifier
        else:
            updates = requests.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates").json()
            chat_id = None

            for update in updates.get("result", []):
                if "message" in update and "chat" in update["message"]:
                    chat = update["message"]["chat"]
                    if identifier.startswith("+") and "contact" in update["message"]:
                        if update["message"]["contact"]["phone_number"] == identifier:
                            chat_id = chat["id"]
                            break
                    elif identifier.startswith("@") and chat.get("username") == identifier:
                        chat_id = chat["id"]
                        break
                    elif chat.get("username") == f"@{identifier}" or chat.get("username") == identifier:
                        chat_id = chat["id"]
                        break

            if not chat_id:
                self.logger.error(
                    "Identificador não encontrado. O usuário deve iniciar uma conversa com o bot primeiro.")
                raise ValueError(
                    "Identificador não encontrado. O usuário deve iniciar uma conversa com o bot primeiro.")
        
        # Split the message if it's too long
        message_chunks = [text[i:i + self.MAX_MESSAGE_LENGTH] 
                          for i in range(0, len(text), self.MAX_MESSAGE_LENGTH)]

        for chunk in message_chunks:
            params = {"chat_id": chat_id, "text": chunk}
            response = requests.post(url, params=params)

            if response.status_code != 200:
                self.logger.error(f"Erro ao enviar mensagem: {response.text}")
                raise Exception(f"Erro ao enviar mensagem: {response.text}")
            else:
                self.logger.info(f"Mensagem enviada com sucesso: {chunk[:18]}...")

    def list_interacted_users(self):
        """Lists all users who have interacted with the bot."""
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            response = requests.get(url)
            if response.status_code != 200:
                self.logger.error(f"Erro ao obter atualizações: {response.text}")
                raise Exception(f"Erro ao obter atualizações: {response.text}")

            updates = response.json().get("result", [])
            users = {}

            for update in updates:
                if "message" in update and "chat" in update["message"]:
                    chat = update["message"]["chat"]
                    chat_id = chat["id"]
                    user_info = {
                        "chat_id": chat_id,
                        "username": chat.get("username", "N/A"),
                        "first_name": chat.get("first_name", "N/A"),
                        "phone_number": "N/A"
                    }

                    if "contact" in update["message"]:
                        user_info["phone_number"] = update["message"]["contact"].get(
                            "phone_number", "N/A")

                    users[chat_id] = user_info

            user_list = list(users.values())
            if not user_list:
                self.logger.info("Nenhum usuário encontrou interação com o bot.")

            return user_list

        except Exception as e:
            self.logger.error(f"Erro ao listar usuários: {str(e)}")
            raise Exception(f"Erro ao listar usuários: {str(e)}")