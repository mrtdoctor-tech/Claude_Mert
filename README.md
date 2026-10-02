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

## Ses ile tanıma (3.0)

Asistan kimin konuştuğunu sesinden anlar. Özel bilgiler (hafıza, eski sohbetler) yalnızca tanıdığı kişiye açılır.

1. **Ayarlar → 🎙️ Ses profilleri → "+ Ses tanıt"**. Adını yaz (ör. `Mert`), "Kaydı başlat"a bas ve ekrana gelen 3 kısa
   cümleyi normal sesinle oku (cümleler Türkçedeki bütün sesleri içerecek şekilde seçildi; kayıttan önce ekranda görünür). **İlk tanıtılan kişi yöneticidir**; o ana kadarki sohbetler ve hafıza onun olur.
2. Aynı yerden eşin için de tanıt (ör. `Sezin`). Onun hafızası ve sohbetleri ayrıdır.
3. Mikrofonla konuşunca ekranın altında adın yazar (**👤 Mert · yönetici**). Sonra klavyeden yazdıkların da senin sayılır.
4. Tanınmayan bir ses konuşursa ya da klavyeden **`1234`** yazılırsa **Misafir** moduna geçilir: genel sorular cevaplanır,
   özel bilgiler söylenmez, misafirin yazdıkları hafızaya karışmaz. **Ayarlar**'ı yalnızca yönetici görür; Sezin ve misafirler yöneticinin seçtiği ayarlarla kullanır, yeni ses tanıtamaz. Kilidi yalnızca tanınan bir ses açar.
5. Yönetici olarak oturumundayken **`Sezin1234`** yazarsan Sezin'in oturumuna geçersin (test etmek için).
6. **Şifre (sesin değişirse):** Ayarlar → Ses profilleri → kişinin yanındaki **🔑**. En az 6 karakter, içinde harf ve
   rakam olsun, `1234` içermesin (ör. `Kartal77`). Sesin tanınmadığında (hastayken) şifreni mesaj kutusuna yazıp gönder;
   kendi oturumuna geçersin. Şifre asistana gitmez, hiçbir yere açık yazılmaz. Misafir 5 kez yanlış denerse şifreyle giriş
   10 dakika kapanır. Sezin'in şifresini de sen belirlersin.
7. **🛡️ Güvenlik kaydı** (yalnızca yönetici görür): tanınmayan sesler, misafir mesajları, kilitlemeler ve "benzerlik" puanları.

İlk kullanımda yaklaşık 40 MB'lık ses parmak izi modeli bir kez indirilir; sonra tamamen internetsiz çalışır.
Uyarı: Bu bir caydırıcıdır, güçlü bir kilit değildir (ses kaydıyla kandırılabilir). Asıl koruma için Windows hesabına
şifre koy.

## Neler yapabilirim?

Asistanın yapabildikleri ve örnek komutlar (ör. "20 dakikalık sayaç kur") **[NELER_YAPABILIR.md](NELER_YAPABILIR.md)**
dosyasında. Aynı sayfa uygulamada sol menüdeki **❓ Neler yapabilirim?** düğmesiyle de açılır.

## Verilerin nerede?

- **Sohbetler ve hafıza:** proje klasöründeki **`data\asistan.db`** (`C:\Apps\Claude_Mert\data`). Yalnızca bu bilgisayarda durur, buluta eşitlenmez; yedeklemek için `data` klasörünü kopyala.
- **Ayarlar ve Python ortamı:** bilgisayarın `%LOCALAPPDATA%\YerelAsistan` klasöründe.

