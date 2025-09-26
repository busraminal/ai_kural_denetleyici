# 🏗️ AI Kural Denetleyici  

**AI Kural Denetleyici**, gayrimenkul değerleme raporlarının **mevzuat ve standartlara uygunluğunu** hem **kural tabanlı** (rule-engine) hem de **yapay zekâ destekli** analizlerle denetleyen bir sistemdir.  

Bu proje, manuel kontrol süreçlerinde kaybolan zamanı azaltmayı, hata payını düşürmeyi ve düzenleyici uyumu (compliance) artırmayı hedefler.  

---

## 📌 Amaç  

Gayrimenkul değerleme raporlarında:  
- 📑 **Eksik alanlar** (ör. ada/parsel, ekspertiz tarihi, rapor no)  
- 🧾 **Format hataları** (ör. yanlış TCKN, yanlış tarih formatı)  
- 🔀 **Çapraz-alan tutarsızlıkları** (ör. raporda konut yazıyor ama fiili kullanım depo)  
- 📖 **Mevzuat uyumsuzlukları** (SPK, BDDK, IVSC, RICS standartları)  

gibi sorunlar sıkça görülür.  

AI Kural Denetleyici, bu sorunları otomatik tespit ederek **Excel/PDF çıktıları** üretir.  

---

## ⚙️ Teknik Mimari  

```
ai_kural_denetleyici/
│
├── src/                  
│   ├── rules/            # JSON/YAML kural setleri
│   ├── analyzers/        # Rapor çözümleme modülleri
│   ├── llm/              # Ollama + FAISS + BM25 + reranker entegrasyonu
│   ├── outputs/          # Excel/PDF rapor üretici
│   └── main.py           
│
├── data/rules/           # Örnek mevzuat kuralları
├── report/               # Örnek değerleme raporları
├── config.yaml           # Sistem ayarları
└── README.md
```

### 🧠 AI Katmanı
- **Yerel LLM (Ollama)** → Phi-3, Qwen, Mistral gibi modellerle *offline inference*.  
- **FAISS + BM25 hibrit arama** → rapor ve mevzuat dokümanlarında arama & chunk retrieval.  
- **Reranker** → semantic aramadan sonra en uygun kuralı seçme.  
- **RAG (Retrieval-Augmented Generation)** → PDF mevzuatlardan bağlamlı kural denetimi.  

### 🔧 Rule Engine Katmanı
- YAML/JSON kural dosyaları → zorunlu alan & format kuralları.  
- Hızlı if-else kontrolleri → TCKN, tarih formatı, ada/parsel yapısı.  

### 📊 Çıktı Katmanı
- Renk kodlu **Excel raporu**  
- Yöneticiye hazır **PDF özet raporu**  

---

## 🚀 Kurulum  

### Gereksinimler  
- Python **3.11+**  
- Ollama (yerel LLM çalıştırmak için)  
- `pip install -r requirements.txt`  

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

Ollama için:  
```bash
ollama pull qwen2.5:7b
ollama pull mistral
```

---

## ▶️ Kullanım  

```bash
# Kural tabanlı kontrol
python src/main.py --input report/ornek_rapor.pdf --output kontrol.xlsx

# AI destekli RAG kontrol
python src/main.py --input report/ornek_rapor.pdf --rag --output kontrol_ai.xlsx
```

---

## 📊 Örnek Çıktı  

| Alan Adı           | Beklenen Değer | Rapor Değeri  | Durum       | Açıklama |
|--------------------|----------------|---------------|-------------|----------|
| Rapor Numarası     | Zorunlu        | (boş)         | ❌ Eksik     | SPK Mevzuatı md.12 gereği zorunlu |
| Fiili Kullanım     | Konut          | Depo          | ⚠️ Tutarsız | Tapu kaydı ile uyumsuz |
| Ada/Parsel         | Numeric        | "12/A"        | ❌ Hatalı   | Format hatası |
| Uzman TCKN         | 11 haneli      | 123456        | ❌ Hatalı   | Regex kontrolü başarısız |

---

## 🧩 Özellikler  

- 📑 **Eksik Alan Kontrolü** → zorunlu alanların boş olup olmadığını tespit eder.  
- 🧮 **Format Denetimi** → TCKN, tarih, ada/parsel kuralları.  
- 🔀 **Çapraz Alan Tutarlılığı** → fiili kullanım vs rapor bilgisi.  
- 📖 **Mevzuat RAG** → PDF mevzuatından kuralları otomatik çekip yorumlatır.  
- 📊 **Excel/PDF Raporlama** → yöneticiye hazır çıktı üretir.  
- ⚡ **Yerel LLM Desteği** → internet olmadan çalışır, gizlilik dostu.  

---

## 🛠️ Yol Haritası  

- [ ] Çoklu rapor batch analizi  
- [ ] Web arayüzü (Flask/Django)  
- [ ] Docker imajı  
- [ ] CI/CD pipeline  
- [ ] LLM destekli otomatik kural çıkarımı  

---

## 📜 Lisans  
MIT License © 2025  
