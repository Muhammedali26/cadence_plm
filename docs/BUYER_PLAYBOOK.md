# CadencePLM – Enterprise Buyer Playbook & Commercial Value Card (Buyer Playbook)
> **Bilingual Commercial & Sales Enablement Guide / İki Dilli Kurumsal Satış Kılavuzu**  
> *English version is presented first, followed by the Turkish version below.*  
> *Önce İngilizce versiyon sunulmuştur; Türkçe versiyon belgenin devamında yer almaktadır.*

---

# [ENGLISH] Enterprise Buyer Playbook & Battlecard

This playbook defines the commercial value proposition, return on investment (ROI) economic model, technical objection handling, and live demo runbooks for deploying **CadencePLM** within Tier-1 and Tier-2 automotive and industrial manufacturers.

---

## 1. TARGET BUYER PERSONAS (ICP & DECISION MAKERS)

| Executive Role | Primary Pain Point / Operational Risk | CadencePLM Value Proposition |
| :--- | :--- | :--- |
| **VP of Engineering / R&D Director** | Inability to immediately forecast down-line assembly impact; risk of manual Excel Where-Used errors; recurring IATF 16949 audit non-conformances. | Resolves complete top-down and bottom-up DAG Where-Used chains to root assembly in milliseconds; auto-generates audit-ready IATF 16949 / PPAP Level 3 impact dossiers. |
| **Plant Manager / COO / Head of Operations** | Unplanned assembly line shutdowns due to miscalculated effectivity cut-offs (Automotive line stoppage costs: **~$1,200/minute**); obsolete inventory lingering in buffer warehouses. | Compares `run_out_days` against supplier tooling lead times using deterministic mathematics to decide `USE_UP_STOCK` vs. `IMMEDIATE_CUTOFF`, preventing buffer shortages. |
| **Head of Procurement / Supply Chain Director** | Unnecessary bulk scrapping of parts undergoing minor tolerance tightening; blind spots regarding supplier die/tooling changeover lead times. | Evaluates precision secondary machining (CNC turning/grinding) feasibility; salvages existing inventory at 15% unit cost, shielding quarterly scrap reserves. |

---

## 2. ROI CALCULATION & VALUE FINANCIAL MODEL

The core commercial question posed by enterprise CFOs:  
> *"We pay an annual enterprise license fee of $60,000 for CadencePLM. How does this system pay for itself within the first quarter?"*

### Baseline Scenario (Typical Tier-1 Transmission / Drivetrain Plant)
- **Annual Average ECO Count:** 35 engineering change orders per year.
- **Manual Engineering Labor Per ECO:** 3 senior engineers (R&D, Manufacturing, Procurement) $\times$ 4 working days = 96 engineering hours.
  - Fully burdened rate: $50/hour $\rightarrow$ **$4,800** in manual engineering analysis cost per ECO.
  - Annual manual analysis burden: $35 \times 4,800 = \mathbf{\$168,000}$.
- **Erroneous Scrap vs. Rework Losses:** In ~4 ECOs per year, salvageable parts are mistakenly scrapped in haste (average scrap write-off of $12,000 per ECO = **$48,000/year**).
- **Assembly Line Stoppage Risk:** At least 1 annual incident where existing inventory is prematurely cut off before supplier tooling is qualified, causing a 45-minute assembly stoppage ($45\text{ min} \times \$1,200/\text{min} = \mathbf{\$54,000}$).

### Financial Return Summary (Annual Net Value)

| Financial Metric | Annual Financial Value |
| :--- | :--- |
| **Engineering Analysis Time Saved** (35 ECOs/yr, 85% reduction) | +$142,800 |
| **Scrap Saved via Precision CNC Rework** | +$42,000 |
| **Prevented Assembly Line Stoppage** (1 incident @ $1,200/min) | +$54,000 |
| **Total Annual Gross Benefit** | **+$238,800** |
| **CadencePLM Enterprise License Fee** | -$60,000 |
| **Net Annual Enterprise Benefit** | **+$178,800 (298% Net ROI)** |

**Payback Period:** CadencePLM pays for its entire annual license fee upon the **second major ECO** (approximately **2.5 months** into deployment).

---

## 3. TOP 5 TOUGHEST CUSTOMER OBJECTIONS & ENGINEERING ANSWERS

### Objection 1: *"We already invested millions in SAP S/4HANA and Siemens Teamcenter. Why do we need this?"*
> **Engineering Answer:**  
> "Siemens Teamcenter manages CAD geometry and engineering revisions; SAP S/4HANA manages physical warehouse counts and purchase orders. Neither system talks to the other to answer: *'If we tighten the pinion tolerance by 0.02 mm, can our 55 on-hand gears be salvaged on a CNC lathe for $20 each, or must we scrap $7,400 in stock and wait 30 days for new tooling?'*  
> CadencePLM does not replace your ERP or PLM investments. It sits on top of them as a 10-second autonomous trade-off decision simulator, eliminating weeks of cross-departmental alignment meetings and error-prone Excel spreadsheets."

---

### Objection 2: *"If an LLM hallucinates a cost formula or tolerance threshold, our assembly line could shut down!"*
> **Engineering Answer:**  
> "In CadencePLM's architecture, the AI **NEVER** performs arithmetic calculations, cost multiplication, or graph traversals (`.antigravityrules §1`).  
> Scrap costs, Where-Used hierarchies, CNC turning salvage math, and inventory run-out durations are computed entirely by deterministic, pure Python engines. The LLM (OpenAI GPT-4o) is used exclusively to interpret unstructured engineer text and format the engine's hard numbers into executive summaries. Even if internet or external API access drops completely, our deterministic engines continue executing with 100% mathematical precision."

---

