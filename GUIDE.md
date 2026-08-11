# 📖 Spor İstanbul Botu - Detaylı Kurulum & Kullanım Rehberi

Bu rehber, Spor İstanbul rezervasyon botunuzun **Telegram entegrasyonu**, **İki Botlu (Bot-to-Bot) iletişim yapılandırması** ve **iPhone (iOS) Kestirmeler (Shortcuts)** otomasyonu ile SMS doğrulama kodlarının bot sistemine otomatik ve güvenli bir şekilde aktarılmasını sağlamak için gereken tüm ayarları adım adım, detaylı bir şekilde açıklamaktadır.

---

## 🤖 1. Telegram Botları ve Grup Yapılandırması

Botun anlık durum güncellemelerini gönderebilmesi ve telefonunuza gelen SMS onay kodlarını kesintisiz okuyabilmesi için **2 Adet Telegram Botu** kurulumu en ideal ve güvenilir yöntemdir:

- **Bot 1 (SporBot):** Ana yazılımın kontrol ettiği, rezervasyon işlemlerini yapan ve takvimi tarayan ana Python botu.
- **Bot 2 (SmsBridge / Kestirme Botu):** Yalnızca telefonunuza gelen Spor İstanbul SMS'ini okuyup Telegram grubuna iletmekle görevli yardımcı bot.

### 🔑 Adım 1: Telegram Bot Token Alma (Her İki Bot İçin)

Her iki botu da oluşturmak için Telegram'ın resmi bot yöneticisi olan **BotFather**'ı kullanacağız.

