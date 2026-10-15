# CadencePLM – Sistem Yetenekleri ve Mimari Sınırlar Dokümanı (Capabilities & Boundaries)

Bu doküman, **CadencePLM** otonom mühendislik değişiklik yönetimi (ECO) karar destek sisteminin çekirdek yeteneklerini, matematiksel modellerini, mimari sınırlarını, yapamadığı işlemleri ve veri iletişim protokollerini teknik kesinlikle tanımlar.

---

## BÖLÜM 1: ÇEKİRDEK YETENEKLER (NE YAPABİLİR?)

### 1.1 Serbest Metin ECO Ayrıştırma (Unstructured Text Extraction)
CadencePLM, mühendisler ve saha operatörleri tarafından serbest metin olarak yazılmış değişiklik taleplerini yapılandırılmış Pydantic v2 veri modellerine (`ECORequest`) dönüştürür.

- **Yakalanan Parametreler:**
  - `affected_part_number` (str): Değişikliğe uğrayan hedef parçanın kodu (örn. `GB-PINION-02`, `GBX-1210`). Sistem, otomotiv mühendisliği takma adlarını (alias) çözümler (örn. `GB-SHAFT-01` $\rightarrow$ `GBX-1210`).
  - `target_revision` (str): Yeni revizyon seviyesi (örn. `Rev-B`, `C`, `B`).
  - `change_type` (Enum): `TOLERANCE` (tolerans daralması/genişlemesi), `MATERIAL` (alaşım/hammadde değişimi), `GEOMETRY` (boyut/geometri revizyonu), `OBSOLETE` (parçanın kullanımdan kaldırılması).
  - `eco_id` (str): Metin içinde açıkça belirtilen kimlik (`ECO-2024-0099`) veya benzersiz otomatik üretilen anahtar (`ECO-AUTO-XXXXXX`).
  - `description` (str): Değişikliğin teknik özeti.
- **Çalışma Mekanizması:**
  - Öncelikli Yol: Google Gemini / OpenAI yapılandırılmış JSON extraction (API anahtarı mevcut olduğunda).
  - Deterministik Fallback: Tamamen yerel, regex tabanlı sözdizim motoru (sıfır internet veya API bağımlılığı ile deterministik ayrıştırma).

---

### 1.2 Deterministik BOM Ağacı Gezintisi (DAG Traversal) ve Where-Used Analizi
Mühendislik Ürün Ağacı (EBOM), matematiksel olarak **Döngüsel Olmayan Yönlü Çizge (Directed Acyclic Graph - DAG)** olarak modellenir.

- **Top-Down Etki Gezintisi (`get_affected_subassemblies`):**
  - Hedef parçadan başlayarak altındaki tüm doğrudan ve dolaylı çocuk parçaları, alt montajları ve yaprak bileşenleri aşağı yönlü (top-down) BFS/DFS gezintisiyle tespit eder.
  - Ağaçtaki döngüleri tespit etmek için `visited_parts` kümesi kullanılır; döngü tespit edildiğinde sistem sessizce geçmek yerine anında `BOMStructureError` fırlatır.
- **Bottom-Up Üst Montaj Zinciri (`get_where_used`):**
  - Hedef parçanın dahil olduğu tüm üst montaj sistemlerini kök montaja (L0) kadar yukarı yönlü (bottom-up) hiyerarşik seviyesiyle (`assembly_level: 1, 2, ... N`) tespit eder.
  - **Maksimum Derinlik:** Sınırsız ($N$ seviye). Şanzıman ana montajında `GB-PINION-02` (Yaprak) $\rightarrow$ `GBX-1300` (Seviye 1: Diferansiyel Grubu) $\rightarrow$ `GBX-1000` (Seviye 2: Şanzıman Ana Montajı) zincirini hiyerarşik olarak çıkarır.

---

### 1.3 Hurda Maliyeti ve Rework (Kurtarma) Optimizasyon Motoru
Sistem, değişiklik durumunda stoktaki fiziksel parçaların hurdaya mı ayrılacağını yoksa talaşlı imalatla kurtarılıp kurtarılamayacağını belirler.

- **Brüt Hurda Maliyeti Formülü:**
  $$\text{Scrap Cost} = \sum_{i \in \text{Etkilenen Parçalar}} \text{round}(\text{stock\_quantity}_i \times \text{unit\_cost}_i, 2)$$
