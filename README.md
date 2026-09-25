# Yerel Asistan

Tamamen **kendi bilgisayarında** çalışan, yazarak ya da sesli konuşabildiğin ve söylediklerini hatırlayan kişisel yapay zekâ asistanı.

- 🔒 **Gizli:** Konuşmalar, hafıza ve ses kayıtları bilgisayarından çıkmaz. İnternet yalnızca kurulumda (model indirme) kullanılır.
- 🧠 **Hatırlar:** Sohbetlerden önemli bilgileri (adın, ailen, işin, tercihlerin...) kendiliğinden öğrenir ve yeni sohbetlerde de bilir. Neyi hatırladığını **Hafıza** penceresinden görüp silebilir, kendin ekleyebilirsin.
- 💬 **Sohbet geçmişi:** Eski sohbetlerin sol menüde durur, kaldığın yerden devam edebilirsin.
- 🎤 **Sesli konuşma:** Mikrofonla konuş (ses, bilgisayarında Whisper ile yazıya çevrilir), asistan yanıtını Windows'un sesiyle okusun.

## Kurulum (Windows, bir kerelik)

1. **Python'u kur:** https://www.python.org/downloads/ → "Download Python" → kurulumun ilk ekranında **"Add python.exe to PATH"** kutusunu işaretle.
2. **Ollama'yı kur:** https://ollama.com/download → Windows sürümünü indirip kur. (Yapay zekâ modelini çalıştıran program; kurulumdan sonra arka planda kendiliğinden çalışır.)
3. **Bu projeyi indir:** GitHub sayfasında yeşil **Code** butonu → **Download ZIP** → ZIP'i örneğin `Belgeler\Asistan` klasörüne çıkar.
4. Klasördeki **`kurulum.bat`** dosyasına çift tıkla. Paketleri ve yapay zekâ modelini (~3 GB) indirir; internet hızına göre 5-20 dakika sürebilir.

> Windows "bilgisayarınız korundu" uyarısı gösterirse **Ek bilgi → Yine de çalıştır**'a tıkla.

## Kullanım

**`baslat.bat`**'a çift tıkla. Tarayıcında asistan açılır. Kullandığın sürece siyah pencereyi kapatma; kapatınca asistan da kapanır.

- **Yazarak:** Mesajını yaz, Enter'a bas (alt satıra geçmek için Shift+Enter).
- **Sesli:** 🎤'a bas, konuş, bitirince 🎤'a tekrar bas. Sesli sorduğun sorulara asistan sesli yanıt verir. Her yanıtın okunmasını istersen sağ üstteki **🔊 Sesli yanıt**'ı aç.
  - İlk sesli kullanımda ses tanıma modeli bir kez indirilir (~500 MB), birkaç dakika sürebilir.
  - Tarayıcı mikrofon izni isterse **İzin ver** de.
  - Türkçe ses yoksa: Windows **Ayarlar → Zaman ve dil → Konuşma → Ses ekle → Türkçe**.

## Daha akıllı bir model istersen

Varsayılan model `gemma3:4b` çoğu bilgisayarda rahat çalışır. Bilgisayarın güçlüyse (16 GB+ RAM ya da iyi bir ekran kartı) daha büyük bir model daha iyi yanıt verir. Komut istemine (Başlat → "cmd") yaz:

```
ollama pull gemma3:12b
```

Sonra asistanda **⚙️ Ayarlar → Yapay zekâ modeli**'nden seç.

## Verilerin nerede?

Tüm sohbetler, hafıza ve ayarlar proje klasöründeki **`data`** klasöründe durur. Yedeklemek için bu klasörü kopyalaman yeterli. Başka bir bilgisayara taşırken de bu klasörü yanında götür.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| "Ollama'ya bağlanılamadı" | Başlat menüsünden Ollama'yı aç, sonra tekrar dene. |
| "... modeli yüklü değil" | Komut isteminde mesajdaki `ollama pull ...` komutunu çalıştır. |
| Yanıtlar çok yavaş | Ayarlar'dan daha küçük bir model seç (ör. `ollama pull gemma3:1b`). |
| Mikrofon çalışmıyor | Tarayıcı adres çubuğundaki kilit/mikrofon simgesinden izin ver. |

## Teknik bilgi

- Sunucu: Python + FastAPI (`app/`), yalnızca `127.0.0.1:8765` adresinden, yani sadece bu bilgisayardan erişilebilir.
- Yapay zekâ: [Ollama](https://ollama.com) (yerel).
- Ses → yazı: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (yerel). Yazı → ses: tarayıcıdaki çevrimdışı Windows sesleri.
- Veritabanı: SQLite (`data/asistan.db`).
