# CadencePLM – System Capabilities & Architectural Boundaries (Capabilities & Boundaries)
> **Bilingual Technical Specification / İki Dilli Teknik Şartname**  
> *English version is presented first, followed by the Turkish version below.*  
> *Önce İngilizce versiyon sunulmuştur; Türkçe versiyon belgenin devamında yer almaktadır.*

---

# [ENGLISH] System Capabilities & Architectural Boundaries

This document defines with industrial precision the core capabilities, deterministic mathematical models, architectural boundaries, intentional non-capabilities, and data interface protocols of the **CadencePLM** autonomous Engineering Change Order (ECO) decision-support system.

---

## PART 1: CORE CAPABILITIES (WHAT CAN IT DO?)

### 1.1 Unstructured Text Extraction (Free-Text ECO Parsing)
CadencePLM transforms natural language change requests written by plant engineers and shop floor operators into strongly-typed Pydantic v2 data models (`ECORequest`).

- **Extracted Parameters:**
  - `affected_part_number` (str): Target component identifier undergoing modification (e.g., `GB-PINION-02`, `GBX-1210`). The system resolves automotive engineering aliases (e.g., `GB-SHAFT-01` $\rightarrow$ `GBX-1210`).
  - `target_revision` (str): Target engineering revision level (e.g., `Rev-B`, `C`, `B`).
  - `change_type` (Enum): `TOLERANCE` (tolerance tightening/widening), `MATERIAL` (alloy or raw material change), `GEOMETRY` (dimensional revision), `OBSOLETE` (part phase-out).
  - `eco_id` (str): Explicitly stated identifier in the text (`ECO-2024-0099`) or an automatically generated unique key (`ECO-AUTO-XXXXXX`).
  - `description` (str): Concise technical summary of the modification.
- **Execution Mechanism:**
  - Primary Route: Google Gemini / OpenAI structured JSON extraction (when active API key is provided).
  - Deterministic Fallback: Fully local, regex-based syntactic parser engine (operates with zero internet connectivity and zero external API dependencies).

---

### 1.2 Deterministic BOM Tree Traversal (DAG) & Where-Used Analysis
The Engineering Bill of Materials (EBOM) is modeled mathematically as a **Directed Acyclic Graph (DAG)**.

- **Top-Down Impact Traversal (`get_affected_subassemblies`):**
  - Traverses downward from the modified component using BFS/DFS to identify all direct and indirect children, subassemblies, and leaf parts.
  - Cycle Detection: A strict `visited_parts` set detects circular dependencies; when a loop is encountered, the system raises `BOMStructureError` immediately rather than silently looping.
- **Bottom-Up Parent Where-Used Chain (`get_where_used`):**
  - Resolves all parent assemblies up to the root level (L0), documenting hierarchical depths (`assembly_level: 1, 2, ... N`).
  - **Maximum Depth:** Unlimited ($N$ levels). For example, in a heavy-duty gearbox:
    `GB-PINION-02` (Leaf) $\rightarrow$ `GBX-1300` (Level 1: Output Differential) $\rightarrow$ `GBX-1000` (Level 2: Main Gearbox Assembly).

---

### 1.3 Scrap Cost & Salvage (Rework) Optimization Engine
The engine computes whether physical inventory must be scrapped or whether components can be salvaged via precision CNC secondary machining operations.

- **Gross Scrap Cost Formula:**
  $$\text{Scrap Cost} = \sum_{i \in \text{Impacted Parts}} (\text{Stock}_i \times \text{Unit Cost}_i)$$
- **Rework Feasibility Decision Logic:**
  1. If change type is `TOLERANCE` or `DIMENSION` **AND** the component belongs to machinable metal classes (`pinion`, `shaft`, `gear`, `bushing`, `flange`, `axle`, etc.):
     - `is_reworkable = True`
     - Operation Type: `CNC_TURNING` (CNC lathe turning / cylindrical grinding)
     - Per-Unit Rework Cost (`rework_cost_per_unit`):
       $$\text{Rework Cost Per Unit} = 0.15 \times \text{Unit Cost} \quad (15\%\ \text{of unit cost})$$
     - Net Salvage Savings (`net_savings`):
       $$\text{Net Savings} = (\text{Unit Cost} - \text{Rework Cost Per Unit}) \times \text{Stock Quantity}$$
  2. If change type is `MATERIAL` (alloy change, e.g., 16MnCr5 to 42CrMo4 steel) or the component is a non-machinable standard part (elastomeric seal, O-ring, bearing, circlip, fastener):
     - `is_reworkable = False`, `operation_type = NONE`
     - `rework_cost_per_unit = 0.00`, `net_savings = 0.00` (Scrap is mandatory).

---

### 1.4 Effectivity & Run-Out Planning Engine
Calculates whether the manufacturing facility should exhaust current stock or enforce an immediate transition when tooling arrives.

