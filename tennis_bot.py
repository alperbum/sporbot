import time
import re
import os
import requests
import threading
from datetime import datetime, timedelta

_alarm_lock = threading.Lock()

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

LOGIN_URL = "https://online.spor.istanbul/uyegiris.aspx"
SPOR_URL = "https://online.spor.istanbul/uyespor.aspx"
SEANS_SECIM_URL = "https://online.spor.istanbul/uyeseanssecim.aspx"

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

def log(msg: str):
    ts = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    log_line = f"[{ts}] {msg}"
    try:
        print(log_line)
    except Exception:
        pass
        
    try:
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")
        # Log rotation: dosya 5MB'ı aşarsa eski log'u .bak yap
        if os.path.exists(log_file):
            try:
                if os.path.getsize(log_file) > LOG_MAX_BYTES:
                    bak_file = log_file + ".bak"
                    if os.path.exists(bak_file):
                        os.remove(bak_file)
                    os.rename(log_file, bak_file)
            except Exception:
                pass
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass

def send_telegram(message: str, config: dict, max_retry: int = 2):
    token = config.get("telegram_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    for attempt in range(1, max_retry + 1):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return  # Başarılı, çık
        except requests.exceptions.ConnectionError:
            if attempt < max_retry:
                time.sleep(3)
            else:
                log("Telegram bağlantı hatası (tüm denemeler başarısız).")
        except Exception as e:
            log(f"Telegram hatası: {e}")
            return  # Bağlantı dışı hatada tekrar deneme

def telegram_webhook_kontrol(config: dict):
    """Webhook ayarlıysa kaldırır. Webhook varken getUpdates çalışmaz."""
    token = config.get("telegram_token", "").strip()
    if not token: return
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
        data = resp.json()
        webhook_url = data.get("result", {}).get("url", "")
        if webhook_url:
            log(f"⚠️ Bot üzerinde webhook tespit edildi: {webhook_url}")
            log("Webhook kaldırılıyor (getUpdates ile çakışıyor)...")
            requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=10)
            log("✅ Webhook kaldırıldı. getUpdates artık çalışacak.")
        else:
            log("Webhook kontrolü: Temiz (webhook yok).")
    except Exception as e:
        log(f"Webhook kontrol hatası: {e}")

def telegram_eski_mesajlari_temizle(config: dict):
    """Telegram update kuyruğundaki tüm eski mesajları okundu olarak işaretler."""
    token = config.get("telegram_token", "").strip()
    if not token: return
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        updates = data.get("result", [])
        if updates:
            last_id = max(u["update_id"] for u in updates)
            requests.get(url, params={"offset": last_id + 1, "limit": 1}, timeout=5)
            log(f"Telegram: {len(updates)} eski mesaj temizlendi.")
    except Exception:
        pass

def telegram_son_mesajlari_oku(config: dict, son_n_saniye: int = 300, commit: bool = True, debug: bool = False) -> list:
    token = config.get("telegram_token", "").strip()
    chat_id = str(config.get("telegram_chat_id", "")).strip()
    if not token: return []
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        # Long polling: Telegram sunucusu 5sn boyunca yeni mesaj bekler, varsa hemen döner
        resp = requests.get(url, params={"timeout": 5}, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            if debug:
                log(f"Telegram API hata döndü: {data}")
            return []

        mesajlar = []
        simdi = int(time.time())
        updates = data.get("result", [])
        
        if debug and updates:
            log(f"[DEBUG] getUpdates: {len(updates)} raw update geldi")
        
        for update in updates:
            msg = update.get("message", {})
            msg_date = msg.get("date", 0)
            msg_text = msg.get("text", "")
            msg_chat_id = str(msg.get("chat", {}).get("id", "")).strip()
            msg_from = msg.get("from", {}).get("first_name", "?")

            zaman_farki = simdi - msg_date
            
            if debug and msg_text:
                log(f"[DEBUG] Update: chat={msg_chat_id}, from={msg_from}, age={zaman_farki}sn, text={msg_text[:60]}")

            if zaman_farki < son_n_saniye:
                if not chat_id or msg_chat_id == chat_id:
                    if msg_text:
                        mesajlar.append(msg_text)
                elif debug:
                    log(f"[DEBUG] Chat ID eşleşmedi: beklenen={chat_id}, gelen={msg_chat_id}")

        # Okunan mesajları okundu olarak işaretle (offset commit)
        if commit and updates:
            last_id = max(u["update_id"] for u in updates)
            try:
                requests.get(url, params={"offset": last_id + 1, "limit": 1}, timeout=5)
            except Exception:
                pass

        return mesajlar
    except Exception as e:
        if debug:
            log(f"[DEBUG] telegram_son_mesajlari_oku exception: {e}")
        return []

def sms_kodunu_bekle(config: dict, max_bekleme_sn: int = 180):
    log(f"SMS kodu bekleniyor (max {max_bekleme_sn}sn)...")
    
    # Webhook kontrolü (webhook varken getUpdates çalışmaz!)
    telegram_webhook_kontrol(config)
    
    # NOT: Başlangıçta telegram_eski_mesajlari_temizle çağrılmıyor!
    # Çünkü seans tıklandığı an Telegram gruba düşen SMS kodu temizlenmemeli.
    
    send_telegram("<b>[SPOR BOTU] SMS Onayı Bekleniyor!</b>\nTelefona gelen kodu buraya yönlendirin.", config)
    time.sleep(1)

    baslangic = time.time()
    tur_sayaci = 0
    while (time.time() - baslangic) < max_bekleme_sn:
        tur_sayaci += 1
        gecen = int(time.time() - baslangic)
        
        # İlk 3 turda debug=True, sonra her 10 turda bir
        debug_mode = (tur_sayaci <= 3) or (tur_sayaci % 10 == 0)
        
        mesajlar = telegram_son_mesajlari_oku(config, son_n_saniye=180, commit=False, debug=debug_mode)
        
        if mesajlar:
            log(f"Telegram'dan {len(mesajlar)} mesaj okundu: {mesajlar}")
        elif tur_sayaci % 10 == 0:
            log(f"SMS bekleniyor... ({gecen}sn / {max_bekleme_sn}sn) - henüz Telegram'dan mesaj yok")
            
        for mesaj in mesajlar:
            # Bot'un kendi gönderdiği mesajları atla (Sadece [SPOR BOTU] etiketli mesajlar)
            if "[SPOR BOTU]" in mesaj:
                continue
            
            # SMS kodunu ayıkla (Öncelik: Spor İstanbul "Seans seçim onay kodunuz: XXXX" ve "#XXXX" formatları)
            match = re.search(r'Seans\s+seçim\s+onay\s+kodunuz[:\s]*(\d{4,6})', mesaj, re.IGNORECASE)
            if not match:
                match = re.search(r'kodunuz[:\s]*(\d{4,6})', mesaj, re.IGNORECASE)
            if not match:
                match = re.search(r'#(\d{4,6})', mesaj)
            if not match:
                match = re.search(r'(?:kod[u]?|onay|doğrulama|code)[:\s]*(\d{4,6})', mesaj, re.IGNORECASE)
            if not match:
                match = re.search(r'\b(\d{4,6})\b', mesaj)
            if not match:
                match = re.search(r'(\d{4,6})', mesaj)
            if match:
                kod = match.group(1)
                log(f"✅ SMS kodu bulundu: {kod}")
                # Kodu bulduktan sonra eski mesajları temizleyelim ki sonraki seanslarda tekrar okunmasın
                telegram_eski_mesajlari_temizle(config)
                return kod
            else:
                log(f"Mesaj geldi ama SMS kodu çıkarılamadı: '{mesaj[:80]}'")
        time.sleep(3)

    log("❌ SMS kodu zaman aşımına uğradı!")
    send_telegram("SMS kodu alınamadı! Zaman aşımı.", config)
    return None

def alarm_zamanlayici_thread(config: dict, is_running_func):
    """Arka planda çalışıp vakti gelen alarmları Telegram'a basar."""
    while is_running_func():
        try:
            with _alarm_lock:
                alarmlar = config.get("aktif_alarmlar", [])
            simdi = datetime.now()
            kalan = []
            any_triggered = False
            for a in alarmlar:
                try:
                    tetik = datetime.fromisoformat(a["tetikleme_zamani"])
                except Exception:
                    continue
                if tetik <= simdi:
                    send_telegram(a["mesaj"], config)
                    log(f"⏰ Alarm tetiklendi: {a['mesaj']}")
                    any_triggered = True
                else:
                    kalan.append(a)
            if any_triggered or len(kalan) != len(alarmlar):
                with _alarm_lock:
                    config["aktif_alarmlar"] = kalan
                    from config_manager import save_config
                    save_config(config)
        except Exception as e:
            log(f"Alarm zamanlayıcı hatası: {e}")
        time.sleep(20)

def alarm_sil(config: dict, date_str: str):
    """Belirtilen tarihe ait var olan alarmları temizler."""
    try:
        with _alarm_lock:
            alarmlar = config.get("aktif_alarmlar", [])
            yeni_alarmlar = [a for a in alarmlar if a.get("tarih") != date_str and date_str not in a.get("mesaj", "")]
            if len(yeni_alarmlar) != len(alarmlar):
                config["aktif_alarmlar"] = yeni_alarmlar
                from config_manager import save_config
                save_config(config)
                log(f"⏰ {date_str} tarihli eski alarmlar temizlendi.")
    except Exception as e:
        log(f"Alarm silme hatası: {e}")

def alarm_olustur(config: dict, date_str: str, time_str: str, court: str, dakika_once=None):
    """Rezervasyon saatine 3 saatten az kaldıysa X dakika önceye alarm kurar."""
    if dakika_once is None:
        dakika_once = config.get("alarm_dakika_once", 30)
    try:
        # date_str: "12.08.2025", time_str: "19:00 - 20:00"
        d_parts = date_str.split(".")
        t_parts = time_str.split(" - ")[0].split(":")
        seans_dt = datetime(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]),
                            int(t_parts[0]), int(t_parts[1]))
        
        simdi = datetime.now()
        kalan_saniye = (seans_dt - simdi).total_seconds()
        
        # 1. Bu tarih ve saat için zaten alarm kurulmuş mu?
        with _alarm_lock:
            mevcut_alarmlar = config.get("aktif_alarmlar", [])
            for a in mevcut_alarmlar:
                if a.get("tarih") == date_str and time_str in a.get("mesaj", ""):
                    return

        # 2. Seansa 3 saatten (10800 saniye) fazla varsa alarmı henüz kurma
        if kalan_saniye > 3 * 3600:
            log(f"⏰ Seansa {int(kalan_saniye // 3600)} saat var (>3 saat). Alarm henüz kurulmadı, seansa 3 saat kala kurulacak.")
            return

        tetik_dt = seans_dt - timedelta(minutes=dakika_once)
        if tetik_dt <= simdi:
            log(f"Alarm zamanı zaten geçmiş ({tetik_dt.strftime('%H:%M')}), kurulmadı.")
            return

        mesaj = (f"⏰ <b>SEANS YAKLAŞIYOR</b>\n"
                 f"{date_str} {time_str}\nKort: {court}\n"
                 f"{dakika_once} dk içinde başlıyor.")

        with _alarm_lock:
            config.setdefault("aktif_alarmlar", []).append({
                "tarih": date_str,
                "tetikleme_zamani": tetik_dt.isoformat(),
                "mesaj": mesaj
            })
            from config_manager import save_config
            save_config(config)
        log(f"⏰ Alarm kuruldu: {tetik_dt.strftime('%d.%m %H:%M')} -> {date_str} {time_str}")
    except Exception as e:
        log(f"Alarm kurulum hatası: {e}")

