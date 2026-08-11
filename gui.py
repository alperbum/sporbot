import customtkinter as ctk
import threading
import sys
import os

from config_manager import load_config, save_config

ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class SporBotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Spor İstanbul Rezervasyon Botu - [Debug & Otomasyon]")
        self.geometry("980x760")
        self.minsize(850, 650)

        self.config = load_config()
        self.bot_thread = None
        self.is_running = False
        self.debug_driver_ref = [None]  # Debug oturumunda açık kalan Chrome sürücüsü

        # --- Grid Layout Setup ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==================== SIDEBAR (Settings) ====================
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(16, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="SporBot v2.0", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # --- Credentials ---
        self.tc_label = ctk.CTkLabel(self.sidebar_frame, text="TC Kimlik No:")
        self.tc_label.grid(row=1, column=0, padx=20, pady=(5, 0), sticky="w")
        self.tc_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="TC Kimlik")
        self.tc_entry.grid(row=2, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.tc_entry.insert(0, self.config.get("tc_kimlik", ""))

        self.sifre_label = ctk.CTkLabel(self.sidebar_frame, text="Şifre:")
        self.sifre_label.grid(row=3, column=0, padx=20, pady=(0, 0), sticky="w")
        self.sifre_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sifre_frame.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.sifre_frame.grid_columnconfigure(0, weight=1)
        self.sifre_entry = ctk.CTkEntry(self.sifre_frame, placeholder_text="Şifre", show="*")
        self.sifre_entry.grid(row=0, column=0, sticky="ew")
        self.sifre_entry.insert(0, self.config.get("sifre", ""))
        self.sifre_show_btn = ctk.CTkButton(self.sifre_frame, text="👁", width=32,
                                            command=self._toggle_sifre_goster)
        self.sifre_show_btn.grid(row=0, column=1, padx=(5, 0))

        # --- Telegram ---
        self.tg_token_label = ctk.CTkLabel(self.sidebar_frame, text="Telegram Bot Token:")
        self.tg_token_label.grid(row=5, column=0, padx=20, pady=(5, 0), sticky="w")
        self.tg_token_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Token")
        self.tg_token_entry.grid(row=6, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.tg_token_entry.insert(0, self.config.get("telegram_token", ""))

        self.tg_chat_label = ctk.CTkLabel(self.sidebar_frame, text="Telegram Chat ID:")
        self.tg_chat_label.grid(row=7, column=0, padx=20, pady=(0, 0), sticky="w")
        self.tg_chat_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Chat ID")
        self.tg_chat_entry.grid(row=8, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.tg_chat_entry.insert(0, self.config.get("telegram_chat_id", ""))

        # --- Settings (Sport & Interval) ---
        self.sport_label = ctk.CTkLabel(self.sidebar_frame, text="Branş Seçimi:")
        self.sport_label.grid(row=9, column=0, padx=20, pady=(5, 0), sticky="w")
        self.sport_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["TENİS", "FİTNESS", "YÜZME"],
                                           command=self._on_sport_change)
        self.sport_menu.grid(row=10, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.sport_menu.set(self.config.get("secili_spor", "TENİS"))

        self.alarm_label = ctk.CTkLabel(self.sidebar_frame, text="Alarm: Seanstan kaç dk önce?")
        self.alarm_label.grid(row=11, column=0, padx=20, pady=(5, 0), sticky="w")
        self.alarm_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="örn: 30")
        self.alarm_entry.grid(row=12, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.alarm_entry.insert(0, str(self.config.get("alarm_dakika_once", 30)))

        self.interval_label = ctk.CTkLabel(self.sidebar_frame, text="Tarama Aralığı (sn):")
        self.interval_label.grid(row=13, column=0, padx=20, pady=(5, 0), sticky="w")
        self.interval_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="örn: 20 (min 3)")
        self.interval_entry.grid(row=14, column=0, padx=20, pady=(0, 8), sticky="ew")
        self.interval_entry.insert(0, str(self.config.get("tarama_araligi_saniye", 20)))

        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Ayarları Kaydet", command=self.save_settings)
        self.save_btn.grid(row=15, column=0, padx=20, pady=15, sticky="ew")

        # ==================== MAIN AREA (TABVIEW) ====================
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=15, pady=10, sticky="nsew")
        
        self.tab_auto = self.tabview.add("🤖 Otomatik Bot")
        self.tab_debug = self.tabview.add("🛠️ Debug & Adım Testi")
        
        self._setup_auto_tab()
        self._setup_debug_tab()

        # ==================== LOG AREA (SHARED BOTTOM) ====================
        self.log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.grid(row=1, column=1, padx=15, pady=(0, 15), sticky="nsew")
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, state="disabled", height=200)
        self.log_textbox.grid(row=0, column=0, sticky="nsew")
        
        # Redirection of print statements
        sys.stdout = self.PrintLogger(self, self.log_textbox)
        sys.stderr = self.PrintLogger(self, self.log_textbox)

        self.log("Arayüz yüklendi. Ayarlar config.json'dan okundu.")
        self._on_sport_change(self.sport_menu.get())

    # --------------------------------------------------------------------------
    # TAB 1: OTOMATİK BOT PANELİ
    # --------------------------------------------------------------------------
    def _setup_auto_tab(self):
        self.tab_auto.grid_columnconfigure(0, weight=1)
        self.tab_auto.grid_rowconfigure(0, weight=1)
        
        # --- Filters Frame (Kaydırılabilir Frame) ---
        self.filters_frame = ctk.CTkScrollableFrame(self.tab_auto)
        self.filters_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.filters_frame.grid_columnconfigure(0, weight=1)

        # Days Selection (Chips)
        self.days_label = ctk.CTkLabel(self.filters_frame, text="Tercih Edilen Günler (Boş bırakılırsa hepsi seçili sayılır)", font=ctk.CTkFont(weight="bold"))
        self.days_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.days_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.days_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        self.days_vars = {}
        days_list = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        for i, day in enumerate(days_list):
            var = ctk.StringVar(value=day if day in self.config.get("tercih_edilen_gunler", []) else "")
            cb = ctk.CTkCheckBox(self.days_frame, text=day, variable=var, onvalue=day, offvalue="", width=60)
            cb.grid(row=0, column=i, padx=3, pady=5)
            self.days_vars[day] = var

        # Hours Selection (Chips)
        self.hours_label = ctk.CTkLabel(self.filters_frame, text="Tercih Edilen Saatler", font=ctk.CTkFont(weight="bold"))
        self.hours_label.grid(row=2, column=0, padx=10, pady=(10, 5), sticky="w")

        self.hours_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.hours_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="w")

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

        # Courts Selection (Tenis Kort Seviye Seçenekleri)
        self.courts_label = ctk.CTkLabel(self.filters_frame, text="Tenis Kort / Seviye Tercihleri", font=ctk.CTkFont(weight="bold"))
        self.courts_label.grid(row=4, column=0, padx=10, pady=(10, 5), sticky="w")

        self.courts_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.courts_frame.grid(row=5, column=0, padx=10, pady=(0, 10), sticky="w")

        self.c3_var = ctk.BooleanVar(value=self.config.get("kort_3_izni", True))
        self.c3_cb = ctk.CTkCheckBox(self.courts_frame, text="Kort 3 (Başlangıç - Orta)", variable=self.c3_var)
        self.c3_cb.grid(row=0, column=0, padx=5, pady=5)

        self.c4_var = ctk.BooleanVar(value=self.config.get("kort_4_izni", True))
        self.c4_cb = ctk.CTkCheckBox(self.courts_frame, text="Kort 4", variable=self.c4_var)
        self.c4_cb.grid(row=0, column=1, padx=5, pady=5)

        self.c6_var = ctk.BooleanVar(value=self.config.get("kort_6_izni", True))
        self.c6_cb = ctk.CTkCheckBox(self.courts_frame, text="Kort 6", variable=self.c6_var)
        self.c6_cb.grid(row=0, column=2, padx=5, pady=5)

        self.c1_var = ctk.BooleanVar(value=self.config.get("kort_1_izni", True))
        self.c1_cb = ctk.CTkCheckBox(self.courts_frame, text="Kort 1 (Başlangıç)", variable=self.c1_var)
        self.c1_cb.grid(row=0, column=3, padx=15, pady=5)

        self.c1_req_c3_var = ctk.BooleanVar(value=self.config.get("kort1_kort3_sarti", False))
        self.c1_req_c3_cb = ctk.CTkCheckBox(self.courts_frame, text="Kort 1'i sadece Kort 3 de aynı saatte varsa al", variable=self.c1_req_c3_var)
        self.c1_req_c3_cb.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")

        # Advance toggles
        self.advanced_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        self.advanced_frame.grid(row=6, column=0, padx=10, pady=(5, 10), sticky="w")

        self.upgrade_new_var = ctk.BooleanVar(value=self.config.get("yeni_seans_yukseltme_izni", False))
        self.upgrade_new_cb = ctk.CTkSwitch(self.advanced_frame, text="72 Saatlik Yeni Seanslarda Yükseltme Riski Al (Önerilmez)", variable=self.upgrade_new_var)
        self.upgrade_new_cb.grid(row=0, column=0, padx=5, pady=5)

        # --- Actions Frame ---
        self.actions_frame = ctk.CTkFrame(self.tab_auto, fg_color="transparent")
        self.actions_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        self.actions_frame.grid_columnconfigure(0, weight=1)
        self.actions_frame.grid_columnconfigure(1, weight=1)
        self.actions_frame.grid_columnconfigure(2, weight=1)

        self.start_btn = ctk.CTkButton(self.actions_frame, text="Botu Başlat", fg_color="green", hover_color="darkgreen", command=self.start_bot)
        self.start_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.stop_btn = ctk.CTkButton(self.actions_frame, text="Botu Durdur", fg_color="red", hover_color="darkred", state="disabled", command=self.stop_bot)
        self.stop_btn.grid(row=0, column=1, padx=5, sticky="ew")

        self.clear_log_btn = ctk.CTkButton(self.actions_frame, text="Logları Temizle", command=self.clear_logs)
        self.clear_log_btn.grid(row=0, column=2, padx=(5, 0), sticky="ew")

    # --------------------------------------------------------------------------
    # TAB 2: DEBUG & MANUEL ADIM TESTİ PANELİ
    # --------------------------------------------------------------------------
    def _setup_debug_tab(self):
        self.tab_debug.grid_columnconfigure(0, weight=1)
        self.tab_debug.grid_rowconfigure(1, weight=1)

        # --- Status Banner ---
        self.debug_banner = ctk.CTkFrame(self.tab_debug, fg_color="#1E293B", corner_radius=8)
        self.debug_banner.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.debug_banner.grid_columnconfigure(0, weight=1)

        self.debug_status_label = ctk.CTkLabel(
            self.debug_banner,
            text="🔴 DEBUG MODU PASİF (Otomatik Bot Çalışabilir)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F87171"
        )
        self.debug_status_label.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self.debug_switch_var = ctk.BooleanVar(value=False)
        self.debug_switch = ctk.CTkSwitch(
            self.debug_banner,
            text="Debug Modunu Aç (Otomatik Rotasyonu Durdur)",
            variable=self.debug_switch_var,
            command=self._on_debug_switch_toggle
        )
        self.debug_switch.grid(row=0, column=1, padx=15, pady=10, sticky="e")

        # --- Debug Actions Grid (Kaydırılabilir Frame) ---
        self.debug_grid_frame = ctk.CTkScrollableFrame(self.tab_debug)
        self.debug_grid_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.debug_grid_frame.grid_columnconfigure(0, weight=1)
        self.debug_grid_frame.grid_columnconfigure(1, weight=1)

        # Action 0: Tarayıcıyı Aç
        self.btn_dbg_open = ctk.CTkButton(
            self.debug_grid_frame, text="🌐 0. Tarayıcıyı Aç (Giriş Sayfası)",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0D9488", hover_color="#0F766E",
            command=lambda: self.run_debug_action("open_browser")
        )
        self.btn_dbg_open.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Action 1: Giriş Yap
        self.btn_dbg_login = ctk.CTkButton(
            self.debug_grid_frame, text="🔑 1. Oturum Aç (Giriş Yap)",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.run_debug_action("login")
        )
        self.btn_dbg_login.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Action 2: Takvimi Tara
        self.btn_dbg_scan = ctk.CTkButton(
            self.debug_grid_frame, text="📅 2. Takvimi Tara & Seansları Listele",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.run_debug_action("scan")
        )
        self.btn_dbg_scan.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        # Action 3: Seanslarıma Git
        self.btn_dbg_my_sessions = ctk.CTkButton(
            self.debug_grid_frame, text="📋 3. Seanslarıma Git (Profil / İptaller)",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.run_debug_action("my_sessions")
        )
        self.btn_dbg_my_sessions.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Action 4: En Uygun Seansı Seç (Kaydet'siz)
        self.btn_dbg_select = ctk.CTkButton(
            self.debug_grid_frame, text="🎯 4. En Uygun Seansı Seç & İşaretle (Kaydet'siz)",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.run_debug_action("select_only")
        )
        self.btn_dbg_select.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        # Action 5: En Uygun Seansı Seç + Kaydet
        self.btn_dbg_select_save = ctk.CTkButton(
            self.debug_grid_frame, text="💾 4b. En Uygun Seansı Seç + Kaydet'e Bas",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#D97706", hover_color="#B45309",
            command=lambda: self.run_debug_action("select_and_save")
        )
        self.btn_dbg_select_save.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # Action 6: Seans İptal Et
        self.btn_dbg_cancel = ctk.CTkButton(
            self.debug_grid_frame, text="❌ 5. Var Olan Seansı İptal Et (Test)",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#DC2626", hover_color="#991B1B",
            command=lambda: self.run_debug_action("cancel")
        )
        self.btn_dbg_cancel.grid(row=3, column=0, padx=10, pady=10, sticky="ew")

        # Action 7: Telegram Test
        self.btn_dbg_telegram = ctk.CTkButton(
            self.debug_grid_frame, text="💬 6. Telegram Bildirimini Test Et",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563EB", hover_color="#1D4ED8",
            command=lambda: self.run_debug_action("telegram")
        )
        self.btn_dbg_telegram.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        # Action 8: Chrome Kapat
        self.btn_dbg_close = ctk.CTkButton(
            self.debug_grid_frame, text="🚪 7. Chrome Tarayıcıyı Kapat",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#475569", hover_color="#334155",
            command=lambda: self.run_debug_action("close")
        )
        self.btn_dbg_close.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    def _on_debug_switch_toggle(self):
        if self.debug_switch_var.get():
            self.debug_status_label.configure(
                text="🟢 DEBUG MODU AKTİF (Otomatik Tarama Durduruldu)",
                text_color="#4ADE80"
            )
            if self.is_running:
                self.stop_bot()
                self.log("🛑 Debug Modu açıldığı için otomatik bot durduruldu.")
        else:
            self.debug_status_label.configure(
                text="🔴 DEBUG MODU PASİF (Otomatik Bot Çalışabilir)",
                text_color="#F87171"
            )

    def run_debug_action(self, action_type: str):
        """Bireysel debug adımını arka plan thread'inde güvenle çalıştırır."""
        self.save_settings()

        # Otomatik bot çalışıyorsa durdur
        if self.is_running:
            self.stop_bot()
            self.log("⚠️ Debug işlemi çalıştırılacağı için otomatik bot durduruldu.")

        # Debug modunu otomatik aktif yap
        if not self.debug_switch_var.get():
            self.debug_switch_var.set(True)
            self._on_debug_switch_toggle()

        from tennis_bot import (
            debug_step_open_browser, debug_step_login, debug_step_scan_scheduler,
            debug_step_goto_my_sessions, debug_step_select_and_fill_slot,
            debug_step_cancel_booking, debug_step_test_telegram,
            debug_step_close_driver
        )

        def runner():
            try:
                if action_type == "open_browser":
                    debug_step_open_browser(self.config, self.debug_driver_ref)
                elif action_type == "login":
                    debug_step_login(self.config, self.debug_driver_ref)
                elif action_type == "scan":
                    debug_step_scan_scheduler(self.config, self.debug_driver_ref)
                elif action_type == "my_sessions":
                    debug_step_goto_my_sessions(self.config, self.debug_driver_ref)
                elif action_type == "select_only":
                    debug_step_select_and_fill_slot(self.config, self.debug_driver_ref, click_save=False)
                elif action_type == "select_and_save":
                    debug_step_select_and_fill_slot(self.config, self.debug_driver_ref, click_save=True)
                elif action_type == "cancel":
                    debug_step_cancel_booking(self.config, self.debug_driver_ref)
                elif action_type == "telegram":
                    debug_step_test_telegram(self.config)
                elif action_type == "close":
                    debug_step_close_driver(self.debug_driver_ref)
            except Exception as e:
                self.log(f"❌ [DEBUG] İşlem hatası: {e}")

        t = threading.Thread(target=runner, daemon=True)
        t.start()

    # --------------------------------------------------------------------------
    # GENEL YARDIMCI METODLAR
    # --------------------------------------------------------------------------
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
                line_count = int(self.textbox.index("end-1c").split(".")[0])
                if line_count > 2500:
                    self.textbox.delete("1.0", f"{line_count - 2000}.0")
                self.textbox.see("end")
                self.textbox.configure(state="disabled")
            except Exception:
                pass

        def flush(self):
            pass

    def log(self, message):
        print(f"> {message}")

    def _toggle_sifre_goster(self):
        if self.sifre_entry.cget("show") == "*":
            self.sifre_entry.configure(show="")
            self.sifre_show_btn.configure(text="🙈")
        else:
            self.sifre_entry.configure(show="*")
            self.sifre_show_btn.configure(text="👁")

    def _on_sport_change(self, sport: str):
        """Kort tercihleri yalnızca Tenis için anlamlı; diğer branşlarda gizle."""
        if sport.upper() == "TENİS":
            self.courts_label.grid()
            self.courts_frame.grid()
        else:
            self.courts_label.grid_remove()
            self.courts_frame.grid_remove()

    def clear_logs(self):
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.configure(state="disabled")
            self.log("Loglar temizlendi.")
        except Exception as e:
            print(f"Log temizleme hatası: {e}")

    def save_settings(self):
        disk_config = load_config()
        
        disk_config["tc_kimlik"] = self.tc_entry.get()
        disk_config["sifre"] = self.sifre_entry.get()
        disk_config["telegram_token"] = self.tg_token_entry.get()
        disk_config["telegram_chat_id"] = self.tg_chat_entry.get()
        disk_config["secili_spor"] = self.sport_menu.get()
        
        disk_config["tercih_edilen_gunler"] = [day for day, var in self.days_vars.items() if var.get() != ""]
        disk_config["tercih_edilen_saatler"] = [hour for hour, var in self.hours_vars.items() if var.get() != ""]
        
        disk_config["yeni_seans_yukseltme_izni"] = self.upgrade_new_var.get()
        
        disk_config["kort_3_izni"] = self.c3_var.get()
        disk_config["kort_4_izni"] = self.c4_var.get()
        disk_config["kort_6_izni"] = self.c6_var.get()
        disk_config["kort_1_izni"] = self.c1_var.get()
        disk_config["kort1_kort3_sarti"] = self.c1_req_c3_var.get()
        
        try:
            disk_config["alarm_dakika_once"] = int(self.alarm_entry.get())
        except ValueError:
            disk_config["alarm_dakika_once"] = 30

        try:
            disk_config["tarama_araligi_saniye"] = max(3, int(self.interval_entry.get()))
        except ValueError:
            disk_config["tarama_araligi_saniye"] = 20

        disk_config.pop("tarama_araligi_dakika", None)
        
        self.config.update(disk_config)
        save_config(self.config)
        self._on_sport_change(self.config.get("secili_spor", "TENİS"))
        self.log("Ayarlar kaydedildi.")

    def start_bot(self):
        self.save_settings()
        
        # Debug modu açık ise uyar/kapat
        if self.debug_switch_var.get():
            self.debug_switch_var.set(False)
            self._on_debug_switch_toggle()

        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log("Bot otomatik tarama modunda başlatılıyor...")
        
        from tennis_bot import run_bot_thread
        
        def thread_target():
            try:
                run_bot_thread(self.config, lambda: self.is_running, self.debug_driver_ref)
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
    app.mainloop()
