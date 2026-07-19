import time
from config_manager import load_config
from tennis_bot import telegram_son_mesajlari_oku, telegram_eski_mesajlari_temizle

def test_telegram_okuma():
    print("===========================================")
    print("TELEGRAM SMS OKUMA TESTİ BAŞLIYOR")
    print("===========================================")
    config = load_config()
    chat_id = config.get("telegram_chat_id", "")
    
    print(f"Tanımlı Chat ID: {chat_id}")
    print("\nEski mesajlar temizleniyor...")
    telegram_eski_mesajlari_temizle(config)
    
    print("\nŞimdi lütfen telefonunuza test amaçlı normal bir SMS gelmesini sağlayın")
    print("(veya Kestirmeyi manuel olarak çalıştırın).")
    print("Mesajın gruba YENİ BOT (SmsBridge) tarafından atıldığından emin olun.")
    print("Bot 60 saniye boyunca grubu dinleyecek...\n")
    
    baslangic = time.time()
    while (time.time() - baslangic) < 60:
        mesajlar = telegram_son_mesajlari_oku(config, son_n_saniye=60)
        
        # Sadece bizim botun mesajlarını atlıyoruz, diğer tüm mesajları ekrana basıyoruz
        for mesaj in mesajlar:
            if "[SPOR BOTU]" in mesaj or "SMS Onayı" in mesaj or "Seans Alınıyor" in mesaj:
                continue
                
            print("\n✅ BAŞARILI! Gruptan bir mesaj okundu:")
            print("-------------------------------------------")
            print(mesaj)
            print("-------------------------------------------")
            print("Telegram bağlantınız ve Kestirme otomasyonunuz KUSURSUZ çalışıyor!")
            return
            
        time.sleep(3)
        print(".", end="", flush=True)
        
    print("\n\n❌ SÜRE DOLDU. 60 saniye içinde mesaj okunamadı.")
    print("Lütfen Kestirmedeki tokenin yeni botun tokeni olduğundan ve")
    print("Chat ID'nin doğru olduğundan emin olun.")

if __name__ == "__main__":
    test_telegram_okuma()
    input("\nÇıkmak için ENTER tuşuna basın...")