- **Kurtarılabilirlik (Rework Feasibility) Karar Mantığı:**
  1. Değişiklik türü `TOLERANCE` veya `DIMENSION` ise **VE** parça işlenebilir metal sınıfında ise (`pinion`, `shaft`, `gear`, `mil`, `dişli`, `burç`, `flanş`, `aks` vb.):
     - `is_reworkable = True`
     - Operasyon Türü: `CNC_TURNING` (CNC Torna / Taşlama)
     - Parça Başı Rework Maliyeti:
       $$\text{rework\_cost\_per\_unit} = \text{round}(\text{unit\_cost} \times 0.15, 2) \quad (\text{Birim maliyetin \%15'i})$$
     - Net Kurtarma Tasarrufu:
       $$\text{net\_savings} = \text{round}((\text{unit\_cost} - \text{rework\_cost\_per\_unit}) \times \text{stock\_quantity}, 2)$$
  2. Değişiklik türü `MATERIAL` (malzeme alaşımı değişimi) ise veya parça işlenemez standart bileşen ise (conta, o-ring, rulman, segman, civata, somun):
     - `is_reworkable = False`, `operation_type = NONE`
     - `rework_cost_per_unit = 0.00`, `net_savings = 0.00` (Hurda kaçınılmazdır).

---

### 1.4 Yürürlük ve Run-Out Analizi (Effectivity Engine)
Parça değişikliğinin devreye giriş tarihi için fabrikanın mevcut stoğunu tüketip tüketmeyeceğini matematiksel olarak hesaplar.

- **Stok Tüketim Süresi (Run-Out Days):**
  $$\text{run\_out\_days} = \left\lceil \frac{\text{stock\_quantity}}{\text{daily\_consumption\_rate}} \right\rceil \quad (\text{Varsayılan: 5 adet/gün})$$
- **Karar Algoritması:**
  - $\text{run\_out\_days} \le \text{tooling\_lead\_time\_days}$ ise:
    - **Strateji:** `USE_UP_STOCK` (Stoğu Bitir)
    - **Geçiş Süresi:** $\text{run\_out\_days}$ iş günü
    - **Hurda Maliyeti:** $0.00$ USD (Mevcut stok montajda doğal olarak tüketilir, sıfır hurda ile yeni revizyona geçilir).
  - $\text{run\_out\_days} > \text{tooling\_lead\_time\_days}$ ise:
    - **Strateji:** `IMMEDIATE_CUTOFF` (Derhal Kesinti)
    - **Geçiş Süresi:** $0$ gün (Yeni parça geldiği an hat revize edilir)
    - **Hurda Maliyeti:** $\text{round}(\text{stock\_quantity} \times \text{unit\_cost}, 2)$ (Eski stok derhal hurdaya yazılır).

---

### 1.5 ISO 10303-21 STEP AP214 CAD Metadata Ayrıştırıcısı
CadencePLM, ağır C++ kütüphanelerine (OpenCASCADE, FreeCAD) ihtiyaç duymaksızın saf Python ortamında ISO 10303-21 ASCII STEP dosyalarını ayrıştırır.

- **Ayrıştırılan Standart STEP Entity'leri:**
  - `PRODUCT_DEFINITION` & `PRODUCT_DEFINITION_FORMATION`: Parça tanımları, CAD parça numaraları ve revizyon etiketleri.
  - `NEXT_ASSEMBLY_USAGE_OCCURRENCE`: Üst montaj - alt montaj hiyerarşik bağları, montaj ilişkileri ve parça kullanım miktarları (`quantity`).
- **Çıktı:** CAD dosyasından doğrudan `list[BOMItem]` üretir ve `BOMTreeEngine`'e yükler.

---

### 1.6 IATF 16949 / PPAP Uyumlu Resmi ECO Dossier Üretimi
Simülasyon sonuçlarını otomotiv kalite denetimlerine (IATF 16949 Madde 8.5.6 ve AIAG/VDA PPAP Seviye 3) uygun, bağımsız bir HTML/CSS raporuna (`reports/ECO_IMPACT_REPORT_{eco_id}.html`) dönüştürür.

- **Rapor Bölümleri:**
  - Finansal Trade-Off Analiz Kartları (Hurda Riski vs. Rework Net Tasarrufu vs. Net Finansal Maruziyet).
  - Where-Used Görsel Akış Şeması ve Parça Etki Matrisi.
  - Tedarikçi Kalıp Risk Değerlendirmesi (Kalıp kodları ve kritik teslim süreleri).
  - Üçlü Resmi İmza ve Onay Bloğu: Ar-Ge Direktörü, Satınalma Müdürü, Kalite Güvence Müdürü.

---

## BÖLÜM 2: SİSTEM SINIRLARI & YAPAMADIKLARI (NE YAPAMAZ?)

### 2.1 Yapay Zeka Halüsinasyon Sınırı (LLM vs. Motor Ayrımı)
- **YAPAMAZ:** LLM (GPT-4o / Gemini) kesinlikle hurda maliyeti çarpımı yapamaz, stok gün hesabı yapamaz, BOM ağacı seviyelerini tahmin edemez.
- **MİMARİ KURAL:** `.antigravityrules §1` uyarınca tüm matematiksel, finansal ve hiyerarşik işlemler saf Python motorlarında (`src/engines/`) deterministik olarak çalışır.
- **LLM'in Rolü:** Sadece serbest metin niyetini anlamak ve Python motorlarının ürettiği sayısal sonuçları yöneticilere doğal dilde raporlamakla sınırlıdır. API anahtarı olmasa veya OpenAI erişimi kesilse dahi CadencePLM motorları ve REST API'si %100 doğrulukla çalışmaya devam eder.

---

### 2.2 CAD & Geometrik Hesaplama Sınırları
- **YAPAMAZ:** 
  - 3D yüzey çakışması (Geometric Collision Mesh / Interference Check) yapmaz.
  - Sonlu Elemanlar Analizi (FEA) gerilme/yorgunluk simülasyonu yapmaz.
  - Tolerans zinciri (1D/3D Tolerance Stack-up) analizi yapmaz.
- **KAPSAMI:** Sadece STEP AP203/AP214 formatındaki ürün ağacı topolojisini, montaj ilişkilerini (`occurrence`) ve parça metadatasını okur. Geometrik katı model render motoru değildir.

---

### 2.3 ERP / PLM Entegrasyon ve Yazma Sınırları (Read-Only Prensibi)
- **YAPAMAZ:** SAP S/4HANA, IFS veya Siemens Teamcenter veritabanlarına otomatik yazma (Write-back / commit / transactional record update) yapmaz.
- **MİMARİ PRENSİP:** Sistem **Salt-Okunur (Read-Only) Karar Destek Simülatörüdür**. 
  - ERP ve PLM'den veriyi anlık okur veya içeri alır.
  - Simülasyonu çalıştırır ve IATF 16949 uyumlu ECN onay taslağı sunar.
  - Değişikliğin ERP'de kesinleşmesi, kalite ve mühendislik direktörlerinin resmi onayından sonra insan kontrolünde (Human-in-the-Loop) gerçekleşir.

---

### 2.4 Ölçekleme ve Performans Limitleri
- **Bellek İçi Pandas / Dict Motoru Kapasitesi:**
  - $\le 10.000$ parçalık BOM ağaçları: Anlık yanıt ($< 50\text{ ms}$).
  - $10.000 - 50.000$ parçalık BOM ağaçları: Kabul edilebilir bellek tüketimi ($< 500\text{ ms}$).
  - $> 100.000$ parça (örneğin tam bir yolcu uçağı veya gemi BOM'u): Bellek içi tekil Pandas DataFrame yetersiz kalır; bu ölçekte sistemin dağıtık bir graf veritabanına (Neo4j / Memgraph) bağlanması gerekir.

---

## BÖLÜM 3: VERİ GİRDİ FORMATLARI & PROTOKOLLERİ

### 3.1 Desteklenen Formatlar ve Şemalar

| Alan | Desteklenen Format | Zorunlu Alanlar / Standart |
| :--- | :--- | :--- |
| **EBOM Verisi** | CSV, Pandas DataFrame, FastMCP Stream | `part_number`, `part_name`, `revision`, `parent_part_number`, `quantity`, `unit_cost`, `supplier_id` (Opsiyonel: `tooling_id`) |
| **Envanter Verisi** | CSV, Pandas DataFrame, SAP API JSON | `part_number`, `stock_quantity`, `lead_time_days`, `location` |
| **3D CAD Modeli** | ISO 10303-21 STEP (`.step`, `.stp`) | AP203 veya AP214 uygulama protokolü |
| **API İstekleri** | REST JSON, Multipart Form-Data | `POST /api/v1/simulate`, `POST /api/v1/agent/analyze` |
| **Protokoller** | FastMCP (Model Context Protocol) | stdio, JSON-RPC 2.0 (`tool_get_ebom`, `tool_get_inventory`, `tool_run_impact_simulation`) |

### 3.2 Desteklenmeyen Formatlar
- Tescilli (Proprietary) İkili CAD Formatları: `.sldprt` / `.sldasm` (SolidWorks), `.catpart` / `.catproduct` (CATIA), `.prt` (NX). *Bu dosyalar sisteme verilmeden önce standart STEP AP214 formatına dönüştürülmelidir.*
- Şablonlanmamış, ilişkisel olmayan düz metin veya taranmış PDF dosyaları (doğrudan BOM olarak kabul edilmez; metin ayrıştırma katmanına girdi olarak verilebilir).
