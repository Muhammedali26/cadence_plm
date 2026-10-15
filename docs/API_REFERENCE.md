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

## 2. FASTMCP (MODEL CONTEXT PROTOCOL) SERVER

CadencePLM implements standard Model Context Protocol (FastMCP) tools over stdio/JSON-RPC 2.0 (`src/mcp_server.py`).

| Tool Identifier | Description | Input Parameters | Output Type |
| :--- | :--- | :--- | :--- |
| `tool_get_ebom` | Retrieves hierarchical bill-of-materials and Where-Used parent links. | `part_number: str` | JSON EBOM Graph |
| `tool_get_inventory` | Inspects physical warehouse stock, unit costs, and supplier tooling days. | `part_number: str` | Stock Record |
| `tool_run_impact_simulation` | Executes comprehensive deterministic simulation (Scrap + Rework + Run-out). | `part_number: str, change_type: str` | `SimulationSummary` |

---

## 3. ERROR CODES & EXCEPTIONS CONTRACT

All system errors inherit from `CadencePLMException` (`src/core/exceptions.py`):

| Exception Class | HTTP Status | Error Code | Industrial Rationale |
| :--- | :--- | :--- | :--- |
| `PartNotFoundError` | 404 Not Found | `PART_NOT_FOUND` | Queried part number does not exist in EBOM or ERP inventory snapshot. |
| `BOMStructureError` | 422 Unprocessable | `BOM_STRUCTURE_ERROR` | A cyclic loop ($A \rightarrow B \rightarrow A$) or malformed parent relationship was detected. |
| `CostCalculationError` | 400 Bad Request | `COST_CALCULATION_ERROR` | Negative unit cost, negative stock quantity, or invalid arithmetic input encountered. |
| `ECOParsingError` | 400 Bad Request | `ECO_PARSING_ERROR` | Free text input lacked identifiable part numbers or essential change parameters. |

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

## 2. FASTMCP SUNUCU ARAÇLARI (TOOLS)

CadencePLM, stdio ve JSON-RPC 2.0 üzerinden standart FastMCP araçları sunar (`src/mcp_server.py`):

| Araç Adı | Açıklama | Parametreler | Çıktı Türü |
| :--- | :--- | :--- | :--- |
| `tool_get_ebom` | Ürün ağacını ve Where-Used üst montaj zincirini sorgular. | `part_number: str` | JSON EBOM Grafı |
| `tool_get_inventory` | Stok adedi, birim maliyet ve kalıp teslim süresini sorgular. | `part_number: str` | Envanter Kaydı |
| `tool_run_impact_simulation` | Deterministik simülasyonu (Hurda + Rework + Run-out) koşturur. | `part_number: str, change_type: str` | `SimulationSummary` |

---

## 3. HATA KODLARI VE SÖZLEŞMELER

Tüm sistem istisnaları `CadencePLMException` temel sınıfından türetilmiştir (`src/core/exceptions.py`):

| İstisna Sınıfı | HTTP Durumu | Hata Kodu | Endüstriyel Gerekçe |
| :--- | :--- | :--- | :--- |
| `PartNotFoundError` | 404 Bulunamadı | `PART_NOT_FOUND` | Sorgulanan parça EBOM veya ERP envanter listesinde mevcut değil. |
| `BOMStructureError` | 422 İşlenemez | `BOM_STRUCTURE_ERROR` | Ürün ağacında döngü ($A \rightarrow B \rightarrow A$) veya hatalı ebeveyn bağı tespit edildi. |
| `CostCalculationError` | 400 Geçersiz İstek | `COST_CALCULATION_ERROR` | Negatif stok, negatif maliyet veya geçersiz aritmetik girdi ile karşılaşıldı. |
| `ECOParsingError` | 400 Geçersiz İstek | `ECO_PARSING_ERROR` | Serbest metin içinde parça numarası veya gerekli parametreler tespit edilemedi. |