def ensure_not_minimized(driver):
    """Minimize edilmiş Chrome'u ekran dışına taşıyarak 'açık' duruma getirir.
    Böylece DOM render devam eder ve find_elements çalışır."""
    try:
        is_minimized = driver.execute_script(
            "return document.hidden || document.visibilityState === 'hidden';"
        )
        if is_minimized:
            log("⚠️ Chrome minimize/gizli durumda tespit edildi, düzeltiliyor...")
            try:
                # Önce maximize ile minimize durumundan çıkar
                driver.maximize_window()
                time.sleep(0.3)
                # Sonra ekran dışına taşı (kullanıcı görmez ama Chrome 'açık' sanır)
                driver.set_window_position(-2000, 0)
                time.sleep(0.3)
                log("✅ Chrome penceresi ekran dışına taşındı (arka planda aktif).")
            except Exception:
                # Alternatif: sadece maximize dene
                try:
                    driver.maximize_window()
                except Exception:
                    pass
    except Exception:
        try:
            driver.maximize_window()
            time.sleep(0.3)
            driver.set_window_position(-2000, 0)
        except Exception:
            pass

def init_chrome_driver() -> webdriver.Chrome:
    log("Chrome tarayıcı başlatılıyor...")
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    
    # Alta atıldığında (minimized) Chrome'un uykuya geçmesini/throttle olmasını engellemek için:
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=CalculateNativeWinOcclusion")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        log(f"ChromeDriverManager hatası ({e}), varsayılan Selenium sürücüsü deneniyor...")
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e2:
            log(f"Chrome başlatılamadı: {e2}")
            raise e2
    return driver

def login(driver: webdriver.Chrome, config: dict) -> bool:
    log("Giriş sayfasına gidiliyor...")
    driver.get(LOGIN_URL)
    try:
        wait = WebDriverWait(driver, 15)
        tc_input = wait.until(EC.presence_of_element_located((By.ID, "txtTCPasaport")))
        tc_input.clear()
        tc_input.send_keys(config.get("tc_kimlik", ""))

        sifre_input = driver.find_element(By.ID, "txtSifre")
        sifre_input.clear()
        sifre_input.send_keys(config.get("sifre", ""))

        btn = driver.find_element(By.ID, "btnGirisYap")
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(3)
        if "uyegiris" in driver.current_url.lower():
            log("Giriş yapılamadı. TC veya şifre hatalı olabilir.")
            return False
        log("Giriş başarılı.")
        return True
    except Exception as e:
        log(f"Giriş hatası: {e}")
        return False

def has_active_booking(driver: webdriver.Chrome, config: dict) -> list:
    """Gets existing active bookings from the Seanslarım page."""
    log("Aktif rezervasyonlar kontrol ediliyor...")
    driver.get(SPOR_URL)
    time.sleep(3)
    
    bookings = []
    sport = config.get("secili_spor", "TENİS").upper()
    
    try:
        # İlgili spor paketinin detay butonunu bul (mor buton)
        # Birden fazla eski paket olabileceği için tesise ve en güncel tarihe göre filtrele
        details_btns = driver.find_elements(By.CSS_SELECTOR, "a[id*='lbtnDetayGoster']")
        
        best_btn = None
        best_date = datetime(1900, 1, 1)
        sport = config.get("secili_spor", "TENİS").upper()
        facility = config.get("secili_tesis", "").upper()
        
        for btn in details_btns:
            try:
                row = btn.find_element(By.XPATH, "./ancestor::tr")
                text = row.text.upper()
                if sport in text and (not facility or facility in text):
                    # Satırdaki en büyük (en ileri) tarihi bulalım
                    dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', text)
                    max_d = datetime(1900, 1, 1)
                    for d_str in dates:
                        try:
                            d = datetime.strptime(d_str, "%d.%m.%Y")
                            if d > max_d:
                                max_d = d
                        except:
                            pass
                    
                    if max_d > best_date:
                        best_date = max_d
                        best_btn = btn
            except:
                continue
                
        target_btn = best_btn
                
        if target_btn:
            try:
                # Butonun içindeki ikona bak
                icon = target_btn.find_element(By.TAG_NAME, "i")
                icon_class = icon.get_attribute("class")
                if "fa-plus" in icon_class:
                    log("Mor detay göster butonu tıklanarak alt tablo açılıyor...")
                    driver.execute_script("arguments[0].click();", target_btn)
                    time.sleep(3)
                elif "fa-minus" in icon_class:
                    log("İlgili spor paketinin detay tablosu zaten açık.")
            except Exception as e:
                log(f"Buton ikonu kontrol edilemedi, yine de tıklanıyor... ({e})")
                driver.execute_script("arguments[0].click();", target_btn)
                time.sleep(3)
        
        # dtUyeSpor içeren tabloların satırlarını al (bulunamazsa tüm satırlara bak)
        rows = driver.find_elements(By.XPATH, "//table[contains(@id, 'dtUyeSpor')]//tr")
        if not rows:
            rows = driver.find_elements(By.TAG_NAME, "tr")
            
        for row in rows:
            text = row.text
            # Başında sıra no ve tarih var mı diye bak. Örn: "15 - 03.08.2026" veya doğrudan "03.08.2026"
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
            if date_match:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    date = date_match.group(0) # Sadece tarih kısmını al
                    time_str = cells[1].text.strip()
                    facility = cells[2].text.strip()
                    court = cells[3].text.strip()
                    status = cells[5].text.strip()
                    
                    action_text = cells[6].text.strip() if len(cells) >= 7 else ""
                    cancel_btn_elem = None
                    if len(cells) >= 7:
                        try:
                            cancel_btn_elem = cells[6].find_element(By.TAG_NAME, "a")
                        except:
                            try:
                                cancel_btn_elem = cells[6].find_element(By.XPATH, ".//*[contains(text(), 'İptal')]")
                            except:
                                pass
                                
                    bookings.append({
                        "date": date,
                        "time": time_str,
                        "facility": facility,
                        "court": court,
                        "status": status,
                        "action_text": action_text,
                        "cancel_btn": cancel_btn_elem,
                        "element": row
                    })
                    
                    if "Satış Yapıldı" in status:
                        alarm_olustur(config, date, time_str, court)
    except Exception as e:
        log(f"Rezervasyon kontrol hatası: {e}")
    
    log(f"Profil geçmişindeki kayıtlı satır sayısı: {len(bookings)}")
    return bookings

