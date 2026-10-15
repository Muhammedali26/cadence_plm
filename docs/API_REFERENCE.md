# CadencePLM – API & FastMCP Protocol Reference (API Reference)
> **Bilingual API & Protocol Specification / İki Dilli API ve Protokol Kılavuzu**  
> *English version is presented first, followed by the Turkish version below.*  
> *Önce İngilizce versiyon sunulmuştur; Türkçe versiyon belgenin devamında yer almaktadır.*

---

# [ENGLISH] API & FastMCP Protocol Reference

CadencePLM exposes dual interface surfaces: an enterprise **FastAPI REST API** with OpenAPI/Swagger compliance, and an Anthropic/FastMCP **Model Context Protocol (MCP)** server for autonomous LLM agent integration.

---

## 1. REST API ENDPOINTS

Base URL: `http://localhost:8000` (or Docker port mapping)  
Interactive OpenAPI Documentation: `http://localhost:8000/docs`

### 1.1 POST /api/v1/simulate
Executes a fully deterministic simulation over the in-memory BOM tree and warehouse inventory without invoking external language models.

- **Request Headers:** `Content-Type: application/json`
- **Request Body (`ECORequest`):**
  ```json
  {
    "eco_id": "ECO-2024-0042",
    "affected_part_number": "GB-PINION-02",
    "target_revision": "B",
    "change_type": "TOLERANCE",
    "description": "Contact patch tolerance tightening on pinion gear"
  }
  ```
- **Response (`SimulationSummary`):**
  ```json
  {
    "eco_id": "ECO-2024-0042",
    "affected_part_number": "GB-PINION-02",
    "target_revision": "B",
    "change_type": "TOLERANCE",
    "total_scrap_cost": 7425.00,
    "impacted_subassemblies": [
      {
        "part_number": "GBX-1300",
        "part_name": "Output Differential Assembly",
        "quantity": 1,
        "unit_cost": 450.00
      }
    ],
    "where_used": [
      {
        "assembly_level": 1,
        "parent_part_number": "GBX-1300",
        "parent_part_name": "Output Differential Assembly"
      },
      {
        "assembly_level": 2,
        "parent_part_number": "GBX-1000",
        "parent_part_name": "Main Gearbox Root Assembly"
      }
    ],
    "rework_analysis": {
      "is_reworkable": true,
      "operation_type": "CNC_TURNING",
      "rework_cost_per_unit": 20.25,
      "net_savings": 6311.25
    },
    "run_out_days": 11,
    "max_transition_lead_time_days": 11,
    "recommended_strategy": "USE_UP_STOCK"
  }
  ```

---

### 1.2 POST /api/v1/agent/analyze
Orchestrates autonomous multi-turn cognitive reasoning. Accepts natural language text from engineers, invokes internal deterministic engine tools via OpenAI Function Calling, and synthesizes executive findings.

- **Request Formats:** Supports both `application/json` and `application/x-www-form-urlencoded`.
- **Request Body (`AgentAnalyzeRequest`):**
  ```json
  {
    "eco_text": "GB-PINION-02 ayna pinyon dişlisinin temas yüzeyi toleransı daraltıldı. Yeni revizyon B olarak güncellenecek.",
    "custom_context": "Tier-1 Heavy Transmission Assembly Line"
  }
  ```
- **Response (`AgentAnalyzeResponse`):**
  ```json
  {
    "status": "SUCCESS",
    "target_part_number": "GB-PINION-02",
    "change_type": "TOLERANCE",
    "total_scrap_cost": 7425.00,
    "net_savings": 6311.25,
    "is_reworkable": true,
    "recommended_strategy": "USE_UP_STOCK",
    "run_out_days": 11,
    "max_transition_lead_time_days": 11,
    "where_used_chain": [
      {
        "assembly_level": 1,
        "parent_part_number": "GBX-1300"
      },
      {
        "assembly_level": 2,
        "parent_part_number": "GBX-1000"
      }
    ],
    "tools_called": [
      "tool_run_simulation",
      "tool_evaluate_rework",
      "tool_calculate_effectivity"
    ],
    "executive_summary": "ECO successfully analyzed for pinion gear GB-PINION-02. Salvageable via CNC turning with $6,311.25 in net cash savings."
  }
  ```

