# Asistanla neler yapabilirsin?

Bu sayfa, asistanın bugün yapabildiklerini **örnek komutlarla** anlatır. Komutları yazabilir ya da 🎤 düğmesine basıp
söyleyebilirsin. Aynen böyle söylemen gerekmez; benzer cümleler de çalışır.

Sürüm: 3.6

---

## 💬 Sohbet ve sorular

Aklına gelen her şeyi sorabilirsin. Asistan senin bilgisayarında çalışır, internete gitmez.

- "Bana akşam yemeği için kolay bir tarif öner."
- "Bu e-postayı daha kibar yaz: …"
- "Şunu İngilizceye çevir: …"
- "Bir çocuğa fotosentezi nasıl anlatırım?"

## 🎤 Sesli konuşma

- 🎤 düğmesine bas ve konuş. Sustuğunda kayıt kendiliğinden biter.
- Sağ üstteki **🔊 Sesli yanıt** açıksa cevaplar sesli okunur.
- Ayarlar'da "Sesli sohbet" açıksa, cevap okunduktan sonra mikrofon kendiliğinden yeniden açılır. Böylece eller serbest
  konuşmaya devam edebilirsin.

## 🕐 Saat ve tarih

Bu sorular yapay zekâya gitmez; doğrudan bilgisayarın saatinden, anında ve her zaman doğru cevaplanır.

- "Saat kaç?"
- "Bugün ayın kaçı?"
- "Bugün günlerden ne?"

## ⏰ Hatırlatıcılar, alarmlar, sayaçlar (3.5)

**Sayaç:**
- "20 dakikalık sayaç kur"
- "Yarım saatlik sayaç"
- "10 dakika sonra çayı hatırlat"
- "1 saat 30 dakika sonra fırını kapatmamı hatırlat"

Çalışan sayaç, mesaj kutusunun üstünde geri sayımla görünür. ✕ ile iptal edebilirsin.

**Alarm:**
- "Yarın sabah 7'de uyandır"
- "7 buçukta uyandır"
- "Gece 11'de alarm kur"

**Tarihli hatırlatma:**
- "Saat 15:30'da annemi aramamı hatırlat"
- "Akşam 8'de ilacımı hatırlat"
- "Cuma akşamı çöpleri çıkarmayı hatırlat"
- "15 Ekim'de Sezin'in doğum gününü hatırlat"
- "30 Eylül 2026 saat 10'da dişçi randevumu hatırlat"

**Tekrarlayan hatırlatma:**
- "Her gün saat 22'de ilacımı hatırlat"
- "Her pazartesi 9'da haftalık toplantıyı hatırlat"
- "Her yıl 15 Ekim'de evlilik yıldönümümüzü hatırlat"

**Sorma ve iptal etme:**
- "Hatırlatmalarım neler?"
- "Sayaç ne kadar kaldı?"
- "Sayacı iptal et" / "Alarmı iptal et" / "Tüm alarmları iptal et"

**Nasıl çalışır?**
- Zamanı gelince ekranda bir pencere açılır, zil çalar ve asistan hatırlatmayı sesli okur. **Tamam**'a basınca susar.
- Tarayıcı kapalı ama siyah pencere (`baslat.bat`) açıksa, sağ altta bir **Windows bildirimi** çıkar.
- Asistan tamamen kapalıysa, bir sonraki açılışta hatırlatma "Kaçırılan hatırlatma" olarak gösterilir.
- Saat verilmeyen tarihlerde (ör. "15 Ekim'de") hatırlatma sabah **09:00**'da çalar.
- Hatırlatmalar **kişiye özel**: Mert'inkileri Sezin görmez, Sezin'inkileri Mert görmez. Başkasının alarmı çalarsa
  yalnızca "Sezin için bir hatırlatma var" yazar, içeriği görünmez. Misafir hatırlatma kuramaz.
- Sol menüdeki **⏰ Hatırlatıcılar** panelinden hepsini görebilir, elle ekleyebilir ve silebilirsin.

## 📅 Outlook takvimi ve telefon (3.6)

Hatırlatmaların Outlook takvimine de eklenir, böylece telefonunda da bildirim çıkar.

- Açmak için (bir kez): **⚙️ Ayarlar** → "📅 Hatırlatmalarımı Outlook takvimime de ekle" kutusunu işaretle →
  **Outlook bağlantısını dene** → **Kaydet**.
