# Yerel Asistan

Tamamen **kendi bilgisayarında** çalışan, yazarak ya da sesli konuşabildiğin ve söylediklerini hatırlayan kişisel yapay zekâ asistanı.

- 🔒 **Gizli:** Konuşmalar, hafıza ve ses kayıtları bilgisayarından çıkmaz. Tek istisna, seçersen çevrimiçi yanıt sesi (aşağıya bak).
- 🧠 **Hatırlar:** Sohbetlerden önemli bilgileri (adın, ailen, işin, tercihlerin...) kendiliğinden öğrenir ve yeni sohbetlerde de bilir. Neyi hatırladığını **Hafıza** penceresinden görüp silebilir, kendin ekleyebilirsin.
- 💬 **Sohbet geçmişi:** Eski sohbetlerin sol menüde durur, kaldığın yerden devam edebilirsin.
- 🎤 **Sesli konuşma:** Mikrofonla konuş (ses, bilgisayarında Whisper ile yazıya çevrilir), asistan yanıtını sesli okusun.

## Kurulum (Windows, bir kerelik)

1. **Python'u kur:** https://www.python.org/downloads/ → "Download Python" → kurulumun ilk ekranında **"Add python.exe to PATH"** kutusunu işaretle.
2. **Ollama'yı kur:** https://ollama.com/download → Windows sürümünü indirip kur. (Yapay zekâ modelini çalıştıran program; kurulumdan sonra arka planda kendiliğinden çalışır.)
3. **Bu projeyi indir:** GitHub sayfasında yeşil **Code** butonu → **Download ZIP** → ZIP'i örneğin `Belgeler\Asistan` klasörüne çıkar.
4. Klasördeki **`kurulum.bat`** dosyasına çift tıkla. Paketleri ve yapay zekâ modelini (~3 GB) indirir; internet hızına göre 5-20 dakika sürebilir.

> Windows "bilgisayarınız korundu" uyarısı gösterirse **Ek bilgi → Yine de çalıştır**'a tıkla.

## Kullanım

**`baslat.bat`**'a çift tıkla. Tarayıcında asistan açılır. Kullandığın sürece siyah pencereyi kapatma; kapatınca asistan da kapanır.

- **Yazarak:** Mesajını yaz, Enter'a bas (alt satıra geçmek için Shift+Enter).
- **Sesli:** 🎤'a bas ve konuş. Sustuğunda asistan bunu anlar ve mesajını gönderir. Sesli sorduğun sorulara sesli yanıt verir, sonra mikrofonu kendiliğinden yeniden açar; böylece karşılıklı konuşabilirsin. 8 saniye bir şey söylemezsen sesli sohbet biter. Bunu istemezsen **⚙️ Ayarlar → Sesli sohbet** kutusunu kapat. Her yazılı yanıtın da okunmasını istersen sağ üstteki **🔊 Sesli yanıt**'ı aç.
  - İlk sesli kullanımda ses tanıma modeli bir kez indirilir (~500 MB), birkaç dakika sürebilir.
  - Tarayıcı mikrofon izni isterse **İzin ver** de.
  - **Yanıt sesi** (⚙️ Ayarlar): Varsayılan **Emel**, doğal bir Türkçe kadın sesi. Bu ses Microsoft'un sunucusunda üretilir: yalnızca okunacak yanıt metni Microsoft'a gönderilir, mesajların ve hafızan gönderilmez. İnternet yoksa o cümle Windows sesiyle okunur. Tamamen internetsiz kalmak istersen **Windows sesi**'ni seç (Türkçe'de yalnızca erkek sesi "Tolga" var).
  - Windows sesinde Türkçe yoksa: Windows **Ayarlar → Zaman ve dil → Konuşma → Ses ekle → Türkçe**.

## Daha akıllı bir model istersen

Varsayılan model `gemma3:4b` çoğu bilgisayarda rahat çalışır. Bilgisayarın güçlüyse (16 GB+ RAM ya da iyi bir ekran kartı) daha büyük bir model daha iyi yanıt verir. Komut istemine (Başlat → "cmd") yaz:

```
ollama pull gemma3:12b
```

Sonra asistanda **⚙️ Ayarlar → Yapay zekâ modeli**'nden seç.

## Bilgisayarın yavaşsa

