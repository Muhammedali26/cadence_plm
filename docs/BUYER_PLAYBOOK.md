# CadencePLM – Kurumsal Satış ve Değer Kanıtlama Kılavuzu (Buyer Playbook)

Bu kılavuz; Tier-1 ve Tier-2 otomotiv imalatçılarında **CadencePLM** çözümünün değer teklifini, ekonomik getirisini (ROI), müşteri itirazlarına karşı teknik yanıtları ve canlı demo senaryolarını endüstriyel gerçeklikle tanımlar.

---

## 1. HEDEF MÜŞTERİ PROFİLİ (ICP & KARAR VERİCİ ROLLER)

| Rol | Birincil Öncelik / Ağrı Noktası | CadencePLM Değer Argümanı |
| :--- | :--- | :--- |
| **VP of Engineering / Ar-Ge Direktörü** | Revizyonların montaj hattına etkisini görememe; Where-Used zincirini manuel Excel ile çıkarma riski; IATF 16949 denetim bulguları. | Tek bir ECO metninden kök montaja kadar tüm etkilenen alt/üst sistemleri saniyeler içinde çıkarır; IATF 16949 / PPAP Seviye 3 resmi etki raporunu otomatik üretir. |
| **Fabrika Müdürü / Operasyon Direktörü** | Hatalı yürürlük (effectivity) planı yüzünden montaj hattının durması (Otomotiv montaj hattı duruş maliyeti: **~1.200 $/dakika**); ambarda unutulan eski revizyon stokları. | `run_out_days` ve kalıp teslim süresini karşılaştırarak `USE_UP_STOCK` vs `IMMEDIATE_CUTOFF` kararını deterministik matematik ile verir; hat duruşunu sıfıra indirir. |
| **Satınalma / Tedarik Zinciri Direktörü** | Toleransı değişen parçaların gereksiz yere toptan hurdaya (scrap) yazılması; tedarikçi kalıp teslim sürelerinin (tooling lead time) hesaba katılmaması. | Tolerans ve geometri değişikliklerinde talaşlı imalat (CNC Torna) kurtarma fizibilitesini hesaplar; parça başı %15 maliyetle stoğu kurtarıp hurda bütçesini korur. |

---

## 2. ROI HESAPLAMA VE DEĞER MATEMATİĞİ

Müşteriye yöneltilen temel soru:  
> *"CadencePLM için yıllık 60.000 $ lisans bedeli ödüyorsunuz. Bu sistem kendini ilk çeyrekte nasıl amorti eder?"*

### Senaryo Verileri (Tipik Tier-1 Şanzıman / Aktarma Fabrikası)
- **Yıllık Ortalama ECO Sayısı:** 35 adet.
- **ECO Başına Manuel Mühendislik Emeği:** 3 mühendis (Ar-Ge, İmalat, Satınalma) $\times$ 4 iş günü = 96 mühendis-saati.
  - Saatlik maliyet: 50 $/saat $\rightarrow$ ECO başına **4.800 $** analiz maliyeti.
  - Yıllık analiz işçilik yükü: $35 \times 4.800 = \mathbf{168.000\ \$}$.
- **Hatalı Hurda / Rework Kaybı:** Yıllık ortalama 4 ECO'da kurtarılabilir parçalar aceleyle hurdaya ayrılır (ECO başına ortalama 12.000 $ hurda kaybı = **48.000 $**).
- **Montaj Hattı Duruş Riski:** Yılda en az 1 kez tedarikçi kalıbı yetişmeden eski revizyon stokunun erken kesilmesi sonucu 45 dakikalık hat duruşu ($45 \text{ dk} \times 1.200\ \$/\text{dk} = \mathbf{54.000\ \$}$).

### Finansal Getiri Özeti (Yıllık Kazanç)

| Finansal Kalem | Yıllık Parasal Değer |
| :--- | :--- |
| **Analiz Süresi Tasarrufu** (35 ECO/yıl, %85 azalma) | +142.800 $ |
| **Hurda Tasarrufu** (Rework / CNC Kurtarma) | +42.000 $ |
| **Önlenen Hat Duruşu Riski** (1 vaka @ 1.200 $/dk) | +54.000 $ |
| **Toplam Yıllık Brüt Tasarruf** | **+238.800 $** |
| **CadencePLM Lisans Bedeli** | -60.000 $ |
| **Net Yıllık Kazanç** | **+178.800 $ (%298 Net ROI)** |

**Amortisman Süresi:** 2. büyük ECO değişikliğinde (yaklaşık **2,5 ayda**) sistem kendi lisans bedelini amorti eder.

---

