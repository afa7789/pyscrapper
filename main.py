# main.py
import tkinter as tk
from threading import Thread
import os
import sys
from tkinter import messagebox # Import messagebox for user-visible errors
from AppKit import NSProcessInfo, NSActivityUserInitiated

# Add error handling for imports
try:
    from gui import MarketRoxoGUI
    from monitor import Monitor
    from scraper import MarketRoxoScraper
    from telegram_bot import TelegramBot
except ImportError as e:
    # For a truly fatal import error on launch, use messagebox if Tkinter is available
    try:
        # Create a temporary Tkinter root to show the message box, then hide it
        root_temp = tk.Tk()
        root_temp.withdraw() # Hide the small default Tkinter window
        messagebox.showerror("Initialization Error", f"Failed to load required modules: {e}\n\nPlease contact support.")
        root_temp.destroy() # Clean up the temporary root
    except tk.TclError:
        # Fallback if Tkinter itself is completely broken or unavailable
        sys.stderr.write(f"CRITICAL: Import error and Tkinter unavailable: {e}\n")
        sys.stderr.flush()
    sys.exit(1) # Ensure the application exits after showing the error

class MainApp:
    def __init__(self):
        self.root = None  # Initialize root to None
        try:
            self.root = tk.Tk()

            # Prevent system sleep (macOS only)
            def prevent_sleep():
                activity = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
                    NSActivityUserInitiated, "Mantendo o aplicativo ativo"
                )
                return activity

            self.activity = prevent_sleep()  # Keep a reference to the activity

            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            self.gui = MarketRoxoGUI(
                root=self.root,
                start_callback=self.start_monitoring,
                stop_callback=self.stop_monitoring
            )
            self.monitor = None
            self.monitor_thread = None
            self.base_url = os.environ.get("MAIN_URL_SCRAPE_ROXO", "")
            if not self.base_url:
                raise ValueError("MAIN_URL_SCRAPE_ROXO environment variable is not set or is empty")
        
        except Exception as e:
            # If an error occurs during MainApp __init__, show a messagebox
            if self.root: # Check if Tkinter root was successfully created before the error
                self.root.withdraw() # Hide the main window if it briefly appeared
                messagebox.showerror("Application Error", f"Failed to initialize the application GUI:\n{e}")
                self.root.destroy()
            else:
                # If root couldn't even be created, log to stderr as a last resort
                sys.stderr.write(f"CRITICAL: Failed to create Tkinter root window: {e}\n")
                sys.stderr.flush()
            sys.exit(1) # Crucial: exit after showing error

   
    def start_monitoring(self, keywords, telegram_token, chat_input):
        """Starts monitoring in a separate thread."""
        try:
            self.gui.log("🔧 Inicializando componentes...")
            
            # Test Telegram bot first
            self.gui.log("🔍 Testando conexão com Telegram...")
            telegram_bot = TelegramBot(log_callback=self.gui.log,token=telegram_token)
            
            # Simple test to validate token
            test_url = f"https://api.telegram.org/bot{telegram_token}/getMe"
            response = requests.get(test_url, timeout=10)
            if response.status_code != 200:
                raise Exception("Token do Telegram inválido!")
            
            self.gui.log("✅ Token do Telegram válido!")
            
            scraper = MarketRoxoScraper(
                log_callback=self.gui.log,  # Pass the log callback to the scraper
                base_url=self.base_url
            )
            
            self.monitor = Monitor(
                keywords=keywords,
                scraper=scraper,
                telegram_bot=telegram_bot,
                chat_id=chat_input,
                log_callback=self.gui.log
            )
            
            # Thread to prevent GUI from freezing
            self.monitor_thread = Thread(target=self.monitor.start)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            self.gui.log("🚀 Monitoramento iniciado com sucesso!")
            self.gui.set_monitoring_active()
            
        except Exception as e:
            self.gui.log(f"❌ Erro ao iniciar monitoramento: {str(e)}")
            self.gui.set_monitoring_error(str(e))
    
    # def _reset_buttons_on_error(self):
    #     """Reset button states after error"""
    #     self.gui.start_button.config(state=tk.NORMAL)
    #     self.gui.stop_button.config(state=tk.DISABLED)
    #     self.gui.status_label.config(text="Status: Erro - Tente novamente", fg="red")
    
    def stop_monitoring(self):
        """Stops the monitoring."""
        try:
            if self.monitor:
                self.monitor.stop()
                self.gui.log("Parando monitoramento...")
                
                # Wait a bit for the thread to finish
                if self.monitor_thread and self.monitor_thread.is_alive():
                    self.monitor_thread.join(timeout=2)
                    
            self.gui.log("Monitoramento parado com sucesso!")
            
        except Exception as e:
            self.gui.log(f"Erro ao parar monitoramento: {str(e)}")
    
    def on_closing(self):
        """Handle application closing"""
        try:
            if self.monitor:
                self.monitor.stop()
            self.root.quit()
            self.root.destroy()
        except:
            pass
    
    def run(self):
        """Runs the application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()
        except Exception as e:
            print(f"Error running application: {e}")

def main():
    try:
        os.environ["TK_SILENCE_DEPRECATION"] = "1" # Suppress Tkinter deprecation warnings

        app = MainApp()
        app.run() # This calls self.root.mainloop()
    except Exception as e:
        # This catch is mainly for errors *after* mainloop exits or if mainloop itself fails.
        # For --windowed apps, messagebox is preferred if a window is still available.
        try:
            # Attempt to show a messagebox if a default Tkinter root is still active
            if tk._default_root: 
                messagebox.showerror("Fatal Application Error", f"An unexpected error occurred:\n{e}")
        except Exception:
            # Fallback if messagebox itself fails
            sys.stderr.write(f"FATAL: Application encountered an unhandled error: {e}\n")
            sys.stderr.flush()
        sys.exit(1) # Ensure the process exits cleanly

if __name__ == "__main__":
    main()