def goto_scheduler(driver: webdriver.Chrome, config: dict = None) -> bool:
    try:
        # Eğer zaten takvim sayfasındaysak (uyeseanssecim) doğrudan başarılı dön
        if "uyeseanssecim" in driver.current_url.lower():
            return True
            
        # Eğer SPOR_URL (Seanslarım) sayfasında değilsek oraya gidelim
        if SPOR_URL not in driver.current_url:
            driver.get(SPOR_URL)
            time.sleep(3)
            
        sport = config.get("secili_spor", "TENİS").upper() if config else "TENİS"
        facility = config.get("secili_tesis", "").upper() if config else ""
        booking_link = None
        
        # Yöntem 1: Seçili spora ve tesise ait satırdaki "Seans Seç" butonunu bul
        seans_btns = driver.find_elements(By.CSS_SELECTOR, "a[id*='lbtnSeansSecim']")
        for btn in seans_btns:
            try:
                row = btn.find_element(By.XPATH, "./ancestor::tr")
                text = row.text.upper()
                if sport in text and (not facility or facility in text):
                    booking_link = btn
                    break
            except:
                continue

        # Yöntem 2: Eğer bulunamadıysa (veya seans_btns listesi boş değilse) ilkini al
        if not booking_link and seans_btns:
            booking_link = seans_btns[0]

        # Yöntem 3: Sadece CSS class ile bul (Yeşil btn-success)
        if not booking_link:
            try:
                booking_link = driver.find_element(By.CSS_SELECTOR, "a.btn.btn-success")
            except NoSuchElementException:
                pass

        if booking_link:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", booking_link)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", booking_link)
            time.sleep(3)
            return True

        log("❌ Rezervasyon Yap/Seans Seç butonu bulunamadı!")
        return False
    except Exception as e:
        log(f"Scheduler navigasyon hatası: {e}")
        return False

def is_newly_opened(date_str: str, time_str: str, config: dict = None) -> bool:
    """Seans yeni mi açıldı kontrolü. Pencere config'den okunur (varsayılan 69-73 saat)."""
    try:
        date_parts = date_str.split('.')
        time_parts = time_str.split(' - ')[0].split(':')
        slot_dt = datetime(
            int(date_parts[2]), int(date_parts[1]), int(date_parts[0]),
            int(time_parts[0]), int(time_parts[1])
        )
        now = datetime.now()
        diff_hours = (slot_dt - now).total_seconds() / 3600
        # Config'den pencere değerleri (varsayılan: 72 saat ± 3 saat tolerans)
        min_hours = 69
        max_hours = 73
        if config:
            try:
                min_hours = int(config.get("yeni_seans_min_saat", 69))
                max_hours = int(config.get("yeni_seans_max_saat", 73))
            except (ValueError, TypeError):
                pass
        return min_hours <= diff_hours <= max_hours
    except Exception as e:
        log(f"is_newly_opened parse hatası ({date_str} {time_str}): {e}")
        return False

def get_start_hour(time_str: str) -> int:
    """Seans başlangıç saatinin saat değerini döndürür (00:00 -> 0).
    Parse edilemezse -1 döner (sıralamada en sona atılır)."""
    if not time_str:
        return -1
    match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if not match:
        return -1
    h = int(match.group(1))
    if 0 <= h <= 23:
        return h
    return -1

def filter_slots(all_slots: list, config: dict) -> list:
    pref_days = config.get("tercih_edilen_gunler", [])
    pref_hours = config.get("tercih_edilen_saatler", [])
    sport = config.get("secili_spor", "TENİS").upper()
    
    filtered = []
    DAY_MAP = {
        "pazartesi": "Pzt", "pzt": "Pzt",
        "salı": "Sal", "sali": "Sal", "sal": "Sal", 
        "çarşamba": "Çar", "carsamba": "Çar", "çar": "Çar", 
        "perşembe": "Per", "persmbe": "Per", "per": "Per", 
        "cuma": "Cum", "cum": "Cum", 
        "cumartesi": "Cmt", "cmt": "Cmt", 
        "pazar": "Paz", "pzr": "Paz", "paz": "Paz"
    }
    
    for slot in all_slots:
        # Day filter
        if pref_days:
            norm = DAY_MAP.get(slot['day_name'].lower().strip(), slot['day_name'][:3])
            if norm not in pref_days: continue
            
        # Hour filter
        if pref_hours:
            slot_hour = slot['time'].split(' - ')[0].strip()
            if slot_hour not in pref_hours: continue
            
        filtered.append(slot)
        
    if sport != "TENİS":
        return filtered
        
    # Tennis court priority & level logic
    slots_by_date_time = {}
    for s in filtered:
        key = (s['date'], s['time'])
        slots_by_date_time.setdefault(key, []).append(s)
        
    allow_c3 = config.get("kort_3_izni", True)
    allow_c4 = config.get("kort_4_izni", True)
    allow_c6 = config.get("kort_6_izni", True)
    allow_c1 = config.get("kort_1_izni", True)
    req_c3_for_c1 = config.get("kort1_kort3_sarti", False)
    
    final_eligible = []
    for (date_str, time_str), dt_slots in slots_by_date_time.items():
        has_court_3 = any(("KORT 3" in s['court'].upper() or "KORT 4" in s['court'].upper() or "KORT 6" in s['court'].upper()) for s in dt_slots)
        
        for s in dt_slots:
            court_name = (s['court'] or "").upper()
            is_c3 = "KORT 3" in court_name
            is_c4 = "KORT 4" in court_name
            is_c6 = "KORT 6" in court_name
            is_c1 = "KORT 1" in court_name
            
            if is_c3:
                if allow_c3:
                    final_eligible.append(s)
            elif is_c4:
                if allow_c4:
                    final_eligible.append(s)
            elif is_c6:
                if allow_c6:
                    final_eligible.append(s)
            elif is_c1:
                if allow_c1:
                    if req_c3_for_c1 and not has_court_3:
                        # Kort 3 şartı aktif ve o gün/saatte Kort 3/4/6 yoksa alma
                        continue
                    final_eligible.append(s)
            else:
                # Diğer kortlar (Kort 2 vb.)
                final_eligible.append(s)
                
    return final_eligible

def select_slot_checkbox(driver, well_element):
    """
    Finds and clicks the session checkbox / input / label inside a .well card.
    Stops after the first successful click to avoid accidental toggling.
    """
    # 1. Try checkbox/radio inputs
    try:
        inputs = well_element.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], input[type='radio']")
        for inp in inputs:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                if not inp.is_selected():
                    driver.execute_script("arguments[0].click();", inp)
                return True
            except Exception:
                pass
    except Exception:
        pass

    # 2. Try label elements (excluding header labels)
    try:
        labels = well_element.find_elements(By.TAG_NAME, "label")
        for lbl in labels:
            try:
                title_attr = lbl.get_attribute("title") or ""
                if "Salon Adı" not in title_attr:
                    driver.execute_script("arguments[0].click();", lbl)
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # 3. Fallback: click well element itself
    try:
        driver.execute_script("arguments[0].click();", well_element)
        return True
    except Exception:
        pass
    
    log("Seans kutucuğu tıklanamadı!")
    return False

