# Proje notları: Yerel Asistan

Bu dosya, projeyi geliştiren Claude oturumları ve proje sahibi için ortak not defteridir.
Her oturumun sonunda "Geçmiş" ve "Sıradaki fikirler" bölümlerini güncelle.

## Kullanıcı hakkında

- Proje sahibi yazılımcı değil: açıklamaları **Türkçe**, sade ve adım adım yap; teknik terimleri açıkla.
- **Windows** kullanıyor. Kurulum/çalıştırma talimatları Windows'a göre olmalı (çift tıklanan `.bat` dosyaları).
- Öncelik **gizlilik**: veriler bilgisayardan çıkmamalı. Bulut servisi / API anahtarı gerektiren bir şey eklemeden önce kullanıcıya sor.

## Projenin amacı

Kullanıcının kendi bilgisayarında çalışan, güzel arayüzlü, yazılı ve sesli konuşulabilen,
konuşulanları hatırlayan ve yeni sohbetlerde de unutmayan kişisel yapay zekâ asistanı.

## Mimari

- `run.py`: Sunucuyu `127.0.0.1:8765`'te başlatır ve tarayıcıyı açar (yalnızca yerelden erişilir).
- `app/main.py`: FastAPI uç noktaları (sohbet akışı NDJSON, sohbetler, hafıza, ayarlar, ses→yazı).
- `app/llm.py`: Yerel **Ollama** istemcisi (`http://127.0.0.1:11434`). Varsayılan model `gemma3:4b`.
- `app/memory.py`: Sistem istemini kurar (hafızadaki bilgiler + tarih). Her yanıttan sonra arka planda
  modelden JSON ile yeni kalıcı bilgiler çıkarır ve `memories` tablosuna ekler (büyük/küçük harf duyarsız tekrar kontrolü).
- `app/db.py`: SQLite (`data/asistan.db`): `conversations`, `messages`, `memories`.
- `app/stt.py`: **faster-whisper** ile çevrimdışı ses→yazı (model ilk kullanımda indirilir).
- `app/config.py`: Ayarlar `data/settings.json` (asistan adı, model, whisper modeli, dil).
- `static/`: Harici kütüphane kullanmayan arayüz (HTML/CSS/JS). Yazı→ses tarayıcıdaki
  **yalnızca yerel** (`localService`) Windows sesleriyle yapılır, çevrimiçi seslere metin gönderilmez.
- `kurulum.bat` / `baslat.bat`: Windows kurulumu ve başlatma (CRLF satır sonları, `.gitattributes` ile korunuyor).
- `data/` git'e girmez: kullanıcının özel verileri orada.

## Test

- Bulut ortamında Ollama yok: `app` sahte bir Ollama sunucusuyla (`/api/tags`, `/api/chat` akışlı + `format: json`)
  test edildi; arayüz headless Chromium ile ekran görüntüsü alınarak kontrol edildi.
- Gerçek Windows + Ollama + mikrofon üzerinde **henüz kullanıcıdan geri bildirim alınmadı**.

## Geçmiş

- **2026-09-25:** İlk sürüm yazıldı (sohbet, kalıcı hafıza, sohbet geçmişi, sesli giriş/çıkış, ayarlar,
  Türkçe README). Kullanıcı kurulumu henüz denemedi.

## Sıradaki fikirler

- Kullanıcının ilk kurulum deneyimini dinle, çıkan hataları düzelt.
- Hafıza büyüdükçe: tüm bilgileri isteme koymak yerine anlamsal arama (Ollama embedding modeli).
- Eski sohbetlerde arama.
- Dosya/belge yükleyip onun hakkında konuşma.
- Hatırlatıcılar / notlar.
- Tek tıkla çalışan masaüstü uygulaması (Python kurulumu gerektirmeyen paket).
