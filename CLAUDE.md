# Proje notları: Yerel Asistan

Bu dosya, projeyi geliştiren Claude oturumları ve proje sahibi için ortak not defteridir.
Her oturumun sonunda "Geçmiş" ve "Sıradaki fikirler" bölümlerini güncelle.

**Sürüm kuralı (kullanıcı isteği):** Kullanıcıya giden her değişiklikte `VERSION` dosyasındaki numarayı artır
(küçük değişiklik 1.6 → 1.7; büyük yeni özellik 1.x → 2.0) ve README'deki "Sürüm geçmişi"ne Türkçe bir satır ekle.
Kullanıcıya cevapta yeni sürüm numarasını söyle ki ekranda doğru sürümü gördüğünü kontrol edebilsin.

## Kullanıcı hakkında

- Proje sahibi yazılımcı değil: açıklamaları **Türkçe**, sade ve adım adım yap; teknik terimleri açıkla.
- **Windows** kullanıyor. Kurulum/çalıştırma talimatları Windows'a göre olmalı (çift tıklanan `.bat` dosyaları).
- Öncelik **gizlilik**: veriler bilgisayardan çıkmamalı. Bulut servisi / API anahtarı gerektiren bir şey eklemeden önce kullanıcıya sor.

## Projenin amacı

Kullanıcının kendi bilgisayarında çalışan, güzel arayüzlü, yazılı ve sesli konuşulabilen,
konuşulanları hatırlayan ve yeni sohbetlerde de unutmayan kişisel yapay zekâ asistanı.

## Mimari

- `VERSION`: Sürüm numarası. Sol menünün altında ve `baslat.bat` penceresinde gösterilir; `index.html`'deki
  `{{VERSION}}` sunucuda doldurulur, CSS/JS adreslerine `?v=` olarak da eklenir (tarayıcı önbelleği eski dosya veremez).
- `run.py`: Sunucuyu `127.0.0.1:8765`'te başlatır ve tarayıcıyı açar (yalnızca yerelden erişilir).
  `reload=True` (watchfiles, `*.py` + `VERSION`): kullanıcı GitHub Desktop'tan Pull yapınca sunucu kendini yeniler.
  Arayüz `/api/version`'ı dakikada bir ve pencere odaklanınca kontrol eder, farklıysa "F5'e bas" der.
- `app/main.py`: FastAPI uç noktaları (sohbet akışı NDJSON, sohbetler, hafıza, ayarlar, ses→yazı).
- `app/llm.py`: Yerel **Ollama** istemcisi (`http://127.0.0.1:11434`). Varsayılan model `gemma3:4b`.
  `keep_alive=60m`: model bellekte kalır, her mesajda yeniden yüklenmez.
- **Ollama önbelleği (hız için kritik):** Ollama tek bir "okunmuş istem" önbelleği tutar. Sistem istemi veya geçmişin
  başı değişirse ya da araya başka bir istek (ör. hafıza çıkarma) girerse model tüm sohbeti baştan okur; zayıf
  bilgisayarda bu dakikalar sürer. Bu yüzden: sistem istemi sohbet başına sabit (`system_prompt_for`), geçmiş penceresi
  10'luk adımlarla kayar (`HISTORY_STEP`), saat yalnızca son mesajda, hafıza öğrenmesi 5 dk boşta (`IDLE_SECONDS=300`).
