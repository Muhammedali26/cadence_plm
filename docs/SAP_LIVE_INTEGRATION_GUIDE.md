# CadencePLM – Live SAP S/4HANA Cloud & Business Accelerator Hub Integration Guide
> **Bilingual Enterprise Guide / İki Dilli Kurumsal Entegrasyon Kılavuzu**  
> *English version is presented first, followed by the Turkish version below.*  
> *Önce İngilizce versiyon sunulmuştur; Türkçe versiyon belgenin devamında yer almaktadır.*

---

# [ENGLISH] SAP S/4HANA Cloud Sandbox Integration Guide

This guide provides technical directors, ERP integration specialists, and software engineers with complete instructions for connecting CadencePLM directly to the live **SAP Business Accelerator Hub** (`api.sap.com`) using the standard **`API_MATERIAL_STOCK_SRV`** OData service.

---

## 1. Enterprise Architecture Overview

CadencePLM features a multi-tiered SAP S/4HANA connector (`src/connectors/sap_odata_client.py`) engineered for production industrial reliability:
- **Dual-Mode Connectivity:** Seamlessly switches between the live SAP Cloud Sandbox (`sandbox.api.sap.com`) and on-premise / local mock SAP instances.
- **CSRF Token Handshake:** Employs pre-flight `x-csrf-token: fetch` negotiation with cookie persistence for secure SAP NetWeaver and S/4HANA session management.
- **Multi-Storage Location (LGORT) Aggregation:** Aggregates stock across multiple physical warehouses while automatically excluding quarantine and scrap locations (`SCRP`, `QUAR`, `BLOCK`, `DEFECT`).
- **Currency Normalization (`WAERS`):** Automatically normalizes international currencies (`EUR`, `TRY`, `GBP`, `JPY`) into standard baseline costs without calculation crashes.
- **Zero-Downtime Graceful Fallback:** If internet connectivity drops, or the sandbox API key expires, the system automatically falls back to an embedded local emulator without crashing or stalling operations.

---

## 2. Step-by-Step: Obtaining Free SAP Sandbox API Key

SAP provides instant developer sandbox access to SAP S/4HANA Cloud OData APIs through the SAP Business Accelerator Hub:

1. **Create an Account:**
   - Navigate to [https://api.sap.com](https://api.sap.com).
   - Click **Log On / Register** at the top right and create a free SAP Community account.
2. **Locate the Material Stock API:**
   - Search for **"Material Stock"** or navigate to `SAP S/4HANA Cloud Public Edition` $\rightarrow$ `OData V2` $\rightarrow$ `Material Stock - Read (API_MATERIAL_STOCK_SRV)`.
3. **Generate Sandbox API Key:**
   - In the API overview page, click the **"Show API Key"** button (or navigate to your user profile $\rightarrow$ **Settings** $\rightarrow$ **API Keys**).
   - Copy the alphanumeric API key (e.g., `aBcDeFg123456789...`).

---

## 3. Configuring CadencePLM (`.env`)

Add the following variables to your `.env` file in the project root:

```env
# ---------------------------------------------------------------------------
# SAP S/4HANA Cloud Sandbox Configuration (Stage 17)
# ---------------------------------------------------------------------------
SAP_USE_SANDBOX=True
SAP_ODATA_BASE_URL=https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV
SAP_API_KEY=your_sap_business_hub_api_key_here
```

> **Note on Fallback Behavior:**  
> If `SAP_USE_SANDBOX=False` or `SAP_API_KEY` is left blank, CadencePLM automatically runs in local deterministic emulator mode, providing instant offline testing.

---

## 4. Verification & Testing

Execute the automated end-to-end sandbox test script:

```bash
python scripts/test_live_sap_sandbox.py
```

Expected output:
```text
===============================================================================================
  CADENCE PLM — SAP S/4HANA CLOUD SANDBOX VE ENDÜSTRİYEL ADAPTÖR TESTİ (AŞAMA 17)
  SAP Business Accelerator Hub (api.sap.com) Entegrasyonu & Graceful Fallback Denetimi
===============================================================================================

  [PASS] Adım 1: CSRF Token Handshake
  [PASS] Adım 2: Çoklu Depo (LGORT) Agregasyonu (Karantina/Hurda Filtrelendi)
  [PASS] Adım 3: Kur Dönüşümü & Normalizasyon (EUR/TRY -> USD)
  [PASS] Adım 4: Canlı Sandbox / Graceful Fallback Doğrulaması
===============================================================================================
✔ SAP S/4HANA CLOUD SANDBOX VE ENDÜSTRİYEL ADAPTÖR TESTİ BAŞARIYLA GEÇTİ (4/4).
```

---
---

# [TÜRKÇE] SAP S/4HANA Cloud Canlı Sandbox Entegrasyon Kılavuzu

Bu kılavuz, teknik direktörler, kurumsal ERP mimarları ve yazılım mühendisleri için CadencePLM'in resmi **SAP Business Accelerator Hub** (`api.sap.com`) üzerindeki canlı **`API_MATERIAL_STOCK_SRV`** OData servisine nasıl bağlanacağını adım adım açıklamaktadır.

---

## 1. Mimari Genel Bakış

CadencePLM, endüstriyel üretim şartlarına tam uyumlu kurumsal bir SAP konnektörü (`src/connectors/sap_odata_client.py`) sunar:
- **Çift Modlu Çalışma:** Canlı bulut sandbox'ı (`sandbox.api.sap.com`) ile şirket içi (on-premise) veya yerel emülatör arasında dinamik geçiş yapar.
- **CSRF Token El Sıkışması:** Güvenli SAP NetWeaver / S/4HANA oturumu için işlem öncesinde `x-csrf-token: fetch` başlığı ile oturum çerezlerini ve güvenlik token'ını alır.
- **Çoklu Depo (LGORT) Toplulaştırması:** Tek bir malzeme için dönen birden fazla depoyu tarar; karantina ve hurda depolarını (`SCRP`, `QUAR`, `BLOCK`, `DEFECT`) hariç tutarak yalnızca kullanılabilir fiziksel stoku toplar.
- **Döviz Kuru Normalizasyonu (`WAERS`):** SAP'den dönen farklı para birimlerini (`EUR`, `TRY`, `GBP`, `JPY`) standart baz maliyete dönüştürerek simülasyon motorunun çökmesini engeller.
- **Sıfır Kesinti (Graceful Fallback):** İnternet bağlantısı koptuğunda veya sandbox API anahtarı geçersiz olduğunda sistem asla çökmez; otomatik olarak yerel güvenli emülatör verisine geçer.

---

## 2. Adım Adım: Ücretsiz SAP Sandbox API Anahtarı Alma

1. **Hesap Oluşturma:**
   - [https://api.sap.com](https://api.sap.com) adresine gidin.
   - Sağ üstteki **Log On / Register** butonuna tıklayarak ücretsiz bir SAP Community hesabı oluşturun veya giriş yapın.
2. **Malzeme Stok Servisini Bulma:**
   - Arama çubuğuna **"Material Stock"** yazın veya `SAP S/4HANA Cloud Public Edition` $\rightarrow$ `OData V2` $\rightarrow$ `Material Stock - Read (API_MATERIAL_STOCK_SRV)` paketini seçin.
3. **Sandbox API Anahtarını Kopyalama:**
   - API sayfasındaki **"Show API Key"** butonuna tıklayın (veya profilinizdeki **Settings** $\rightarrow$ **API Keys** sekmesine gidin).
   - Üretilen API anahtarını kopyalayın (ör. `aBcDeFg123456789...`).

---

## 3. CadencePLM Yapılandırması (`.env`)

Proje kök dizinindeki `.env` dosyasına şu satırları ekleyin:

```env
# ---------------------------------------------------------------------------
# SAP S/4HANA Cloud Canlı Sandbox Yapılandırması (Aşama 17)
# ---------------------------------------------------------------------------
SAP_USE_SANDBOX=True
SAP_ODATA_BASE_URL=https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV
SAP_API_KEY=kopyalanan_sap_api_anahtariniz_buraya
```

> **Not:**  
> `SAP_USE_SANDBOX=False` yapıldığında veya `SAP_API_KEY` boş bırakıldığında CadencePLM otomatik olarak yerel emülatör modunda çalışır; geliştirme ve birim testler için internet gerekmez.

---

## 4. Test ve Doğrulama

Kurulumu doğrulamak için terminalden canlı test betiğini çalıştırın:

```bash
python scripts/test_live_sap_sandbox.py
```

Sistem tüm el sıkışmalarını, çoklu depo filtrelemesini ve canlı/fallback durumunu ekranda tablo olarak onaylayacaktır.
