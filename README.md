# Spor İstanbul Rezervasyon Botu 🎾

Spor İstanbul (online.spor.istanbul) tesislerinde tenis, fitness ve yüzme seansları için otomatik rezervasyon yapabilen, SMS 2FA doğrulamasını Telegram üzerinden alan ve gelişmiş arayüze (GUI) sahip Python botu.

## Özellikler

- 🖥️ **Gelişmiş Arayüz (CustomTkinter)**: Kolay gün, saat ve spor branşı seçimi.
- ⚡ **Otomatik Oturum Tazeleme**: Oturum kapandığında veya giriş sayfasına atıldığında otomatik yeniden giriş yapma.
- ⏰ **Akıllı Yükseltme & İptal**: Mevcut seansınızdan daha iyi (daha geç saat veya Kort 3) seans açıldığında otomatik yükseltme.
- 📱 **Telegram Entegrasyonu & SMS 2FA**: SMS ile gelen onay kodunu Telegram üzerinden okuma ve anlık bildirim gönderme.
- 🔔 **Otomatik Alarm**: Rezervasyon saatinden belirlenen dakika önce Telegram üzerinden hatırlatma alarmı.
- 🛡️ **Güvenli & Thread-Safe**: Arayüz kilitlenmelerine karşı korumalı asenkron yapı.

## 📖 Detaylı Kurulum & Kullanım Rehberi

Telegram botu oluşturma ve iOS (iPhone) üzerinde otomatik SMS doğrulama otomasyonunu kurmak için hazırlanan adım adım resimli rehber için:
👉 **[GUIDE.md / Kurulum Rehberi](GUIDE.md)** dosyasını inceleyebilirsiniz.

## Kurulum & Kullanım

1. **Gerekli paketleri yükleyin:**
   ```bash
   pip install customtkinter selenium webdriver-manager requests
   ```

2. **Ayarları Oluşturun:**
   `config.example.json` dosyasının adını `config.json` yapıp kendi TC Kimlik ve şifrenizi girin. (Arayüz üzerinden de değiştirebilirsiniz).

3. **Çalıştırma:**
   `baslat.bat` dosyasına çift tıklayın veya terminalden çalıştırın:
   ```bash
   python gui.py
   ```

## Lisans
MIT
