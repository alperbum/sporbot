import time
import re
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

def log(msg: str):
    ts = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    log_line = f"[{ts}] {msg}"
    try:
        print(log_line)
    except Exception:
        pass
        
    try:
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass

def send_telegram(message: str, config: dict):
    token = config.get("telegram_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        log(f"Telegram hatası: {e}")

def telegram_son_mesajlari_oku(config: dict, son_n_saniye: int = 180) -> list:
    token = config.get("telegram_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not token: return []
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": -10}, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            return []

        mesajlar = []
        simdi = int(time.time())
        updates = data.get("result", [])
        for update in updates:
            msg = update.get("message", {})
            msg_date = msg.get("date", 0)
            msg_text = msg.get("text", "")
            msg_chat_id = str(msg.get("chat", {}).get("id", ""))

            if msg_chat_id == str(chat_id) and (simdi - msg_date) < son_n_saniye:
                mesajlar.append(msg_text)

        if updates:
            last_id = max(u["update_id"] for u in updates)
            try:
                requests.get(url, params={"offset": last_id + 1, "limit": 1}, timeout=5)
            except Exception:
                pass

        return mesajlar
    except Exception as e:
        return []

def sms_kodunu_bekle(config: dict, max_bekleme_sn: int = 180):
    log(f"SMS kodu bekleniyor (max {max_bekleme_sn}sn)...")
    send_telegram("<b>[SPOR BOTU] SMS Onayı Bekleniyor!</b>\nTelefona gelen kodu buraya yönlendirin.", config)

    baslangic = time.time()
    while (time.time() - baslangic) < max_bekleme_sn:
        mesajlar = telegram_son_mesajlari_oku(config, son_n_saniye=60)
        for mesaj in mesajlar:
            match = re.search(r'onay kodunuz[:\s]*(\d+)', mesaj, re.IGNORECASE)
            if not match:
                match = re.search(r'(\d{4,6})', mesaj)
            if match:
                kod = match.group(1)
                log(f"SMS kodu bulundu: {kod}")
                return kod
        time.sleep(3)

    log("SMS kodu zaman aşımına uğradı!")
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

def init_chrome_driver() -> webdriver.Chrome:
    log("Chrome tarayıcı başlatılıyor...")
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

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

        driver.find_element(By.ID, "btnGirisYap").click()
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
        # Detay tablosu zaten görünür mü kontrol et
        dt_visible = False
        try:
            dt_elem = driver.find_element(By.ID, "dtUyeSpor")
            if dt_elem.is_displayed():
                dt_visible = True
        except NoSuchElementException:
            pass

        if not dt_visible:
            details_btns = driver.find_elements(By.CSS_SELECTOR, "a[id^='pageContent_rptListe_lbtnDetayGoster_']")
            target_btn = None
            for btn in details_btns:
                row = btn.find_element(By.XPATH, "./ancestor::tr")
                if sport in row.text.upper():
                    target_btn = btn
                    break
            
            if target_btn:
                try:
                    icon = target_btn.find_element(By.TAG_NAME, "i")
                    if "fa-plus" in icon.get_attribute("class"):
                        driver.execute_script("arguments[0].click();", target_btn)
                        time.sleep(3)
                except Exception:
                    driver.execute_script("arguments[0].click();", target_btn)
                    time.sleep(3)
                
        rows = driver.find_elements(By.CSS_SELECTOR, "#dtUyeSpor tr")
        for row in rows:
            text = row.text
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
            if date_match:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    date = cells[0].text.strip()
                    time_str = cells[1].text.strip()
                    facility = cells[2].text.strip()
                    court = cells[3].text.strip()
                    status = cells[5].text.strip()
                    
                    bookings.append({
                        "date": date,
                        "time": time_str,
                        "facility": facility,
                        "court": court,
                        "status": status,
                        "element": row
                    })
                    if "Satış Yapıldı" in status:
                        alarm_olustur(config, date, time_str, court)
    except Exception as e:
        log(f"Rezervasyon kontrol hatası: {e}")
    
    log(f"Bulunan aktif seans sayısı: {len(bookings)}")
    return bookings

def goto_scheduler(driver: webdriver.Chrome) -> bool:
    try:
        booking_link = None
        # Yöntem 1: ID ile bul
        try:
            booking_link = driver.find_element(By.ID, "pageContent_rptListe_lbtnSeansSecim_0")
        except NoSuchElementException:
            pass

        # Yöntem 2: XPATH ile lbtnSeansSecim içeren ID bul
        if not booking_link:
            try:
                booking_link = driver.find_element(By.XPATH, "//*[contains(@id, 'lbtnSeansSecim')]")
            except NoSuchElementException:
                pass

        # Yöntem 3: Link metni ile ara
        if not booking_link:
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                t = link.text
                if "Seans" in t or "Rezervasyon" in t or "Seans Seç" in t or "Rezervasyon Yap" in t:
                    booking_link = link
                    break

        # Yöntem 4: CSS class ile bul
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

        log("Rezervasyon Yap/Seans Seç butonu bulunamadı!")
        return False
    except Exception as e:
        log(f"Scheduler navigasyon hatası: {e}")
        return False

def is_newly_opened(date_str: str, time_str: str) -> bool:
    try:
        date_parts = date_str.split('.')
        time_parts = time_str.split(' - ')[0].split(':')
        slot_dt = datetime(
            int(date_parts[2]), int(date_parts[1]), int(date_parts[0]),
            int(time_parts[0]), int(time_parts[1])
        )
        now = datetime.now()
        diff_hours = (slot_dt - now).total_seconds() / 3600
        return 69 <= diff_hours <= 73
    except:
        return False

def get_start_hour(time_str: str) -> int:
    match = re.search(r'^(\d{2}):(\d{2})', time_str)
    return int(match.group(1)) if match else 0

def filter_slots(all_slots: list, config: dict) -> list:
    pref_days = config.get("tercih_edilen_gunler", [])
    pref_hours = config.get("tercih_edilen_saatler", [])
    sport = config.get("secili_spor", "TENİS").upper()
    
    filtered = []
    DAY_MAP = {
        "pazartesi": "Pzt", "salı": "Sal", "sali": "Sal", 
        "çarşamba": "Çar", "carsamba": "Çar", 
        "perşembe": "Per", "persmbe": "Per", 
        "cuma": "Cum", "cumartesi": "Cmt", "pazar": "Paz"
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
        
    # Tennis court priority logic
    slots_by_hour = {}
    for s in filtered:
        slots_by_hour.setdefault(s['time'], []).append(s)
        
    final_eligible = []
    for hour, h_slots in slots_by_hour.items():
        has_court_3 = any("KORT 3" in s['court'].upper() for s in h_slots)
        
        for s in h_slots:
            is_court_3 = "KORT 3" in s['court'].upper()
            is_court_1 = "KORT 1" in s['court'].upper()
            
            if is_court_3:
                final_eligible.append(s)
            elif is_court_1 and has_court_3:
                # Kort 1 is only acceptable if Kort 3 is ALSO available at the SAME hour
                final_eligible.append(s)
                
    return final_eligible

def run_bot_thread(config: dict, is_running_func):
    driver = None
    try:
        driver = init_chrome_driver()
        
        if not login(driver, config):
            log("Giriş yapılamadığı için bot durduruldu.")
            return

        # Start alarm background thread
        alarm_thread = threading.Thread(
            target=alarm_zamanlayici_thread,
            args=(config, is_running_func),
            daemon=True
        )
        alarm_thread.start()

        interval = max(5, config.get("tarama_araligi_dakika", 2) * 60)
        
        # Initially navigate to scheduler
        if not goto_scheduler(driver):
            log("Scheduler başlangıçta açılamadı, doğrudan SPOR_URL'ye gidiliyor...")
            driver.get(SPOR_URL)

        while is_running_func():
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
                    goto_scheduler(driver)
                    curr_url = driver.current_url.lower()

                # 2. Ensure we are on the scheduler page
                if "uyeseanssecim" not in curr_url:
                    if not goto_scheduler(driver):
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
                
                # Target columns containing a panel header and panel-title (scheduler days)
                columns = driver.find_elements(By.XPATH, "//div[contains(@class, 'col-') and .//h3[contains(@class, 'panel-title')]]")
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
                            # Evaluate computed border color in addition to inline style for robustness
                            border_color = driver.execute_script(
                                "return window.getComputedStyle(arguments[0]).borderColor;", well
                            ) or ""
                            style = well.get_attribute("style") or ""
                            
                            is_green = (
                                "8, 245, 26" in border_color or "rgb(8, 245, 26)" in border_color or "08f51a" in border_color.lower() or
                                "8, 245, 26" in style or "08f51a" in style.lower() or "rgb(8, 245, 26)" in style
                            )
                            
                            if is_green:
                                court_lbl = well.find_element(By.CSS_SELECTOR, "label[title='Salon Adı']")
                                court = court_lbl.text.strip() if court_lbl else ""
                                
                                time_spn = well.find_element(By.CSS_SELECTOR, "span[id*='lblSeansSaat']")
                                time_str = time_spn.text.strip() if time_spn else ""
                                
                                all_available_slots.append({
                                    "element": well,
                                    "date": date_str,
                                    "day_name": day_name,
                                    "time": time_str,
                                    "court": court
                                })
                    except Exception as e:
                        log(f"Sütun parse hatası: {e}")
                
                eligible_slots = filter_slots(all_available_slots, config)
                log(f"Uygun boş seans sayısı: {len(eligible_slots)}")
                
                if not eligible_slots:
                    log(f"Kriterlere uygun seans yok. {interval} saniye bekleniyor...")
                    time.sleep(interval)
                    try:
                        driver.refresh()
                    except Exception:
                        pass
                    time.sleep(3)
                    continue

                # --- SADECE UYGUN SEANS BULUNDUĞUNDA BURAYA GEÇİLİR ---
                if config.get("test_modu", False):
                    eligible_slots.sort(key=lambda s: get_start_hour(s['time']))
                else:
                    eligible_slots.sort(key=lambda s: (get_start_hour(s['time']), 1 if "KORT 3" in s['court'].upper() else 0), reverse=True)
                    
                best_slot = eligible_slots[0]
                log(f"🎯 Uygun seans tespit edildi: {best_slot['date']} | {best_slot['time']} | {best_slot['court']}")

                # 1. Şimdi aktif rezervasyonları kontrol et
                bookings = has_active_booking(driver, config)
                same_day_booking = next((b for b in bookings if b['date'] == best_slot['date'] and "Satış Yapıldı" in b['status']), None)
                
                action_taken = False
                
                if same_day_booking:
                    exist_hour = get_start_hour(same_day_booking['time'])
                    new_hour = get_start_hour(best_slot['time'])
                    sport = config.get("secili_spor", "TENİS").upper()
                    
                    is_better = False
                    if new_hour > exist_hour:
                        is_better = True
                    elif new_hour == exist_hour and sport == "TENİS":
                        new_c3 = "KORT 3" in best_slot['court'].upper()
                        old_c3 = "KORT 3" in same_day_booking['court'].upper()
                        if new_c3 and not old_c3:
                            is_better = True
                            
                    if is_better:
                        # 72-hour protection
                        if is_newly_opened(best_slot['date'], best_slot['time']) and not config.get("yeni_seans_yukseltme_izni", False):
                            log(f"Yeni açılan seansla (72s) yükseltme pas geçildi. ({best_slot['time']})")
                        else:
                            if config.get("test_modu", False):
                                log(f"Test Modu: Mevcut seans ({same_day_booking['time']}) iptal edilmedi. Yeni seans ({best_slot['time']}) alınmayacak.")
                            else:
                                log(f"Daha iyi seans bulundu! {same_day_booking['time']} iptal ediliyor, {best_slot['time']} alınacak.")
                                try:
                                    # Find cancel button
                                    rows = driver.find_elements(By.CSS_SELECTOR, "#dtUyeSpor tr")
                                    for row in rows:
                                        if same_day_booking['date'] in row.text and same_day_booking['time'] in row.text:
                                            cancel_btn = row.find_element(By.TAG_NAME, "a")
                                            driver.execute_script("window.confirm = function() { return true; };")
                                            driver.execute_script("arguments[0].click();", cancel_btn)
                                            log("İptal edildi. Yeni seans için takvime dönülüyor.")
                                            alarm_sil(config, same_day_booking['date'])
                                            send_telegram(f"<b>[SPOR BOTU] Mevcut Seans İptal Edildi</b>\nYeni Seans İçin Yol Açıldı: {best_slot['date']} {best_slot['time']}", config)
                                            action_taken = True
                                            break
                                except Exception as e:
                                    log(f"İptal işlemi hatası: {e}")

                                if action_taken:
                                    goto_scheduler(driver)
                    else:
                        log(f"Mevcut seansınız ({same_day_booking['time']}) zaten eşit veya daha iyi. İptal/Yükseltme yapılmadı.")
                
                if not same_day_booking or action_taken:
                    # Direct Booking or Booking after cancellation
                    if "uyeseanssecim" not in driver.current_url.lower():
                        goto_scheduler(driver)

                    log(f"Kort rezerve ediliyor: {best_slot['date']} | {best_slot['time']} | {best_slot['court']}")
                    send_telegram(f"<b>[SPOR BOTU] Seans Alınıyor</b>\n{best_slot['date']} | {best_slot['time']} | {best_slot['court']}", config)
                    
                    try:
                        driver.execute_script("arguments[0].click();", best_slot['element'])
                    except Exception:
                        wells = driver.find_elements(By.CSS_SELECTOR, ".well")
                        for w in wells:
                            if best_slot['court'] in w.text and best_slot['time'] in w.text:
                                driver.execute_script("arguments[0].click();", w)
                                break
                    time.sleep(2)
                    
                    if config.get("test_modu", False):
                        log("Test Modu: Onay kutusu işaretlenmedi. Çıkılıyor.")
                        time.sleep(5)
                    else:
                        # Checkbox
                        try:
                            try:
                                checkbox = driver.find_element(By.ID, "pageContent_cboxOnay")
                            except NoSuchElementException:
                                checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                            
                            driver.execute_script("arguments[0].click();", checkbox)
                            
                            # Save btn
                            save_btn = driver.find_element(By.ID, "lbtnKaydet")
                            driver.execute_script("arguments[0].click();", save_btn)
                            log("Kaydet'e basıldı. 2FA Bekleniyor...")
                            
                            sms_code = sms_kodunu_bekle(config)
                            if sms_code:
                                sms_input = driver.find_element(By.XPATH, 
                                    "//input[contains(@id,'SMS') or contains(@id,'Sms') or contains(@id,'sms') "
                                    "or contains(@placeholder,'Doğrulama') or contains(@placeholder,'Kod')]"
                                )
                                sms_input.send_keys(sms_code)
                                
                                verify_btn = driver.find_element(By.ID, "lbtnSms")
                                driver.execute_script("arguments[0].click();", verify_btn)
                                log("SMS girildi, rezervasyon tamam!")
                                send_telegram(f"<b>[SPOR BOTU] BAŞARILI!</b>\nRezervasyon onaylandı.", config)
                                alarm_olustur(config, best_slot['date'], best_slot['time'], best_slot['court'])
                        except Exception as e:
                            log(f"Onaylama ekranı hatası: {e}")
                
                log(f"Döngü tamamlandı. {interval} saniye bekleniyor...")
                time.sleep(interval)
                try:
                    driver.refresh()
                except Exception:
                    pass
                time.sleep(3)
            
            except Exception as e:
                log(f"Döngü hatası: {e}")
                time.sleep(10)
                
    except Exception as e:
        log(f"Bot Çöktü: {e}")
    finally:
        if driver:
            driver.quit()
        log("Bot durduruldu. Chrome kapatıldı.")

if __name__ == "__main__":
    from config_manager import load_config
    config = load_config()
    log("Tennis Bot konsol modunda başlatılıyor...")
    run_bot_thread(config, lambda: True)