---

### 1.3 GET /sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock('{matnr}')
SAP S/4HANA OData v4/v2 standard material stock integration endpoint. Emulates real-world enterprise ERP stock and cost feeds.

- **Request Headers:**
  - `X-SAP-API-Key: <api_key>` (or `Authorization: Basic <base64(user:pass)>`)
  - Optional `X-SAP-Fault: 503` (for chaos engineering / resilience testing)
- **Response Format (`{"d": {...}}`):**
  ```json
  {
    "d": {
      "MATNR": "GB-PINION-02",
      "MAKTX": "Ayna Pinyon Dislisi",
      "LABST": "55.000",
      "MEINS": "EA",
      "STPRS": "135.00",
      "WAERS": "USD",
      "PLIFZ": "30",
      "TOOL_IMP": true,
      "LGORT": "WH-01"
    }
  }
  ```
- **Error Codes:**
  - `401 Unauthorized`: Missing or invalid API key / Basic Auth credentials.
  - `404 Not Found`: Material not registered in SAP inventory.
  - `503 Service Unavailable`: SAP gateway failure / busy simulator.

---

## 2. FASTMCP (MODEL CONTEXT PROTOCOL) SERVER

CadencePLM implements standard Model Context Protocol (FastMCP) tools over stdio/JSON-RPC 2.0 (`src/mcp_server.py`).

| Tool Identifier | Description | Input Parameters | Output Type |
| :--- | :--- | :--- | :--- |
| `tool_get_ebom` | Retrieves hierarchical bill-of-materials and Where-Used parent links. | `part_number: str` | JSON EBOM Graph |
| `tool_get_inventory` | Inspects physical warehouse stock, unit costs, and supplier tooling days. | `part_number: str` | Stock Record |
| `tool_run_impact_simulation` | Executes comprehensive deterministic simulation (Scrap + Rework + Run-out). | `part_number: str, change_type: str` | `SimulationSummary` |

---

## 3. SAP S/4HANA ODATA CONNECTOR & CHAOS ENGINEERING