- Sonra her hatırlatmada "📅 Outlook takvimine de ekliyorum" dersin. İptal edince takvimden de silinir.
- Yalnızca yöneticinin (Mert'in) hatırlatmaları eklenir; sayaçlar eklenmez.
- Bilgisayarda **klasik Outlook** programı kurulu ve hesabın ekli olmalı ("yeni Outlook" desteklenmiyor).

## 📊 Excel ve dosyalar (3.6)

- "Excel'i aç"
- "Bütçe dosyasını Excel'de aç"
- "Notlar dosyasını aç" (Word, PDF, PowerPoint dosyalarını da açar)
- "Açık Excel dosyaları neler?"
- "Bütçe dosyasını kaydet"
- "Excel'i kaydederek kapat"
- "Excel'i kaydetmeden kapat"
- "Bütçe dosyasını kaydetmeden kapat"
- "Excel'i kapat" (kaydedilmemiş değişiklik varsa Excel kendisi sorar)

Dosyalar Masaüstü, Belgeler, İndirilenler ve OneDrive klasörlerinde adına göre aranır. Aynı adda birden çok dosya
varsa en son değiştirilen açılır. Hiç kaydedilmemiş yeni bir kitap ("Kitap1") "kaydederek kapat" denince açık bırakılır,
çünkü bir dosya adı yoktur.

Excel hakkında soru sormak ("Düşeyara nasıl kullanılır?") komut sayılmaz; asistan normal cevap verir.

## 🎵 Müzik ve Spotify (3.6)

Bilgisayarda çalan müziği (Spotify, YouTube, vb.) yönetir:

- "Sonraki şarkı" / "Önceki şarkı"
- "Müziği durdur" / "Müziğe devam et"
- "Sesi aç" / "Sesi kıs" / "Sesi kapat"

Spotify:

- "Spotify'ı aç"
- "Spotify'da Tarkan çal" → Spotify'da aramayı açar; çalmak için sonuçlardan birine basarsın.
  (Şarkıyı kendiliğinden başlatmak için Spotify Premium bağlantısı gerekir; planlananlar arasında.)

Misafir modunda bilgisayar komutları (Excel, dosyalar, müzik, Spotify) çalışmaz.

## 🧠 Hafıza

Asistan sohbetlerden senin hakkındaki önemli bilgileri kendiliğinden öğrenir ve yeni sohbetlerde de hatırlar.

- "Benim adım Mert, Bursa'da yaşıyorum."
- "Kızımın adı Elif, 3 Mayıs'ta doğdu."
- "Hakkımda neler biliyorsun?"

Sol menüdeki **🧠 Hafıza** panelinden öğrendiklerini görebilir, yanlış olanları silebilir, kendin de ekleyebilirsin.
Herkesin hafızası ayrıdır.

## 🎙️ Ses ile tanıma ve güvenlik

- Asistan konuşanı sesinden tanır. Altta **👤 Mert · yönetici** ya da **👤 Sezin** yazar.
- Tanımadığı bir ses konuşursa **Misafir** moduna geçer. Misafir genel sorular sorabilir ama özel bilgileri, hafızayı,
  hatırlatmaları göremez; internet gerektiren özellikleri kullanamaz.
- **`1234`** yaz: kilitlenir ve misafir moduna geçer. Kilidi tanınan bir ses ya da şifre açar.
- **Kişisel şifre** (ör. hastayken sesin değişirse): şifreni yazıp gönder, kendi oturumuna geçersin.
- **`Sezin1234`** (yalnızca yönetici, kendi oturumundayken): Sezin'in oturumuna geçer.
- **🛡️ Güvenlik kaydı** (yalnızca yönetici): tanınmayan sesler, misafir mesajları, şifre denemeleri.
- **⚙️ Ayarlar** yalnızca yöneticiye görünür.

## 💡 İpuçları

- Ses tanıma cümle uzadıkça daha iyi çalışır. Tek kelime ("Asiye?") yerine kısa bir cümle kur.
- Sol alttaki sürüm numarası, güncellemenin gelip gelmediğini gösterir.
- Bir şey tuhaf davranırsa siyah pencereyi kapatıp `baslat.bat` ile yeniden aç.

---

## 🔜 Planlananlar

- 🎧 Spotify'da şarkıyı kendiliğinden başlatma (Premium hesap + bağlantı gerekir)
- 📝 Notlar ve alışveriş listesi ("Listeye süt ekle")
- 🖼️ Fotoğraf anlama ("Bu fişte ne yazıyor?")
- 📄 Belge yükleme ("Bu PDF'i özetle")
- ☀️ Sabah özeti ("Günaydın" deyince günün hatırlatmaları)
- 👂 Uyandırma sözcüğü (mikrofona basmadan "Asiye" diye seslenmek)
- 🔎 Eski sohbetlerde arama
- 🌦️ Hava durumu ve haberler (internet gerekir; yalnızca tanınan kişiler kullanabilir)