def run_bot_thread(config: dict, is_running_func, driver_ref: list = None):
    driver = None
    try:
        if driver_ref is not None:
            driver = get_or_init_driver(driver_ref)
        else:
            driver = init_chrome_driver()
            
        curr_url = ""
        try:
            curr_url = driver.current_url.lower()
        except Exception:
            pass

        if "uyegiris" in curr_url or not curr_url or "online.spor.istanbul" not in curr_url:
            login_ok = False
            for attempt in range(3):
                log(f"Giriş deneniyor... (Deneme {attempt + 1}/3)")
                if login(driver, config):
                    login_ok = True
                    break
                log(f"Giriş başarısız. {'Tekrar deneniyor...' if attempt < 2 else ''}")
                time.sleep(3)
            if not login_ok:
                log("Giriş yapılamadığı için bot durduruldu.")
                return

        # Start alarm background thread
        alarm_thread = threading.Thread(
            target=alarm_zamanlayici_thread,
            args=(config, is_running_func),
            daemon=True
        )
        alarm_thread.start()

        def get_scan_interval():
            try:
                return max(3, int(config.get("tarama_araligi_saniye", 20)))
            except (ValueError, TypeError):
                return 20

        # Initially navigate to scheduler
        if not goto_scheduler(driver, config):
            log("Scheduler başlangıçta açılamadı, doğrudan SPOR_URL'ye gidiliyor...")
            driver.get(SPOR_URL)

        slot_cooldowns = {}  # key: "date_time_court", value: expiry_timestamp
        consecutive_errors = 0  # Ardışık döngü hatası sayacı

        while is_running_func():
            interval = get_scan_interval()
            try:
                curr_url = driver.current_url.lower()
                has_login_input = False
                try:
                    has_login_input = len(driver.find_elements(By.ID, "txtTCPasaport")) > 0
                except Exception:
                    pass

                # 1. Oturum kapandı mı / Giriş sayfasında mıyız kontrolü
                if "uyegiris" in curr_url or has_login_input:
                    log("🔑 Oturum kapanmış veya giriş sayfasındayız! Otomatik olarak yeniden giriş yapılıyor...")
                    if not login(driver, config):
                        log("⚠️ Otomatik giriş yapılamadı. TC/Şifre kontrol edin. 30 saniye sonra tekrar denenecek...")
                        time.sleep(30)
                        continue
                    log("✅ Oturum başarıyla tazelendi. Takvime gidiliyor...")
                    goto_scheduler(driver, config)
                    curr_url = driver.current_url.lower()

                # 2. Ensure we are on the scheduler page
                if "uyeseanssecim" not in curr_url:
                    if not goto_scheduler(driver, config):
                        log("Scheduler açılamadı, sayfa kontrol ediliyor...")
                        driver.get(SPOR_URL)
                        time.sleep(3)
                        if "uyegiris" in driver.current_url.lower():
                            log("Oturum kapanmış (Giriş sayfasına atıldı). Sonraki turda giriş yapılacak...")
                            continue
                        time.sleep(5)
                        continue
                    
                # Parse scheduler
                log("Tablo taranıyor...")
                
                all_available_slots = []
                booked_dates = {}  # Takvimden alınan mavi seans bilgileri: {tarih: {time, court}}
                total_sessions_count = 0
                green_count = 0  # Yeşil: Boş / Alınabilir Seans
                blue_count = 0   # Mavi: Seçilmiş / Mevcut Seans
                gray_count = 0   # Gri: Kapalı / Boşluk Beklenen Seans
                red_count = 0    # Kırmızı: Dolu / Seçilemeyen Seans
                
                # Sayfadaki seans elementlerinin yüklenmesini bekle
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".well"))
                    )
                except TimeoutException:
                    pass  # Timeout olursa yine de dene, belki hiç .well yok
                except Exception:
                    pass
                
                # Target columns containing a panel header and panel-title (scheduler days)
                columns = driver.find_elements(By.XPATH, "//div[contains(@class, 'col-') and .//h3[contains(@class, 'panel-title')]]")
                
                # Eğer 0 sütun bulunduysa, sayfa tam yüklenmemiş olabilir - sayfaya tekrar git ve bekle
                if len(columns) == 0:
                    log("⚠️ Tablo sütunları bulunamadı, sayfa yeniden yükleniyor...")
                    try:
                        driver.get(SEANS_SECIM_URL)
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".well"))
                        )
                    except Exception:
                        time.sleep(5)
                    columns = driver.find_elements(By.XPATH, "//div[contains(@class, 'col-') and .//h3[contains(@class, 'panel-title')]]")
                    if len(columns) == 0:
                        log("⚠️ Yeniden yükleme sonrası da tablo bulunamadı. Sonraki taramada tekrar denenecek.")
                        time.sleep(interval)
                        continue
                for col in columns:
                    try:
                        header = col.find_element(By.CSS_SELECTOR, ".panel-heading, h3.panel-title")
                        header_text = header.text
                        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', header_text)
                        if not date_match: continue
                        date_str = date_match.group(0)
                        day_name = header_text.split('\n')[0].strip()
                        
                        wells = col.find_elements(By.CSS_SELECTOR, ".well")
                        for well in wells:
                            total_sessions_count += 1
                            # Evaluate computed border color in addition to inline style for robustness
                            border_color = driver.execute_script(
                                "return window.getComputedStyle(arguments[0]).borderColor;", well
                            ) or ""
                            style = well.get_attribute("style") or ""
                            b_str = f"{border_color} {style}".lower()
                            
                            is_green = "8, 245, 26" in b_str or "08f51a" in b_str
                            is_blue = "62, 209, 255" in b_str or "3ed1ff" in b_str or "00d0ff" in b_str or "232, 253, 47" in b_str or "e8fd2f" in b_str
                            is_gray = "128, 128, 128" in b_str or "808080" in b_str
                            
                            if is_green:
                                green_count += 1
                                court = ""
                                try:
                                    court_lbl = well.find_element(By.CSS_SELECTOR, "label[title='Salon Adı']")
                                    court = court_lbl.text.strip() if court_lbl else ""
                                except Exception:
                                    pass
                                if not court:
                                    try:
                                        court = well.text.strip()
                                    except Exception:
                                        court = ""
                                
                                time_spn = well.find_element(By.CSS_SELECTOR, "span[id*='lblSeansSaat']")
                                time_str = time_spn.text.strip() if time_spn else ""
                                
                                all_available_slots.append({
                                    "element": well,
                                    "date": date_str,
                                    "day_name": day_name,
                                    "time": time_str,
                                    "court": court
                                })
                            elif is_blue:
                                blue_count += 1
                                # Mavi seansın tarih/saat/kort bilgisini kaydet (takvimden çakışma kontrolü için)
                                try:
                                    blue_court_lbl = well.find_element(By.CSS_SELECTOR, "label[title='Salon Adı']")
                                    blue_court = blue_court_lbl.text.strip() if blue_court_lbl else ""
                                    blue_time_spn = well.find_element(By.CSS_SELECTOR, "span[id*='lblSeansSaat']")
                                    blue_time = blue_time_spn.text.strip() if blue_time_spn else ""
                                    booked_dates[date_str] = {"time": blue_time, "court": blue_court}
                                except Exception:
                                    # Saat/kort okunamazsa bile tarihi kaydet
                                    booked_dates[date_str] = {"time": "", "court": ""}
                            elif is_gray:
                                gray_count += 1
                            else:
                                red_count += 1
                    except Exception as e:
                        log(f"Sütun parse hatası: {e}")
                
                log_summary = f"Tabloda toplam {total_sessions_count} seans kutusu bulundu (Yeşil/Boş: {green_count}"
                if blue_count > 0:
                    log_summary += f" | Mavi/Seçilmiş: {blue_count}"
                if gray_count > 0:
                    log_summary += f" | Gri/Kapalı: {gray_count}"
                if red_count > 0:
                    log_summary += f" | Kırmızı/Dolu: {red_count}"
                log_summary += ")"
                log(log_summary)
                
                if booked_dates:
                    booked_info = ", ".join([f"{d}: {info['time']}" for d, info in booked_dates.items()])
                    log(f"Takvimde mevcut seanslar (mavi): {booked_info}")
                
                eligible_slots = filter_slots(all_available_slots, config)
                log(f"Kriterlerinize uyan boş seans sayısı: {len(eligible_slots)}")

                # Expired cooldown temizleme ve aktif cooldown kontrolü
                simdi_ts = time.time()
                slot_cooldowns = {k: v for k, v in slot_cooldowns.items() if v > simdi_ts}
                
                active_eligible_slots = []
                for s in eligible_slots:
                    s_key = f"{s['date']}_{s['time']}_{s['court']}"
                    if s_key in slot_cooldowns:
                        kalan_sn = int(slot_cooldowns[s_key] - simdi_ts)
                        log(f"⏳ Seans {s['date']} | {s['time']} | {s['court']} bekleme (cooldown) modunda ({kalan_sn}sn kaldı). Atlanıyor...")
                        continue
                    active_eligible_slots.append(s)
                
                if not active_eligible_slots:
                    if eligible_slots:
                        log(f"Kriterlere uygun boş seans var ancak hepsi bekleme (cooldown) modunda. {interval} saniye bekleniyor...")
                    else:
                        log(f"Kriterlere uygun seans yok. {interval} saniye bekleniyor...")
                    time.sleep(interval)
                    try:
                        driver.get(SEANS_SECIM_URL)
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".well"))
                        )
                    except Exception:
                        time.sleep(5)
                    continue

                # --- SADECE UYGUN SEANS BULUNDUĞUNDA BURAYA GEÇİLİR ---
                if config.get("test_modu", False):
                    active_eligible_slots.sort(key=lambda s: get_start_hour(s['time']))
                else:
                    if config.get("kort1_kort3_sarti", False):
                        active_eligible_slots.sort(key=lambda s: (get_start_hour(s['time']), 1 if ("KORT 3" in s['court'].upper() or "KORT 4" in s['court'].upper() or "KORT 6" in s['court'].upper()) else 0), reverse=True)
                    else:
                        active_eligible_slots.sort(key=lambda s: get_start_hour(s['time']), reverse=True)
                    
                best_slot = active_eligible_slots[0]
                log(f"🎯 Uygun seans tespit edildi: {best_slot['date']} | {best_slot['time']} | {best_slot['court']}")

                # Takvimden mavi seans kontrolü - seanslarım sayfasına gitmeye gerek yok!
                same_day_booked = booked_dates.get(best_slot['date'])
                
                action_taken = False
                
                if same_day_booked:
                    # Bu gün için zaten mavi (alınmış) seans var
                    exist_time = same_day_booked.get("time", "")
                    exist_court = same_day_booked.get("court", "")
                    exist_hour = get_start_hour(exist_time) if exist_time else 0
                    new_hour = get_start_hour(best_slot['time'])
                    sport = config.get("secili_spor", "TENİS").upper()
                    
                    is_better = False
                    if exist_time and new_hour > exist_hour:
                        is_better = True
                    elif exist_time and new_hour == exist_hour and sport == "TENİS":
                        if config.get("kort1_kort3_sarti", False):
                            new_c3 = "KORT 3" in best_slot['court'].upper() or "KORT 4" in best_slot['court'].upper() or "KORT 6" in best_slot['court'].upper()
                            old_c3 = "KORT 3" in exist_court.upper() or "KORT 4" in exist_court.upper() or "KORT 6" in exist_court.upper()
                            if new_c3 and not old_c3:
                                is_better = True
                            
                    if is_better:
                        # 72-hour protection
                        if is_newly_opened(best_slot['date'], best_slot['time'], config) and not config.get("yeni_seans_yukseltme_izni", False):
                            log(f"Yeni açılan seansla (72s) yükseltme pas geçildi. ({best_slot['time']})")
                        else:
                            if config.get("test_modu", False):
                                log(f"Test Modu: Mevcut seans ({exist_time}) iptal edilmedi. Yeni seans ({best_slot['time']}) alınmayacak.")
                            else:
                                log(f"Daha iyi seans bulundu! {exist_time} iptal ediliyor, {best_slot['time']} alınacak.")
                                # İptal için seanslarım sayfasına SADECE ŞİMDİ gidiyoruz
                                try:
                                    bookings = has_active_booking(driver, config)
                                    same_day_booking = next((b for b in bookings if b['date'] == best_slot['date'] and ("Satış Yapıldı" in b['status'] or "İptal Et" in b.get("action_text", ""))), None)
                                    if same_day_booking:
                                        cancel_btn = same_day_booking.get("cancel_btn")
                                        if not cancel_btn:
                                            cancel_btn = same_day_booking['element'].find_element(By.XPATH, ".//*[contains(text(), 'İptal Et')]")
                                            
                                        driver.execute_script("window.confirm = function() { return true; };")
                                        driver.execute_script("arguments[0].click();", cancel_btn)
                                        time.sleep(3)
                                        log("İptal edildi. Yeni seans için takvime dönülüyor.")
                                        alarm_sil(config, best_slot['date'])
                                        send_telegram(f"<b>[SPOR BOTU] Mevcut Seans İptal Edildi</b>\nYeni Seans İçin Yol Açıldı: {best_slot['date']} {best_slot['time']}", config)
                                        action_taken = True
                                    else:
                                        log("Seanslarım sayfasında iptal edilecek seans bulunamadı, devam ediliyor.")
                                except Exception as e:
                                    log(f"İptal işlemi hatası: {e}")

                                if action_taken:
                                    goto_scheduler(driver, config)
                    else:
                        log(f"Bu gün ({best_slot['date']}) için zaten seans alınmış ({exist_time}). Yükseltme gerekmiyor, atlanıyor.")
                
                if not same_day_booked or action_taken:
                    # Direct Booking or Booking after cancellation
                    if "uyeseanssecim" not in driver.current_url.lower():
                        goto_scheduler(driver, config)

                    log(f"Kort rezerve ediliyor: {best_slot['date']} | {best_slot['time']} | {best_slot['court']}")
                    send_telegram(f"<b>[SPOR BOTU] Seans Alınıyor</b>\n{best_slot['date']} | {best_slot['time']} | {best_slot['court']}", config)
                    
                    # Re-find best_slot well on page
                    target_well = None
                    try:
                        wells = driver.find_elements(By.CSS_SELECTOR, ".well")
                        for w in wells:
                            w_text = w.text
                            if best_slot['court'] in w_text and best_slot['time'] in w_text:
                                target_well = w
                                break
                    except Exception:
                        pass
                        
                    if not target_well:
                        log("Seans kutucuğu sayfada yeniden bulunamadı! Bu tur atlanıyor.")
                        continue

                    log(f"Seans kutucuğu işaretleniyor ({best_slot['time']} - {best_slot['court']})...")
                    select_slot_checkbox(driver, target_well)
                    time.sleep(1.5)
                    
                    if config.get("test_modu", False):
                        log("Test Modu: Kaydet butonuna basılmadı. Çıkılıyor.")
                        time.sleep(5)
                    else:
                        # Terms Checkbox ("Rezervasyon işlemimi onaylıyorum")
                        try:
                            try:
                                terms_cb = driver.find_element(By.ID, "pageContent_cboxOnay")
                            except NoSuchElementException:
                                terms_cb = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                            
                            if not terms_cb.is_selected():
                                driver.execute_script("arguments[0].click();", terms_cb)
                            
                            # Save btn
                            best_slot_key = f"{best_slot['date']}_{best_slot['time']}_{best_slot['court']}"
                            save_btn = driver.find_element(By.ID, "lbtnKaydet")
                            driver.execute_script("arguments[0].click();", save_btn)
                            log("Kaydet'e basıldı. SMS doğrulama kutusu ve sayfa yüklenmesi bekleniyor...")
                            
                            # ASP.NET postback sonrası sayfanın yüklenmesini bekle
                            time.sleep(3)
                            try:
                                WebDriverWait(driver, 15).until(
                                    lambda d: d.execute_script("return document.readyState") == "complete"
                                )
                            except Exception:
                                pass
                            
                            # SMS input'unu 15 saniyeye kadar döngü ile sabırla ara (AJAX/Postback gecikmeleri için)
                            sms_input = None
                            selectors = [
                                "//input[contains(@class,'swal2-input')]",
                                "//input[contains(@class,'swal2')]",
                                "//input[contains(@id,'txtDogrulamaKodu')]",
                                "//input[contains(@id,'DogrulamaKodu')]",
                                "//input[contains(@id,'txtDogrulama')]",
                                "//input[contains(@id,'txtKod')]",
                                "//input[contains(@id,'txtSms')]",
                                "//input[contains(@id,'Sms')]",
                                "//input[contains(@id,'SMS')]",
                                "//input[contains(@id,'sms')]",
                                "//input[contains(@id,'Dogrulama')]",
                                "//input[contains(@name,'Dogrulama')]",
                                "//input[contains(@name,'Sms')]",
                                "//input[contains(@name,'SMS')]",
                                "//input[contains(@placeholder,'Do')]",
                                "//input[contains(@placeholder,'Kod')]",
                                "//input[contains(@placeholder,'kod')]",
                            ]

                            start_wait_sms = time.time()
                            while (time.time() - start_wait_sms) < 15:
                                # Yöntem 1: Selector'lar
                                for sel in selectors:
                                    try:
                                        el = driver.find_element(By.XPATH, sel)
                                        if el.is_displayed():
                                            sms_input = el
                                            log(f"SMS kutusu bulundu: selector={sel}, id={el.get_attribute('id')}")
                                            break
                                    except Exception:
                                        pass
                                if sms_input:
                                    break

                                # Yöntem 2: Görünür text input'lar
                                try:
                                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='tel'], input:not([type])")
                                    for inp in all_inputs:
                                        try:
                                            if inp.is_displayed():
                                                inp_id = (inp.get_attribute("id") or "").lower()
                                                inp_val = inp.get_attribute("value") or ""
                                                if "tc" in inp_id or "sifre" in inp_id or "giris" in inp_id or "password" in inp_id:
                                                    continue
                                                if len(inp_val) > 5:
                                                    continue
                                                sms_input = inp
                                                log(f"SMS kutusu (fallback): id={inp.get_attribute('id')}, name={inp.get_attribute('name')}")
                                                break
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                                if sms_input:
                                    break
                                time.sleep(2)
                            
                            # SMS KUTUSU BULUNAMADIYSA (Hata kontrolü ve Spam Koruması)
                            if not sms_input:
                                error_msg = ""
                                error_selectors = [
                                    (By.ID, "pageContent_dvSepeteEkleHataMesaj"),
                                    (By.ID, "lblMesaj"),
                                    (By.ID, "lblHata"),
                                    (By.CSS_SELECTOR, ".alert-danger"),
                                    (By.CSS_SELECTOR, ".help-block-error"),
                                    (By.CSS_SELECTOR, ".invalid-feedback"),
                                    (By.CSS_SELECTOR, ".swal2-error")
                                ]
                                for by, sel in error_selectors:
                                    try:
                                        err_els = driver.find_elements(by, sel)
                                        for err_el in err_els:
                                            if err_el.is_displayed() and err_el.text.strip():
                                                error_msg = err_el.text.strip()
                                                break
                                        if error_msg:
                                            break
                                    except Exception:
                                        pass

                                try:
                                    debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms_page_debug.html")
                                    with open(debug_path, "w", encoding="utf-8") as f:
                                        f.write(driver.page_source)
                                except Exception:
                                    pass

                                log(f"⚠️ SMS kutusu tespit edilemedi! Sitedeki mesaj: '{error_msg or 'Yok'}'")
                                send_telegram(
                                    f"⚠️ <b>[SPOR BOTU] UYARI</b>\n"
                                    f"Kaydet'e basıldı ancak SMS doğrulama kutusu ekrana gelmedi.\n"
                                    f"Site Uyarısı: {error_msg or 'Yok'}\n"
                                    f"Telefonunuza SMS gönderilmiş olabilir. 20 defa SMS gelmesini önlemek için bot 120 saniye beklemeye geçiyor ve aynı seansa 3 dakika boyunca tekrar basmayacaktır.",
                                    config
                                )

                                # Seansa 3 dakika cooldown + 120 saniye zorunlu bekleme (Spam önleme)
                                slot_cooldowns[best_slot_key] = time.time() + 180
                                log("🛡️ SMS spam koruması devreye girdi: 120 saniye bekleniyor...")
                                time.sleep(120)
                                try:
                                    goto_scheduler(driver, config)
                                except Exception:
                                    driver.get(SEANS_SECIM_URL)
                                    time.sleep(3)

                            else:
                                # SMS KUTUSU BULUNDU
                                sms_code = sms_kodunu_bekle(config)
                                if sms_code:
                                    log(f"SMS kodu giriliyor: {sms_code}")
                                    
                                    # SMS kodunu girmeden önce kutuyu yeniden bul (stale element hatasını önlemek için)
                                    target_input = None
                                    try:
                                        sms_input.clear()
                                        target_input = sms_input
                                    except Exception:
                                        log("⚠️ SMS kutusu yenilendi, tekrar aranıyor...")
                                        for sel in selectors:
                                            try:
                                                el = driver.find_element(By.XPATH, sel)
                                                if el.is_displayed():
                                                    target_input = el
                                                    break
                                            except Exception:
                                                pass
                                        if not target_input:
                                            try:
                                                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='tel'], input:not([type])")
                                                for inp in all_inputs:
                                                    if inp.is_displayed():
                                                        inp_id = (inp.get_attribute("id") or "").lower()
                                                        inp_val = inp.get_attribute("value") or ""
                                                        if "tc" in inp_id or "sifre" in inp_id or "giris" in inp_id or "password" in inp_id:
                                                            continue
                                                        if len(inp_val) > 5:
                                                            continue
                                                        target_input = inp
                                                        break
                                            except Exception:
                                                pass
                                    
                                    if target_input:
                                        try:
                                            target_input.clear()
                                        except Exception:
                                            pass
                                        target_input.send_keys(sms_code)
                                        time.sleep(1)
                                    else:
                                        log("❌ SMS input kutusu bulunamadığı için kod girilemedi!")

                                    # Doğrula butonunu bul
                                    # ÖNEMLİ: SMS input kutusu (pageContent_txtDogrulamaKodu) ID'sinde
                                    # "Dogrulama" geçtiği için input selector'ları çakışır — hariç tutulmalı!
                                    sms_input_id = (sms_input.get_attribute("id") or "") if sms_input else ""
                                    verify_btn = None
                                    verify_selectors = [
                                        # 1. Bilinen ID'ler (en güvenilir)
                                        (By.ID, "pageContent_lbtnSmsDogrula"),
                                        (By.ID, "pageContent_lbtnDogrula"),
                                        (By.ID, "pageContent_btnDogrula"),
                                        (By.ID, "pageContent_lbtnKodDogrula"),
                                        (By.ID, "pageContent_lbtnKodunuDogrula"),
                                        (By.ID, "pageContent_btnKodDogrula"),
                                        (By.ID, "pageContent_btnKodunuDogrula"),
                                        (By.ID, "pageContent_btnDogrulamaKodu"),
                                        (By.ID, "pageContent_lbtnDogrulamaKodu"),
                                        (By.ID, "pageContent_lbtnDogrulamaGonder"),
                                        (By.ID, "pageContent_lbtnCepTelDogrulamaGonder"),
                                        (By.ID, "lbtnSms"),
                                        # 2. SweetAlert2 butonu
                                        (By.CSS_SELECTOR, ".swal2-confirm"),
                                        (By.CSS_SELECTOR, "button.swal2-confirm"),
                                        # 3. XPath: sadece <a> ve <button> (input hariç - SMS kutusu ile çakışır!)
                                        (By.XPATH, "//a[contains(@id,'Dogrula')]"),
                                        (By.XPATH, "//a[contains(@id,'Gonder')]"),
                                        (By.XPATH, "//button[contains(@id,'Dogrula')]"),
                                        (By.XPATH, "//button[contains(@id,'Gonder')]"),
                                        (By.XPATH, "//a[contains(@id,'Sms') or contains(@id,'SMS')]"),
                                        (By.XPATH, "//button[contains(@id,'Sms') or contains(@id,'SMS')]"),
                                        # 4. Metin tabanlı arama (descendant text ile)
                                        (By.XPATH, "//a[contains(.,'oğrula')]"),
                                        (By.XPATH, "//button[contains(.,'oğrula')]"),
                                        (By.XPATH, "//a[contains(.,'Gönder')]"),
                                        (By.XPATH, "//button[contains(.,'Gönder')]"),
                                        (By.XPATH, "//input[@type='submit' and contains(@value,'oğrula')]"),
                                        (By.XPATH, "//input[@type='submit' and contains(@value,'Gönder')]"),
                                    ]
                                    for by, sel in verify_selectors:
                                        try:
                                            btn = driver.find_element(by, sel)
                                            if btn.is_displayed():
                                                # SMS input kutusunu yakalamadığımızdan emin ol
                                                btn_id = btn.get_attribute("id") or ""
                                                btn_tag = btn.tag_name.lower()
                                                if btn_id == sms_input_id:
                                                    log(f"⚠️ Selector '{sel}' SMS input kutusunu yakaladı, atlanıyor!")
                                                    continue
                                                if btn_tag == "input" and btn.get_attribute("type") in ("text", "tel", "number", None):
                                                    log(f"⚠️ Selector '{sel}' text input yakaladı (id={btn_id}), atlanıyor!")
                                                    continue
                                                verify_btn = btn
                                                log(f"Doğrula butonu bulundu: tag={btn_tag}, id={btn_id}, sel={sel}")
                                                break
                                        except Exception:
                                            pass
                                    
                                    if verify_btn:
                                        try:
                                            verify_btn.click()
                                        except Exception:
                                            driver.execute_script("arguments[0].click();", verify_btn)
                                        time.sleep(4)
                                        
                                        # Doğrulama başarılı mı kontrol et
                                        post_url = driver.current_url.lower()
                                        page_text = ""
                                        try:
                                            page_text = driver.find_element(By.TAG_NAME, "body").text
                                        except Exception:
                                            pass
                                        
                                        if "seanssecim" in post_url and ("başarı" in page_text.lower() or "tamamlandı" in page_text.lower() or "onaylandı" in page_text.lower() or "Seçilmiş Seanslarınız" in page_text):
                                            log("✅ SMS girildi, doğrulama butonuna basıldı. Rezervasyon tamamlandı!")
                                            send_telegram(f"<b>[SPOR BOTU] BAŞARILI!</b>\nRezervasyon onaylandı: {best_slot['date']} {best_slot['time']} {best_slot['court']}", config)
                                            alarm_olustur(config, best_slot['date'], best_slot['time'], best_slot['court'])
                                        else:
                                            log(f"⚠️ Doğrula butonuna basıldı ama başarı doğrulanamadı. URL: {post_url}")
                                            log("SMS girildi, doğrulama butonuna basıldı. Sonuç kontrol ediliyor...")
                                            send_telegram(f"<b>[SPOR BOTU]</b> Doğrula butonuna basıldı.\n{best_slot['date']} {best_slot['time']} {best_slot['court']}\nSonucu kontrol edin.", config)
                                            alarm_olustur(config, best_slot['date'], best_slot['time'], best_slot['court'])
                                    else:
                                        log("❌ Doğrula butonu bulunamadı!")
                                        # Sayfa kaynağını kaydet (bir sonraki seferde buton ID'si tespit edilebilsin)
                                        try:
                                            debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms_dogrula_debug.html")
                                            with open(debug_path, "w", encoding="utf-8") as f:
                                                f.write(driver.page_source)
                                            log("SMS doğrulama sayfası sms_dogrula_debug.html'e kaydedildi.")
                                        except Exception:
                                            pass
                                        send_telegram(f"⚠️ <b>[SPOR BOTU]</b> SMS kodu girildi ama Doğrula butonu bulunamadı!\n{best_slot['date']} {best_slot['time']}\nManuel doğrulama gerekli!", config)
                                else:
                                    log("SMS kodu zaman aşımına uğradığı için tekrar deneme yapmadan önce 120 saniye bekleniyor (SMS spam önleme)...")
                                    slot_cooldowns[best_slot_key] = time.time() + 180
                                    time.sleep(120)
                                    try:
                                        goto_scheduler(driver, config)
                                    except Exception:
                                        driver.get(SEANS_SECIM_URL)
                                        time.sleep(3)
                        except Exception as e:
                            log(f"Onaylama ekranı hatası: {e}")
                
                log(f"Döngü tamamlandı. {interval} saniye bekleniyor...")
                time.sleep(interval)
                try:
                    driver.refresh()
                except Exception:
                    pass
                time.sleep(3)
                consecutive_errors = 0  # Başarılı tur: hata sayacı sıfırla
            
            except Exception as e:
                consecutive_errors += 1
                log(f"Döngü hatası ({consecutive_errors}. ardışık): {e}")
                if consecutive_errors >= 10:
                    log("⛔ 10 ardışık döngü hatası! Bot durduruluyor.")
                    send_telegram("⛔ <b>[SPOR BOTU]</b> 10 ardışık döngü hatası nedeniyle bot durduruldu. Lütfen kontrol edin.", config)
                    break
                time.sleep(10)
                
    except Exception as e:
        log(f"Bot Çöktü: {e}")
    finally:
        if driver_ref is None:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            log("Bot durduruldu. Chrome kapatıldı.")
        else:
            log("Bot çalışma döngüsü durduruldu. Chrome penceresi açık bırakıldı (Debug / Manuel kullanım için).")

