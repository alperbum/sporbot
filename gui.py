import customtkinter as ctk
import threading
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR:
    os.chdir(BASE_DIR)

from config_manager import load_config, save_config

ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class SporBotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Spor İstanbul Rezervasyon Botu")
        self.geometry("900x700")
        self.minsize(800, 600)

        self.config = load_config()
        self.bot_thread = None
        self.is_running = False

        # --- Grid Layout Setup ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==================== SIDEBAR (Settings) ====================
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="SporBot", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # --- Credentials ---
        self.tc_label = ctk.CTkLabel(self.sidebar_frame, text="TC Kimlik No:")
        self.tc_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.tc_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="TC Kimlik")
        self.tc_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.tc_entry.insert(0, self.config.get("tc_kimlik", ""))

        self.sifre_label = ctk.CTkLabel(self.sidebar_frame, text="Şifre:")
        self.sifre_label.grid(row=3, column=0, padx=20, pady=(0, 0), sticky="w")
        self.sifre_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Şifre", show="*")
        self.sifre_entry.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.sifre_entry.insert(0, self.config.get("sifre", ""))

        # --- Telegram ---
        self.tg_token_label = ctk.CTkLabel(self.sidebar_frame, text="Telegram Bot Token:")
        self.tg_token_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")
        self.tg_token_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Token")
        self.tg_token_entry.grid(row=6, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.tg_token_entry.insert(0, self.config.get("telegram_token", ""))

        self.tg_chat_label = ctk.CTkLabel(self.sidebar_frame, text="Telegram Chat ID:")
        self.tg_chat_label.grid(row=7, column=0, padx=20, pady=(0, 0), sticky="w")
        self.tg_chat_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Chat ID")
        self.tg_chat_entry.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.tg_chat_entry.insert(0, self.config.get("telegram_chat_id", ""))

        # --- Settings (Sport & Interval) ---
        self.sport_label = ctk.CTkLabel(self.sidebar_frame, text="Branş Seçimi:")
        self.sport_label.grid(row=9, column=0, padx=20, pady=(10, 0), sticky="w")
        self.sport_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["TENİS", "FİTNESS", "YÜZME"])
        self.sport_menu.grid(row=10, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.sport_menu.set(self.config.get("secili_spor", "TENİS"))

        self.alarm_label = ctk.CTkLabel(self.sidebar_frame, text="Alarm: Seanstan kaç dk önce?")
        self.alarm_label.grid(row=11, column=0, padx=20, pady=(10, 0), sticky="w")
        self.alarm_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="örn: 30")
        self.alarm_entry.grid(row=12, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.alarm_entry.insert(0, str(self.config.get("alarm_dakika_once", 30)))

        self.interval_label = ctk.CTkLabel(self.sidebar_frame, text="Tarama Aralığı (dk):")
        self.interval_label.grid(row=13, column=0, padx=20, pady=(10, 0), sticky="w")
        self.interval_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="örn: 2")
        self.interval_entry.grid(row=14, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.interval_entry.insert(0, str(self.config.get("tarama_araligi_dakika", 2)))

        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Ayarları Kaydet", command=self.save_settings)
        self.save_btn.grid(row=15, column=0, padx=20, pady=20, sticky="ew")

        # ==================== MAIN AREA ====================
        
        # --- Filters Frame ---
        self.filters_frame = ctk.CTkFrame(self)
        self.filters_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.filters_frame.grid_columnconfigure(0, weight=1)

        # Days Selection (Chips)
        self.days_label = ctk.CTkLabel(self.filters_frame, text="Tercih Edilen Günler (Boş bırakılırsa hepsi seçili sayılır)", font=ctk.CTkFont(weight="bold"))
        self.days_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.days_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.days_frame.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="w")
        
        self.days_vars = {}
        days_list = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        for i, day in enumerate(days_list):
            var = ctk.StringVar(value=day if day in self.config.get("tercih_edilen_gunler", []) else "")
            cb = ctk.CTkCheckBox(self.days_frame, text=day, variable=var, onvalue=day, offvalue="")
            cb.grid(row=0, column=i, padx=5, pady=5)
            self.days_vars[day] = var

        # Hours Selection (Chips)
        self.hours_label = ctk.CTkLabel(self.filters_frame, text="Tercih Edilen Saatler", font=ctk.CTkFont(weight="bold"))
        self.hours_label.grid(row=2, column=0, padx=10, pady=(10, 5), sticky="w")

        self.hours_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.hours_frame.grid(row=3, column=0, padx=10, pady=(0, 15), sticky="w")

        self.hours_vars = {}
        hours_list = [f"{str(h).zfill(2)}:00" for h in range(7, 24)]
        
        row_idx = 0
        col_idx = 0
        for hour in hours_list:
            var = ctk.StringVar(value=hour if hour in self.config.get("tercih_edilen_saatler", []) else "")
            cb = ctk.CTkCheckBox(self.hours_frame, text=hour, variable=var, onvalue=hour, offvalue="")
            cb.grid(row=row_idx, column=col_idx, padx=5, pady=5)
            self.hours_vars[hour] = var
            col_idx += 1
            if col_idx > 5:
                col_idx = 0
                row_idx += 1

        # Advance toggles
        self.advanced_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.advanced_frame.grid(row=4, column=0, padx=10, pady=(10, 10), sticky="w")
        
        self.test_mode_var = ctk.BooleanVar(value=self.config.get("test_modu", False))
        self.test_mode_cb = ctk.CTkSwitch(self.advanced_frame, text="Test Modu (Kaydet'e Basmaz)", variable=self.test_mode_var)
        self.test_mode_cb.grid(row=0, column=0, padx=5, pady=5)

        self.upgrade_new_var = ctk.BooleanVar(value=self.config.get("yeni_seans_yukseltme_izni", False))
        self.upgrade_new_cb = ctk.CTkSwitch(self.advanced_frame, text="72 Saatlik Yeni Seanslarda Yükseltme Riski Al (Önerilmez)", variable=self.upgrade_new_var)
        self.upgrade_new_cb.grid(row=0, column=1, padx=20, pady=5)

        # --- Actions Frame ---
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.grid(row=1, column=1, padx=20, pady=(0, 10), sticky="ew")

        self.start_btn = ctk.CTkButton(self.actions_frame, text="Botu Başlat", fg_color="green", hover_color="darkgreen", command=self.start_bot)
        self.start_btn.pack(side="left", padx=10, expand=True, fill="x")

        self.stop_btn = ctk.CTkButton(self.actions_frame, text="Botu Durdur", fg_color="red", hover_color="darkred", state="disabled", command=self.stop_bot)
        self.stop_btn.pack(side="right", padx=10, expand=True, fill="x")

        # --- Logs Frame ---
        self.log_textbox = ctk.CTkTextbox(self, state="disabled")
        self.log_textbox.grid(row=2, column=1, padx=20, pady=(0, 20), sticky="nsew")
        
        # Redirection of print statements
        sys.stdout = self.PrintLogger(self, self.log_textbox)
        sys.stderr = self.PrintLogger(self, self.log_textbox)

        self.log("Arayüz yüklendi. Ayarlar config.json'dan okundu.")

    class PrintLogger:
        def __init__(self, app, textbox):
            self.app = app
            self.textbox = textbox

        def write(self, text):
            if text:
                try:
                    self.app.after(0, self._append_text, text)
                except Exception:
                    pass

        def _append_text(self, text):
            try:
                self.textbox.configure(state="normal")
                self.textbox.insert("end", text)
                self.textbox.see("end")
                self.textbox.configure(state="disabled")
            except Exception:
                pass

        def flush(self):
            pass

    def log(self, message):
        print(f"> {message}")

    def save_settings(self):
        disk_config = load_config()
        
        disk_config["tc_kimlik"] = self.tc_entry.get()
        disk_config["sifre"] = self.sifre_entry.get()
        disk_config["telegram_token"] = self.tg_token_entry.get()
        disk_config["telegram_chat_id"] = self.tg_chat_entry.get()
        disk_config["secili_spor"] = self.sport_menu.get()
        
        disk_config["tercih_edilen_gunler"] = [day for day, var in self.days_vars.items() if var.get() != ""]
        disk_config["tercih_edilen_saatler"] = [hour for hour, var in self.hours_vars.items() if var.get() != ""]
        
        disk_config["test_modu"] = self.test_mode_var.get()
        disk_config["yeni_seans_yukseltme_izni"] = self.upgrade_new_var.get()
        
        try:
            disk_config["alarm_dakika_once"] = int(self.alarm_entry.get())
        except ValueError:
            disk_config["alarm_dakika_once"] = 30

        try:
            disk_config["tarama_araligi_dakika"] = int(self.interval_entry.get())
        except ValueError:
            disk_config["tarama_araligi_dakika"] = 2

        self.config.update(disk_config)
        save_config(self.config)
        self.log("Ayarlar kaydedildi.")

    def start_bot(self):
        self.save_settings()
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log("Bot başlatılıyor...")
        
        # Import dynamically to avoid circular issues
        from tennis_bot import run_bot_thread
        
        def thread_target():
            try:
                run_bot_thread(self.config, lambda: self.is_running)
            finally:
                self.after(0, self.on_bot_stopped)

        self.bot_thread = threading.Thread(target=thread_target, daemon=True)
        self.bot_thread.start()

    def on_bot_stopped(self):
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.log("Bot çalışma döngüsü sonlandı.")

    def stop_bot(self):
        self.is_running = False
        self.log("Bot durduruluyor, lütfen tarayıcı penceresinin kapanmasını veya mevcut döngünün bitmesini bekleyin.")

if __name__ == "__main__":
    app = SporBotGUI()
    sys.stdout = app.PrintLogger(app, app.log_textbox)
    sys.stderr = app.PrintLogger(app, app.log_textbox)
    app.mainloop()
