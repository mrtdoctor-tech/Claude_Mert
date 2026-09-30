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
  `keep_alive=60m`: model bellekte kalır, her mesajda yeniden yüklenmez. `NUM_CTX=8192` (2.8): Ollama varsayılanı 4096
  token'dı, sistem istemi + 30-40 mesaj sığmıyor, başı (hafızalı sistem istemi dahil) sessizce kesiliyordu.
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
  cevaplanır (1b verilen saati bile yanlış okuyordu). `meta` olayında `instant: true`; sayaç "hazır cevap (yapay zekâ kullanılmadı)" yazar (3.11; hatırlatıcı, bilgisayar, hava/haber cevapları da böyle).
- `app/db.py`: SQLite (`data/asistan.db`): `conversations`, `messages`, `memories`, `meta`.
- `app/stt.py`: **faster-whisper** ile çevrimdışı ses→yazı (model ilk kullanımda indirilir). 2.9: ayar `whisper_device`
  ("auto"/"cpu"). "auto"da CTranslate2 CUDA görürse ve CUDA DLL'leri (`CUDA_DLLS`, ctypes ile tek tek denenir — eksik DLL
  süreci çökertebildiği için önceden kontrol) yüklenebiliyorsa GPU'da float16, yoksa CPU'da int8. GPU'da hata olursa
  `_gpu_failed` ile uygulama yeniden başlayana dek CPU'ya düşer. DLL'ler pip `nvidia-cublas-cu12`/`nvidia-cudnn-cu12`
  (`requirements-gpu.txt`) paketlerinden gelir; `_add_nvidia_dlls` bunların `bin` klasörlerini DLL aramasına ekler.
  `baslat.bat`/`kurulum.bat` bu paketleri yalnızca `nvidia-smi` varsa kurar (zayıf bilgisayar 1 GB indirmesin).
  `ctranslate2>=4.5` (CUDA 12 + cuDNN 9) sabitlendi. `/api/transcribe` ve `/api/version` cihazı (`gpu`/`cpu`) döner;
  arayüz sayaçta ve sol alt özette gösterir. Bulutta GPU yok: GPU yolu gerçek donanımda denenmedi.
- `app/config.py`: Ayarlar **bilgisayara özel** `%LOCALAPPDATA%\YerelAsistan\settings.json` (2.6; yoksa ilk açılışta eski
  ortak `data/settings.json`'dan okunur). Veritabanı `data/` içinde, OneDrive ile **ortak** (kullanıcı kararı).
- `app/presence.py`: `data/kullanimda.json`'a dakikada bir bilgisayar adı + zaman yazar; başka bilgisayarın 150 sn'den
  yeni notu varsa `/api/version` `other_computer` döner ve arayüz kırmızı uyarı gösterir (ortak SQLite'ı aynı anda iki
  bilgisayarda kullanmak bozabilir). Kapanışta kendi notunu siler.
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
  **Python ortamı her bilgisayarda ayrı** (proje klasörü OneDrive ile iki bilgisayar arasında eşitleniyor):
  2.6'dan beri `kurulum.bat` önce Anaconda/Miniconda arar (Pinokio'nunkini atlar) ve **`asistan` adlı conda ortamı**
  açar (`conda create -n asistan --override-channels -c conda-forge python=3.12`, conda-forge = Anaconda ToS derdi yok);
  yoksa python.org Python'u ile `%LOCALAPPDATA%\YerelAsistan\venv`. Seçilen python.exe yolu
  `%LOCALAPPDATA%\YerelAsistan\python-yolu.txt`'e yazılır, `baslat.bat` oradan okur. Conda ortamı "activate" edilmeden
  kullanıldığı için iki dosya da `Library\bin` vb. klasörleri PATH'e ekler (yoksa ssl DLL'leri bulunamaz);
  `baslat.bat` `import ssl` ile sağlamlık kontrolü yapar. Conda arama sırası (`:findconda`): bilinen klasörler
  (`C:\Apps\anaconda3` dahil) → `%USERPROFILE%\.conda\environments.txt` (conda'nın tüm kurulumlardaki ortam listesi;
  kök klasör `Scripts\conda.exe` içerir) → `where conda`. Yolunda "pinokio" geçen her şey atlanır.
  **Toplu düzenleme uyarısı:** `.bat`'ta `:etiket` ararken `call :etiket` satırıyla karışmasın (2.7'de bir kez oldu,
  git'ten geri alındı); satır başı `\n:etiket\n` ile ara.
  Bulutta Windows yok: `.bat` dosyaları çalıştırılarak test edilemiyor, dikkatle gözden geçir (blok içinde `)` yok).
  `baslat.bat` her açılışta `pip install -r requirements.txt` çalıştırır; güncellemelerle gelen yeni paketler kendiliğinden kurulur.