# ==============================================================================
# DEBUG & MANUEL ADIM TESTİ FONKSİYONLARI
# ==============================================================================

def get_or_init_driver(driver_ref: list) -> webdriver.Chrome:
    """Tek bir Chrome driver örneğini saklar ve gerektiğinde oluşturur."""
    if driver_ref and len(driver_ref) > 0 and driver_ref[0] is not None:
        try:
            _ = driver_ref[0].current_url
            return driver_ref[0]
        except Exception:
            # Eski driver çökmüş veya pencere kapanmış, temizle
            log("⚠️ Eski Chrome oturumu geçersiz, yeni tarayıcı açılacak...")
            try:
                driver_ref[0].quit()
            except Exception:
                pass
            driver_ref[0] = None

    drv = init_chrome_driver()
    if driver_ref is not None:
        if len(driver_ref) == 0:
            driver_ref.append(drv)
        else:
            driver_ref[0] = drv
    return drv

def debug_step_open_browser(config: dict, driver_ref: list):
    log("🔧 [DEBUG] Chrome Tarayıcı Açılıyor ve Giriş Sayfasına Gidiliyor...")
    drv = get_or_init_driver(driver_ref)
    try:
        drv.get(LOGIN_URL)
        log("✅ [DEBUG] Tarayıcı başarıyla açıldı ve Giriş Sayfasına (uyegiris.aspx) gidildi.")
    except Exception as e:
        log(f"⚠️ [DEBUG] Sayfaya gidilirken uyarı: {e}")