- **Daha küçük model:** Komut isteminde `ollama pull gemma3:1b` yaz, sonra **⚙️ Ayarlar**'dan bu modeli seç. Çok daha hızlıdır ama yanıtları daha basittir.
- **Daha hızlı ses tanıma:** **⚙️ Ayarlar → Ses tanıma kalitesi → Hızlı (base)**.
- **Diğer programları kapat:** Özellikle çok sekmeli tarayıcılar belleği doldurur, model yavaşlar.
- **İlk mesaj her zaman biraz yavaştır:** Model belleğe yükleniyor. Sonrakiler daha hızlıdır. Model 1 saat kullanılmazsa bellekten çıkarılır.
- Asistan yeni bilgileri öğrenme işini sen 30 saniye sustuktan sonra yapar, böylece konuşmanı yavaşlatmaz.

## Verilerin nerede?

Tüm sohbetler, hafıza ve ayarlar proje klasöründeki **`data`** klasöründe durur. Yedeklemek için bu klasörü kopyalaman yeterli. Başka bir bilgisayara taşırken de bu klasörü yanında götür.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| "Ollama'ya bağlanılamadı" | Başlat menüsünden Ollama'yı aç, sonra tekrar dene. |
| "... modeli yüklü değil" | Komut isteminde mesajdaki `ollama pull ...` komutunu çalıştır. |
| Yanıtlar çok yavaş | Yukarıdaki "Bilgisayarın yavaşsa" bölümüne bak. |
| Kurulum Pinokio / Miniconda / Anaconda Python'unu kullanıyor | Python'u python.org'dan kur, `.venv` klasörünü sil, `kurulum.bat`'ı tekrar çalıştır. (`pyvenv.cfg`'yi elle düzenleme; yeni `kurulum.bat` bozuk `.venv`'i kendisi yeniler.) |
| Mikrofon çalışmıyor | Tarayıcı adres çubuğundaki kilit/mikrofon simgesinden izin ver. |

## Güncelleme

- **GitHub Desktop ile:** **Fetch origin**'e, ardından çıkan **Pull origin**'e bas. Asistan açıksa kendini yeni sürümle yeniden başlatır; sayfada uyarı çıkınca **F5**'e bas.
- **ZIP ile:** GitHub'dan ZIP'i yeniden indirip dosyaları eski klasörün üzerine kopyala (`data` klasörüne dokunulmaz).

Yeni paket gerektiren güncellemelerde `baslat.bat`'ı bir kez kapatıp açman gerekir; paketleri kendiliğinden kurar.

## Sürüm geçmişi

Kullandığın sürüm, asistanın sol menüsünün en altında ve siyah pencerenin ilk satırında yazar.

- **1.8** — Mikrofon konuşmanın bittiğini kendisi anlar (tekrar basmaya gerek yok). Sesli sohbet: yanıt okununca mikrofon kendiliğinden yeniden açılır.
- **1.7** — Güncellemeden sonra asistan kendini yeniden başlatır; açık sayfada "yeni sürüm yüklendi, F5'e bas" uyarısı çıkar.
- **1.6** — Sürüm numarası eklendi; güncellemeden sonra tarayıcı artık eski arayüzü göstermiyor.
- **1.5** — Güncellemeden sonra tarayıcının eski dosyaları kullanması engellendi (ilk adım).
- **1.4** — Kadın sesi: Microsoft Emel (Ayarlar → Yanıt sesi). `baslat.bat` yeni paketleri kendiliğinden kurar.
- **1.3** — `kurulum.bat` doğru Python'u seçer (Pinokio/Miniconda değil), bozuk `.venv`'i yeniler.
- **1.2** — Hızlandırma: yanıt cümle cümle okunur, hafıza öğrenme boşta çalışır, model bellekte kalır.
- **1.1** — Proje notları (CLAUDE.md).
- **1.0** — İlk sürüm: sohbet, kalıcı hafıza, sohbet geçmişi, sesli konuşma.

## Teknik bilgi

- Sunucu: Python + FastAPI (`app/`), yalnızca `127.0.0.1:8765` adresinden, yani sadece bu bilgisayardan erişilebilir.
- Yapay zekâ: [Ollama](https://ollama.com) (yerel).
- Ses → yazı: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (yerel). Yazı → ses: [edge-tts](https://github.com/rany2/edge-tts) ile Microsoft sinirsel sesleri (çevrimiçi) ya da tarayıcıdaki çevrimdışı Windows sesleri.
- Veritabanı: SQLite (`data/asistan.db`).