- **Stock Depletion Duration (Run-Out Days):**
  $$\text{Run-Out Days} = \left\lceil \frac{\text{Stock Quantity}}{\text{Daily Consumption Rate}} \right\rceil \quad (\text{Default: 5 units/day})$$
- **Decision Algorithm:**
  - If $\text{Run-Out Days} \le \text{Tooling Lead Time}$:
    - **Strategy:** `USE_UP_STOCK` (Exhaust Existing Inventory)
    - **Transition Lead Time:** Run-out duration (working days)
    - **Scrap Cost:** $0.00 (Stock is naturally consumed on assembly line; zero scrap incurred).
  - If $\text{Run-Out Days} > \text{Tooling Lead Time}$:
    - **Strategy:** `IMMEDIATE_CUTOFF` (Immediate Hard Cut-Off)
    - **Transition Lead Time:** 0 days once tooling arrives
    - **Scrap Cost:** $\text{Stock Quantity} \times \text{Unit Cost}$ (Remaining stock is written off to avoid line stoppage).

---

### 1.5 ISO 10303-21 STEP AP214 CAD Metadata Parser
CadencePLM parses standard ISO 10303-21 ASCII STEP files in pure Python without requiring heavy C++ geometry kernels (OpenCASCADE, FreeCAD).

- **Parsed Standard STEP Entities:**
  - `PRODUCT_DEFINITION` & `PRODUCT_DEFINITION_FORMATION`: Part names, CAD part numbers, and revision tags.
  - `NEXT_ASSEMBLY_USAGE_OCCURRENCE`: Hierarchical parent-child links, assembly constraints, and occurrence quantities (`quantity`).
- **Output:** Produces a native `list[BOMItem]` directly from CAD files and loads them into `BOMTreeEngine`.

---

### 1.6 IATF 16949 / PPAP Level 3 Compliant ECO Dossier Generation
Transforms simulation results into an audit-ready, executive HTML/CSS report (`reports/ECO_IMPACT_REPORT_{eco_id}.html`) adhering to automotive quality standards (IATF 16949 Clause 8.5.6 and AIAG/VDA PPAP Level 3).

- **Dossier Sections:**
  - Financial Trade-Off KPI Cards (Gross Scrap Risk vs. Rework Net Savings vs. Net Financial Exposure).
  - Where-Used Visual Assembly Flow & Component Impact Matrix.
  - Supplier Tooling Risk Assessment (Tooling codes and critical lead-time days).
  - Tripartite Sign-off Block: **R&D Director**, **Procurement Manager**, and **Quality Assurance Manager**.

---

## PART 2: ARCHITECTURAL BOUNDARIES & NON-CAPABILITIES (WHAT CAN IT NOT DO?)

### 2.1 AI Hallucination Boundary (LLM vs. Deterministic Engine Separation)
- **CANNOT DO:** The LLM (GPT-4o / Gemini) is strictly forbidden from performing multiplication, computing scrap costs, evaluating run-out days, or traversing BOM hierarchies.
- **ARCHITECTURAL RULE:** Per `.antigravityrules §1`, all mathematical, financial, and structural computations are strictly executed by deterministic Python engines (`src/engines/`).
- **LLM Role:** The LLM's role is restricted to parsing unstructured natural language requests into structured tool calls and synthesizing engine numbers into natural language summaries. If external APIs fail or are unavailable, CadencePLM continues to function with 100% deterministic accuracy.

---

### 2.2 CAD & Geometric Calculation Boundaries
- **CANNOT DO:**
  - No 3D surface collision or geometric interference checking.
  - No Finite Element Analysis (FEA) stress/strain or fatigue simulation.
  - No 1D/3D tolerance stack-up analysis.
- **SCOPE:** Reads assembly graph topology, occurrence counts, and part metadata from STEP AP203/AP214 files. It is an engineering BOM decision engine, not a solid modeling CAD renderer.

---

### 2.3 ERP / PLM Integration & Write Boundaries (Read-Only Principle)
- **CANNOT DO:** Does not perform automated write-back, transactional record commits, or database mutations into live SAP S/4HANA or Siemens Teamcenter databases.
- **ARCHITECTURAL PRINCIPLE:** CadencePLM operates as a **Salt-Okunur / Read-Only Decision-Support Simulator**.
  - Ingests snapshot data from ERP and PLM.
  - Executes simulation and renders an IATF 16949 compliant ECN dossier.
  - Actual ERP commits remain under human governance (Human-in-the-Loop) following formal executive approvals.

---

### 2.4 Scalability & Performance Limits
- **In-Memory Pandas / Graph Engine Capacity:**
  - $\le 10,000$ BOM parts: Sub-millisecond response ($< 50\text{ ms}$).
  - $10,000 - 50,000$ BOM parts: Negligible memory consumption ($< 500\text{ ms}$).
  - $> 100,000$ parts (e.g., complete commercial aircraft or marine vessel): Single-process in-memory Pandas DataFrames become memory-constrained; at this scale, the engine connects to a distributed graph database (Neo4j / Memgraph).