def debug_step_login(config: dict, driver_ref: list):
    log("🔧 [DEBUG] Adım 1: Oturum Açılıyor...")
    drv = get_or_init_driver(driver_ref)
    success = login(drv, config)
    if success:
        log("✅ [DEBUG] Oturum başarıyla açıldı.")
    else:
        log("❌ [DEBUG] Giriş yapılamadı! TC Kimlik veya Şifrenizi kontrol edin.")

def debug_step_scan_scheduler(config: dict, driver_ref: list):
    log("🔧 [DEBUG] Adım 2: Seans Takvimi Taranıyor...")
    drv = get_or_init_driver(driver_ref)
    curr_url = drv.current_url.lower()
    if "uyeseanssecim" not in curr_url:
        log("Takvim sayfasına gidiliyor...")
        if not goto_scheduler(drv, config):
            drv.get(SEANS_SECIM_URL)
            time.sleep(3)

    log("Tablo taranıyor...")
    all_available_slots = []
    booked_dates = {}
    total_sessions_count = 0
    green_count = 0
    blue_count = 0
    gray_count = 0
    red_count = 0

    columns = drv.find_elements(By.XPATH, "//div[contains(@class, 'col-') and .//h3[contains(@class, 'panel-title')]]")
    for col in columns:
        try:
            header = col.find_element(By.CSS_SELECTOR, ".panel-heading, h3.panel-title")
            header_text = header.text
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', header_text)
            if not date_match: continue
            date_str = date_match.group(0)
            day_name = header_text.split('\n')[0].strip()

            wells = col.find_elements(By.CSS_SELECTOR, ".well")
            for well in wells:
                total_sessions_count += 1
                border_color = drv.execute_script("return window.getComputedStyle(arguments[0]).borderColor;", well) or ""
                style = well.get_attribute("style") or ""
                b_str = f"{border_color} {style}".lower()

                is_green = "8, 245, 26" in b_str or "08f51a" in b_str
                is_blue = "62, 209, 255" in b_str or "3ed1ff" in b_str or "00d0ff" in b_str or "232, 253, 47" in b_str or "e8fd2f" in b_str
                is_gray = "128, 128, 128" in b_str or "808080" in b_str

                court = ""
                try:
                    court_lbl = well.find_element(By.CSS_SELECTOR, "label[title='Salon Adı']")
                    court = court_lbl.text.strip() if court_lbl else ""
                except Exception:
                    pass
                if not court:
                    try: court = well.text.strip()
                    except Exception: court = ""

                time_spn = well.find_element(By.CSS_SELECTOR, "span[id*='lblSeansSaat']")
                time_str = time_spn.text.strip() if time_spn else ""

                if is_green:
                    green_count += 1
                    all_available_slots.append({
                        "element": well, "date": date_str, "day_name": day_name, "time": time_str, "court": court
                    })
                elif is_blue:
                    blue_count += 1
                    booked_dates[date_str] = {"time": time_str, "court": court}
                elif is_gray:
                    gray_count += 1
                else:
                    red_count += 1
        except Exception as e:
            log(f"Sütun parse hatası: {e}")

    log(f"📊 [DEBUG] Takvim Özeti: Toplam {total_sessions_count} kutu (Boş/Yeşil: {green_count} | Seçili/Mavi: {blue_count} | Kapalı/Gri: {gray_count} | Dolu/Kırmızı: {red_count})")
    if booked_dates:
        booked_info = ", ".join([f"{d}: {info['time']}" for d, info in booked_dates.items()])
        log(f"Takvimde mevcut seanslar (mavi): {booked_info}")

    eligible = filter_slots(all_available_slots, config)
    log(f"✅ [DEBUG] Filtrelerinize uyan boş seans sayısı: {len(eligible)}")
    for i, s in enumerate(eligible, 1):
        log(f"   [{i}] {s['date']} ({s['day_name']}) | {s['time']} | {s['court']}")
    return eligible