- **Ses ile kimlik (3.0):** `app/voiceid.py` sherpa-onnx `SpeakerEmbeddingExtractor` + 3D-Speaker ERes2Net modeli
  (~40 MB, ilk kullanımda GitHub releases'ten `SETTINGS_DIR/models`'e iner). Sessiz 30 ms kareler atılır (`_speech_only`),
  <0,8 sn konuşma → (None, None) = kimlik değişmez. Kosinüs benzerliği. 3.3: `THRESHOLD=0.33` + `MARGIN=0.08` (en iyi eşleşme ikinciyi bu kadar
  geçmeli); `score ≥ ADAPT_MIN=0.50` ve fark ≥ 2×MARGIN ise mesajın vektörü profile %10 karıştırılır (okuma sesi ≠ sohbet
  sesi). Her sesli mesaj tüm profillerin puanlarıyla loglanır ("Ses doğrulandı"/"Ses ile tanındı"/"Tanınmayan ses";
  `voiceid.describe`). Çok kısa konuşmada `voice_too_short` → misafir çubuğu "bir cümle daha söyle" der. Kayıt: 3 cümle × 7 sn, ortalama vektör; cümleler (`ENROLL_SENTENCES`) tüm Türkçe ünlü/ünsüzleri kapsar (3.1).
  `app/identity.py`: süreç içi `_current`; 3.14'ten beri `_set` ile `SETTINGS_DIR/oturum.json`'a da yazılır (her bilgisayara
  özel, OneDrive'daki DB'ye değil), `touch()` her mesajda (dakikada en çok bir) tazeler, açılışta `restore()` son 15 dk
  (`RESTORE_SECONDS`) içindeki oturumu geri getirir ("Oturum geri yüklendi" loglanır). Neden: uvicorn reload (Pull, OneDrive'ın
  dosyalara dokunması) kullanıcıyı sessizce misafire düşürüyordu. 3.25: `run.py` (yalnızca elle başlatmada çalışan
  `__main__` bloğu; reload işçisi çalıştırmaz) `oturum.json`'u siler → baslat.bat açılışında oturum yok (kullanıcı fark etti:
  "başlat Mert profilini açarak getiriyor"). Yankı: `main._last_reply` (son cevap, 120 sn) ile duyulan
  metnin kelimelerinin ≥%60'ı örtüşürse `/api/transcribe` `echo: true` döner, kimlik değişmez, arayüz mesajı göndermez
  (sesli sohbette hoparlörden Emel'in sesi "Tanınmayan ses" sayılabiliyordu). Hiç profil yoksa özellik kapalı, owner `db.ALL`
  ("*"). İlk profil yönetici olur ve `assign_unowned` ile eski tüm veriler onun olur. `1234` → misafir; yönetici
  `<Ad>1234` → o profilin oturumu (misafir yazarsa normal mesaj sayılır). Kodlar veritabanına/modele gitmez
  (`_notice_stream`). `db`: `conversations.owner`, `messages.speaker`, `memories.owner` (+ `_NEW_COLUMNS` göçü), `speakers`,
  `security_log`. Misafir: hafızasız ayrı sistem istemi, mesajları "Misafir mesajı" olarak loglanır, hafıza çıkarma
  `speaker=misafir`'i atlar. Güvenlik kaydı ve profil listesi yalnızca yöneticiye açık. 3.2: Ayarlar yalnızca yöneticiye açık (özellik aktifken yönetici olmayan herkes için düğme gizli, sol alt özet tıklanmaz, `PUT /api/settings` → `_require_admin` 403). Ayarlar bilgisayar başına tektir; herkes yöneticinin seçtiklerini kullanır (kullanıcı kararı).
  3.4: profil başına **şifre** (`speakers.passcode` = "salt$hash", PBKDF2-SHA256 200k; `PUT /api/voice/profiles/{id}/passcode`,
  yalnızca yönetici). Kural: ≥6 karakter, harf + rakam, boşluksuz, `1234` içermez, profiller arası benzersiz.
  `identity._passcode_attempt` `handle_code` içinde (1234'ten sonra, `<Ad>1234`'ten önce): doğruysa o profile geçer.
  Misafirin harf+rakam içeren tek kelimesi **şifre denemesi** sayılır: modele/geçmişe gitmez, metni loglanmaz ("Yanlış
  şifre denemesi n/5"); 5 yanlışta 10 dk kapanır (`MAX_TRIES`, `PAUSE_SECONDS`, süreç içi). Oturum açıkken böyle
  kelimeler (ör. "iPhone15") normal mesajdır.
- **Hatırlatıcılar (3.5):** `app/reminders.py`. Türkçe zaman ifadeleri **kurallarla** çözülür (`parse`; model değil):
  sayı kelimeleri (`_numbers`: yirmi beş, yarım saat, buçuk), süre → sayaç (`timer`), gün (bugün/yarın/öbür gün, gün
  adları, "15 Ekim", "30.09.2026") + saat (`_CLOCK`: yalnızca "saat X", X:YY, "buçuk", ek ('de/'da) ya da dönem kelimesinden
  sonra kabul; çıplak sayı saat değildir) + dönem (sabah/akşam/gece…, +12) + tekrar (her gün/hafta/ay/yıl, her
  pazartesi). Saatsiz tarih 09:00. "saat 3'te" öğleden sonra ise 15:00; "uyandır" ise sabah. Metin: zaman ve istek kelimeleri
  çıkarılır, kullanıcının büyük harfleri korunur. Tetik kelimesi (`_TRIGGER`: hatırlat, uyandır, alarm, sayaç, haber ver…)
  + zaman yoksa mesaj modele gider. `handle` chat'te `quick.answer`'dan sonra çağrılır (anında cevap, mesajlar kaydedilir);
  liste/iptal/"ne kadar kaldı" de burada. Misafir: kuramaz. `db`: `reminders` (owner, kind, text, due_at yerel
  "YYYY-MM-DD HH:MM:SS", repeat, status) + `alerts` (acknowledged). Başlangıçta `reminders.run()` her 3 sn `fire_due`:
  vakti gelen → alert, tekrarlayan ileri alınır. Sayfa `/api/alerts`'ı 3 sn'de bir sorar (çalışan sayaçlar + çalan
  uyarılar; başkasının uyarısında metin gizli: `visible_text`); son sorgu 20 sn'den eskiyse Windows bildirimi (PowerShell
  WinRT toast, PowerShell'in AppID'si; **gerçek Windows'ta denenmedi**). Kapalıyken geçen uyarılar açılışta `missed`.
  Arayüz: `#timer-bar` geri sayım çipleri, `#alert-dialog` (WebAudio zil 1,5 sn'de bir, en çok 1 dk + `speak`),
  `#reminders-dialog` (elle ekleme, datetime-local). Hafıza çıkarma komutları atlar (`memory._is_command`).
- **Bilgisayar kontrolü (3.6):** `app/pc.py`, chat'te reminders'tan sonra `run_in_threadpool(pc.handle)`. Misafire kapalı.
  Excel: pywin32 COM (`GetActiveObject("Excel.Application")`), açma `os.startfile` (dosya araması `find_file`: Masaüstü,
  Belgeler, İndirilenler, OneDrive; tüm sorgu kelimeleri adda geçmeli; tam ad > en yeni). "kaydederek/kaydetmeden kapat",
  "kaydet", "açık dosyalar"; seçim yoksa Excel'in kendi sorusu (arka plan thread'inde `Quit`). Hiç kaydedilmemiş kitap
  (Path boş) "kaydederek"te açık bırakılır. **Dikkat:** "kaydederek" ≠ "kaydet" alt dizgisi (`_SAVE` = `kayded|kaydet(?!me)`).
  "Excel" geçmeden "<ad> dosyasını aç/kapat/kaydet" de komut; açma o zaman Word/PDF/PPT'yi de bulur. Soru kelimesi
  (nasıl, nedir, formül…) varsa komut sayılmaz. Müzik (3.12): Spotify masaüstü penceresi bulunursa (`_spotify_window`:
  EnumWindows + işlem yolu `spotify.exe`) ona `WM_APPCOMMAND` (oynat/duraklat 14, sonraki 11, önceki 12); pencere başlığı
  "Spotify"/"Spotify Free/Premium" ise duruyor, "Sanatçı - Şarkı" ise çalıyor → "durdur" zaten durmuşsa geçiş yapmaz.
  Spotify yoksa `keybd_event` medya tuşları **KEYEVENTF_EXTENDEDKEY (1/3)** ile (3.6'da bayraksızdı: "müziği durdur" kullanıcıda
  çalışmadı; ayrıca Chrome, TTS sesi yüzünden medya tuşlarını kendine alıyor olabilir). Ses aç/kıs sistem tuşları.
  `handle` sırası: excel → media → spotify ("Spotify'ı durdur" açma değil durdurma).
  3.13: Spotify'ın "GDI+ Window (Spotify.exe)" gibi yardımcı pencereleri de başlık taşıyor → yalnızca sınıfı
  `Chrome_WidgetWin*` olan pencereler; durum üç değerli: " - " içeren başlık = çalıyor, "Spotify/Spotify Free/Premium" =
  durmuş, diğer = bilinmiyor (o zaman sadece oynat/duraklat gönderilir, "zaten…" denmez). Spotify: `spotify:` /
  `spotify:search:<q>` (Premium'suz otomatik çalma yok). `COM` her thread'de `pythoncom.CoInitialize` (`pc.com`).
- **Outlook takvimi (3.6):** `app/outlook.py`, ayar `outlook_sync` (Ayarlar'da, yönetici). Microsoft Graph/uygulama kaydı
  yerine **klasik Outlook COM**: `CreateItem(1)` randevu (Start yerel "YYYY-MM-DD HH:MM" dizgisi, 15 dk, meşgul değil,
  hatırlatma 0 dk; tekrar → `GetRecurrencePattern`, NoEndDate). EntryID `reminders.calendar_id`'de, hata
  `calendar_note`'ta (panelde ⚠️). İptal → `GetItemFromID().Delete()`. Yalnızca yöneticinin (ya da kimlik kapalıyken)
  hatırlatma/alarmları; sayaç yok. "Yeni Outlook"ta COM yok → test mesajı bunu söyler. `/api/outlook/test`.
  3.7: `Dispatch` öncesi `classic_outlook_path()` (kayıt defteri `Outlook.Application\CLSID` → `LocalServer32` → dosya
  var mı): kullanıcıda `Dispatch` bir sihirbaz açtı. 3.8: asıl neden büyük olasılıkla klasik Outlook'ta **posta
  profili yok** (M365 Personal var → klasik Outlook kurulu; kullanıcı yeni Outlook kullanıyor) → `has_mail_profile()`
  (HKCU `Software\Microsoft\Office\16.0|15.0\Outlook\Profiles` alt anahtar sayısı) yoksa COM'a hiç gidilmez.
  **Gerçek Windows/Excel/Outlook'ta denenmedi**; bulutta sahte `win32com`/`pythoncom` modülleriyle test edildi.
- **Ajanda + güvenlik tablosu (3.9):** Sağda `<aside id="agenda">` (300 px; ≤1100 px genişlikte CSS ile gizli).
  `applyIdentity` → `showAgenda(!guest)`; tercih `localStorage["agenda"]`, başlıkta `#toggle-agenda`. `/api/reminders`'ı
  (sayaç hariç) 20 sn'de bir ve sohbet/ekleme/silme sonrası yükler; ay takvimi Pazartesi başlar, tekrarlar istemcide
  (`occursOn`: due_at = sonraki oluşum, öncesi gösterilmez). Güvenlik kaydı `<table class="grid">`: arama, olay süzgeci,
  başlığa tıkla-sırala, CSV dışa aktarma (`;` + BOM + virgüllü ondalık: Türkçe Excel doğru açsın).
- **Outlook kayıtları ajandada (3.10):** `outlook.events(start, end)` → `GetDefaultFolder(9).Items`, `IncludeRecurrences`,
  `Sort("[Start]")`, `Restrict("[Start] < 'bitiş' AND [End] > 'başlangıç'")`. Tarih biçimi Windows yerel ayarına bağlı →
  sırayla `%x %H:%M` (setlocale LC_TIME ""), ABD biçimi, `dd.mm.yyyy` denenir; sonuç ayrıca aralığa göre süzülür.
  pywin32 Outlook saatlerini "UTC" etiketli verir ama değer yerel saattir → `_local` tz'yi atar. Body/Organizer okunmaz
  (Outlook güvenlik uyarısı çıkarabilir). Asistanın eklediği randevular (konu + başlangıç dakikası eşleşen, `calendar_id`'li
  hatırlatmalar) çıkarılır. 60 sn önbellek; ekleme/silmede temizlenir. `GET /api/outlook/events` yalnızca yönetici (ya da
  kimlik kapalıyken) + `outlook_sync` açık + klasik Outlook ve profil varsa. Arayüz: salt okunur mavi kayıtlar, çok günlü
  (tüm gün) kayıtlar her güne nokta koyar. **Gerçek Outlook'ta denenmedi** (sahte COM ile test edildi).
- **Hava durumu + haberler (3.11):** `app/online.py`, chat'te pc'den sonra `run_in_threadpool(online.handle)`; **misafire
  kapalı** (kullanıcı kuralı). Hava: Open-Meteo geocoding (`language=tr`) + forecast (current + 7 günlük daily), WMO
  kodları Türkçe (`WEATHER_CODES`); cevap kurallarla kurulur (model değil). Gün seçimi: bugün/yarın/öbür gün/gün adı/hafta
  sonu/bu hafta. Şehir: "X'da hava" (`_CITY`, `_NOT_CITIES` + tam kelime kontrolü: "hafta" → "haf"+"ta" hatası oldu) ya da
  ayar `weather_city`. Haber: NTV (Atom) + BBC Türkçe (RSS) akışları (`NEWS_FEEDS`, kategori: gündem/ekonomi/spor/dünya/
  teknoloji/sağlık), RSS+Atom ayrıştırma, tarih sıralı, başlık tekrarları atılır, 7 başlık Markdown bağlantısıyla.
  Önbellek: hava 15 dk, haber 10 dk. "haber ver" hatırlatıcı kelimesi sayılmaz; "nedir/neden" soruları modele gider.
  `/api/weather` → ajandanın üstündeki hava satırı. `renderMarkdown` artık `[metin](https://…)` bağlantılarını açar;
  `plainText` sesli okumada bağlantı adresini atar. **Bulutta dış ağ kapalı: gerçek servislerle denenmedi**, sahte
  yanıtlarla test edildi (feed adresleri: ntv.com.tr/<kategori>.rss, feeds.bbci.co.uk/turkce/rss.xml).
- **Mikrofon kalibrasyonu + Ayarlar düzeni (3.15):** Tüm kayıtlar `openMic()` üzerinden: getUserMedia (echoCancellation,
  noiseSuppression, `autoGainControl: !mic_calibrated`) → WebAudio GainNode (`mic_gain` dB) → MediaStreamDestination
  (MediaRecorder bunu kaydeder) + analyser (`level()` = kazanç sonrası RMS/tepe; sessizlik algılama da bunu kullanır).
  "Mikrofonu ayarla": kazançsız + AGC kapalı 5 sn; kareler (50 ms RMS) → gürültü = %10'luk dilim, konuşma = gürültü×3 üstü
  karelerin medyanı; kazanç = clamp(−20 dBFS − konuşma, 0, 30) ve tepe −1 dBFS'yi geçmeyecek kadar; sonuç hemen
  `PUT /api/settings` (`mic_gain`, `mic_calibrated`). Test kaydı kaydırıcıdaki kazançla dinlenebilir. Ayarlar penceresi
  `.settings-dialog`: `.settings-grid` 2 kolon kart (≤820 px tek kolon), profiller formun dışında (içinde iç içe şifre
  formları var), Kaydet altta `form="settings-form"`. Sahte kısık mikrofonla (Chromium `--use-file-for-fake-audio-capture`)
  test edildi: −53 dB konuşma → +30 dB, uyarı.
  3.24: kullanıcı isteğiyle **sekmeli** (`#settings-tabs`, `.note-tabs` görünümü; kartlarda `data-tab` ai/voice/mic/links/
  profiles, yalnızca `.shown` görünür, tek kolon, 760 px, sabit yükseklik). Tek form: Kaydet tüm sekmeleri kaydeder.
  Son sekme `localStorage["settingsTab"]`; profiller gizliyse (yönetici değil) o sekme de gizli.
- **Notlar ve listeler (3.16):** `app/notes.py`, chat'te reminders'tan sonra (`quick → reminders → notes → pc → online`),
  kurallarla (model değil), misafire kapalı, kişiye özel (`notes` tablosu: owner, list_name, text, done). Liste adı tek kelime
  ve yalnızca "X listesine/listesinden/listesini" biçiminde; çıplak "listeye/listeden" = `alışveriş` (`DEFAULT_LIST`),
  "not al" = `notlar`; `ALIASES` (market → alışveriş, iş → yapılacaklar). `_split_items` virgül/ve/ile ile böler, `_same`
  Türkçe ekleri tolere eder (sütü = süt, ekmeği = ekmek) ve tekrar eklemeyi engeller. İsmin -i hali ("Peyniri listeye
  ekle") olduğu gibi kaydedilir: ek kesmek "zeytinyağı", "çamaşır suyu" gibi adları bozardı. `/api/notes` (GET/POST,
  PUT/DELETE `{id}`), arayüzde `#notes-dialog` (sekmeler, işaretleme, silme, virgüllü ekleme).
  3.17: `_clean` baştaki/sondaki "lütfen" ve noktalamayı atar; fiil `ekle\w*` + `_ASK` (ekler misin, ekleyebilir misin,
  yazar mısın), `(?!n)` "eklenir/eklendi mi"yi dışlar; `_QUESTION` (nasıl/neden/nedir) → komut değil. Sistem istemi:
  model listelere/hatırlatıcılara kendisi ekleyemez, "ekledim" demesin, kısa komut önersin.
  3.18: "listem…" biçimleri: baştan başlayan kalıplar (ADD/SHOW/CLEAR) `liste[sm]`; ortadakiler (ADD_AFTER/REMOVE)
  için `_KNOWN_MY` yalnızca bilinen adlarda "alışveriş listemi" → "alışveriş listesini" çevirir ("ekmeği listeme"de
  "ekmeği" liste adı sanılmasın). Sistem istemi: model listelerin içini göremez, "listen boş" diye tahmin etmesin.
- **Adınla seslenme / uyandırma sözü (3.19):** Ayar `wake_word` (bool) + `wake_phrase` ("" = `assistant_name`). Türkçe için
  hazır bir anahtar kelime modeli yok (openWakeWord/sherpa KWS eğitim ister), bu yüzden aynı yerel Whisper kullanılıyor:
  `static/app.js` `wakeListener` kendi `openMic()`'i + ScriptProcessor ile ham ses alır, 500 ms ön kayıt, gürültü tabanı
  (EMA, eşik max(0,015, taban×3)), ≥250 ms konuşma + 700 ms sessizlik (en çok 8 sn) → 16 kHz WAV → `POST /api/transcribe`
  `wake_check=true`. Sunucu önce yalnızca yazıya çevirir; `app/wake.py` `match` (sözün başta olması, önünde en çok bir selam
  kelimesi `GREETINGS`; tek kelimelik sözde benzerlik ≥0,75 — "Ayşe"/"Asya" 0,67 geçmez —, iki kelimede ≥0,6; "Asiyeciğim"
  gibi ekler) tutmazsa `{"wake": false}`: log yok, kimlik/hafıza sayacı değişmez. Tutarsa normal yol (yankı, ses kimliği)
  ve kalan metin döner: metin varsa doğrudan `send`, yoksa `chime()` + `startListening`. Asistan konuşurken, kayıt/cevap
  sürerken, istek yoldayken veya bir `dialog` açıkken dinlemez (`deaf`). `#wake-toggle` 👂 duraklatır (`localStorage`
  `wakePaused`). AudioContext askıdaysa ilk tıklama/tuşta `resume`. Sahte mikrofon (ses patlamalı WAV) + sahte STT ile
  test edildi; **gerçek Whisper/gerçek mikrofonla denenmedi** (TV/müzik açıkken GPU'ya sürekli iş düşebilir).
  3.20: tüm yazıya çevirmelerde faster-whisper `hotwords` = asistan adı + uyandırma sözü (`wake.hotwords`; eski sürümde
  TypeError → hotwords'süz tekrar). Neden: kullanıcının hızlı "Merhaba Asiye"si "Merhaba size" yazıldı.
  3.21: müzikte uyandı ve şarkı sözü + "İzlediğiniz için teşekkür ederim" mesaj olarak gitti, kullanıcı misafire düştü
  (büyük olasılıkla hotwords istemi Whisper'a müzikte sözü uydurttu). → `wake_check`'te hotwords YOK; `stt.clean`
  (`HALLUCINATIONS`: altyazı/izlediğiniz için/abone olmayı unutma/thanks for watching…) tüm çevirilerde;
  `wake.sounds_foreign` (dil tr iken İngilizce sözcük oranı ≥%25, Türkçe harf yok) `wake_check` ve `hands_free`
  (otomatik yeniden açılan mikrofon + uyandırma sonrası dinleme; `startListening(auto, handsFree)`) isteklerinde metni
  atar, kimlik kontrolüne gitmeden `music: true` döner. Misafir modunda uyandırma açık kalır (kullanıcı kararı).
  3.22: telefonda müzik (mikrofondan 30 cm) çalarken "Merhaba Asiye" yakalanmadı: ses hiç susmadığından tek parça 8 sn'ye
  kadar uzuyor, söz ortada kalıyor, `match` başta arıyordu. → çok kelimeli söz her konumda aranır (tek kelimelik yalnızca
  başta); susmayan ses 6 sn pencereler, 2 sn örtüşme (`OVERLAP_MS`), bu parçalar `noisy=true` → ses kimliği atlanır
  (kimlik değişmez); kontrol sürerken biten parça `waiting`'de bekler (eskiden atılıyordu); uyanınca 3 sn `restUntil`.
  Yabancı dil kontrolü artık sözden SONRAKİ metne: şarkı ise uyanır ama komut boş ("dıt dıt" + dinle), kimlik atlanır.
- **Belgeler (3.23):** `app/documents.py` + `db.documents` (conversation_id CASCADE, name, pages, language, text, summary).
  `POST /api/documents` (dosya + isteğe bağlı conversation_id; yoksa "📄 ad" sohbeti) → `extract`: PDF `pypdf` ("[Sayfa N]"
  işaretli; yazısız → taranmış uyarısı; şifreli → uyarı), .docx `python-docx` (paragraflar + tablolar), .txt/.md/.csv
  (utf-8 → cp1254 → latin-1). `language` (tr/en sözcük sayımı). Sohbete "📄 … belgesini okudum" asistan mesajı eklenir.
  Sohbette belge varsa `num_ctx = DOC_CTX` (16384; normal 8192 — değişince Ollama modeli yeniden yükler, GPU'da ~1-2 sn).
  Toplam ≤ `FULL_CHARS` (28 000) ise belgeler **sistem istemine** tam girer (sohbet boyunca sabit → Ollama önbelleği korunur).
  Daha uzunsa: soru `wants_summary` ise `section_summaries` (18 000 karakterlik bölümler, en çok 24, `llm.chat_text`,
  `progress` olayları, sonuç `documents.summary`'de saklanır) → özetler son mesaja; değilse `search_words` (soru dili ≠ belge
  dili ise modelden anahtar kelime çevirisi) + `passages` (1 500 karakterlik parçalar, 5 harflik kök eşleşmesi, IDF, 18 000
  bütçe) son mesaja (kaydedilmez). `quick._DATE` artık "teslim tarihi ne?"yi saat/tarih sorusu saymaz. Arayüz: 📎 `#attach`,
  sürükle-bırak (`body.dropping`), `#doc-bar` çipleri (`loadDocs`), `progress` balonda gösterilir. Misafire açık (yerel).
  Sahte Ollama + Chromium'un yazdığı PDF, python-docx ile yapılan .docx ve uzun .txt ile test edildi; **gerçek modelle
  denenmedi** (cevap kalitesi, 16k bağlamın 8 GB VRAM'e sığması kullanıcıda görülecek).
- **Sohbet adları + güvenlik kaydı temizleme (3.25):** yeni sohbet `main._new_title` = `%Y%m%d%H%M` + ilk kelime
  (kullanıcı isteği, ör. "202609301324 Merhaba"; belge sohbeti "… 📄 ad"); `meta` olayı `title` taşır. `PUT
  /api/conversations/{id}` (yeniden adlandırma; listede ✏️, başlığa tıklama, `prompt`). `DELETE /api/security-log`
  (yönetici; ardından "Güvenlik kaydı temizlendi" satırı yazılır), güvenlik penceresinde 🧹.
- **Klasör analizi (3.26):** `app/analysis.py`. Klasör: ayar `analysis_folder` ya da `~/My Drive*/HourGlowMusic/Scripts/Asiye`
  (Google Drive yansıtma; yol kodda e-postasız). Komut `is_command` (analiz + klasör/dosya/şarkı/resim + et/yap/eder),
  "analiz klasörünü aç" → `os.startfile`. Chat'te notes'tan sonra, pc'den önce; `job` → `analysis.run` akışı `progress`
  olayları, sonunda özet. Misafire kapalı (`refusal`). Rapor yoksa / dosyadan eskiyse analiz; "hepsini yeniden" → hepsi.
  Rapor `<ad>.analiz.txt` (utf-8-sig). Müzik: PyAV ile çözme (faster-whisper'la gelir, mp3/m4a), pyloudnorm LUFS, tepe/RMS,
  dinamik (0,5 sn blokların %95-%10'u), kırpılma, kenar sessizliği, stereo korelasyon/genişlik, librosa `beat_track`, ton
  (chroma_stft + Krumhansl), spektral merkez/düzlük, olay yoğunluğu, 10 sn bölüm çubukları, modelden yorum. Resim: Pillow
  (EXIF + GPS uyarısı, parlaklık/kontrast/doygunluk/kenar varyansı, MEDIANCUT 6 renk + Türkçe ad) + modele 896 px JPEG
  (`images`, gemma3 görür). İlk müzik dosyası numba derlemesi yüzünden ~30 sn. Sentetik mp3/wav/jpg/png + sahte Ollama ile
  test edildi; **gerçek dosyalar ve gerçek model yorumları denenmedi**.
  3.27: yalnızca "hepsini/yeniden/tekrar + analiz et" (başka nesne kelimesi yok, `_BARE_WORDS`) da komut. Sistem
  istemine: model klasör analizi yapamaz, sonuç uydurmasın.
- **Özel kelimeler (3.28):** `app/vocab.py`, ayar `vocabulary` (virgüllü, varsayılan "HourGlow"). Whisper `hotwords`'e eklenir
  (wake_check hariç) ve `/api/transcribe` her metinde `vocab.fix`: 1-3 kelimelik gruplar, sadeleştirme (Türkçe harf
  katlama, ğ→h, ou→a, ow→o) + ünsüz iskeleti (a e i o u h w v y atılır) eşit ve benzerlik ≥0,6 → terim (kesme işaretli ek
  korunur). "Avır glo/Aurglo/Hour glow/Havır Glov/Ağır glo" → HourGlow; "Argo", "Ağır gelir", "Avrupa" değişmez.
  `pc._search_roots` Google Drive'ı da tarar (`~/My Drive*`, `~/Google Drive*`, `G:/My Drive`), `find_file` tarama sınırı
  yer başına; ad eşleşmesi boşluk/altçizgi yok sayarak da ("hour glow" = "HourGlow_Takip").
- **Yardım (3.5):** `NELER_YAPABILIR.md` = yapabildikleri + örnek komutlar; `/api/help` ile uygulamada "❓ Neler
  yapabilirim?". **Yeni özellik eklendikçe bu dosyayı güncelle.**
- **Saat notu yankısı (3.0):** model son mesajdaki "(Şu an: …)" notunu cevabına kopyalıyordu. Not artık
  "[Sistem notu, yanıtta yazma: …]" ve `memory.strip_clock_echo` cevaptan (kaydetmeden önce) temizler.
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
  bulutunda ve aynı anda iki bilgisayarda açmak SQLite'ı bozabilir.
- **2026-09-28 (2.6):** Kullanıcının kararları: veritabanı OneDrive'da **ortak**, ayarlar **her bilgisayarda ayrı**, Python
  için Anaconda'da **yeni `asistan` ortamı** (base önerilmedi: paket sürümleri base'i bozabilir). Kullanıcıda Anaconda ve
  birkaç conda ortamı var; **ileride ortamları birleştirmek/düzenlemek için yardım isteyecek.**
- **2026-09-28 (2.7):** Evdeki bilgisayarda kurulum Anaconda'yı bulamadı. `conda env list` (Pinokio'nun conda'sı PATH'te):
  Anaconda **`C:\Apps\anaconda3`**, ortamları: `ComfyUI`, `comfyui` (ComfyUI için), `ai_assistant` (kullanıcının kurduğu;
  **Hourglow betikleri** bunu ve Comfy ortamlarından birini kullanıyor), `muzik`, `tts` (müzikle ilgili Python kodu için,
  başka bir konuşmada yapılmış — bu oturumda bilgisi yok). Pinokio'nun Miniconda'sı `P:\pinokio\bin\miniconda` PATH'te
  ve "base" olarak görünüyor. Ayrıca PATH'te Microsoft Store'un sahte `WindowsApps\python.exe`'si var. Kurulum artık
  conda'nın ortam listesinden Anaconda'yı buluyor.
- **2026-09-29:** 2.7 ile evdeki bilgisayarda **kurulum başarılı** (Anaconda `asistan` ortamı). **Ev bilgisayarı:** Intel
  i7-14700F (20 çekirdek/28 iş parçacığı), 32 GB DDR4-3200, NVIDIA GeForce RTX (model/VRAM henüz bilinmiyor), NVMe SSD;
  Pinokio `P:` (USB disk). Ayarlar: sohbet `gemma4:31b`, hafıza "aynı", Whisper `medium`, Emel. Sayaç: ses→yazı ~6 sn,
  ilk kelime 174–218 sn, toplam ~260–290 sn (~2 kelime/sn). RAM %83 dolu, GPU kullanımı %12 → 31b VRAM'e sığmıyor, çoğu
  CPU'da çalışıyor. Kullanıcıdan GPU adı + "Dedicated GPU memory" ve `ollama ps` (PROCESSOR sütunu) istendi; VRAM'e
  sığan model önerilecek (kural: model boyutu < VRAM − 1-2 GB).
- **2026-09-29 (2.8):** Ev bilgisayarının ekran kartı **RTX 4060, 8 GB VRAM**. `ollama ps`: gemma4:31b **21 GB, 76%/24%
  CPU/GPU**, CONTEXT 4096; CPU %100, paylaşılan GPU belleği 14,5 GB; ilk kelime 222 sn. Öneri: sohbet `gemma3:4b` (tam
  GPU'ya sığar), istenirse hafıza modeli daha büyük (ör. `gemma3:12b`, arka planda). Ayrıca 4096 bağlam sınırı fark
  edildi → `num_ctx=8192`. README'ye VRAM'e göre model tablosu eklendi.
- **2026-09-29:** Ev bilgisayarında `gemma3:4b`'ye geçildi: `ollama ps` → 3,0 GB, **100% GPU**, CONTEXT **8192** (2.8 doğrulandı).
  Sayaç: ses→yazı 5,7 sn · ilk kelime 6,4 sn · toplam 10,8 sn (31b'de 309 sn). Kullanıcı memnun ("çok hızlı").
  Artık en yavaş halka Whisper (CPU'da medium ~5,7 sn) → GPU'ya taşıma önerildi.
- **2026-09-29 (2.9):** Kullanıcı önce Whisper'ı GPU'ya taşımayı, sonra ses kimlik doğrulamasını seçti. GPU desteği eklendi
  (ayrıntı: Mimari → `app/stt.py`). Kullanıcının ev bilgisayarında denemesi bekleniyor: sol altta "GPU" ve sayaçta
  ses→yazı süresi.
- **2026-09-29:** 2.9 ev bilgisayarında doğrulandı: ses→yazı **0,6 sn (GPU)**, ilk kelime 0,3 sn, toplam 5,8 sn.
  Ekranda modelin cevabın sonuna "(Şu an: 29.09.2026, Salı, saat 18:59)" yazdığı görüldü → 3.0'da düzeltildi.
- **2026-09-29 (3.0):** Ses ile kimlik doğrulama. Kullanıcı kararları: sesle doğrulanınca yazı da o kişinin (zaman aşımı
  yok); `1234` kilitler (sabit kod); misafir genel soru sorabilir, altta "Misafir", tanınınca ad yazar; eşi **Sezin**
  ayrı hafızayla tanıtılacak; yönetici Mert, kendi oturumundayken `Sezin1234` ile Sezin'in oturumuna geçebilir.
  Bulutta sherpa-onnx'in 4 konuşmacılı örnek kaydıyla test edildi (Mert 0,77, Sezin 0,44, yabancı ≤0,20); gerçek seslerle
  denenmedi. Kullanıcının denemesi bekleniyor: tanınmazsa/yanlış tanırsa güvenlik kaydındaki puanlara göre eşik ayarlanır.
- **2026-09-29 (3.1):** Kullanıcı isteği: ses tanıtmada ayırt edici kelimeler içeren 3 cümle (tüm Türkçe sesler; kayıt
  ekranında önceden gösteriliyor) ve misafir modunda Ayarlar'ın hiç görünmemesi (kimse ses kaydı yapamasın).
- **2026-09-29 (3.2):** Kullanıcı: Ayarlar'ı yalnızca admin görsün/kullansın; seçilmiş ayarlar herkes için geçerli.
  Kullanıcı henüz ses kaydı yapmadı (3.1'in cümleleriyle yapacak).
- **2026-09-29:** Mert ev bilgisayarında sesini tanıttı: tutarlılık **0,906** (örnek kayıttaki 0,85'ten iyi). Sezin'in
  kaydı ve tanıma puanları bekleniyor.
- **2026-09-29 (3.3):** Gerçek seslerle ilk test (ev bilgisayarı; Sezin iki kez kaydedildi): Mert kısa sesli mesajlarda
  0,43 / 0,50 / 0,55 / 0,44 / 0,51 ve bir kez **0,364 → misafir sayıldı**; Sezin 0,655. İki kez "Merhaba ben Mert"
  çok kısa bulundu (puan yok, misafir kaldı). Yanlış kişiye eşleşme **hiç olmadı**, ama çapraz puanlar (Sezin'in sesinin
  Mert profiline benzerliği) loglanmıyordu → 3.3'te eklendi. Kullanıcıdan yeni kayıttaki puanlar beklenecek; eşik ve
  MARGIN buna göre ayarlanacak.
- **2026-09-29:** 3.3 ile gerçek puanlar: Mert 0,39 / 0,42 / 0,46 / 0,52 / 0,56 / 0,59 (hepsi tanındı), aynı seslerin
  Sezin profiline benzerliği 0,10–0,17 → ayrım net, eşik 0,33 + MARGIN uygun, değişiklik gerekmedi. "Benim adım Mert",
  "Asya?" gibi tek kelime/çok kısa sesler puansız (misafir kalır); kullanıcı "cümle uzayınca benzerlik artıyor, problem
  değil" dedi. Sezin'in bu sürümdeki puanları henüz görülmedi.
- **2026-09-29 (3.4):** Kullanıcı isteği: hastalıkta ses değişirse şifreyle kendi profiline girebilmek. Profil başına
  şifre eklendi (yönetici belirler). İlk denemede bulunan açık: bekleme süresinde doğru şifre misafir mesajı olarak düz
  metin loglanıyordu, yanlış denemeler de → misafirin kod benzeri tek kelimeleri artık hiç loglanmıyor/gönderilmiyor.
- **2026-09-29 (3.5):** Kullanıcı kararları: hatırlatmalar kişiye özel (ortak "aile" yok); tarayıcı kapalıyken Windows
  bildirimi, asistan kapalıyken sonraki açılışta kaçırılanlar; yalnızca ev bilgisayarında kullanılacak (başka bilgisayar
  düşünülmüyor). Ayrıca **telefon takvimine kayıt** istedi (telefonda bildirim için) → hangi takvim olduğu soruldu
  (Google / iPhone-iCloud / Outlook); bulut servisi olduğundan kullanıcı onayıyla yapılacak ve misafire kapalı olacak.
  Komut örnekli belge (`NELER_YAPABILIR.md`) istendi → eklendi. Windows bildirimi gerçek Windows'ta denenmedi.
- **2026-09-29 (3.6):** 3.5'in Windows bildirimi gerçekte **çalıştı** (sayaç). Kullanıcı Microsoft takvimi kullanıyor
  (kişisel Microsoft hesabı, outlook.com). Graph API için Azure uygulama kaydı gerekeceğinden önce klasik Outlook COM
  yolu seçildi; Outlook'ta hangi hesabın/"yeni Outlook" mu olduğu bilinmiyor → "Outlook bağlantısını dene" sonucu
  beklenecek. Olmazsa: Microsoft Graph + cihaz kodu girişi (msal; kullanıcının kendi Azure uygulama kaydı) düşünülebilir.
  Ayrıca Spotify (Premium olup olmadığı soruldu) ve Excel aç/kapat/kaydet istedi → eklendi.
- **2026-09-29 (3.7):** "Outlook bağlantısını dene" Outlook 2016 kurulum sihirbazını açtı (kullanıcı iptal etti);
  kullanıcının kullandığı Outlook büyük olasılıkla "yeni Outlook" → COM yolu kapalı. Spotify: **ücretsiz** hesap,
  Windows uygulaması kurulu → Web API ile çalma mümkün değil (Premium gerekir), arama açma + medya tuşları kalır.
  Takvim/telefon bildirimi için seçenekler soruldu: (1) ntfy ile doğrudan telefon bildirimi (kolay, takvim kaydı yok),
  (2) Microsoft Graph ile Outlook.com takvimi (tam otomatik; Microsoft'ta bir kerelik uygulama kaydı gerekir,
  kişisel hesapta ücretsiz Azure hesabı isteyebilir), (3) klasik Outlook kurmak (3.6 kodu çalışır).
- **2026-09-29 (3.8):** 3.7'den sonra da sihirbaz açıldı (kullanıcı 3.7'yi çekmemiş olabilir; ya da sihirbaz "hesap ekle"
  penceresiydi). Kullanıcıda **Microsoft 365 Personal** var, telefon **Android**. Yol: klasik Outlook'u bir kez açıp
  hesabı eklemek → 3.6 COM yolu. Olmazsa kullanıcının 2. tercihi **Gmail/Google Takvim** (Google Cloud projesi +
  OAuth; kart gerekmez). Spotify Chrome'da (web oynatıcı) da aynı: çalma kontrolü API'si Premium ister, medya tuşları çalışır.
- **2026-09-29:** 3.8 sonrası kullanıcı klasik Outlook'a hesabını ekledi → "Outlook bağlantısını dene": **✅ Outlook
  çalışıyor, takvim "Calendar" (kişisel Outlook.com hesabı)**. `outlook_sync` açıldı. Takvime gerçekten randevu eklenip
  telefonda (Android) bildirim çıkıp çıkmadığı henüz bildirilmedi. Gmail yoluna gerek kalmadı.
- **2026-09-30:** **Outlook takvimi uçtan uca doğrulandı:** "deneme" hatırlatması panelde "📅 Outlook'ta" göründü ve
  kullanıcının Android telefonundaki takvime işlendi. (Aynı anda "deneme" adlı bir sayaç da vardı; sayaçlar takvime gitmez.)
- **2026-09-30 (3.9):** Kullanıcı isteği: güvenlik kaydı tablo gibi, hatırlatıcılar sağda takvim görünümlü bir bölümde
  (profil açılınca). Kullanıcının asıl sıradaki seçimi bundan sonra sorulacak (notlar/liste, fotoğraf, belge, sabah özeti,
  uyandırma sözcüğü, eski sohbet arama, hava/haber). Excel/müzik komutları gerçek bilgisayarda henüz denenmedi.
- **2026-09-30 (3.10):** Kullanıcı: ajanda boş ama Outlook'ta kayıtlar var → Outlook kayıtları ajandada salt okunur
  gösteriliyor. Gerçek Outlook'ta tarih biçimi (`Restrict`) sorun çıkarırsa ajandada ⚠️ mesajı görünür.
- **2026-09-30:** 3.10 **gerçek Outlook'ta doğrulandı**: tüm gün, tekrarlanan ve Teams toplantısı kayıtları ajandada doğru
  gün/saatte görünüyor (Türkçe Windows'ta `Restrict` tarih biçimi çalıştı). Asistanın eklediği "deneme 13:00" tek kez
  (🔔 + "📅 Outlook'ta") görünüyor; mavi kopya gizleniyor → kullanıcıya bunun normal olduğu açıklandı.
- **2026-09-30 (3.11):** Kullanıcı 7'yi seçti: hava durumu + haberler (misafire kapalı). API anahtarsız kaynaklar:
  Open-Meteo, NTV/BBC Türkçe RSS. Gerçek ağda ilk deneme kullanıcıda olacak; RSS adresleri değişmişse haber hata verir.
- **2026-09-30 (3.12):** Kullanıcı: "Spotify açıyor, müziği durdur çalışmıyor" → Spotify'a doğrudan WM_APPCOMMAND,
  genişletilmiş medya tuşları. Hava/haber (3.11) gerçek ağda henüz denendiği bildirilmedi.
- **2026-09-30 (3.13):** 3.12 gerçekte: "sonraki şarkı" (çalan şarkıyı söyledi) ve "müziği durdur" **çalıştı**; "müziğe devam et"
  "Zaten çalıyor: GDI+ Window (Spotify.exe)" dedi → yardımcı pencere hatası düzeltildi.
- **2026-09-30 (3.14):** 3.13 doğrulandı (müzik devam/durdur çalışıyor). Kullanıcı: "komut vermeden misafire geçti, daha önce
  de birkaç kez oldu" → oturum diskte saklanıp yeniden başlatmada geri yükleniyor + yankı algılama. Kullanıcıdan güvenlik
  kaydında o saatlerde "Tanınmayan ses" olup olmadığına bakması istendi (asıl nedeni ayırt etmek için).
- **2026-09-30:** Mikrofon kontrolü: ev bilgisayarında **MC-PW8 (Generic USB Audio)** mikrofon, Windows giriş düzeyi 100,
  Levels 0,0 dB (boost yok), ama Windows mikrofon testi **%1** → sinyal cihazdan çok zayıf (Studio One'da da tepe yok).
  Kullanıcıya: mikrofon konumu, cihazın kendi kazanç ayarı/pil, "exclusive mode" kutusunu kaldırma önerildi; hedef test
  %30–60. Düşük seviye kısa cümlelerde düşük ses tanıma puanlarının/"Tanınmayan ses"in nedeni olabilir.
  **SIRADAKİ (yarın):** Kullanıcı cihazı test edip sonucu (% değeri) söyleyecek. Değişmezse: Ayarlar'a canlı mikrofon
  seviye göstergesi + "mikrofon yükseltme" (yazılım kazancı, Whisper/ses tanımaya gitmeden önce) eklenecek. Ayrıca 3.14'ün
  (oturum geri yükleme, yankı) ve 3.11'in (hava/haber gerçek ağda) sonuçları, güvenlik kaydındaki "Tanınmayan ses"
  satırları sorulacak. Sonra kalan fikirler: notlar/liste, fotoğraf, belge, sabah özeti, uyandırma sözcüğü, sohbet arama.
- **2026-09-30 (3.15):** Mikrofon: **JMARY MC-PW8** USB masa mikrofonu (hiperkardioid, üzerinde +1…+25 dB kazanç ayarı
  var; ayrı sürücüsü yok, "Generic USB Audio" doğru sürücü). Kullanıcıya kazanç düğmesi ve konuşma yönü (logolu yüz) önerildi.
  İsteği: test kaydıyla kendi kendine ayarlayan mikrofon kalibrasyonu + Ayarlar'ın iki kolon ve kategorili olması → yapıldı.
  Kullanıcıdan kalibrasyon sonucunu (konuşma dB'i, önerilen kazanç) ve ardından sesini yeniden tanıtmasını beklemek.
- **2026-09-30:** 3.15 kalibrasyon gerçek sonucu (MC-PW8): konuşma **−42 dB**, tepe **−15 dB**, önerilen kazanç **+14 dB**
  (tepe sınırı yüzünden; hedef için +22 gerekirdi), gürültü (kazanç sonrası) **−68 dB** (çok temiz). Kazanç sonrası konuşma
  ≈ −28 dB: kullanılabilir. İyileştirme fikri: GainNode'dan sonra DynamicsCompressor (limiter, eşik −6 dB) koyup tepe
  sınırını kaldırmak → tam +22 dB. Kullanıcıya sesini yeniden tanıtması önerildi.
  Mert kalibrasyondan sonra sesini yeniden tanıttı: tutarlılık **0,886** (ilk kayıt 0,906; benzer). Sezin'in profili eski
  ayarla (Chrome AGC açık, kazanç yok) kaydedildi → onun da yeniden tanıtması önerildi. Yeni benzerlik puanları bekleniyor.
- **2026-09-30 (3.16):** Kullanıcı "kaldığımız işlerden devam" dedi (Sezin'i sonra yeniden tanıtacak) → listedeki ilk fikir:
  notlar ve alışveriş listesi. Sahte sunucu + Chromium ile test edildi. Sıradaki fikirler: fotoğraf anlama, belge yükleme,
  sabah özeti (hava + ajanda + listeler), uyandırma sözcüğü, eski sohbet arama.
- **2026-09-30 (3.17):** 3.16 gerçekte çalıştı ("…yoğurt ekle.", "Listelerimi göster."), ama "Alışveriş listesine peynir
  ekler misin?" modele gitti ve model "ekledim" diye uydurdu → rica biçimleri + sistem istemine dürüstlük satırı.
- **2026-09-30 (3.18):** 3.17 gerçekte çalıştı ("gösterir misin", "ekler misin" hazır cevap). "Alışveriş listemi göster."
  modele gitti, model "listende yok" dedi → "listem" biçimleri + istemde "içini tahmin etme".
  3.18 gerçekte doğrulandı (temizle, ekle, "Alışveriş listemi göster" hepsi hazır cevap). Kullanıcı sayaçtaki "hazır cevap"
  ifadesini anlamadı → anlamı açıklandı (etiketi değiştirmek istenirse ör. "yapay zekâsız, anında").
- **2026-09-30 (3.19):** Kullanıcı sıradaki olarak "Asiye diye seslenmek"i seçti; kısa olduğu için yanlış anlaşılmasından
  endişeli, "Merhaba Asiye" gibi daha uzun söz önerdi → söz ayarlanabilir, öneri olarak iki kelimelik söz yazıldı.
  Kullanıcının gerçek denemesi bekleniyor: yanlış uyanma / uyanmama, GPU yükü.
- **2026-09-30 (3.20):** İlk deneme: 👂 görünmüyordu → Ayarlar'daki kutu açılmamıştı (varsayılan kapalı). Mikrofonla
  "Merhaba Asiye" → Whisper "Merhaba size" yazdı → hotwords. Kullanıcıya kutuyu açması ve "Merhaba Asiye" sözü önerildi.
  3.20 gerçekte **çalıştı** (👂 görünüyor, seslenince cevap verdi). Kullanıcı misafir modunu sordu: uyandırma misafirde de
  açık (kodda misafir kısıtı yok); ses kimliği her seslenmede çalışır, tanınan ses profiline geçer. Kullanıcı: "misafir
  modunda çalışsın". Konuşurken kendiliğinden uyanmadı; müzik açınca uyandı → 3.21.
  3.21 gerçekte: müzikte yanlış uyanma olmadı ama müzik çalarken "Merhaba Asiye" de yakalanmadı → 3.22.
  3.22 gerçekte **doğrulandı**: telefonda müzik çalarken "Merhaba Asiye saat kaç" cevaplandı; Spotify yüksek seste
  "müziği durdur" yakalanmadı, ses kısılınca çalıştı. Kullanıcı: "normal, bu kadar tepki yeterli" → uyandırma tamam.
- **2026-09-30 (3.23):** Kullanıcı "3 (belge yükleme) ile devam, hem Türkçe hem İngilizce belgeleri algılasın" dedi →
  belgeler eklendi. Kullanıcının gerçek PDF/Word ile denemesi bekleniyor (özet kalitesi, hız, `ollama ps` ile 16k bağlamda
  %100 GPU kalıp kalmadığı).
- **2026-09-30 (3.24):** 3.23 PDF ile gerçekte çalıştı (.txt/.docx henüz denenmedi; bulutta test edildi). Kullanıcı Ayarlar'ı
  Notlar penceresi gibi sekmeli istedi → yapıldı.
- **2026-09-30 (3.25):** Word ve .txt belgeleri gerçekte çalıştı. İstekler: açılışta Mert oturumunun gelmesi fark edildi
  (→ elle açılışta oturum yok), sohbet adı "tarih-saat + ilk kelime", sohbet adını değiştirme, güvenlik kaydını temizleme.
  3.25 gerçekte doğrulandı (baslat → misafir, güvenlik kaydı silindi). Yeni istek: **HourGlow Music** betikleri
  (müzik/resim analizi) `C:\Users\mertbilgin\My Drive (hourglowmusic@gmail.com)\HourGlowMusic\Scripts\` altında; kullanıcı
  `Scripts\Asiye` klasörü açtı, "oraya attığım dosyaları analiz etsin, basit, çok parametre gerektirmeyen analizler" dedi.
  Klasördekiler medya dosyası mı betik mi, hangi analizler ve hangi conda ortamı (not: Hourglow betikleri `ai_assistant`
  ortamını kullanıyor) kullanıcıya soruldu. Kullanıcı: önerilen (asistan kendi analizini yapsın, istenince), "yapabildiği
  bütün analizleri yapsın, tek tek bir txt dosyasına yazsın, aynı klasörde" → 3.26.
- **2026-09-30 (3.27):** 3.26 gerçekte: "klasörünü aç" çalıştı, gerçek .wav'ın raporu yazıldı. "Hepsini yeniden analiz et."
  klasör kelimesi olmadığı için modele gitti; model 4 olmayan şarkıyı (BPM/ton/LUFS ile) uydurdu → düzeltildi.
  3.27 gerçekte doğrulandı ("doğru çalıştı"). Tempo/ton doğruluğu gerçek şarkılarda kullanıcıdan henüz duyulmadı.
- **2026-09-30 (3.28):** Kullanıcı: "HourGlow dediğimde Türkçe algılıyor, 'HourGlow Takip Dosyasını Excel'de aç' şaşırıyor" →
  özel kelimeler + Google Drive araması. Whisper'ın gerçekte ne yazdığı bilinmiyor; düzelmezse sayaçtaki/sohbetteki
  yazılışı kullanıcıdan iste ve `vocab`'a örnek ekle.
- **2026-09-30 (3.29):** 3.28 gerçekte: Whisper "HourGlow"u doğru yazdı, Google Drive aranıyordu, ama
  `HourGlow_Yayin_Takip.xlsx` bulunamadı: söylenen "yayın" (ı) ≠ dosya adı "Yayin" → `pc._ascii` ile iki taraf da Türkçe
  harfsiz karşılaştırılıyor. Kullanıcının dosyaları `My Drive (hourglowmusic…)\HourGlowMusic\` altında.

## Sıradaki fikirler

- **KURAL (kullanıcı, 2026-09-29): İnternet gerektiren her özellik (hava durumu, haberler, takvim eşitleme vb.) misafir
  modunda KAPALI olmalı.** Yalnızca sesle/şifreyle tanınmış kişiler kullanabilir.
- **Kullanıcının seçtiği sıra (2026-09-29):** 1) ✅ 3.5'te yapıldı: Hatırlatıcılar (sayaç, alarm, tarihli hatırlatma; kişiye özel, ortak
  "aile" yok; tarayıcı kapalıyken Windows bildirimi, asistan kapalıyken sonraki açılışta "kaçırılanlar"; yalnızca ev
  bilgisayarı) + **takvim kaydı oluşturma** (telefona bildirim gelsin diye; hangi takvim olduğu sorulacak — bulut servisi,
  kullanıcı onayı gerekir). 2) Yapabildiklerini komut örnekleriyle anlatan belge. Sonra listeden: notlar/alışveriş
  listesi (✅ 3.16), fotoğraf anlama (gemma3:4b görebilir), ✅ belge yükleme (3.23), sabah özeti, ✅ uyandırma sözcüğü (3.19), eski
  sohbetlerde arama, ✅ hava durumu/haber (3.11). Kullanıcı "hepsi çok güzel" dedi.

- Spotify: kullanıcı ücretsiz hesapta → otomatik çalma yok. Premium'a geçerse Spotify Web API (PKCE) ile "X çal".
- Kullanıcı conda ortamlarını (ComfyUI, comfyui, ai_assistant, muzik, tts, asistan) düzenlemek/birleştirmek için yardım isteyecek.
- Ses tanıma: Sezin'in 3.3 puanlarını gör (özellikle Mert profiline benzerliği); gerekirse eşik/MARGIN ayarı.
- 1b yetersiz kalırsa zayıf bilgisayar için başka küçük model dene (ör. `gemma3n:e2b`, `qwen3:1.7b`); sonucu kullanıcıdan öğren.
- Ana bilgisayara kurulum (henüz yapılmadı).
- İstenirse tamamen yerel kadın sesi: NVIDIA olduğu için ses klonlama (XTTS-v2 / Chatterbox Multilingual gibi,
  Türkçe destekli) eklenebilir; kullanıcı bir kadın sesi örneği verir.
- Hafıza büyüdükçe: tüm bilgileri isteme koymak yerine anlamsal arama (Ollama embedding modeli).
- Eski sohbetlerde arama.
- Tek tıkla çalışan masaüstü uygulaması (Python kurulumu gerektirmeyen paket).
