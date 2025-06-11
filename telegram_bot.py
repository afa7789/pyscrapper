import requests

class TelegramBot:
    def __init__(self, log_callback, token):
        self.token = token
        self.log_callback = log_callback

    def send_message(self, identifier, text):
        """Sends message to a chat ID, phone number, or username (if valid)."""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        # Check if identifier is a chat ID (numeric, can be a string or int)
        if isinstance(identifier, (int, str)) and str(identifier).isdigit():
            chat_id = identifier
        else:
            # Fetches updates to find the chat_id associated with the phone number or username
            updates = requests.get(f"https://api.telegram.org/bot{self.token}/getUpdates").json()
            chat_id = None
            
            for update in updates.get("result", []):
                if "message" in update and "chat" in update["message"]:
                    chat = update["message"]["chat"]
                    # Check if identifier is a phone number (starts with "+")
                    if identifier.startswith("+") and "contact" in update["message"]:
                        if update["message"]["contact"]["phone_number"] == identifier:
                            chat_id = chat["id"]
                            break
                    # Check if identifier is a username (starts with "@")
                    elif identifier.startswith("@") and chat.get("username") == identifier:
                        chat_id = chat["id"]
                        break
                    # Check if identifier is a username without "@" prefix
                    elif chat.get("username") == f"@{identifier}" or chat.get("username") == identifier:
                        chat_id = chat["id"]
                        break
            
            if not chat_id:
                self.log_callback("Identificador não encontrado. O usuário deve iniciar uma conversa com o bot primeiro.")
                raise ValueError("Identificador não encontrado. O usuário deve iniciar uma conversa com o bot primeiro.")
        
        # Sends the message
        params = {"chat_id": chat_id, "text": text}
        response = requests.post(url, params=params)
        
        if response.status_code != 200:
            self.log_callback(f"Erro ao enviar mensagem: {response.text}")
            raise Exception(f"Erro ao enviar mensagem: {response.text}")

    def list_interacted_users(self):
        """Lists all users who have interacted with the bot."""
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            response = requests.get(url)
            # print(response)
            if response.status_code != 200:
                self.log_callback(f"Erro ao obter atualizações: {response.text}")
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
                    
                    # Check if contact information is available
                    if "contact" in update["message"]:
                        user_info["phone_number"] = update["message"]["contact"].get("phone_number", "N/A")
                    
                    users[chat_id] = user_info
            
            user_list = list(users.values())
            if not user_list:
                self.log_callback("Nenhum usuário encontrou interação com o bot.")
            
            return user_list
        
        except Exception as e:
            self.log_callback(f"Erro ao listar usuários: {str(e)}")
            raise Exception(f"Erro ao listar usuários: {str(e)}")