def debug_step_goto_my_sessions(config: dict, driver_ref: list):
    log("🔧 [DEBUG] Adım 3: Seanslarım Sayfasına Gidiliyor...")
    drv = get_or_init_driver(driver_ref)
    bookings = has_active_booking(drv, config)
    log(f"📋 [DEBUG] Profilinizdeki aktif kayıt sayısı: {len(bookings)}")
    for i, b in enumerate(bookings, 1):
        log(f"   [{i}] Tarih: {b['date']} | Saat: {b['time']} | Tesis: {b['facility']} | Kort: {b['court']} -> Durum: {b['status']}")

def debug_step_select_and_fill_slot(config: dict, driver_ref: list, click_save: bool = False):
    log(f"🔧 [DEBUG] Adım 4: Uygun Seans Seçme & İşaretleme Testi (Kaydet'e Bas: {click_save})...")
    drv = get_or_init_driver(driver_ref)
    curr_url = drv.current_url.lower()
    if "uyeseanssecim" not in curr_url:
        goto_scheduler(drv, config)

    eligible = debug_step_scan_scheduler(config, driver_ref)
    if not eligible:
        log("⚠️ [DEBUG] Filtrelerinize uyan boş seans bulunamadığı için seçim yapılamadı.")
        return

    best = eligible[0]
    log(f"🎯 [DEBUG] Seçilen seans: {best['date']} | {best['time']} | {best['court']}")

    target_well = None
    wells = drv.find_elements(By.CSS_SELECTOR, ".well")
    for w in wells:
        if best['court'] in w.text and best['time'] in w.text:
            target_well = w
            break

    if not target_well:
        log("❌ [DEBUG] Seans kutucuğu sayfada yeniden bulunamadı!")
        return

    select_slot_checkbox(drv, target_well)
    time.sleep(1)

    try:
        try:
            terms_cb = drv.find_element(By.ID, "pageContent_cboxOnay")
        except NoSuchElementException:
            terms_cb = drv.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
        if not terms_cb.is_selected():
            drv.execute_script("arguments[0].click();", terms_cb)
        log("✅ [DEBUG] Seans kutucuğu ve Onay Sözleşmesi kutucuğu işaretlendi.")
    except Exception as e:
        log(f"⚠️ [DEBUG] Onay kutusu işaretleme uyarısı: {e}")

    if click_save:
        try:
            save_btn = drv.find_element(By.ID, "lbtnKaydet")
            drv.execute_script("arguments[0].click();", save_btn)
            log("💾 [DEBUG] Kaydet butonuna tıklandı! SMS penceresi bekleniyor...")
        except Exception as e:
            log(f"❌ [DEBUG] Kaydet butonuna tıklanamadı: {e}")
    else:
        log("ℹ️ [DEBUG] Test Modunda 'Kaydet' basılmadı. İşaretli seansı açık Chrome pencerenizde görebilirsiniz.")