1. Telegram arama çubuğuna **[@BotFather](https://t.me/BotFather)** yazın ve başlatın.
2. Yeni bir bot oluşturmak için sohbete `/newbot` komutunu gönderin.
3. Bot 1 için bir isim (Örn: `SporBot`) ve benzersiz bir kullanıcı adı (Örn: `@kendi_bot_adiniz`) belirleyin.
4. İşlem tamamlandığında BotFather size uzun bir **HTTP API Token** verecektir. Bu token'ı kopyalayıp güvenli bir yere not edin.
5. Aynı adımları tekrar uygulayarak **Bot 2**'yi oluşturun ve onun da token'ını kopyalayın.

### ⚠️ Adım 2: Telegram @BotFather Ayarları (KRİTİK ADIM)

İki botun aynı grupta birbiriyle iletişim kurabilmesi (Bot 2'nin attığı SMS mesajının Bot 1 tarafından okunabilmesi) için bu ayarlar **zorunludur**.

1. **Grup Gizliliğini Kapatma (`/setprivacy`):**
   - `@BotFather`'a gidin ve `/setprivacy` komutunu yazın.
   - Listeden **Bot 1**'i seçin ve durumu **Disable** (Kapat) olarak ayarlayın.
   - Aynı işlemi **Bot 2** için de uygulayın.
   *(Bu ayar, botların gruptaki tüm mesajları okuyabilmesine olanak tanır.)*

2. **Bot-to-Bot İletişimini Açma (`/setbot2bot`):**
   - `@BotFather`'a `/setbot2bot` komutunu yazın.
   - **Bot 1**'i seçin ve **Enable** (Etkinleştir) seçeneğine tıklayın.
   - Aynı işlemi **Bot 2** için de uygulayın.
   *(Normalde botlar başka botların mesajlarını okuyamaz, bu ayar bu kısıtlamayı kaldırır.)*

3. **Grup Yöneticiliği:**
   - Telegram'da yeni bir "Yeni Grup" oluşturun veya mevcut bir grubunuzu kullanın.
   - Hem **Bot 1**'i hem de **Bot 2**'yi bu gruba ekleyin.
   - Grup ayarlarına girip her iki bota da **Yönetici (Admin)** yetkisi verin.

### 🆔 Adım 3: Grup Chat ID Alma

Botun doğru gruba mesaj gönderebilmesi için grubun benzersiz kimlik numarasını (Chat ID) öğrenmeniz gerekir. Bunu öğrenmek için aşağıdaki alternatif yöntemlerden birini kullanabilirsiniz:

**Yöntem 1: Web Telegram Kullanarak (En Kolay Yöntem)**
1. Bilgisayarınızdan tarayıcınızı açın ve [Telegram Web](https://web.telegram.org/)'e giriş yapın.
2. Oluşturduğunuz gruba tıklayın.
3. Tarayıcının üst kısmındaki adres çubuğuna bakın. Link şu şekilde görünecektir: `https://web.telegram.org/a/#-1001234567890` veya `https://web.telegram.org/k/#-1001234567890`.
4. Buradaki `#` işaretinden sonraki eksi (`-`) ile başlayan numara (örn: `-1001234567890`) sizin **Chat ID**'nizdir.

**Yöntem 2: API Üzerinden Öğrenme (Manuel Yöntem)**
1. Grubunuza botunuzu eklediğinizden emin olun ve gruba `test` yazıp gönderin.
2. Tarayıcınızda yeni bir sekme açın ve şu adrese gidin (kendi bot token'ınızı yazın):
   `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
3. Açılan karmaşık yazılar (JSON) içerisinde `"chat":{"id":-1001234567890` gibi bir kısım bulun. Oradaki eksi ile başlayan sayı sizin Chat ID'nizdir.

**Yöntem 3: ID Botları Kullanarak (Alternatif)**
1. Oluşturduğunuz gruba **[@RawDataBot](https://t.me/RawDataBot)** veya **[@GetIDBot](https://t.me/GetIDBot)** ekleyin.
2. Bot gruba katıldığında size bir mesaj gönderecek ve "Chat" veya "Message" bölümünün altında id numaranızı (örn: `-100...`) gösterecektir. (Not: Bazı ID botları zaman zaman çalışmayabilir veya kapanmış olabilir, bu durumda diğer yöntemleri kullanın).

**Önemli Not:** Grup Chat ID'leri her zaman eksi (`-`) işareti ile başlar ve genellikle `-100` ile devam eder. Bu ID numarasını kopyalayıp arayüzdeki **Telegram Chat ID** kutucuğuna eksiksiz (başındaki eksi işareti dahil) yapıştırın.

---

## 📱 2. iOS (iPhone) Otomatik SMS Kestirmesi (Shortcuts)

Spor İstanbul rezervasyonu sırasında sistem size bir SMS kodu gönderir. Bu adımla birlikte, telefonunuza kod geldiği anda iPhone'unuz bu kodu saniyesinde yakalayıp Telegram'daki **Bot 2** üzerinden gruba iletecek, **Bot 1** de bu kodu okuyup rezervasyonu tamamlayacaktır.

### ⚙️ Otomasyon Oluşturma Adımları:

1. iPhone'unuzda yüklü olan **Kestirmeler (Shortcuts)** uygulamasını açın.
2. Alt menüden **Otomasyon (Automation)** sekmesine dokunun ve sağ üstteki **+** (artı) butonuna basın.
3. Arama kutusuna "Mesaj" yazın ve **Mesaj (Message)** seçeneğine tıklayın.
   - **İçerik Şunları İçeriyorsa:** Kutuya `onay kodunuz` yazın. (Spor İstanbul SMS'lerinde bu ifade geçer.)
   - **Çalıştırma Seçeneği:** **Hemen Çalıştır (Run Immediately)** seçeneğini işaretleyin. (Bu, size sormadan direkt kodu Telegram'a atmasını sağlar.)
   - **Çalıştırıldığında Bildir:** Tercihen **Kapalı** duruma getirin.
4. **İleri (Next)** butonuna basın ve ardından **Boş Yeni Otomasyon (New Blank Automation)** kutucuğunu seçin.
5. "İşlem Ekle" butonuna basın ve arama çubuğuna **URL İçeriğini Al (Get Contents of URL)** yazıp bu eylemi ekleyin.

### 🌐 HTTP İsteği Yapılandırması:

"URL İçeriğini Al" eyleminin üzerine tıklayarak aşağıdaki şekilde tam olarak doldurun:

- **URL Kısmı:** `https://api.telegram.org/bot<BOT_2_TOKEN>/sendMessage`
  *(Dikkat: `<BOT_2_TOKEN>` yazan yere Bot 2'nin tokenını kopyalayıp yapıştırın. `bot` kelimesini silmeyin!)*
- **Yöntem (Method):** `POST` olarak seçin.
- **İstek Gövdesi (Request Body):** `JSON` olarak seçin.
- Aşağıdan **Yeni Alan Ekle ➔ Metin (Text)** diyerek 2 adet alan oluşturun:

  **Alan 1 (Metin):**
  - **Anahtar (Key):** `chat_id`
  - **Değer (Value):** `-1234567890` *(Kendi Grup Chat ID'nizi yazın)*

  **Alan 2 (Metin):**
  - **Anahtar (Key):** `text`
  - **Değer (Value):** Kutuya tıklayın, klavyenin üstündeki "Değişken Seç" veya doğrudan menüden **Kestirme Girdisi (Shortcut Input)** seçeneğini ekleyin. Fakat **Kestirme Girdisi** metninin en başına Bot 1'in adını yazmalısınız.
  - Örnek Görünüm: `@kendi_bot_adiniz Kestirme Girdisi`
  *(Başına Bot 1'in kullanıcı adını etiketleyerek eklemek, Telegram'ın bot mesajını diğer bota iletmesini kesinleştirir!)*

Otomasyonu kaydedin. Artık size içinde "onay kodunuz" geçen bir mesaj geldiğinde, telefonunuz bunu saniyesinde Telegram grubuna yollayacaktır.

---

## 🚀 3. Bot Özellikleri ve Başlatma Adımları

Tüm altyapıyı kurduğunuza göre botu çalıştırmaya hazırsınız!

1. **Arayüzü Başlatma:** Proje klasöründeki `baslat.bat` dosyasına çift tıklayın veya terminalden `python gui.py` komutunu çalıştırın.
2. **Kullanıcı Bilgileri:** TC Kimlik Numaranız, Şifreniz, **Bot 1'in Token'ı** ve **Grup Chat ID**'nizi ilgili yerlere eksiksiz girin.
3. **Tarama Aralığı (Saniye):** Botun boş yerleri kaç saniyede bir kontrol edeceğini yazın (Önerilen: **20 saniye**).
4. **Alarm Süresi:** Rezervasyon saatinizden kaç dakika önce size Telegram'dan hatırlatma mesajı atmasını istiyorsanız onu ayarlayın (Örn: 30 veya 45 dk).
5. **Seans Tercihleri:** Hangi gün ve saat aralıklarında rezervasyon istediğinizi işaretleyin.
6. **Kort Ayarları:** Kort 1 veya Kort 3 gibi seçimlerinizi yapın. Gelişmiş seçenekleri (Örn: Sadece belirli bir kortu yedek olarak alma) değerlendirebilirsiniz.
7. **Kaydet ve Başlat:** **"Ayarları Kaydet"** butonuna basarak verilerinizi kalıcı hale getirin, ardından **"Botu Başlat"** diyerek arkanıza yaslanın.

### 🛡️ Botun Önemli Güvenlik ve Performans Özellikleri:

- 🎭 **SweetAlert2 & Modal Desteği:** İBB Spor sitesindeki karmaşık SMS doğrulama kutucukları, aniden çıkan popup pencereler otomatik olarak aşılır.
- ⏱️ **Akıllı SMS Spam Koruması:** SMS kodu sistemde bir sebepten zaman aşımına uğrar veya geçersiz kalırsa, sisteme sürekli aynı geçersiz kodun yüklenmesini önlemek amacıyla 90 saniyelik güvenlik bekleme süresi devreye girer.
- 🧹 **Otomatik Webhook Temizleme:** Bot başlatılırken, geçmişten kalan ve mesaj akışını engelleyebilecek Telegram Webhook çakışmalarını otomatik olarak temizler. Bu sayede hiçbir mesajı kaçırmaz.
- 🔄 **Oturum Canlı Tutma:** Sistem sizi dışarı atsa bile bot otomatik olarak tekrar giriş yapar ve taramaya kaldığı yerden devam eder.

---
> 💡 **İpucu:** Bot çalışırken terminal penceresini (siyah ekran) kapatmayın, aksi takdirde bot kapanır. Arayüz ile birlikte her şey entegre çalışır. Sorunsuz rezervasyonlar! 🎾
