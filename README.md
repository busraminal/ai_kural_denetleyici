# 🏗️ AI Kural Denetleyici  

**AI Kural Denetleyici**, gayrimenkul değerleme raporlarının **mevzuat ve standartlara uygunluğunu otomatik denetleyen** bir yazılım sistemidir.  
Bu proje, manuel kontrol süreçlerinde kaybolan zamanı azaltmayı, hata payını düşürmeyi ve düzenleyici uyumu (compliance) artırmayı hedefler.  

---

## 📌 Amaç  

Gayrimenkul değerleme raporları; **SPK, BDDK, TSKB** ve uluslararası standartlara (IVSC, RICS vb.) uygun hazırlanmak zorundadır.  
Ancak bu raporlarda:  
- Eksik alanlar (ör. ada/parsel, ekspertiz tarihi, rapor no)  
- Format hataları (ör. yanlış TCKN, yanlış tarih formatı)  
- Çapraz-alan tutarsızlıkları (ör. raporda konut yazıyor ama fiili kullanım depo)  

gibi sorunlar sıkça görülür.  

AI Kural Denetleyici, bu sorunları otomatik tespit ederek **Excel/PDF çıktıları** ile raporlar.  

---

## ⚙️ Teknik Mimari  

```
ai_kural_denetleyici/
│
├── src/                  # Ana uygulama kodları
│   ├── rules/            # JSON/YAML kural setleri
│   ├── analyzers/        # Rapor çözümleme modülleri
│   ├── outputs/          # Excel/PDF rapor üretici
│   └── main.py           # Çalıştırma dosyası
│
├── data/rules/           # Örnek mevzuat kuralları
├── report/               # Örnek değerleme raporları
├── .gitignore
├── config.yaml           # Sistem ayarları
└── README.md
```

- **Kural Motoru (Rule Engine)** → YAML/JSON dosyalarından kuralları okur.  
- **Metin Çözücü (Parser)** → PDF/Word raporlarını chunk’lara ayırır.  
- **Denetleyici (Validator)** → her chunk için zorunlu alan/format kontrolü yapar.  
- **Raporlayıcı (Reporter)** → eksik ve hatalı kısımları Excel’de renk kodlu olarak işaretler.  

---

## 🚀 Kurulum  

### Gereksinimler  
- Python **3.11+**  
- `pip install -r requirements.txt`  

### Adımlar  
```bash
# Repo klonla
git clone https://github.com/busraminal/ai_kural_denetleyici.git
cd ai_kural_denetleyici

# Sanal ortam (opsiyonel)
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/Mac

# Bağımlılıkları yükle
pip install -r requirements.txt
```

---

## ▶️ Kullanım  

```bash
python src/main.py --input report/ornek_rapor.pdf --output kontrol_sonucu.xlsx
```

- `--input` → kontrol edilecek rapor dosyası  
- `--output` → denetim sonucunun kaydedileceği Excel dosyası  

---

## 📊 Örnek Çıktı  

| Alan Adı           | Beklenen Değer | Rapor Değeri  | Durum       |
|--------------------|----------------|---------------|-------------|
| Rapor Numarası     | Zorunlu        | (boş)         | ❌ Eksik     |
| Fiili Kullanım     | Konut          | Depo          | ⚠️ Tutarsız |
| Ada/Parsel         | Numeric        | "12/A"        | ❌ Hatalı   |
| Uzman TCKN         | 11 haneli      | 123456        | ❌ Hatalı   |

---

## 🧩 Özellikler  

- 📑 **Eksik Alan Kontrolü** → zorunlu alanların boş olup olmadığını tespit eder.  
- 🧮 **Format Denetimi** → tarih, TCKN, ada/parsel gibi format kurallarını kontrol eder.  
- 🔀 **Çapraz Alan Tutarlılığı** → farklı alanların birbiriyle uyumunu karşılaştırır.  
- 📊 **Excel/PDF Raporlama** → sonuçları renk kodlu, yöneticiye hazır formatta üretir.  
- ⚡ **Hızlı ve Modüler** → yeni kural setleri kolayca eklenebilir.  

---

## 🛠️ Yol Haritası  

- [ ] Mevzuat RAG entegrasyonu (PDF mevzuattan kural çekme)  
- [ ] Web arayüzü (Flask/Django ile)  
- [ ] Çoklu rapor toplu kontrol özelliği  
- [ ] CI/CD ve Docker desteği  

---

## 📜 Lisans  

MIT License © 2025  