def debug_step_cancel_booking(config: dict, driver_ref: list):
    log("🔧 [DEBUG] Adım 5: Var Olan Seansı İptal Etme Testi...")
    drv = get_or_init_driver(driver_ref)
    bookings = has_active_booking(drv, config)
    
    # İptal edilebilecek seansları bul
    active_b = [b for b in bookings if b.get("cancel_btn") is not None or "İptal Et" in b.get("action_text", "")]
    if not active_b:
        # Fallback to status
        active_b = [b for b in bookings if "Satış Yapıldı" in b.get("status", "")]
        
    if not active_b:
        log("⚠️ [DEBUG] İptal edilecek aktif (İptal Et butonu olan veya 'Satış Yapıldı' durumunda) seans bulunamadı.")
        try:
            html = drv.page_source
            with open("cancel_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            log("🔍 [DEBUG] Sayfa kaynağı cancel_debug.html olarak kaydedildi.")
        except:
            pass
        return

    target = active_b[-1] # Listede genellikle en alttaki (en yeni/aktif) olandır
    log(f"⚠️ [DEBUG] İptal edilecek seans bulundu: {target['date']} {target['time']} ({target['court']})")
    try:
        cancel_btn = target.get("cancel_btn")
        if not cancel_btn:
            cancel_btn = target['element'].find_element(By.XPATH, ".//*[contains(text(), 'İptal Et')]")
            
        drv.execute_script("window.confirm = function() { return true; };")
        drv.execute_script("arguments[0].click();", cancel_btn)
        time.sleep(3)
        log(f"✅ [DEBUG] {target['date']} {target['time']} seansı başarıyla iptal edildi.")
        alarm_sil(config, target['date'])
    except Exception as e:
        log(f"❌ [DEBUG] İptal hatası: {e}")

def debug_step_test_telegram(config: dict):
    log("🔧 [DEBUG] Telegram Bildirim Testi...")
    telegram_webhook_kontrol(config)
    send_telegram("<b>[SPOR BOTU] DEBUG TESTİ</b>\nTelegram bildiriminiz başarıyla iletildi! 🚀", config)
    log("✅ [DEBUG] Telegram test mesajı gönderildi.")

def debug_step_close_driver(driver_ref: list):
    log("🔧 [DEBUG] Chrome Kapatılıyor...")
    if driver_ref and len(driver_ref) > 0 and driver_ref[0]:
        try:
            driver_ref[0].quit()
        except Exception:
            pass
        driver_ref[0] = None
        log("✅ [DEBUG] Chrome penceresi kapatıldı.")
    else:
        log("ℹ️ [DEBUG] Zaten açık bir Chrome penceresi yok.")

if __name__ == "__main__":
    from config_manager import load_config
    config = load_config()
    log("Tennis Bot konsol modunda başlatılıyor...")
    run_bot_thread(config, lambda: True)