### Objection 3: *"Are our proprietary 3D CAD models and bill-of-materials sent to OpenAI? Is our intellectual property (IP) at risk?"*
> **Engineering Answer:**  
> "Absolutely not. Your 3D CAD files, geometry data, and STEP models never leave your private server; they are parsed strictly in-memory by our local ISO 10303-21 CAD parser.  
> Only the high-level textual ECO description is processed by the language model. Furthermore, our enterprise deployment supports local self-hosted open-source models (Llama 3 via vLLM) on private on-premise hardware, as well as isolated, zero-retention Microsoft Azure OpenAI corporate tenants."

---

### Objection 4: *"Our bill of materials and assemblies are non-standard and highly customized."*
> **Engineering Answer:**  
> "CadencePLM is built on standard Directed Acyclic Graph (DAG) graph theory rather than rigid naming templates. Whether modeling a simple 3-piece sheet metal bracket or a 15-level dual-clutch transmission, parent-child relationships and cycle detection are resolved with mathematical rigor. If a circular loop is ever introduced, the system raises `BOMStructureError` immediately, isolating corrupted input before it impacts operations."

---

### Objection 5: *"Will integration take months and disrupt our enterprise IT roadmap?"*
> **Engineering Answer:**  
> "No. CadencePLM is built on modern microservices and ships with turnkey `Docker` and `Docker-Compose` configurations. Deployment takes under 5 minutes.  
> Once your team provides a standard SAP inventory export and an EBOM CSV or STEP file from Teamcenter, the live cockpit is immediately operational. No heavy database migrations, schema redesigns, or months of ERP consultancy required."

---

## 4. 3 GOLDEN DEMO SCENARIOS (STEP-BY-STEP LIVE RUNBOOK)

When presenting to customer leadership on the live UI (`http://localhost:8501`), execute these 3 scenarios in sequence:

```
+-----------------------------------------------------------------------------------------+
|                                    LIVE DEMO RUNBOOK                                    |
|                                                                                         |
|  [Scenario 1: Salvage]       --->   [Scenario 2: Unavoidable Scrap] ---> [Scenario 3: ECN]   |
|  GB-PINION-02 Tolerance             GB-SHAFT-01 Material Alloy          Official Audit HTML |
|  (+$6,311 Net CNC Savings)          ($32,650 Risk & Tooling Lead Time)  Dossier Generation  |
+-----------------------------------------------------------------------------------------+
```

---

### Scenario 1: Machinable Salvage Case (GB-PINION-02 Tolerance Tightening)
- **Action:** Click `Scenario 1: GB-PINION-02 Tolerance Tightening (Reworkable)` in the sidebar and press `🚀 Run Simulation & Autonomous Agent`.
- **Key Display Elements:**
  - KPI Cards: *Total Scrap Cost:* $7,425.00 | *Rework Savings:* **+$6,311.25 Net Savings** | *Run-Out Days:* 11 Days (`USE_UP_STOCK`).
  - Plotly Chart: Visual bar comparison of Gross Scrap vs. Net Salvage Savings.
  - Where-Used Assembly Path: `GB-PINION-02 ➔ GBX-1300 ➔ GBX-1000`.
- **Presenter Pitch Script:**
  > *"Mr. Plant Manager, under standard operating procedures, when a pinion gear's tolerance is tightened, warehouse stock is flagged as non-conforming and $7,425 is written off to scrap.  
  > CadencePLM immediately recognized the part class (machinable alloy gear) and operation type (CNC lathe turning). It determined that for just 15% of unit cost ($20.25), the batch can be salvaged on existing plant machinery, saving your facility **$6,311 in net cash** with a single click."*

---

### Scenario 2: Unavoidable Scrap & Supplier Tooling Risk (GB-SHAFT-01 Material Change)
- **Action:** Select `Scenario 2: GB-SHAFT-01 Shaft Material Alloy Change (Scrap Unavoidable)` and execute.
- **Key Display Elements:**
  - KPI Cards: *Total Scrap Cost:* **$32,650.00** | *Rework:* $0.00 (No Salvage Possible) | *Critical Tooling Lead Time:* 28 Days.
  - Executive Summary: Autonomous explanation that changing from 16MnCr5 to 42CrMo4 alloy renders secondary machining impossible, necessitating controlled scrap write-off.
- **Presenter Pitch Script:**
  > *"Here we examine an alloy change. CadencePLM does not blindly recommend rework; it recognizes that raw material changes make machining salvage impossible and flags scrap as mandatory.  
  > Furthermore, it mapped the entire impact tree down to the drive gears and bearings on this shaft, presenting a full $32,650 risk exposure chain and a 28-day supplier die lead time so Procurement never faces an unexpected line halt."*

---

### Scenario 3: IATF 16949 / PPAP Official ECN Dossier Download & Sign-off
- **Action:** Click `📥 Download Official IATF 16949 / PPAP ECO Impact Report (.html)` at the bottom of the cockpit and open the report in a new browser tab.
- **Key Display Elements:**
  - Dark-mode, publication-grade layout with IATF 16949 Clause 8.5.6 header.
  - Financial trade-off summary cards and supplier tooling risk matrix.
  - Tripartite sign-off authorization boxes: R&D, Procurement, and Quality Assurance (`PPAP-OK`).
- **Presenter Pitch Script:**
  > *"Finally, when OEM quality auditors visit your plant, your engineering staff won't spend weeks assembling retrospective spreadsheets.  
  > CadencePLM auto-generates this audit-ready, AIAG/VDA PPAP Level 3 compliant engineering dossier in seconds. Sign-offs are collected, and your plant passes audits with zero findings."*

---
---

# [TÜRKÇE] Kurumsal Satış ve Değer Kanıtlama Kılavuzu (Buyer Playbook)

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
