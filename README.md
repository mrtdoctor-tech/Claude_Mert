# Yerel Asistan

Tamamen **kendi bilgisayarında** çalışan, yazarak ya da sesli konuşabildiğin ve söylediklerini hatırlayan kişisel yapay zekâ asistanı.

- 🔒 **Gizli:** Konuşmalar, hafıza ve ses kayıtları bilgisayarından çıkmaz. Tek istisna, seçersen çevrimiçi yanıt sesi (aşağıya bak).
- 🧠 **Hatırlar:** Sohbetlerden önemli bilgileri (adın, ailen, işin, tercihlerin...) kendiliğinden öğrenir ve yeni sohbetlerde de bilir. Neyi hatırladığını **Hafıza** penceresinden görüp silebilir, kendin ekleyebilirsin.
- 💬 **Sohbet geçmişi:** Eski sohbetlerin sol menüde durur, kaldığın yerden devam edebilirsin.
- 🎤 **Sesli konuşma:** Mikrofonla konuş (ses, bilgisayarında Whisper ile yazıya çevrilir), asistan yanıtını sesli okusun.

## Kurulum (Windows, bir kerelik)

1. **Python:** Bilgisayarında **Anaconda** (veya Miniconda) varsa bir şey yapma; kurulum Anaconda'da **`asistan`** adında ayrı bir ortam açar (base'e ve diğer ortamlarına dokunmaz). Yoksa https://www.python.org/downloads/ → "Download Python" → kurulumun ilk ekranında **"Add python.exe to PATH"** kutusunu işaretle.
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

## Hangi model? (ekran kartına göre)

Model **ekran kartının belleğine (VRAM) sığarsa** hızlıdır; sığmazsa işlemcide çalışır ve dakikalarca bekletir.
Kural: modelin boyutu (`ollama list`) VRAM'den **1-2 GB küçük** olsun. Nerede çalıştığını görmek için soru sorduktan
sonra komut isteminde `ollama ps` yaz: **PROCESSOR** sütununda "100% GPU" görmelisin.

| Ekran kartı belleği | Önerilen sohbet modeli |
|---|---|
| Ekran kartı yok / zayıf dizüstü | `gemma3:1b` |
| 6-8 GB (ör. RTX 4060) | `gemma3:4b` (tamamen sığar, çok hızlı) |
| 12-16 GB | `gemma3:12b` |
| 24 GB ve üstü | daha büyük modeller (ör. 27b-31b) |

## Bilgisayarın yavaşsa

- **Daha küçük model:** Komut isteminde `ollama pull gemma3:1b` yaz, sonra **⚙️ Ayarlar**'dan bu modeli seç. Çok daha hızlıdır ama yanıtları daha basittir.
- **Hafıza için ayrı model:** Sohbette hızlı `gemma3:1b`'yi kullanırken **⚙️ Ayarlar → Hafıza modeli**'nde `gemma3:4b`'yi seç. Senin hakkındaki bilgileri arka planda, sen beklemezken daha doğru çıkarır; sohbetin hızı değişmez.
- **Daha hızlı ses tanıma:** **⚙️ Ayarlar → Ses tanıma kalitesi → Hızlı (base)**; çok yavaşsa **En hızlı (tiny)** (Türkçeyi daha az doğru anlar).
- **NVIDIA ekran kartı varsa:** ses tanıma kendiliğinden ekran kartında çalışır (`baslat.bat` ilk açılışta gereken ~1 GB'lık paketleri indirir). Sol alttaki özette **GPU** yazmalı; **⚙️ Ayarlar → Ses tanıma kalitesi → En iyi (large-v3-turbo)** ekran kartında hem hızlı hem en doğrusudur.
- **Diğer programları kapat:** Özellikle çok sekmeli tarayıcılar belleği doldurur, model yavaşlar.
- **İlk mesaj her zaman biraz yavaştır:** Model belleğe yükleniyor. Sonrakiler daha hızlıdır. Model 1 saat kullanılmazsa bellekten çıkarılır.
- Asistan yeni bilgileri öğrenme işini sen 5 dakika sustuktan sonra (ya da Hafıza penceresini açınca) yapar, böylece konuşmanı yavaşlatmaz. Yeni öğrendiklerini bir sonraki sohbette kullanır.
- **Eski/zayıf işlemcilerde** (örneğin 2 çekirdekli, 2015 öncesi dizüstüler) `gemma3:1b` kullan; 4b dakikalarca bekletebilir. Cevap altındaki ⏱ sayacı ile karşılaştırabilirsin.

## Verilerin nerede?

- **Sohbetler ve hafıza:** proje klasöründeki **`data\asistan.db`**. Proje klasörü OneDrive'daysa iki bilgisayar aynı sohbetleri ve hafızayı paylaşır. **Asistanı aynı anda iki bilgisayarda açma** (açarsan ekranda uyarı çıkar); yedeklemek için `data` klasörünü kopyala.
- **Ayarlar ve Python ortamı:** her bilgisayarın kendi `%LOCALAPPDATA%\YerelAsistan` klasöründe (model seçimi gibi ayarlar bilgisayara özel).

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| "Ollama'ya bağlanılamadı" | Başlat menüsünden Ollama'yı aç, sonra tekrar dene. |
| "... modeli yüklü değil" | Komut isteminde mesajdaki `ollama pull ...` komutunu çalıştır. |
| Yanıtlar çok yavaş | Yukarıdaki "Bilgisayarın yavaşsa" bölümüne bak. |
| "No Python at ..." hatası | Bu bilgisayarda bir kez `kurulum.bat`'ı çalıştır (2.5'ten itibaren her bilgisayarın kendi Python ortamı var). |
| Kurulum Pinokio / Miniconda / Anaconda Python'unu kullanıyor | Python'u python.org'dan kur, `.venv` klasörünü sil, `kurulum.bat`'ı tekrar çalıştır. (`pyvenv.cfg`'yi elle düzenleme; yeni `kurulum.bat` bozuk `.venv`'i kendisi yeniler.) |
| Mikrofon çalışmıyor | Tarayıcı adres çubuğundaki kilit/mikrofon simgesinden izin ver. |