- `app/memory.py`: Sistem istemini kurar (hafızadaki bilgiler; tarih/saat YOK ki Ollama'nın istem önbelleği bozulmasın).
  Tarih ve saat `clock_note()` ile yalnızca modele giden **son kullanıcı mesajının sonuna** eklenir, veritabanına yazılmaz. Yeni bilgi çıkarma **kullanıcı 30 sn sustuktan sonra** çalışır (`schedule`/`cancel`); yeni mesaj veya
  mikrofon kullanımı bunu iptal eder, CPU cevaba kalır. Hangi mesajların tarandığı `meta` tablosundaki
  `memory_cursor` ile tutulur, uygulama kapanıp açılsa da kaldığı yerden devam eder.
  Mikrofon uç noktaları (`warmup`, `transcribe`) `schedule` ile sayacı **yeniden başlatır** (asla sadece `cancel` etme:
  sonra kimse yeniden kurmazsa öğrenme hiç çalışmaz — 1.8'deki hata buydu). Hafıza paneli açılınca
  `POST /api/memories/learn` (`learn_now`) hemen tarar. `_facts` küçük modellerin bozuk JSON biçimlerini tolere eder.
  Sistem istemi modele hafızaya kendisinin kayıt yapmadığını söyler (1b "kaydettim" diye uyduruyordu).
  2.0: Çıkarma **yalnızca kullanıcı mesajlarını** görür (asistan cevapları "hafızaya kaydettim" gibi çöp üretiyordu),
  dil `tr` ise **Türkçe istem** (`EXTRACT_PROMPT_TR`), `_learning` kilidi (paralel taramalar kopya kaydediyordu),
  `_key` ile noktalama/büyük-küçük harf duyarsız tekrar kontrolü. Ayar `memory_model` ("" = sohbet modeli);
  farklıysa `keep_alive=2m` ile çağrılır ki RAM'de kalıcı yer tutmasın.
- `app/quick.py`: "Saat kaç?", "Bugün ayın kaçı?" gibi kısa (≤60 karakter) sorular modele gitmeden bilgisayar saatinden
  cevaplanır (1b verilen saati bile yanlış okuyordu). `meta` olayında `instant: true`; sayaç "bilgisayar saatinden" yazar.
- `app/db.py`: SQLite (`data/asistan.db`): `conversations`, `messages`, `memories`, `meta`.
- `app/stt.py`: **faster-whisper** ile çevrimdışı ses→yazı (model ilk kullanımda indirilir).
- `app/config.py`: Ayarlar `data/settings.json` (asistan adı, model, whisper modeli, dil, yanıt sesi `tts_voice`).
- `app/tts.py` + `POST /api/tts`: **edge-tts** ile Microsoft sinirsel sesi (varsayılan `tr-TR-EmelNeural`, kadın) →
  MP3. **Çevrimiçi**: okunacak yanıt metni Microsoft'a gider; kullanıcı bunu bilerek seçti (2026-09-27).
  `tts_voice: "windows"` ise sunucu kullanılmaz, tarayıcı internetsiz Windows sesiyle okur.
- `static/`: Harici kütüphane kullanmayan arayüz (HTML/CSS/JS). Yazı→ses tarayıcıdaki
  ya `/api/tts`'ten gelen MP3'lerle (`speakOnline`: her cümle hemen istenir, sırayla çalınır, hata olursa o cümle
  Windows sesine düşer) ya da **yalnızca yerel** (`localService`) Windows sesleriyle (`speakLocal`) yapılır.
  Yanıt **cümle cümle**, yazılırken okunur (`sentenceSpeaker`). Mikrofona basınca Whisper modeli önden yüklenir.
  Mikrofon (`startListening`): Web Audio ile ses seviyesi ölçülür; ilk 300 ms ortam gürültüsü, konuşma ≥250 ms +
  1,3 sn sessizlik → kayıt kendiliğinden biter. Hiç konuşma yoksa 10 sn (elle) / 8 sn (otomatik) sonra kapanır.
  Sesli soruya yanıt okunduktan sonra (`listenAgainAfterReply`) mikrofon yeniden açılır; ayar `auto_listen`.
  `state.voiceRound` yeni mesaj/mikrofon tıklamasında artar ve bekleyen otomatik açmayı iptal eder.
  Sol altta `#config-summary`: model / hafıza modeli / ses tanıma / ses özeti (tıklayınca Ayarlar); eski "Her şey bu
  bilgisayarda saklanır" yazısının yerine (kullanıcı isteği).
  `replyTimer`: cevap beklerken canlı saniye sayacı, bitince "ses→yazı · ilk kelime · toplam · model" özeti
  (yalnızca o anki oturumda; veritabanına yazılmaz, eski sohbetlerde görünmez).
- `kurulum.bat` / `baslat.bat`: Windows kurulumu ve başlatma (CRLF satır sonları, `.gitattributes` ile korunuyor).
  **Python ortamı `%LOCALAPPDATA%\YerelAsistan\venv`** (2.5): proje klasörü kullanıcıda OneDrive'da ve iki bilgisayar
  arasında eşitleniyor; klasör içindeki `.venv` öbür bilgisayarı bozuyordu. `kurulum.bat` eski `.venv`'i siler, Python
  bulamazsa `where python` / `py -0p` çıktısını gösterir; `baslat.bat` ortam yoksa/bozuksa kurulumu işaret eder.
  Bulutta Windows yok: `.bat` dosyaları çalıştırılarak test edilemiyor, dikkatle gözden geçir (blok içinde `)` yok).
  `baslat.bat` her açılışta `pip install -r requirements.txt` çalıştırır; güncellemelerle gelen yeni paketler kendiliğinden kurulur.
- `data/` git'e girmez: kullanıcının özel verileri orada.

## Test

- Bulut ortamında Ollama yok: `app` sahte bir Ollama sunucusuyla (`/api/tags`, `/api/chat` akışlı + `format: json`)
  test edildi; arayüz headless Chromium ile ekran görüntüsü alınarak kontrol edildi.
- Kullanıcı gerçek Windows + Ollama üzerinde çalıştırdı (zayıf bir bilgisayarda); ayrıntılar "Geçmiş" bölümünde.

## Geçmiş

- **2026-09-25:** İlk sürüm yazıldı (sohbet, kalıcı hafıza, sohbet geçmişi, sesli giriş/çıkış, ayarlar,
  Türkçe README). Kullanıcı kurulumu henüz denemedi.
- **2026-09-27:** Kullanıcı zayıf bir bilgisayarda (ana bilgisayarı değil) denedi, çalışıyor. Şikâyet: yazı bittikten
  15-20 sn sonra sesli yanıt başlıyordu. Düzeltmeler: cümle cümle seslendirme, hafıza çıkarmayı boşta çalıştırma,
  Ollama `keep_alive`, sistem isteminden saati çıkarma, Whisper ön yükleme + `beam_size=1`, README'ye
  "Bilgisayarın yavaşsa" bölümü. Kullanıcının düzeltmeyi denemesi bekleniyor.
- **2026-09-27:** Kullanıcının bilgisayarında PATH'teki `python` Pinokio'nun miniconda'sıydı (`P:\pinokio\...`);
  `.venv` onunla kurulmuş, kullanıcı `pyvenv.cfg`'yi elle C:'ye çevirmiş ve ortam bozulmuş. `kurulum.bat` artık
  önce `py -3` başlatıcısını dener, 3.10+ ve conda olmayan Python ister, bozuk/conda tabanlı `.venv`'i silip yeniden kurar.
- **2026-09-27:** Kullanıcı kadın sesi istedi. Windows'un internetsiz tek Türkçe sesi erkek (Tolga); Piper'ın Türkçe
  sesleri (dfki, fahrettin, fettah) de bildiğimiz kadarıyla erkek. Seçenekler sunuldu, kullanıcı **Microsoft Emel
  (çevrimiçi)**'yi seçti → edge-tts eklendi, Ayarlar'a "Yanıt sesi" geldi. Gerçek Microsoft servisiyle bulutta test
  edilemedi (ağ kapalı); sahte edge_tts modülüyle sıra/durdurma/hata-geçişi test edildi. Kullanıcının denemesi bekleniyor.
  Kullanıcının **ana bilgisayarında NVIDIA ekran kartı var**.
- **2026-09-27:** Kullanıcı güncellemeden sonra hâlâ erkek ses duydu. Olası neden: tarayıcı eski `app.js`'i önbellekten
  kullanıyor. `/` ve `/static/` için `Cache-Control: no-cache` eklendi. Kullanıcıdan Ctrl+F5 ile yenilemesi ve
  Ayarlar'da "Yanıt sesi" görünüp görünmediğini / kırmızı uyarı çıkıp çıkmadığını bildirmesi istendi.
  Kullanıcının ekran görüntüsünde Ayarlar'da "Yanıt sesi" **yoktu** → eski arayüz çalışıyordu. Kullanıcı isteğiyle
  sürüm numarası eklendi (**1.6**), sürüm kuralı bu dosyanın başına yazıldı.
- **2026-09-27 (1.7):** Kullanıcı **GitHub Desktop** ile güncelliyor (ZIP değil; depo klonu, `main`). Pull sonrası sol altta
  `{{VERSION}}` gördü: dosyalar yeni ama `baslat.bat` yeniden başlatılmamış, eski sunucu çalışıyordu. Çözüm: otomatik
  yeniden başlatma (uvicorn reload) + sürüm uyuşmazlığı uyarısı. "Fetch origin ≠ Pull origin" farkı anlatıldı.
- **2026-09-27 (1.8):** Zayıf bilgisayarda `gemma3:1b`'ye geçti. Mikrofona iki kez basmak istemedi → sessizlik algılama
  + sesli sohbet modu (Chromium'da sahte mikrofon kaydıyla test edildi). Ayrıca 1b, aynı sohbette verilen adı sorulunca
  "Adın." dedi: geçmiş modele gidiyor (kod doğru), bu 1b'nin zayıflığı. Alternatif küçük model önerildi.
- **2026-09-27 (1.9):** Kullanıcı mikrofonu ilk kez denedi: çalışıyor; Whisper `small` yanlış, `base` doğru çevirdi
  (kullanıcı base'de). Model "adımı kaydettin mi?" sorusuna "Evet" dedi ama Hafıza boştu. Nedenleri: (1) warmup/transcribe
  bekleyen öğrenmeyi iptal edip yeniden kurmuyordu, sesli sohbet sonunda öğrenme hiç çalışmıyordu (düzeltildi);
  (2) model uyduruyordu (istem düzeltildi). Hafıza paneline "hemen tara" eklendi; hata varsa panelde görünür.
- **2026-09-27 (2.0):** Hafıza artık doluyor ama 1b ile kalite kötü: iki kez kaydedilmiş satırlar (paralel tarama),
  İngilizce bilgiler, "Mert'in adını hafızaya kaydettim" gibi asistan cümleleri, anlamca tekrarlar. Hepsi için düzeltme
  + ayrı hafıza modeli (zayıf bilgisayarda sohbet 1b, hafıza 4b önerildi). "Bursa" bilgisini kullanıcının gerçekten
  söyleyip söylemediği soruldu (1b uydurmuş olabilir). Kullanıcı eski hatalı kayıtları panelden elle silmeli.
- **2026-09-28 (2.1):** Kullanıcı Bursa'yı gerçekten söylemiş (uydurma değil). Asistan tarihi doğru, saati yanlış
  söyledi: 1.2'de saat istemden çıkarılmıştı. Artık `clock_note()` ile son mesaja ekleniyor.
- **2026-09-28 (2.2):** Kullanıcı isteğiyle cevap süresi sayacı; zayıf bilgisayar ile evdeki (NVIDIA) bilgisayarı
  karşılaştırmak için. Kullanıcıdan iki bilgisayardaki süreleri paylaşması beklenebilir.
- **2026-09-28 (2.3):** Sayaç: 4b ile "ses→yazı 15 sn · ilk kelime 182 sn · toplam 184 sn". **Zayıf bilgisayar:**
  Intel i5-3427U (2012, 2 çekirdek/4 iş parçacığı, AVX2 yok), 12 GB DDR3 (%87 dolu), SSD. Ayarlar: sohbet `gemma3:4b`,
  hafıza "aynı", Whisper `base`, asistan adı "Asiye". Gecikme istem okumadan: önbellek sürekli bozuluyordu (hafıza
  öğrenmesi araya giriyor, öğrenilen bilgi sistem istemini değiştiriyor, 30+ mesajda pencere kayıyor) → üçü de düzeltildi.
  Bu bilgisayar için 1b önerildi. Kullanıcının yeni süreleri paylaşması bekleniyor.
- **2026-09-28 (2.4):** 2.3 sonrası 1b ile: ilk mesaj 58,8 sn (model yükleme), sonrakiler ilk kelime 4,7 / 6,0 sn — büyük
  iyileşme. ses→yazı `base` ile 9,7–18 sn (yavaş CPU); `tiny` seçeneği eklendi. 1b saati hâlâ yanlış söyledi → `quick.py`.
  Kullanıcı sol alttaki gizlilik yazısı yerine ayar özeti istedi → eklendi.
- **2026-09-28:** 2.4 doğrulandı (yeniden başlatma + Chrome önbelleği temizliği sonrası, başka program kapalı):
  saat/tarih soruları anında ve doğru; ses→yazı (`base`) ilk seferde 21,4 sn (model yükleme), sonra 6,2 sn.

- **2026-09-28 (2.5):** Evdeki (NVIDIA'lı) bilgisayarda ilk deneme: `baslat` → `No Python at '"C:\Users\mertb\...\Python312\python.exe'`,
  `kurulum` → "Uygun bir Python bulunamadı". Neden: proje `C:\Users\mertbilgin\OneDrive\Documents\GitHub\Claude_Mert`,
  yani OneDrive ile eşitleniyor; zayıf bilgisayarın (kullanıcı `mertb`) `.venv`'i evdekine gelmiş. Ortam LOCALAPPDATA'ya
  taşındı. Evde python.org Python'u kurulu olmayabilir (kurulum.bat artık listeyi gösteriyor). **Açık soru:** `data/`
  (sohbetler, hafıza) da OneDrive ile eşitleniyor → iki bilgisayar aynı hafızayı paylaşıyor ama veriler Microsoft
  bulutunda ve aynı anda iki bilgisayarda açmak SQLite'ı bozabilir; kullanıcıya soruldu, karar bekleniyor.

## SIRADAKİ ADIM (kullanıcının istediği, 2026-09-28): Ses ile kimlik doğrulama

Kullanıcının isteği (onaylandı, "net"):
1. Asistan kullanıcının sesini bir kez öğrenir (kayıt), sonra konuşanın o olup olmadığını sesten anlar.
2. Doğrulanmış kişi → özel bilgiler (hafıza, adı, kişisel sorular) kullanılır.
3. Doğrulanmamış (yazan ya da tanınmayan ses) → özel bilgileri açıklamaz ("adım ne?" yazana cevap vermez),
   "kiminle konuşuyorum?" diye bilgi toplar, bu kişinin mesajları hafızaya karışmaz.
4. Doğrulanmamış tüm girişler ayrı bir **güvenlik kaydına** (tarih/saat, yazılan/söylenen) yazılır; kullanıcı panelden görür.
5. Yazarak kullanım için ayrı bir doğrulama yolu gerekir.

Teknik fikir: tamamen yerel konuşmacı doğrulama (ör. SpeechBrain ECAPA-TDNN ya da Resemblyzer ile ses parmak izi;
kayıtta birkaç örnek → ortalama vektör, her sesli mesajda kosinüs benzerliği + eşik). Yabancı modunda sistem istemi
hafızasız kurulur ve hafıza öğrenmesi o mesajları atlar (mesajlara `speaker`/`verified` alanı).
Kullanıcıya söylendi: ses doğrulaması caydırıcıdır, güçlü güvenlik değildir (kayıtla kandırılabilir; `data/` dosyaları
doğrudan açılabilir → Windows hesap şifresi / disk şifreleme önerilecek).

**Başlamadan önce kullanıcıya sorulacaklar (henüz cevaplanmadı):**
- Sesle doğrulandıktan sonra bir süre (ör. 10 dk) yazılanlar da onun sayılsın mı, yoksa yazarak kullanım için PIN/şifre mi?
- Yabancı genel sorular sorabilsin mi, yoksa hiç cevap verilmesin mi?
- Başka kişilerin (aile) sesleri de ayrı hafızayla tanıtılacak mı?

## Sıradaki fikirler

- 1b yetersiz kalırsa zayıf bilgisayar için başka küçük model dene (ör. `gemma3n:e2b`, `qwen3:1.7b`); sonucu kullanıcıdan öğren.
- Ana bilgisayara kurulum (henüz yapılmadı).
- İstenirse tamamen yerel kadın sesi: NVIDIA olduğu için ses klonlama (XTTS-v2 / Chatterbox Multilingual gibi,
  Türkçe destekli) eklenebilir; kullanıcı bir kadın sesi örneği verir.
- NVIDIA varken Whisper'ı `device="cuda"` ile çalıştırmak sesi yazıya çok daha hızlı çevirir.
- Hafıza büyüdükçe: tüm bilgileri isteme koymak yerine anlamsal arama (Ollama embedding modeli).
- Eski sohbetlerde arama.
- Dosya/belge yükleyip onun hakkında konuşma.
- Hatırlatıcılar / notlar.
- Tek tıkla çalışan masaüstü uygulaması (Python kurulumu gerektirmeyen paket).