---

## PART 3: DATA INPUT FORMATS & PROTOCOLS

### 3.1 Supported Formats & Schemas

| Domain | Supported Formats | Required Fields / Standard |
| :--- | :--- | :--- |
| **EBOM Data** | CSV, Pandas DataFrame, FastMCP Stream | `part_number`, `part_name`, `revision`, `parent_part_number`, `quantity`, `unit_cost`, `supplier_id` (Optional: `tooling_id`) |
| **Inventory Data** | CSV, Pandas DataFrame, SAP API JSON | `part_number`, `stock_quantity`, `lead_time_days`, `location` |
| **3D CAD Model** | ISO 10303-21 STEP (`.step`, `.stp`) | AP203 or AP214 application protocol |
| **API Endpoints** | REST JSON, Multipart Form-Data | `POST /api/v1/simulate`, `POST /api/v1/agent/analyze` |
| **Protocols** | FastMCP (Model Context Protocol) | stdio, JSON-RPC 2.0 (`tool_get_ebom`, `tool_get_inventory`, `tool_run_impact_simulation`) |

### 3.2 Unsupported Formats
- Proprietary Binary CAD Formats: `.sldprt` / `.sldasm` (SolidWorks), `.catpart` / `.catproduct` (CATIA), `.prt` (NX). *These files must be exported to standard STEP AP214 prior to ingestion.*
- Non-tabular, unstructured plain text or scanned PDFs (cannot be directly loaded as BOMs; they must pass through the unstructured text extraction layer).

---
---

# [TÜRKÇE] Sistem Yetenekleri ve Mimari Sınırlar Dokümanı

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
  $$\text{Hurda Maliyeti} = \sum_{i \in \text{Etkilenen Parçalar}} (\text{Stok Adedi}_i \times \text{Birim Maliyet}_i)$$
- **Kurtarılabilirlik (Rework Feasibility) Karar Mantığı:**
  1. Değişiklik türü `TOLERANCE` veya `DIMENSION` ise **VE** parça işlenebilir metal sınıfında ise (`pinion`, `shaft`, `gear`, `mil`, `dişli`, `burç`, `flanş`, `aks` vb.):
     - `is_reworkable = True`
     - Operasyon Türü: `CNC_TURNING` (CNC Torna / Taşlama)
     - Parça Başı Rework Maliyeti (`rework_cost_per_unit`):
       $$\text{Rework Birim Maliyeti} = 0{,}15 \times \text{Birim Maliyet} \quad (\text{Birim maliyetin yüzde 15'i})$$
     - Net Kurtarma Tasarrufu (`net_savings`):
       $$\text{Net Kurtarma Tasarrufu} = (\text{Birim Maliyet} - \text{Rework Birim Maliyeti}) \times \text{Stok Adedi}$$
  2. Değişiklik türü `MATERIAL` (malzeme alaşımı değişimi) ise veya parça işlenemez standart bileşen ise (conta, o-ring, rulman, segman, civata, somun):
     - `is_reworkable = False`, `operation_type = NONE`
     - `rework_cost_per_unit = 0.00`, `net_savings = 0.00` (Hurda kaçınılmazdır).

---

### 1.4 Yürürlük ve Run-Out Analizi (Effectivity Engine)
Parça değişikliğinin devreye giriş tarihi için fabrikanın mevcut stoğunu tüketip tüketmeyeceğini matematiksel olarak hesaplar.

- **Stok Tüketim Süresi (Run-Out Days):**
  $$\text{Run-Out (Tüketim Gün)} = \left\lceil \frac{\text{Stok Miktarı}}{\text{Günlük Tüketim Hızı}} \right\rceil \quad (\text{Varsayılan: 5 adet/gün})$$
- **Karar Algoritması:**
  - $\text{Run-Out Gün} \le \text{Kalıp Teslim Süresi}$ ise:
    - **Strateji:** `USE_UP_STOCK` (Stoğu Bitir)
    - **Geçiş Süresi:** Run-Out süresi (iş günü)
    - **Hurda Maliyeti:** 0.00 USD (Mevcut stok montajda doğal olarak tüketilir, sıfır hurda ile yeni revizyona geçilir).
  - $\text{Run-Out Gün} > \text{Kalıp Teslim Süresi}$ ise:
    - **Strateji:** `IMMEDIATE_CUTOFF` (Derhal Kesinti)
    - **Geçiş Süresi:** 0 gün (Yeni parça geldiği an hat revize edilir)
    - **Hurda Maliyeti:** $\text{Stok Miktarı} \times \text{Birim Maliyet}$ (Eski stok derhal hurdaya yazılır).

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
