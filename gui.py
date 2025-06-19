import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading

from dotenv import load_dotenv
import os
import sys


class MarketRoxoGUI:
    def __init__(self, root, start_callback, stop_callback):
        self.root = root
        self.start_callback = start_callback
        self.stop_callback = stop_callback

        # Configure root window
        self.root.title("Monitor MarketRoxoGUI + Telegram")
        self.root.configure(bg='white')  # Force white background

        # --- CHANGE THIS PART ---
        # Determine the path to the .env file
        # If running as a PyInstaller onefile app, sys._MEIPASS points to the temp extraction dir
        # Otherwise, it's the current directory (for development)
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        dotenv_path = os.path.join(base_path, '.env')

        # Load environment variables from specified path
        load_dotenv(dotenv_path=dotenv_path)
        # --- END CHANGE ---

        self.default_keywords = os.getenv(
            "DEFAULT_KEYWORDS", "iphone, samsung, xiaomi")
        self.telegram_token = os.getenv("TELEGRAM_TOKEN", "").strip()
        self.cellphone_number = os.getenv(
            "TELEGRAM_CHAT_ID_OR_PHONE", "").strip()
        self.default_negative_keywords = os.getenv(
            "NEGATIVE_KEYWORDS_LIST", "")
        # Assuming HTTP_PROXY for simplicity, can be expanded
        self.default_proxies = os.getenv("HTTP_PROXY", "")

        # Create all widgets immediately
        self.create_widgets()
        # Center and show window
        try:
            self.root.update()
            self.center_window()
        except tk.TclError:
            # Handle cases where the display might not be ready
            pass

    def center_window(self):
        """Center the window on screen"""
        width = 600
        height = 900
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        """Create all GUI widgets with explicit configuration"""

        # Title
        title_label = tk.Label(self.root, text="Monitor MarketRoxo + Telegram",
                               font=("Arial", 16, "bold"), bg='white', fg='black')
        title_label.pack(pady=20)

        # Keywords section
        kw_label = tk.Label(self.root, text="Palavras-chave (separadas por vírgula):",
                            font=("Arial", 12), bg='white', fg='black')
        kw_label.pack(pady=(20, 5), padx=20, anchor='w')

        self.keywords_entry = tk.Entry(self.root, width=70, font=("Arial", 11),
                                       bg='white', fg='black', relief='solid', bd=1)
        self.keywords_entry.pack(pady=5, padx=20, fill='x')
        self.keywords_entry.insert(
            0, self.default_keywords)  # Default keywords

        # Telegram token section
        token_label = tk.Label(self.root, text="Token do Bot do Telegram:",
                               font=("Arial", 12), bg='white', fg='black')
        token_label.pack(pady=(20, 5), padx=20, anchor='w')

        self.telegram_token_entry = tk.Entry(self.root, width=70, font=("Arial", 11),
                                             bg='white', fg='black', relief='solid', bd=1, show="*")
        self.telegram_token_entry.insert(
            0, self.telegram_token)  # Default token
        self.telegram_token_entry.pack(pady=5, padx=20, fill='x')

        # Negative Keywords section
        neg_kw_label = tk.Label(self.root, text="Palavras-chave Negativas (separadas por vírgula):",
                               font=("Arial", 12), bg=\'white\', fg=\'black\')
        neg_kw_label.pack(pady=(20, 5), padx=20, anchor=\'w\')

        self.negative_keywords_entry = tk.Entry(self.root, width=70, font=("Arial", 11),
                                                bg=\'white\', fg=\'black\', relief=\'solid\', bd=1)
        self.negative_keywords_entry.pack(pady=5, padx=20, fill=\'x\')
        self.negative_keywords_entry.insert(0, self.default_negative_keywords)

        # Proxies section
        proxy_label = tk.Label(self.root, text="Proxy (ex: http://user:pass@host:port):",
                              font=("Arial", 12), bg=\'white\', fg=\'black\')
        proxy_label.pack(pady=(20, 5), padx=20, anchor=\'w\')

        self.proxies_entry = tk.Entry(self.root, width=70, font=("Arial", 11),
                                      bg=\'white\', fg=\'black\', relief=\'solid\', bd=1)
        self.proxies_entry.pack(pady=5, padx=20, fill=\'x\')
        self.proxies_entry.insert(0, self.default_proxies)

        # Chat ID section
        chat_label = tk.Label(self.root, text="Chat ID ou Número de Telefone:",
                              font=("Arial", 12), bg='white', fg='black')
        chat_label.pack(pady=(20, 5), padx=20, anchor='w')

        chat_help = tk.Label(self.root, text="(Ex: 123456789 ou +5511999999999)",
                             font=("Arial", 10), bg='white', fg='gray')
        chat_help.pack(padx=20, anchor='w')

        self.chat_input_entry = tk.Entry(self.root, width=70, font=("Arial", 11),
                                         bg='white', fg='black', relief='solid', bd=1)
        self.chat_input_entry.insert(0, self.cellphone_number)
        self.chat_input_entry.pack(pady=5, padx=20, fill='x')

        # Buttons frame
        button_frame = tk.Frame(self.root, bg='white')
        button_frame.pack(pady=30)

        self.start_button = tk.Button(button_frame, text="🚀 Iniciar Monitoramento",
                                      command=self._on_start, font=(
                                          "Arial", 12, "bold"),
                                      bg="#4CAF50", fg="white", activebackground="#45a049",
                                      width=20, height=2, relief='raised', bd=2)
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.stop_button = tk.Button(button_frame, text="🛑 Parar Monitoramento",
                                     command=self._on_stop, state=tk.DISABLED,
                                     font=("Arial", 12, "bold"), bg="#f44336", fg="white",
                                     activebackground="#da190b", width=20, height=2,
                                     relief='raised', bd=2)
        self.stop_button.pack(side=tk.LEFT, padx=10)

        # Status
        self.status_label = tk.Label(self.root, text="Status: Aguardando configuração...",
                                     font=("Arial", 11, "bold"), bg='white', fg='blue')
        self.status_label.pack(pady=10)

        # Separator
        separator = tk.Frame(self.root, height=2, bg='lightgray')
        separator.pack(fill='x', padx=20, pady=10)

        # Log section
        log_label = tk.Label(self.root, text="Log de Atividades:",
                             font=("Arial", 12, "bold"), bg='white', fg='black')
        log_label.pack(pady=(10, 5), padx=20, anchor='w')

        # Log text area
        self.log_text = scrolledtext.ScrolledText(self.root, height=12, width=70,
                                                  font=("Courier", 10), bg='#f5f5f5',
                                                  fg='black', wrap=tk.WORD, relief='solid', bd=1)
        self.log_text.pack(pady=5, padx=20, fill='both', expand=True)

        # Clear button
        clear_frame = tk.Frame(self.root, bg='white')
        clear_frame.pack(pady=10)

        clear_button = tk.Button(clear_frame, text="Limpar Log", command=self.clear_log,
                                 font=("Arial", 10), bg='lightgray', fg='black',
                                 relief='raised', bd=1, padx=20)
        clear_button.pack()

        # Force update to ensure all widgets are visible
        self.root.update_idletasks()

    def _on_start(self):
        """Handle start button click"""
        keywords = self.keywords_entry.get().strip()
        token = self.telegram_token_entry.get().strip()
        chat_input = self.chat_input_entry.get().strip()

        if not keywords or not token or not chat_input:
            messagebox.showerror(
                "Erro", "Por favor, preencha todos os campos!")
            return

        try:
            keywords_list = [kw.strip()
                             for kw in keywords.split(",") if kw.strip()]
            if not keywords_list:
                messagebox.showerror(
                    "Erro", "Digite pelo menos uma palavra-chave válida!")
                return

            negative_keywords = [kw.strip() for kw in self.negative_keywords_entry.get().strip().split(",") if kw.strip()]

            # Update UI state
            self.start_button.config(state=tk.DISABLED, bg=\'gray\')
            self.stop_button.config(state=tk.NORMAL, bg=\'#f44336\')
            self.status_label.config(
                text="Status: Iniciando monitoramento...", fg="orange")

            # Start monitoring
            self.start_callback(keywords_list, token, chat_input, negative_keywords, proxies)
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Erro ao iniciar monitoramento:\n{str(e)}")
            self._reset_buttons()

    def _on_stop(self):
        """Handle stop button click"""
        try:
            self.status_label.config(
                text="Status: Parando monitoramento...", fg="orange")
            self.stop_callback()
            self._reset_buttons()
            self.status_label.config(
                text="Status: Monitoramento parado", fg="red")

        except Exception as e:
            messagebox.showerror(
                "Erro", f"Erro ao parar monitoramento:\n{str(e)}")

    def _reset_buttons(self):
        """Reset button states"""
        self.start_button.config(state=tk.NORMAL, bg='#4CAF50')
        self.stop_button.config(state=tk.DISABLED, bg='gray')

    def set_monitoring_active(self):
        """Set status to active monitoring"""
        self.status_label.config(
            text="Status: Monitoramento ATIVO", fg="green")

    def set_monitoring_error(self, error_msg=""):
        """Set status to error"""
        self.status_label.config(text=f"Status: Erro - {error_msg}", fg="red")
        self._reset_buttons()

    def log(self, message):
        """Thread-safe logging method"""
        def _log():
            try:
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                formatted_message = f"[{timestamp}] {message}"

                self.log_text.insert(tk.END, formatted_message + "\n")
                self.log_text.see(tk.END)

                # Keep only last 500 lines for performance
                lines = int(self.log_text.index('end-1c').split(".")[0])
                if lines > 500:
                    self.log_text.delete("1.0", "100.0")

            except (tk.TclError, AttributeError):
                # GUI might be destroyed or not ready
                pass

        # Use after() for thread safety
        try:
            if self.root and self.root.winfo_exists():
                self.root.after(0, _log)
        except tk.TclError:
            pass

    def clear_log(self):
        """Clear the log text area"""
        try:
            self.log_text.delete("1.0", tk.END)
            self.log("Log limpo pelo usuário")
        except tk.TclError:
            pass


# Test standalone
if __name__ == "__main__":
    def dummy_start(keywords, token, chat_id):
        print(f"Start: {keywords}, {token}, {chat_id}")

    def dummy_stop():
        print("Stop")

    root = tk.Tk()
    app = MarketRoxoGUI(root, dummy_start, dummy_stop)

    # Add some test logs
    app.log("Interface carregada com sucesso!")
    app.log("Aguardando configuração...")

    root.mainloop()