> **Not (02.10.2026):** Eskiden proje OneDrive'daydı ve iki bilgisayar (laptop + ev bilgisayarı) aynı sohbetleri paylaşıyordu. Artık proje `C:\Apps\Claude_Mert`'te ve yalnızca ev bilgisayarında kullanılıyor. Sürüm geçmişindeki OneDrive / iki bilgisayar satırları o döneme aittir.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| "Ollama'ya bağlanılamadı" | Başlat menüsünden Ollama'yı aç, sonra tekrar dene. |
| "... modeli yüklü değil" | Komut isteminde mesajdaki `ollama pull ...` komutunu çalıştır. |
| Yanıtlar çok yavaş | Yukarıdaki "Bilgisayarın yavaşsa" bölümüne bak. |
| "No Python at ..." hatası | Bir kez `kurulum.bat`'ı çalıştır (Python ortamı proje klasöründe değil, `%LOCALAPPDATA%\YerelAsistan`'da tutulur). |
| Kurulum Pinokio / Miniconda / Anaconda Python'unu kullanıyor | Python'u python.org'dan kur, `.venv` klasörünü sil, `kurulum.bat`'ı tekrar çalıştır. (`pyvenv.cfg`'yi elle düzenleme; yeni `kurulum.bat` bozuk `.venv`'i kendisi yeniler.) |
| Mikrofon çalışmıyor | Tarayıcı adres çubuğundaki kilit/mikrofon simgesinden izin ver. |

## Güncelleme

- **GitHub Desktop ile:** **Fetch origin**'e, ardından çıkan **Pull origin**'e bas. Asistan açıksa kendini yeni sürümle yeniden başlatır; sayfada uyarı çıkınca **F5**'e bas.
- **ZIP ile:** GitHub'dan ZIP'i yeniden indirip dosyaları eski klasörün üzerine kopyala (`data` klasörüne dokunulmaz).

Yeni paket gerektiren güncellemelerde `baslat.bat`'ı bir kez kapatıp açman gerekir; paketleri kendiliğinden kurar.

## Sürüm geçmişi

Kullandığın sürüm, asistanın sol menüsünün en altında ve siyah pencerenin ilk satırında yazar.