## Güncelleme

- **GitHub Desktop ile:** **Fetch origin**'e, ardından çıkan **Pull origin**'e bas. Asistan açıksa kendini yeni sürümle yeniden başlatır; sayfada uyarı çıkınca **F5**'e bas.
- **ZIP ile:** GitHub'dan ZIP'i yeniden indirip dosyaları eski klasörün üzerine kopyala (`data` klasörüne dokunulmaz).

Yeni paket gerektiren güncellemelerde `baslat.bat`'ı bir kez kapatıp açman gerekir; paketleri kendiliğinden kurar.

## Sürüm geçmişi

Kullandığın sürüm, asistanın sol menüsünün en altında ve siyah pencerenin ilk satırında yazar.

- **2.9** — Ses tanıma NVIDIA ekran kartı varsa onda çalışır (çok daha hızlı); yoksa ya da sorun çıkarsa kendiliğinden işlemciye geçer. Sayaçta ve sol altta GPU/CPU yazar. Yeni seçenek: "En iyi (large-v3-turbo)".
- **2.8** — Model artık 8192 token'lık metin okuyabiliyor (Ollama'nın varsayılanı 4096'ydı; uzun sohbetlerde başı, hafızayla birlikte, sessizce kesiliyordu).
- **2.7** — Kurulum, Anaconda standart olmayan bir klasörde olsa da (ör. `C:\Apps\anaconda3`) bulur.
- **2.6** — Anaconda varsa asistan onun içinde ayrı bir `asistan` ortamına kurulur. Ayarlar her bilgisayarda ayrı; sohbetler ve hafıza OneDrive ile ortak. Asistan aynı anda başka bir bilgisayarda da açıksa uyarı çıkar.
- **2.5** — Python ortamı artık proje klasöründe değil, her bilgisayarın kendi klasöründe (`%LOCALAPPDATA%\YerelAsistan`). Proje klasörü OneDrive ile iki bilgisayar arasında eşitlenince ortamlar birbirini bozuyordu. `kurulum.bat` Python bulamazsa bilgisayardaki Python'ları listeler.
- **2.4** — "Saat kaç?", "Bugün ayın kaçı?" gibi sorular bilgisayarın saatinden, anında ve her zaman doğru cevaplanır. Sol altta ayarların özeti (model, hafıza modeli, ses tanıma, ses) görünür; tıklayınca Ayarlar açılır. Ses tanımaya "En hızlı (tiny)" seçeneği eklendi.
- **2.3** — Yavaş bilgisayarlarda büyük hızlanma: model sohbeti her mesajda baştan okumak zorunda kalmıyor. Hafıza öğrenmesi 5 dakika sessizlikten sonra çalışır; yeni öğrenilen bilgiler bir sonraki sohbette kullanılır.
- **2.2** — Cevap süresi sayacı: her cevabın altında ilk kelimenin ve tüm cevabın kaç saniyede geldiği, kullanılan model (sesli sorularda ses→yazı süresi de) görünür.
- **2.1** — Asistan saati doğru söyler.
- **2.0** — Hafıza kalitesi: ayrı "Hafıza modeli" seçilebilir (sohbet hızlı küçük modelle, öğrenme arka planda daha akıllı modelle). Yalnızca senin mesajlarından öğrenir, bilgileri Türkçe yazar, aynı bilgiyi iki kez kaydetmez.
- **1.9** — Düzeltme: sesli sohbetten sonra bilgiler hafızaya kaydedilmiyordu. Hafıza penceresi açılınca son konuşmalar hemen taranır. Asistan artık "kaydettim" diye uydurmaz.
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
