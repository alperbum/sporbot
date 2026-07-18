# Spor İstanbul Botu - Detaylı Kurulum & Kullanım Rehberi 📖

Bu rehber, Spor İstanbul botunun Telegram entegrasyonu ve iPhone (iOS) üzerinden SMS doğrulama kodlarının bot sistemine otomatik aktarılması için yapılması gereken ayarları adım adım anlatmaktadır.

---

## 1. Telegram Botu ve Chat ID Oluşturma 🤖

Spor İstanbul botunun size bildirim gönderebilmesi ve SMS onay kodlarını alabilmesi için bir Telegram botuna ihtiyacınız vardır.

### Adım 1: Bot Token Alma
1. Telegram uygulamasında **[@BotFather](https://t.me/BotFather)** kullanıcısını aratın ve başlatın.
2. `/newbot` komutunu gönderin.
3. Botunuz için bir isim belirleyin (Örn: `SporIstanbulBot`).
4. Botunuz için `bot` ile biten benzersiz bir kullanıcı adı belirleyin (Örn: `benim_spor_botum_bot`).
5. **@BotFather** size bir **HTTP API Token** verecektir (Örn: `8767976833:AAEZThBoMP...`). Bu kodu kopyalayın ve bot ayarlarındaki **Telegram Token** kısmına yapıştırın.

### Adım 2: Chat ID Alma
1. Telegram'da **[@userinfobot](https://t.me/userinfobot)** veya **[@GetIDBot](https://t.me/GetIDBot)** kullanıcısını başlatın.
2. Bot size sayısal bir **Id** verecektir (Örn: `1585282829`).
3. Oluşturduğunuz kendi botunuza gidip `/start` diyerek ilk mesajı atın (Botun size mesaj atabilmesi için başlatılmış olması gerekir).
4. Bu sayısal ID'yi bot ayarlarındaki **Telegram Chat ID** kısmına yapıştırın.

---

## 2. iOS (iPhone) Otomatik SMS Doğrulama Otomasyonu 📱

Spor İstanbul rezervasyon yaparken telefonunuza SMS ile onay kodu gönderir. iPhone'daki **Kestirmeler (Shortcuts)** otomasyonu ile SMS kodunun bot tarafından otomatik okunmasını sağlayabilirsiniz.

### Kestirme (Otomasyon) Oluşturma Adımları:

1. iPhone'unuzda **Kestirmeler (Shortcuts)** uygulamasını açın.
2. Alt menüden **Otomasyon (Automation)** sekmesine geçin ve sağ üstteki **+** (Ekle) butonuna basın.
3. Arama kutusuna **Mesaj (Message)** yazın ve seçin.
4. Ayarları şu şekilde yapın:
   - **İçerik Şunları İçeriyorsa:** `onay kodunuz`
   - **Çalıştırma Seçeneği:** **Hemen Çalıştır (Run Immediately)**
   - **Çalıştırıldığında Bildir:** Kapalı
5. **İleri (Next)** butonuna basın ve **Boş Yeni Otomasyon (New Blank Automation)** seçin.
6. **İşlem Ekle (Add Action)** butonuna basın ve **"URL İçeriğini Al" (Get Contents of URL)** eylemini aratıp ekleyin.

### HTTP İsteği Yapılandırması (Ekran Görüntülerindeki Gibi):

- **URL:** 
  `https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/sendMessage`
  *(Buradaki `<YOUR_TELEGRAM_TOKEN>` yerine 1. Adımda aldığınız Bot Token'ı yazın)*

- **Ok (Aşağı ok)** butonuna basarak detayları açın:
  - **Yöntem (Method):** `POST`
  - **İstek Gövdesi (Request Body):** `JSON`
  - **Yeni Alan Ekle (Add new field) -> Metin (Text):**
    - Key: `chat_id` -> Değer: `Sizin Chat ID'niz` (Örn: `1585282829`)
  - **Yeni Alan Ekle (Add new field) -> Metin (Text):**
    - Key: `text` -> Değer: **Kestirme Girdisi (Shortcut Input)** *(Gelen SMS metni)*

7. **Bitti (Done)** butonuna basarak otomasyonu kaydedin.

> 💡 **Nasıl Çalışır?**
> Spor İstanbul'dan "onay kodunuz: 123456" şeklinde bir SMS geldiğinde, iPhone bu SMS'i anında algılar, Telegram botunuza otomatik iletir. Spor Botu da Telegram'dan kodu okuyarak rezervasyon ekranına otomatik girer ve işlemi tamamlar!

---

## 3. Botun Çalıştırılması ve Kullanımı 🚀

1. Masaüstündeki `baslat.bat` dosyasına çift tıklayarak arayüzü açın.
2. **TC Kimlik**, **Şifre**, **Telegram Token** ve **Chat ID** bilgilerinizi girin.
3. Tercih ettiğiniz **Günler**, **Saatler** ve **Branş** seçimini yapın.
4. **"Ayarları Kaydet"** butonuna basın.
5. **"Botu Başlat"** butonuna basarak taramayı başlatın.