- **3.37** — Yeni araç `araclar\asistani_ai_assistanta_tasi.bat`: asistanı kendi "asistan" ortamından "ai_assistant" ortamına taşır (önce deneme yapar; HourGlow betiklerinin kullandığı torch/numpy/whisper gibi paketler değişecekse hiçbir şey kurmadan durur). Geri almak için `araclar\asistan_ortamini_geri_al.bat`.
- **3.38** — Taşıma aracı artık yaptıklarını `%LOCALAPPDATA%\YerelAsistan\tasima_kaydi.txt` dosyasına yazıyor; ikinci kez çalıştırılırsa eski ortamın yedeğini ezmiyor. Yeni araç `araclar\durum_kontrol.bat`: asistanın hangi Python ortamını kullandığını, taşımanın bitip bitmediğini ve paketlerin çalışıp çalışmadığını gösterir.
- **3.39** — Taşıma aracı artık "ortamda hiç olmayan paketi eklemek" ile "kurulu bir paketin sürümünü değiştirmek" arasındaki farkı görüyor; yalnızca HourGlow'un kullandığı, zaten kurulu bir paket değişecekse duruyor (3.38'de "tokenizers" yüzünden gereksiz yere durmuştu).
- **3.40** — Yeni araç `araclar\comfyui_durum.bat`: ComfyUI'de neyin kurulu olduğunu (sürüm, ekran kartı, eklentiler, modeller, Fooocus'taki modeller, boş disk) gösterir; hiçbir şeyi değiştirmez. Rapor `Belgeler\comfyui_durum.txt`.
- **3.41** — Yeni araç `araclar\comfyui_yeni_kur.bat`: eskisine dokunmadan, kendi Python'u olan yeni bir ComfyUI kurar (`P:\Comfy\ComfyUI_yeni`), Fooocus modellerini kopyalamadan bağlar, ComfyUI-Manager ekler ve masaüstüne "ComfyUI (yeni)" başlatma dosyası koyar.
- **3.55** — Uydurma filtresinin eşiği −40'tan −60 dB'ye indi: bir Whisper parçası ancak ayrılmış vokal o parça boyunca gerçekten sessizse (ortalama −60 dB'nin altı) atılıyor. −40, 25 dB kısık (alçak sesli) gerçek bir vokali de atıyordu.
- **3.54** — Suno eşlemesine ikinci geçiş: Suno'nun şarkıda tekrarladığı ya da yerini değiştirdiği dizeler "TEKRAR / YER DEĞİŞTİ", metinde olmayan söylenişler "SUNO METNİNDE YOK" olarak kendi zamanında rapora girer, hiç söylenmeyen dizeler "SÖYLENMEDİ" listesinde; satırlar söyleniş sırasıyla. Ayrıca vokal kanalı sessizken Whisper'ın uydurduğu parçalar atılıyor (Palabras de Sal 2'nin sonunda 3:03'te olmayan bir nakarat satırı yazıyordu).
- **3.52** — Şarkının yanına `<şarkı adı>.suno.txt` (Suno'daki söz metni) konursa SÖZLER bölümü Suno'nun resmi metnini yazar, her dizeye Whisper'dan başlangıç zamanı verir (tekrar eden nakaratlar sırayla eşleşir; bulunamayan dize "?:??"); Whisper'ın farklı duyduğu dizeler ayrıca listelenir. `.suno.txt` eklenince/değişince şarkı yeniden analiz edilir.
- **3.51** — Klasör analizi tek komutla tüm adımları sırayla yapıyor ve ekranda adım adım gösteriyor: "🔎 1/1 Şarkı: ölçüm… hedef… BPM… sözler…" (resimde "ölçüm… yapay zekâ bakıyor…").
- **3.50** — Düzeltme: SÖZLER Asiye'nin içinde "[WinError 127] … cudnn_cnn64_9.dll" hatası veriyordu (ses tanımanın yüklediği cuDNN ile torch'unki çakışıyordu). Söz çıkarma artık ayrı bir alt süreçte çalışıyor.
- **3.49** — Müzik raporunun sonuna **SÖZLER** bölümü geldi: vokal Demucs ile ayrılır, Whisper (medium, ekran kartında) dili kendisi bulup sözleri satır satır başlangıç zamanıyla yazar; vokalsiz aralıklar ve ad-lib'ler işaretlenir, sözsüz parçada "enstrümantal, söz yok" yazar. HourGlow'un `analiz.py` betiği kullanılıyor (kopya yok). Tempo satırı bir ondalıkla.
- **3.48** — Müzik raporunda tempo artık iki kaynaklı: Asiye'nin kendi ölçümü ve HourGlow'un `hg_bpm.py` aracı yan yana; fark 2 BPM'den fazlaysa UYARI (biri ötekinin yarısı/iki katıysa söylenir), `hg_bpm` kararlılığı 0,7'nin altındaysa "Moises'te elle doğrula" notu. SES YÜKSEKLİĞİ bölümünde artık yalnızca değerler var; "yayın platformları için uygun" gibi değerlendirmeler kaldırıldı (hepsi HEDEF KONTROLÜ'nde).
- **3.47** — Müzik analiz raporunun en üstüne (DOSYA'dan hemen sonra) **HEDEF KONTROLÜ** eklendi: ses yüksekliği (−16 … −13 LUFS), gerçek tepe (en çok −3 dBTP), LRA (4–7 LU), kırpılma (0) ve biçim (24-bit / 44,1 kHz / stereo) için TAMAM ya da UYARI. Sohbetteki özette uyarı sayısı görünür.
- **3.46** — Analiz raporları ve betik envanteri artık BOM'suz UTF-8 ve LF satır sonuyla yazılıyor (proje dosya kuralı).
- **3.45** — Müzik analiz raporunda yapay zekâ yorumu kaldırıldı (−1,6 dBTP'ye "güvenli" diyor, dinamik için sıkıştırma öneriyordu); rapor yalnızca ölçümlerden oluşuyor, etiketler DOSYA bölümünde. Resimlerde "yapay zekânın gördükleri" duruyor.
- **3.44** — Müzik analizine gerçek tepe (true peak, dBTP) ve EBU R128 yükseklik aralığı (LRA) eklendi; eski "dinamik aralık" artık "bölüm yükseklik farkı" adıyla, yorumsuz. Yapay zekâ yorumu artık yarıda kesilmiyor ve tür tahmini yapmıyor. Betik envanteri her betiğin conda ortamını gösteriyor ve düz "conda activate" kullanan başlatma dosyalarını uyarıyor.
- **3.43** — "Gündem haberleri nedir?" artık gerçek haberleri getiriyor (önceden yapay zekâya gidiyor, o da eski/uydurma haber ve çalışmayan bağlantılar veriyordu); yapay zekâya haber ve bağlantı uydurmaması söylendi. Mikrofona sınırlayıcı eklendi: kalibrasyon artık sesi tam hedefe kadar yükseltebiliyor, yüksek anlar bozulmuyor.
- **3.42** — `baslat.bat` artık Ollama kapalıysa (ör. ComfyUI için ekran kartını boşaltmak üzere kapatıldıysa) onu kendiliğinden yeniden başlatıyor.
- **3.36** — Yeni araç `araclar\whisper_muzige_ekle.bat`: "muzik" ortamına OpenAI Whisper'ı ekler (önce deneme yapar; torch/numpy gibi hassas paketler değişecekse hiçbir şey kurmadan durur), sonra muzik_doctor.py ile kontrol eder. `ortam_yedekle.bat` aynı ortamın iki yazılışını ("ComfyUI"/"comfyui") tek yedekler.
- **3.35** — Yeni araç `araclar\ortam_yedekle.bat`: tüm conda ortamlarının paket listesini Belgeler\conda_yedek klasörüne yedekler (hiçbir şeyi değiştirmez); ortam sadeleştirmesinden önce güvence için.
- **3.34** — Betik envanteri düzeltildi: Python'un kendi parçaları (difflib, gc, importlib…) artık "paket" sayılmıyor; .bat/.ps1 dosyalarında yalnızca gerçekten açılan conda ortamları yazılıyor (açıklama satırlarındaki kelimeler değil).
- **3.33** — "Betiklerimi incele": HourGlowMusic\Scripts altındaki betikleri (çalıştırmadan) okuyup Asiye klasörüne "betik_envanteri.txt" yazar: her betiğin ne yaptığı (ilk not), kullandığı paketler, .bat dosyalarının hangi conda ortamını açtığı; asistanın kendi analizinin kapsadığı ve kapsamadığı paketler. Ortamları sadeleştirmeden önce neyin gerçekten gerektiğini görmek için.
- **3.32** — Fotoğraf anlama: sohbete resim ekle (📎, sürükle-bırak ya da ekran görüntüsünü Ctrl+V ile yapıştır) ve sor: "Bunda ne yazıyor?", "Bu fişin toplamı ne?", "Bu hata ne diyor?". Resim sohbette görünür ve bilgisayardan çıkmaz. Taranmış PDF'ler de artık okunuyor: sayfalar yapay zekâya tek tek gösterilip yazıya çevriliyor (en çok 20 sayfa). Güncellemeden sonra baslat.bat yeni paketi (pypdfium2) kendisi kurar.
- **3.31** — Sabah özeti: "Günaydın Asiye" (ya da "Sabah özeti", "Bugün neler var?") deyince tarih-saat, hava durumu, bugünkü Outlook toplantıları ve hatırlatmalar, alışveriş ve yapılacaklar listesi, gündemden 3 haber. Uyandırma sözü "Merhaba Asiye" olsa da "Günaydın Asiye" / "Selam Asiye" ile uyanır. Misafire yalnızca selam ve tarih.
- **3.30** — Eski sohbetlerde arama: sol üstteki 🔎 kutusuna kelime yaz (Türkçe harf/ek fark etmez), sonuca tıklayınca sohbet o mesajda açılır. Sohbette de sorulabilir: "Geçen hafta doktor hakkında ne konuşmuştuk?", "Dün ne konuşmuştuk?", "Eylül'de tatilden bahsetmiştik" — cevabın sonunda kaynak sohbetler yazar. Yalnızca kendi sohbetlerin; misafire kapalı.
- **3.29** — Dosya araması Türkçe harfleri yok sayıyor: söylenen "yayın takip", dosya adındaki "Yayin_Takip" ile eşleşiyor (ı/i, ş/s, ç/c, ğ/g, ö/o, ü/u).
- **3.28** — "HourGlow" gibi yabancı adlar: Ayarlar → Ses ve konuşma → "Özel kelimeler" (varsayılan "HourGlow"); ses tanıma bu kelimeleri bekler ve "Avır glo", "Hour glow" gibi yazılışları "HourGlow"a çevirir. Dosya araması artık Google Drive'a da bakıyor ve "HourGlow_Takip" ile "hour glow takip"i eşleştiriyor.
- **3.27** — "Hepsini yeniden analiz et", "Tekrar analiz eder misin?" gibi kısa cümleler de klasör analizi sayılıyor (önceden yapay zekâya gidiyordu ve olmayan şarkılar uyduruyordu). Yapay zekâya dosya analizi sonucu uydurmaması, bunun yerine doğru komutu önermesi söylendi.
- **3.26** — Klasör analizi (HourGlow Music): Google Drive'daki "HourGlowMusic\Scripts\Asiye" klasörüne attığın müzik ve resimleri "Klasördeki dosyaları analiz et" deyince analiz eder, her dosyanın yanına "….analiz.txt" raporu yazar. Müzikte süre, etiketler, ses yüksekliği (LUFS, tepe, dinamik, kırpılma), tempo (BPM), ton, parlaklık, stereo, bölümler ve yorum; resimde çözünürlük, EXIF, parlaklık/kontrast/doygunluk/keskinlik, baskın renkler ve yapay zekânın gördükleri. Her şey bilgisayarda yapılır; misafire kapalı. Güncellemeden sonra baslat.bat yeni paketleri (librosa, pyloudnorm, pillow) kendisi kurar.
- **3.25** — Yeni sohbetlerin adı tarih-saat ve ilk kelimeyle başlar ("202609301324 Merhaba"); sohbet adı sol listedeki ✏️ ile ya da üstteki başlığa tıklayarak değiştirilir. Güvenlik kaydında "🧹 Kaydı temizle" düğmesi. baslat.bat ile açılışta kimse oturum açmış sayılmaz (sesle ya da şifreyle tanınana kadar misafir); yalnızca güncelleme sonrası kendiliğinden yeniden başlamada son kişi geri gelir.
- **3.24** — Ayarlar sekmeli: Yapay zekâ, Ses ve konuşma, Mikrofon, Bağlantılar, Ses profilleri (Notlar ve listeler penceresindeki gibi). Son açılan sekme hatırlanır; Kaydet tüm sekmeleri birlikte kaydeder.
- **3.23** — Belge yükleme: 📎 düğmesiyle ya da dosyayı sohbete sürükleyerek PDF, Word (.docx), .txt, .md, .csv ekle; "Bu belgeyi özetle", "Teslim tarihi ne?" diye sor. Türkçe ve İngilizce belgeler (İngilizce belgeye Türkçe soru da olur). Belge bilgisayardan çıkmaz. Uzun belgelerde her soruda ilgili bölümler bulunur, özet bölüm bölüm çıkarılır. Güncellemeden sonra baslat.bat yeni paketleri (pypdf, python-docx) kendisi kurar.
- **3.22** — Müzik çalarken adla seslenme: müzik hiç susmadığı için ses 6 saniyelik, üst üste binen parçalar halinde kontrol ediliyor; "Merhaba Asiye" gibi iki kelimelik söz cümlenin ortasında da yakalanıyor ("Merhaba Asiye, müziği durdur"). Müzik üstünden gelen seste kimlik değiştirilmiyor (misafire düşmez).
- **3.21** — Müzik açıkken yanlışlıkla uyanma ve şarkı sözlerini mesaj sanma düzeltildi: adla seslenme kontrolünde ses tanımaya ad ipucu verilmiyor (müzikte adı "duyuyordu"), düğmeye basılmadan duyulan yabancı dilde şarkı sözleri ve ses tanımanın uydurduğu "İzlediğiniz için teşekkür ederim" gibi cümleler atılıyor; bu yüzden müzik seni misafire de düşürmüyor.
- **3.20** — Ses tanıma artık asistanın adını ve uyandırma sözünü bekliyor: hızlı söylenen "Merhaba Asiye" "Merhaba size" diye yazılıyordu.
- **3.19** — Adınla seslenme: mikrofona basmadan "Asiye, saat kaç?" ya da sadece "Asiye" deyince dinlemeye başlar (Ayarlar → Ses ve konuşma → "Adımla seslenince dinle"; istersen "Merhaba Asiye" gibi daha uzun bir söz). Mesaj kutusundaki 👂 ile duraklatılır. Duyulan ses bilgisayardan çıkmaz; adla başlamayan konuşmalar kaydedilmeden silinir.
- **3.18** — "Alışveriş listemi göster", "Listeme süt ekle", "Peyniri alışveriş listemden çıkar" gibi "listem" ile kurulan cümleler de anlaşılıyor. Yapay zekâ listelerin içini göremediği için artık "listen boş" diye tahmin etmiyor, doğru komutu öneriyor.
- **3.17** — Listeler rica cümlelerini de anlıyor: "Listeye peynir ekler misin?", "ekleyebilir misin", "yazar mısın", "…ekle lütfen", "Not alır mısın: …". Yapay zekâ artık listeye/hatırlatıcıya kendisi bir şey eklemiş gibi davranmıyor ("ekledim" diye uydurmuyor), doğru komutu öneriyor.
- **3.16** — Notlar ve listeler: "Listeye süt ekle", "Listemde ne var?", "Sütü listeden çıkar", "Not al: kombiyi ara". Sol menüde yeni "📝 Notlar ve listeler" penceresi (işaretleme, silme, ekleme). Kişiye özel, misafire kapalı.
- **3.15** — Ayarlar iki kolonlu ve kategorili (Yapay zekâ, Ses ve konuşma, Mikrofon, Bağlantılar, Ses profilleri). Yeni "🎙️ Mikrofonu ayarla": 5 saniyelik test kaydıyla sesinin seviyesini ölçer, gereken yükseltmeyi kendisi ayarlar (elle de değiştirilebilir, test kaydı dinlenebilir); sohbet, sesli komutlar ve ses tanıtma bu ayarla kaydeder.
- **3.14** — Kendiliğinden misafire düşme azaltıldı: asistan yeniden başlarsa (güncelleme, OneDrive) son 15 dakikadaki oturum geri gelir; mikrofon hoparlörden asistanın kendi cevabını duyarsa bunu "yabancı ses" saymaz ve mesaj olarak göndermez.
- **3.13** — "Müziğe devam et" düzeltildi: asistan Spotify'ın gizli yardımcı penceresine ("GDI+ Window") bakıp müziği çalıyor sanıyordu; artık yalnızca ana pencereye bakıyor.
- **3.12** — Müzik komutları Spotify uygulamasına doğrudan gidiyor ("Müziği durdur" artık çalışmalı); Spotify çalıyor mu duruyor mu bilir, "sonraki şarkı"dan sonra çalan şarkıyı söyler. Medya tuşları "genişletilmiş tuş" olarak gönderiliyor.
- **3.11** — Hava durumu ("Hava nasıl?", "Yarın yağmur yağacak mı?", "İstanbul'da hava nasıl?", "Bu hafta hava") ve haberler ("Haberler neler?", "Ekonomi haberleri"; tıklanabilir başlıklar). Ajandanın üstünde hava durumu satırı. İnternet gerektirdiği için misafirde kapalı. Şehir Ayarlar'dan.
- **3.10** — Ajandada Outlook takvimindeki kayıtlar da görünür (mavi, 📆; salt okunur, yalnızca yöneticiye). Asistanın Outlook'a eklediği hatırlatmalar iki kez görünmez.
- **3.9** — Sağda **📅 Ajanda** paneli: ay takvimi (hatırlatma olan günler noktalı), çalışan sayaçlar, yaklaşan hatırlatmalar; güne tıklayınca o günün listesi. Tanınan kişide görünür, misafirde gizli; başlıktaki 📅 ile açılıp kapanır. **Güvenlik kaydı** artık tablo: arama, olaya göre süzme, sütuna tıklayınca sıralama, "Excel'e aktar".
- **3.8** — Klasik Outlook kurulu ama içinde hesap yoksa asistan Outlook'u açmıyor ("hesap ekle" sihirbazı çıkmıyor), ne yapılacağını söylüyor.
- **3.7** — "Outlook bağlantısını dene" artık klasik Outlook kurulu değilse kurulum sihirbazını açmıyor, durumu söylüyor. Spotify mesajı ücretsiz hesaba göre düzeltildi.
- **3.6** — Outlook takvimi: hatırlatmaların Outlook'a da eklenir, telefonda bildirim çıkar (Ayarlar'dan açılır). Excel/dosya komutları ("Bütçe dosyasını Excel'de aç", "Excel'i kaydetmeden kapat"), müzik kontrolü ("sonraki şarkı", "sesi kıs") ve Spotify ("Spotify'da Tarkan çal"). Misafire kapalı.
- **3.5** — Hatırlatıcılar: "20 dakikalık sayaç kur", "yarın sabah 7'de uyandır", "15 Ekim'de ... hatırlat", "her gün saat 22'de ...". Zamanı gelince zil + sesli okuma; tarayıcı kapalıysa Windows bildirimi; asistan kapalıysa sonraki açılışta "kaçırılan". Kişiye özel. Yeni: sol menüde ⏰ Hatırlatıcılar ve ❓ Neler yapabilirim? (komut örnekleri: NELER_YAPABILIR.md).
- **3.4** — Kişisel şifre: hastalıkta sesin değişirse, şifreni yazarak kendi oturumuna girebilirsin (Ayarlar → Ses profilleri → 🔑). Şifre bilgisayarda şifrelenmiş (geri çözülemez) hâlde saklanır; misafir 5 kez yanlış denerse şifreyle giriş 10 dakika kapanır.
- **3.3** — Kısa cümlelerde ses tanıma iyileşti: tanıma sınırı 0,40 → 0,33 (ama iki kişiye çok yakın benziyorsa kimseye verilmez), asistan konuştukça sesini daha iyi öğrenir, çok kısa konuşunca "bir cümle daha söyle" der. Güvenlik kaydında her sesli mesaj, tüm kişilerin puanlarıyla yazılır.
- **3.2** — Ayarlar'ı artık yalnızca yönetici (Mert) görür ve değiştirebilir; Sezin ve misafirler, yöneticinin seçtiği ayarlarla çalışır.
- **3.1** — Ses tanıtmada okunacak 3 cümle, Türkçedeki bütün sesleri (ç, ğ, ı, ö, ş, ü, j...) içeren cümlelerle değişti ve kayıttan önce hepsi ekranda gösteriliyor. Misafir modunda Ayarlar gizli (kimse yeni ses tanıtamaz, ayar değiştiremez); Sezin Ayarlar'ı görür ama ses profillerini göremez.
- **3.0** — Ses ile tanıma: asistan Mert ve Sezin'i sesinden tanır, herkesin hafızası ayrı; tanınmayan ses ya da `1234` → Misafir modu; yönetici `Sezin1234` ile oturum değiştirebilir; güvenlik kaydı. Ayrıca yanıtların sonunda "(Şu an: …saat…)" yazması düzeltildi.
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