### 3.1 SAPODataClient (`src/connectors/sap_odata_client.py`)
Enterprise HTTP client built on `httpx` with both synchronous and asynchronous bindings:
- **Live Sandbox & Cloud Connectivity:** Connects directly to SAP Business Accelerator Hub (`sandbox.api.sap.com`) using `ApiKey` authentication or local mock instances (`X-SAP-API-Key`).
- **CSRF Token Handshake:** Negotiates `x-csrf-token: fetch` pre-flight requests and preserves session cookies for secure NetWeaver/S4 transactions.
- **Multi-Storage Location (LGORT) Aggregation:** Aggregates stock across multiple physical warehouses while filtering out scrap and quarantine locations (`SCRP`, `QUAR`, `BLOCK`, `DEFECT`).
- **Currency Normalization (`WAERS`):** Normalizes international currencies (`EUR`, `TRY`, `GBP`, `JPY`) into standard baseline costs without calculation crashes.
- **Zero-Downtime Graceful Fallback:** If internet connectivity drops, or the sandbox API key expires, the system automatically falls back to an embedded local emulator without crashing. Complete guide: [SAP Live Integration Guide](file:///c:/Users/HP/Desktop/rag&fine-tune%20projects/cadence_plm/docs/SAP_LIVE_INTEGRATION_GUIDE.md).
- **Automatic Retry & Backoff:** 3 exponential backoff attempts on HTTP 502/503/504 or connection timeouts.
- **Dirty Data Armor:** Automatically clamps negative warehouse quantities (`-25`) to `0`, cleans `None`/`NaN` costs to `0.0`.

### 3.2 Chaos Engineering Suite (`scripts/run_chaos_tests.py`)
Validates 7 harsh industrial stress scenarios:
1. **Kaos 1 (SAP OData HTTP):** Real HTTP communication via `httpx.AsyncClient` + `ASGITransport`.
2. **Kaos 2 (Unauthorized & 503):** HTTP 401 handling and 3-stage exponential backoff retry.
3. **Kaos 3 (Orphan Part / ERP Mismatch):** Part present in CAD BOM but missing in ERP; zero crash, `missing_in_erp=True`.
4. **Kaos 4 (Circular BOM Trap):** $A \rightarrow B \rightarrow C \rightarrow A$ cyclic loop caught in $< 2\text{ ms}$ (`CircularDependencyError`).
5. **Kaos 5 (Dirty ERP & Zero Division):** Negative stock, missing cost, and zero daily consumption rate sanitized without division errors.
6. **Kaos 6 (Large-Scale Stress):** 2,000-part, 6-level deep BOM Where-Used and scrap analysis completed in $< 2.0\text{ s}$ ($< 100\text{ ms}$ typical).
7. **Kaos 7 (LLM Hallucination Defense):** Non-existent `GHOST-PART-404` prevented from fabricating costs; triggers `PartNotFoundError`.

---

## 4. ERROR CODES & EXCEPTIONS CONTRACT

All system errors inherit from `CadencePLMException` (`src/core/exceptions.py`):

| Exception Class | HTTP Status | Error Code | Industrial Rationale |
| :--- | :--- | :--- | :--- |
| `PartNotFoundError` | 404 Not Found | `PART_NOT_FOUND` | Queried part number does not exist in EBOM or ERP inventory snapshot. |
| `BOMStructureError` | 422 Unprocessable | `BOM_STRUCTURE_ERROR` | A cyclic loop ($A \rightarrow B \rightarrow A$) or malformed parent relationship was detected. |
| `CircularDependencyError` | 422 Unprocessable | `CIRCULAR_DEPENDENCY_ERROR` | Explicit recursive circular dependency detected in BOM tree. |
| `CostCalculationError` | 400 Bad Request | `COST_CALCULATION_ERROR` | Negative unit cost, negative stock quantity, or invalid arithmetic input encountered. |
| `ECOParsingError` | 400 Bad Request | `ECO_PARSING_ERROR` | Free text input lacked identifiable part numbers or essential change parameters. |
| `SAPAuthenticationError` | 401 Unauthorized | `SAP_AUTH_ERROR` | SAP S/4HANA OData API key or Basic credentials missing/invalid. |
| `SAPConnectionError` | 503 Service Unavailable | `SAP_CONNECTION_ERROR` | SAP S/4HANA gateway unreachable after maximum retry attempts. |

---
---

# [TÜRKÇE] API ve FastMCP Protokol Kılavuzu

CadencePLM iki farklı arayüz yüzeyi sunar: kurumsal OpenAPI/Swagger standartlarında bir **FastAPI REST API** ve otonom yapay zeka ajanları için Anthropic/FastMCP uyumlu **Model Context Protocol (MCP)** sunucusu.

---

## 1. REST API UÇ NOKTALARI (ENDPOINTS)

Sunucu Adresi: `http://localhost:8000` (veya Docker port eşlemesi)  
Etkileşimli OpenAPI Dokümantasyonu: `http://localhost:8000/docs`

### 1.1 POST /api/v1/simulate
Harici yapay zeka modellerini çağırmaksızın, doğrudan bellek içi ürün ağacı ve envanter verisi üzerinde %100 deterministik simülasyon çalıştırır.

- **İstek Başlığı:** `Content-Type: application/json`
- **İstek Gövdesi (`ECORequest`):**
  ```json
  {
    "eco_id": "ECO-2024-0042",
    "affected_part_number": "GB-PINION-02",
    "target_revision": "B",
    "change_type": "TOLERANCE",
    "description": "Pinyon dişlisinde temas yüzeyi toleransı daraltıldı"
  }
  ```
- **Yanıt Gövdesi (`SimulationSummary`):**
  ```json
  {
    "eco_id": "ECO-2024-0042",
    "affected_part_number": "GB-PINION-02",
    "target_revision": "B",
    "change_type": "TOLERANCE",
    "total_scrap_cost": 7425.00,
    "impacted_subassemblies": [...],
    "where_used": [...],
    "rework_analysis": {
      "is_reworkable": true,
      "operation_type": "CNC_TURNING",
      "rework_cost_per_unit": 20.25,
      "net_savings": 6311.25
    },
    "run_out_days": 11,
    "max_transition_lead_time_days": 11,
    "recommended_strategy": "USE_UP_STOCK"
  }
  ```

---

### 1.2 POST /api/v1/agent/analyze
Mühendisin serbest metin olarak yazdığı talebi alır, OpenAI Tool Calling ile deterministik motor araçlarını tetikler ve yönetici özetini üretir.

- **Desteklenen Formatlar:** Hem `application/json` hem `application/x-www-form-urlencoded`.
- **İstek Gövdesi (`AgentAnalyzeRequest`):**
  ```json
  {
    "eco_text": "GB-PINION-02 ayna pinyon dişlisinin temas yüzeyi toleransı daraltıldı. Yeni revizyon B olarak güncellenecek.",
    "custom_context": "Şanzıman Montaj Hattı"
  }
  ```

---

### 1.3 GET /sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock('{matnr}')
SAP S/4HANA OData v4/v2 standart malzeme stok entegrasyon uç noktasıdır. Gerçek kurumsal ERP canlı stok ve maliyet beslemesini simüle eder.

- **İstek Başlıkları (Headers):**
  - `X-SAP-API-Key: <api_key>` (veya `Authorization: Basic <base64(kullanıcı:şifre)>`)
  - İsteğe bağlı `X-SAP-Fault: 503` (kaos mühendisliği / dayanıklılık testi için)
- **Yanıt Formatı (`{"d": {...}}`):**
  ```json
  {
    "d": {
      "MATNR": "GB-PINION-02",
      "MAKTX": "Ayna Pinyon Dislisi",
      "LABST": "55.000",
      "MEINS": "EA",
      "STPRS": "135.00",
      "WAERS": "USD",
      "PLIFZ": "30",
      "TOOL_IMP": true,
      "LGORT": "WH-01"
    }
  }
  ```
- **Hata Kodları:**
  - `401 Unauthorized`: API anahtarı veya Basic kimlik bilgisi eksik/geçersiz.
  - `404 Not Found`: Malzeme SAP envanterinde kayıtlı değil.
  - `503 Service Unavailable`: SAP ağ geçidi meşgul / simüle edilmiş sunucu kesintisi.

---

## 2. FASTMCP SUNUCU ARAÇLARI (TOOLS)

CadencePLM, stdio ve JSON-RPC 2.0 üzerinden standart FastMCP araçları sunar (`src/mcp_server.py`):

| Araç Adı | Açıklama | Parametreler | Çıktı Türü |
| :--- | :--- | :--- | :--- |
| `tool_get_ebom` | Ürün ağacını ve Where-Used üst montaj zincirini sorgular. | `part_number: str` | JSON EBOM Grafı |
| `tool_get_inventory` | Stok adedi, birim maliyet ve kalıp teslim süresini sorgular. | `part_number: str` | Envanter Kaydı |
| `tool_run_impact_simulation` | Deterministik simülasyonu (Hurda + Rework + Run-out) koşturur. | `part_number: str, change_type: str` | `SimulationSummary` |

---

## 3. SAP S/4HANA ODATA KONNEKTÖRÜ VE KAOS MÜHENDİSLİĞİ

### 3.1 SAPODataClient (`src/connectors/sap_odata_client.py`)
`httpx` üzerinde inşa edilmiş, hem senkron hem asenkron desteği sunan kurumsal HTTP istemcisidir:
- **Canlı Sandbox & Bulut Bağlantısı:** SAP Business Accelerator Hub (`sandbox.api.sap.com`) ile `ApiKey` kimlik doğrulaması veya yerel emülatör (`X-SAP-API-Key`) üzerinden konuşur.
- **CSRF Token El Sıkışması (Handshake):** Güvenli NetWeaver/S4 oturumları için `x-csrf-token: fetch` ön isteği atarak oturum çerezlerini ve token'ı yönetir.
- **Çoklu Depo (LGORT) Agregasyonu:** Birden çok fiziksel depodaki kullanılabilir stokları toplarken, karantina ve hurda depolarını (`SCRP`, `QUAR`, `BLOCK`, `DEFECT`) eler.
- **Döviz Kuru Normalizasyonu (`WAERS`):** Uluslararası para birimlerini (`EUR`, `TRY`, `GBP`, `JPY`) motoru çökertmeden standart baz maliyete dönüştürür.
- **Sıfır Kesinti (Graceful Fallback):** İnternet koptuğunda veya sandbox anahtarı geçersiz olduğunda çökmeden otomatik olarak yerel emülatöre geçer. Detaylı kılavuz: [SAP Canlı Entegrasyon Kılavuzu](file:///c:/Users/HP/Desktop/rag&fine-tune%20projects/cadence_plm/docs/SAP_LIVE_INTEGRATION_GUIDE.md).
- **Otomatik Retry & Exponential Backoff:** HTTP 502/503/504 veya bağlantı zaman aşımlarında 3 aşamalı katlanarak bekleme ile yeniden dener.
- **Kirli Veri Zırhı:** Ambar sayımındaki negatif stokları (`-25`) `0`'a sabitler, `None`/`NaN` maliyetleri `0.0` yapar.

### 3.2 Kaos ve Stres Testi Paketi (`scripts/run_chaos_tests.py`)
7 acımasız endüstriyel stres senaryosunu doğrular:
1. **Kaos 1 (Gerçek SAP OData HTTP İletişimi):** `httpx.AsyncClient` + `ASGITransport` ile gerçek OData çağrısı ve model dönüşümü.
2. **Kaos 2 (SAP Yetkisiz Erişim & 503 Çökmesi):** HTTP 401 doğrulaması ve 3 kez exponential backoff retry zırhı.
3. **Kaos 3 (Yetim Parça / ERP Uyumsuzluğu):** CAD BOM'da var olup SAP'de kaydı bulunmayan parçada `KeyError` önleme ve `missing_in_erp=True`.
4. **Kaos 4 (Döngüsel BOM Tuzağı):** $A \rightarrow B \rightarrow C \rightarrow A$ sonsuz döngüsünün $< 2\text{ ms}$ içinde `CircularDependencyError` ile yakalanması.
5. **Kaos 5 (Kirli ERP Verisi & Zero Division):** Negatif stok, eksik fiyat ve 0 günlük tüketim hızında sıfıra bölme hatasının önlenmesi.
6. **Kaos 6 (Büyük Ölçek Performans Stres Testi):** 2.000 parçalık, 6 seviye derinlikte devasa BOM ağacında Where-Used ve hurda analizinin $< 2.0\text{ s}$ ($< 100\text{ ms}$) altında bitmesi.
7. **Kaos 7 (LLM Halüsinasyon & Hayalet Parça Savunması):** Sistemde olmayan `GHOST-PART-404` için maliyet uydurulmasının engellenmesi ve `PartNotFoundError` fırlatılması.

---

## 4. HATA KODLARI VE SÖZLEŞMELER

Tüm sistem istisnaları `CadencePLMException` temel sınıfından türetilmiştir (`src/core/exceptions.py`):

| İstisna Sınıfı | HTTP Durumu | Hata Kodu | Endüstriyel Gerekçe |
| :--- | :--- | :--- | :--- |
| `PartNotFoundError` | 404 Bulunamadı | `PART_NOT_FOUND` | Sorgulanan parça EBOM veya ERP envanter listesinde mevcut değil. |
| `BOMStructureError` | 422 İşlenemez | `BOM_STRUCTURE_ERROR` | Ürün ağacında döngü ($A \rightarrow B \rightarrow A$) veya hatalı ebeveyn bağı tespit edildi. |
| `CircularDependencyError` | 422 İşlenemez | `CIRCULAR_DEPENDENCY_ERROR` | Ürün ağacında özyinelemeli döngüsel bağımlılık tespit edildi. |
| `CostCalculationError` | 400 Geçersiz İstek | `COST_CALCULATION_ERROR` | Negatif stok, negatif maliyet veya geçersiz aritmetik girdi ile karşılaşıldı. |
| `ECOParsingError` | 400 Geçersiz İstek | `ECO_PARSING_ERROR` | Serbest metin içinde parça numarası veya gerekli parametreler tespit edilemedi. |
| `SAPAuthenticationError` | 401 Yetkisiz | `SAP_AUTH_ERROR` | SAP S/4HANA OData API anahtarı veya Basic kimlik bilgisi eksik/hatalı. |
| `SAPConnectionError` | 503 Hizmet Dışı | `SAP_CONNECTION_ERROR` | SAP S/4HANA ağ geçidi maksimum deneme sayısı aşıldıktan sonra erişilemez durumda. |