## 3. EN SERT 5 MÜŞTERİ İTİRAZI VE MÜHENDİSLİK YANITLARI

### İtiraz 1: *"Biz zaten SAP S/4HANA ve Siemens Teamcenter kullanıyoruz, buna ne gerek var?"*
> **Yanıt:**  
> "Teamcenter tasarım revizyonunu tutar, SAP ise fabrika ambarındaki stok sayısını tutar. Ancak ikisi birbiriyle konuşup şu soruyu yanıtlamaz: *'Pinyon dişlisinin toleransını 0.02 mm daralttığımızda, SAP'deki 55 adet parça CNC tezgahında 20.25 $'a kurtarılabilir mi, yoksa 7.425 $ hurda yazıp diferansiyel montajını 30 gün bekletecek miyiz?'*  
> Bu sorunun cevabı iki sistemde de yoktur; mühendisleriniz bunu haftalarca Excel tabloları ve departmanlar arası toplantılarla çözmeye çalışır. CadencePLM mevcut ERP ve PLM yatırımlarınızı değiştirmez; onların üzerine 10 saniyelik otonom simülasyon ve trade-off karar katmanı ekler."

---

### İtiraz 2: *"Yapay zeka tolerans veya maliyet hesabı yaparken halüsinasyon görürse fabrikamız durur!"*
> **Yanıt:**  
> "CadencePLM mimarisinde yapay zeka **ASLA** matematik hesabı yapmaz, maliyet çarpımı yapmaz ve ağaç gezintisi yürütmez (`.antigravityrules §1`).  
> Hurda maliyeti, Where-Used hiyerarşisi, CNC tornalama tasarrufu ve stok tüketim günleri tamamen deterministik, saf Python matematik motorlarımızda hesaplanır. Yapay zeka (OpenAI GPT-4o) sadece mühendisin yazdığı serbest metin talebi anlamak ve Python motorlarımızın ürettiği kesin sayıları IATF 16949 formatında yöneticilere özetlemek için kullanılır. API bağlantınız kopsa bile motorlarımız hatasız ve deterministik çalışır."

---

### İtiraz 3: *"Şirket içi 3D CAD ve maliyet verilerimiz OpenAI'a mı gidiyor? Fikri mülkiyet (IP) riski var mı?"*
> **Yanıt:**  
> "Kesinlikle hayır. CAD geometrileriniz, parça çizimleriniz ve STEP dosyalarınız sunucunuzdan dışarı çıkmaz; yerel ISO 10303-21 CAD parser motorumuz tarafından bellekte işlenir.  
> LLM'e sadece metin talebi iletilir. Ayrıca kurumsal mimarimizde OpenAI yerine tamamen şirket içi donanımınızda çalışan yerel açık kaynak modeller (Llama 3 / vLLM) veya izole Microsoft Azure OpenAI kurumsal tenant'ı saniyeler içinde devreye alınabilir."

---

### İtiraz 4: *"Bizim parçalarımız ve montaj ağaçlarımız standart dışı, çok karmaşık."*
> **Yanıt:**  
> "CadencePLM parça isimleriyle değil, endüstri standardı Döngüsel Olmayan Yönlü Çizge (DAG) topolojisiyle çalışır. İster 3 parçalık basit bir braket, ister 15 seviyeli çift kavramalı bir şanzıman olsun; ebeveyn-çocuk ilişkileri ve döngüsel bağımlılık kontrolleri matematiksel kesinlikle çözülür. Sistem döngü tespit ettiği anda `BOMStructureError` fırlatarak hatalı veriyi anında izole eder."

---

### İtiraz 5: *"Geçiş ve entegrasyon süreci aylar sürer mi? BT ekibimizi kilitler mi?"*
> **Yanıt:**  
> "Hayır. CadencePLM mikroservis mimarisindedir ve hazır `Docker` / `Docker-Compose` konteynerleri ile gelir. Kurulum 5 dakikadır.  
> SAP'den standart envanter CSV'si ve Teamcenter'dan EBOM CSV veya STEP çıktısı sağlandığı anda kokpit canlıya geçer. Ağır veritabanı şema dönüşümleri veya aylarca süren ERP danışmanlık süreçleri gerektirmez."

---

## 4. 3 ALTIN DEMO SENARYOSU (ADIM ADIM DEMO PLANI)

Müşteri karşısında ekran açıldığında (`http://localhost:8501`) sırasıyla şu 3 vaka gösterilmelidir:

```
+-----------------------------------------------------------------------------------------+
|                                    DEMO AKIŞ PLANI                                      |
|                                                                                         |
|  [Senaryo 1: Kurtarma]      --->    [Senaryo 2: Kaçınılmaz Hurda] --->  [Senaryo 3: ECN]|
|  GB-PINION-02 Tolerans              GB-SHAFT-01 Malzeme                 Resmi HTML      |
|  (6.311 $ Net Rework Kazancı)       (32.650 $ Hurda & Kalıp Riski)      Dossier İndirme |
+-----------------------------------------------------------------------------------------+
```

---

### Vaka 1: Kurtarılabilir İmalat Vakası (GB-PINION-02 Tolerans Daralması)
- **Aksiyon:** Sol menüden `Senaryo 1: GB-PINION-02 Tolerans Daralması (Kurtarılabilir)` butonuna basılır ve `🚀 Simülasyonu ve Ajanı Başlat` tıklanır.
- **Ekranda Gösterilecekler:**
  - KPI Kartları: *Toplam Hurda Maliyeti:* $7.425,00$ | *Kurtarma (Rework) Tasarrufu:* **+$6.311,25$ Net Tasarruf** | *Stok Tüketim:* 11 Gün (`USE_UP_STOCK`).
  - Plotly Grafiği: Brüt Hurda vs. Rework Tasarrufu bar grafiği.
  - Where-Used Akışı: `GB-PINION-02 ➔ GBX-1300 ➔ GBX-1000`.
- **Konuşma Metni:**
  > *"Sayın Fabrika Müdürüm, pinyon dişlisinde tolerans daraldığında geleneksel sistemde bu parça ambarda 'uygunsuz' işaretlenir ve 7.425 $ hurdaya yazılır.  
  > CadencePLM anında parça tipini (işlenebilir dişli) ve operasyon türünü (CNC torna) tespit etti. Birim maliyetin sadece %15'i ile (20.25 $) parçayı kurtarabileceğimizi hesapladı ve şirketinize tek bir tıklamayla **6.311 $ net nakit tasarruf** sağladı."*

---

### Vaka 2: Kaçınılmaz Hurda & Tedarikçi Kalıp Riski (GB-SHAFT-01 Malzeme Değişimi)
- **Aksiyon:** Sol menüden `Senaryo 2: GB-SHAFT-01 Mil Malzeme Alaşımı Değişimi (Hurda Kaçınılmaz)` seçilir ve çalıştırılır.
- **Ekranda Gösterilecekler:**
  - KPI Kartları: *Toplam Hurda Maliyeti:* **$32.650,00$** | *Kurtarma:* $0.00$ (Kurtarma Yok) | *Kritik Kalıp:* 28 Gün.
  - Yönetici Özeti: Ajanın "Malzeme alaşımı 16MnCr5'ten 42CrMo4'e geçtiği için talaşlı imalatla kurtarma imkansızdır; parçalar hurdaya ayrılmalıdır" tespiti.
- **Konuşma Metni:**
  > *"Şimdi malzeme alaşımı değişen bir vaka görüyoruz. Sistemimiz ezbere 'kurtaralım' demez; malzeme değişiminde talaşlı imalatın imkansız olduğunu bilir ve hurdayı kaçınılmaz olarak işaretler.  
  > Ayrıca bu milin altındaki 1. ve 2. vites tahrik dişlilerini ve rulmanları da etki altına alarak toplam 32.650 $'lık risk zincirini ve 28 günlük kalıp teslim süresini önünüze koyar. Satınalma ekibiniz bu sayede sürpriz bir hat duruşu yaşamaz."*

---

### Vaka 3: IATF 16949 / PPAP Resmi ECN Dossier İndirme & Denetim Onayı
- **Aksiyon:** Ekranın altındaki `📥 IATF 16949 / PPAP Resmi ECO Raporunu İndir (.html)` butonuna basılır ve inen HTML dosyası yeni sekmede açılır.
- **Ekranda Gösterilecekler:**
  - Modern koyu tema, IATF 16949 Madde 8.5.6 başlığı.
  - Finansal Trade-Off kartları, Tedarikçi Kalıp Risk Matrisi.
  - Ar-Ge, Satınalma ve Kalite Güvence müdürlerinin ıslak imza / elektronik onay kutuları (`PPAP-OK`).
- **Konuşma Metni:**
  > *"Son olarak, denetçiler veya otomotiv ana sanayi (OEM) kapınızı çaldığında; mühendislerinizin günlerce rapor hazırlamasına gerek kalmaz.  
  > CadencePLM, AIAG/VDA PPAP Seviye 3 standartlarında, tüm finansal ve teknik kanıtları içeren resmi ECN dosyasını tek tıkla üretir. İmzalar atılır, denetimden sıfır bulguyla geçilir."*
