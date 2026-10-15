# CadencePLM – Contributor & Engineering Guidelines (Contributing)
> **Bilingual Development & Contribution Guide / İki Dilli Katkı ve Geliştirme Kılavuzu**  
> *English version is presented first, followed by the Turkish version below.*  
> *Önce İngilizce versiyon sunulmuştur; Türkçe versiyon belgenin devamında yer almaktadır.*

---

# [ENGLISH] Contributor & Engineering Guidelines

Welcome to the CadencePLM engineering team. We maintain mission-critical manufacturing software where precision, deterministic correctness, and zero-downtime reliability are paramount.

---

## 1. CORE ARCHITECTURAL INVARIANTS (.antigravityrules)

Before submitting any Pull Request or proposing architecture modifications, ensure compliance with these non-negotiable rules:

1. **Deterministic Engine Isolation (§1):**  
   All mathematical calculations, cost accounting, DAG traversals, and run-out projections MUST reside in pure Python engines under `src/engines/`.  
   *Never ask an LLM or prompt to perform arithmetic multiplication, division, or graph searches.*
2. **Strict Typing & Pydantic v2 Models (§2):**  
   Every data object crossing boundary layers must be typed using standard Python typing (`list[str]`, `dict[str, Any]`, `Optional[T]`) and validated via Pydantic v2.
3. **Structured Industrial Exceptions (§3):**  
   Never return silent `None` or catch-all generic exceptions. Raise explicit domain exceptions from `src/core/exceptions.py` (`PartNotFoundError`, `BOMStructureError`, `CostCalculationError`).
4. **Test-Driven Rigor (§4):**  
   Every bug fix or feature addition must include a corresponding pytest test in `tests/`. All 120+ tests must pass with 100% green status.

---

## 2. LOCAL ENVIRONMENT SETUP

### Prerequisites
- Python 3.12+ (64-bit)
- Git
- Docker & Docker-Compose (optional, for containerized testing)

### Step-by-Step Installation
```bash
# 1. Clone the repository
git clone https://github.com/Muhammedali26/cadence_plm.git
cd cadence_plm

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install core and development dependencies in editable mode
pip install -e .
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

---

## 3. RUNNING THE VERIFICATION & TEST SUITE

Always run the full test suite before pushing commits:

```bash
# 1. Run all offline unit & integration tests
pytest -k "not TestRealOpenAIToolCalling and not TestECOAgentExceptions and not test_agent_analyze" -v

# 2. Run documentation and capability integrity tests
pytest tests/test_stage16_capabilities.py -v

# 3. Run the live Industrial Capability Verification Script
python scripts/verify_capabilities.py
```

Expected output of `scripts/verify_capabilities.py`:
```text
✔ TÜM YETENEK TESTLERİ BAŞARIYLA GEÇTİ (5/5). Toplam Süre: ~5 ms
CadencePLM deterministik motorları ve hata bariyerleri endüstriyel üretime hazırdır.
```

---

## 4. DOCKER & CONTAINERIZED VALIDATION

To validate that your changes build and run inside containerized production environments:

```bash
# Build and launch both API (port 8000) and Dashboard (port 8501)
docker compose up --build

# Verify container health
curl http://localhost:8000/docs
```

---
---

# [TÜRKÇE] Katkı ve İmalat Mühendisliği Kılavuzu

CadencePLM geliştirici ekibine hoş geldiniz. Otomotiv ve savunma sanayii gibi kritik imalat hatlarında çalışan bu sistemde matematiksel kesinlik, deterministik tutarlılık ve hat duruşunu önleme en yüksek önceliğe sahiptir.

---

## 1. MİMARİ İLKELER VE ZORUNLU KURALLAR (.antigravityrules)

Herhangi bir Pull Request açmadan veya kod değişikliği önermeden önce aşağıdaki kurallara kesinlikle uyunuz:

1. **Deterministik Motor İzolasyonu (§1):**  
   Tüm matematiksel hesaplamalar, hurda maliyetleri, ürün ağacı (DAG) gezintileri ve stok run-out analizleri `src/engines/` dizinindeki saf Python motorlarında yer almalıdır.  
   *Yapay zekaya (LLM) asla çarpma, bölme veya ağaç gezintisi yaptırılamaz.*
2. **Katı Tip Güvenliği ve Pydantic v2 (§2):**  
   Katmanlar arasında taşınan her veri modeli Pydantic v2 ve modern Python tip belirteçleri (`list[str]`, `dict[str, Any]`, `Optional[T]`) ile doğrulanmalıdır.
3. **Yapılandırılmış Endüstriyel Hata Yönetimi (§3):**  
   Hatalar asla sessizce yutulamaz veya genel `Exception` olarak fırlatılamaz. `src/core/exceptions.py` içindeki kurumsal hata sınıfları kullanılmalıdır.
4. **Test Güvencesi (§4):**  
   Tüm yeni özellikler `tests/` dizininde otomatik testlerle kapsanmalı ve tüm testler %100 başarıyla geçmelidir.

---

## 2. GELİŞTİRME ORTAMININ KURULUMU

```bash
# 1. Depoyu klonlayın
git clone https://github.com/Muhammedali26/cadence_plm.git
cd cadence_plm

# 2. Sanal ortam oluşturup aktif edin
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Bağımlılıkları kurun
pip install -e .
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

---

## 3. DOĞRULAMA VE TESTLERİN ÇALIŞTIRILMASI

```bash
# Çevrimdışı testleri çalıştırın
pytest -k "not TestRealOpenAIToolCalling and not TestECOAgentExceptions and not test_agent_analyze" -v

# Dokümantasyon sözleşmelerini doğrulayın
pytest tests/test_stage16_capabilities.py -v

# Canlı yetenek doğrulama betiğini koşturun
python scripts/verify_capabilities.py
```
