"""
src/mcp_servers/fastmcp_gateway.py
==================================
CadencePLM FastMCP Kurumsal Protokol Katmanı.

Kurallar (.antigravityrules §1, §2, §3):
- Çekirdek motor fonksiyonlarını sıfırdan yazmaz; src/engines/ altındaki
  BOMTreeEngine, ImpactCalculatorEngine ve EffectivityEngine sınıflarını
  import edip MCP Tool standartlarına wrap eder.
- Tip Güvenliği: Python 3.11+, katı tip ipuçları (type hints), sıfır Any kullanımı.
- Bağımsız çalıştırılabilir: `python -m src.mcp_servers.fastmcp_gateway`
  ile stdio protokolü üzerinden doğrudan MCP istemcilerine (Claude, Antigravity vb.)
  hizmet verir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd

# FastMCP içe aktarımı (standart mcp SDK veya fastmcp paketi)
try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from src.core.exceptions import PartNotFoundError
from src.engines.bom_tree import BOMTreeEngine
from src.engines.effectivity_engine import EffectivityEngine
from src.engines.impact_calculator import ImpactCalculatorEngine
from src.engines.rework_optimizer import ReworkOptimizerEngine
from src.schemas.inventory import InventoryItem

# ---------------------------------------------------------------------------
# Veri Yolları ve Yardımcı Fonksiyonlar
# ---------------------------------------------------------------------------

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_DATA_DIR: Path = _PROJECT_ROOT / "data"


def get_ebom_path() -> Path:
    """EBOM CSV dosyasının geçerli yolunu bulur."""
    candidates = [
        _DATA_DIR / "sample_ebom.csv",
        Path("data") / "sample_ebom.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return _DATA_DIR / "sample_ebom.csv"


def get_inventory_path() -> Path:
    """SAP Envanter CSV dosyasının geçerli yolunu bulur."""
    candidates = [
        _DATA_DIR / "sample_sap_inventory.csv",
        _DATA_DIR / "sample_inventory.csv",
        Path("data") / "sample_sap_inventory.csv",
        Path("data") / "sample_inventory.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return _DATA_DIR / "sample_sap_inventory.csv"


def load_inventory_map(path: Path) -> dict[str, InventoryItem]:
    """SAP Envanter CSV verisini okuyarak InventoryItem sözlüğü oluşturur."""
    df = pd.read_csv(path)
    inv_map: dict[str, InventoryItem] = {}
    for _, row in df.iterrows():
        pn = str(row["part_number"]).strip()
        stock = int(row["stock_quantity"])
        lead = int(row["lead_time_days"])
        location = (
            str(row["location"]).strip()
            if "location" in df.columns and not pd.isna(row.get("location"))
            else "WAREHOUSE-DEFAULT"
        )
        inv_map[pn] = InventoryItem(
            part_number=pn,
            stock_quantity=stock,
            lead_time_days=lead,
            location=location,
        )
    return inv_map


# ---------------------------------------------------------------------------
# Zengin Yanıt Tipleri (Dict ve Attr/Iter Uyumlu)
# ---------------------------------------------------------------------------

class BOMTreeDict(dict[str, object]):
    """
    BOM ağaç sonucu için zengin sözlük yapısı.

    - Standart sözlük erişimi: res["part_number"], res["tree"], "tree" in res
    - Nitelik erişimi: res.part_number, res.total_components
    - İterasyon uyumluluğu: for comp in res (alt parçalar üzerinde döner)
    - Dizi indeksleme: res[0] (kök parçayı/ilk bileşeni döner)
    """

    def __getattr__(self, item: str) -> object:
        if item in self:
            return self[item]
        raise AttributeError(f"'BOMTreeDict' nesnesinde {item!r} niteliği bulunamadı.")

    def __iter__(self) -> Iterator[object]:
        components = self.get("components", [])
        if isinstance(components, list):
            return iter(components)
        return super().__iter__()

    def __getitem__(self, key: object) -> object:
        if isinstance(key, int):
            components = self.get("components", [])
            if isinstance(components, list):
                return components[key]
        return super().__getitem__(key)  # type: ignore[index]


class InventoryResultDict(dict[str, object]):
    """SAP Envanter sonucu için zengin sözlük yapısı."""

    def __getattr__(self, item: str) -> object:
        if item in self:
            return self[item]
        raise AttributeError(f"'InventoryResultDict' nesnesinde {item!r} niteliği bulunamadı.")


class SimulationResultDict(dict[str, object]):
    """ECO Simülasyon sonucu için zengin sözlük yapısı."""

    def __getattr__(self, item: str) -> object:
        if item in self:
            return self[item]
        raise AttributeError(f"'SimulationResultDict' nesnesinde {item!r} niteliği bulunamadı.")


# ---------------------------------------------------------------------------
# MCP Sunucu Başlatma
# ---------------------------------------------------------------------------

cadence_mcp: FastMCP = FastMCP("cadence_mcp")
mcp: FastMCP = cadence_mcp


# ---------------------------------------------------------------------------
# Araç 1: Teamcenter PLM EBOM Ağacı
# ---------------------------------------------------------------------------

@mcp.tool(name="tool_get_ebom")
def tool_get_ebom(part_number: str) -> dict[str, object]:
    """
    Teamcenter PLM sistemini taklit eden parça ağacı (EBOM) sorgulama aracı.

    Verilen parça numarasından başlayarak kök bilgilerini, alt montaj
    hiyerarşisini ve yukarı yönlü Where-Used montaj ilişkilerini döner.

    Parameters
    ----------
    part_number : str
        Sorgulanacak parça numarası (örn. 'GBX-1000' veya 'GB-PINION-02').

    Returns
    -------
    dict[str, object]
        Parça detayları, alt montaj ağacı (tree/components) ve where_used listesi.
    """
    bom_engine = BOMTreeEngine()
    bom_engine.load_from_csv(str(get_ebom_path()))

    if part_number not in bom_engine._parts:
        raise PartNotFoundError(
            f"Parça Teamcenter PLM BOM'da bulunamadı: {part_number!r}",
            part_id=part_number,
        )

    root_part = bom_engine.get_part(part_number)
    affected_subassemblies = bom_engine.get_affected_subassemblies(part_number)
    where_used_parents = bom_engine.get_where_used(part_number)

    components: list[dict[str, object]] = [
        item.model_dump() for item in affected_subassemblies
    ]
    where_used: list[dict[str, object]] = [
        w.model_dump() for w in where_used_parents
    ]

    return BOMTreeDict(
        {
            "part_number": root_part.part_number,
            "part_name": root_part.part_name,
            "revision": root_part.revision,
            "parent_part_number": root_part.parent_part_number,
            "quantity": root_part.quantity,
            "unit_cost": root_part.unit_cost,
            "supplier_id": root_part.supplier_id,
            "tooling_id": root_part.tooling_id,
            "components": components,
            "tree": components,
            "subassemblies": components,
            "where_used": where_used,
            "total_components": len(components),
            "source_system": "Teamcenter PLM",
        }
    )


# ---------------------------------------------------------------------------
# Araç 2: SAP S/4HANA Gerçek Zamanlı Envanter
# ---------------------------------------------------------------------------

@mcp.tool(name="tool_get_inventory")
def tool_get_inventory(part_number: str) -> dict[str, object]:
    """
    SAP S/4HANA sistemini taklit eden gerçek zamanlı envanter sorgulama aracı.

    Verilen parçanın güncel stok miktarını, tedarik teslim süresini ve
    depo lokasyonunu döner.

    Parameters
    ----------
    part_number : str
        Sorgulanacak parça numarası (örn. 'GB-PINION-02').

    Returns
    -------
    dict[str, object]
        Stok adedi, teslim süresi (gün) ve depo lokasyonu.
    """
    inventory_map = load_inventory_map(get_inventory_path())

    if part_number not in inventory_map:
        raise PartNotFoundError(
            f"Parça SAP S/4HANA envanterinde bulunamadı: {part_number!r}",
            part_id=part_number,
        )

    inv_item = inventory_map[part_number]
    return InventoryResultDict(
        {
            "part_number": inv_item.part_number,
            "stock_quantity": inv_item.stock_quantity,
            "lead_time_days": inv_item.lead_time_days,
            "location": inv_item.location,
            "source_system": "SAP S/4HANA",
            "status": "AVAILABLE" if inv_item.stock_quantity > 0 else "OUT_OF_STOCK",
        }
    )


# ---------------------------------------------------------------------------
# Araç 3: Çekirdek Simülasyon Motoru (ECO Impact Simulation)
# ---------------------------------------------------------------------------

@mcp.tool(name="tool_run_impact_simulation")
def tool_run_impact_simulation(
    eco_id: str,
    part_number: str,
    change_type: str,
) -> dict[str, object]:
    """
    CadencePLM çekirdek simülasyon motorunu çalıştırarak ECO finansal ve operasyonel
    etki analizini hesaplayan araç.

    BOMTreeEngine, ImpactCalculatorEngine ve EffectivityEngine motorlarını
    deterministik olarak çalıştırır; hurda maliyetini, etkilenen kalıpları,
    kritik teslim süresini ve stok yürürlük (run-out) planını JSON olarak döner.

    Parameters
    ----------
    eco_id : str
        Mühendislik Değişiklik Emri kimliği (örn. 'ECO-2024-001').
    part_number : str
        Değişiklikten etkilenen parça numarası (örn. 'GB-PINION-02').
    change_type : str
        Değişiklik tipi (örn. 'TOLERANCE', 'MATERIAL', 'GEOMETRY', 'OBSOLETE').

    Returns
    -------
    dict[str, object]
        Hurda maliyeti, etkilenen kalıplar, geçiş süresi ve yürürlük stratejisi (JSON).
    """
    # 1. BOM Ağacı ve alt/üst montajları getir
    bom_tree = BOMTreeEngine()
    bom_tree.load_from_csv(str(get_ebom_path()))

    if part_number not in bom_tree._parts:
        raise PartNotFoundError(
            f"Parça BOM hiyerarşisinde bulunamadı: {part_number!r}",
            part_id=part_number,
        )

    affected_parts = bom_tree.get_affected_subassemblies(part_number)
    where_used_parents = bom_tree.get_where_used(part_number)

    # 2. Envanter verisini yükle
    inventory_map = load_inventory_map(get_inventory_path())

    # 3. Hurda, kalıp ve süre etkisini hesapla
    impact_calc = ImpactCalculatorEngine()
    summary = impact_calc.calculate(
        eco_id=eco_id,
        root_part_number=part_number,
        affected_parts=affected_parts,
        inventory_map=inventory_map,
    )

    # 4. Yürürlük ve stok geçiş planını hesapla
    root_part = bom_tree.get_part(part_number)
    root_inv = inventory_map.get(part_number)
    stock_qty = root_inv.stock_quantity if root_inv else 0

    effectivity_engine = EffectivityEngine()
    strategy, run_out_days, _ = effectivity_engine.calculate_transition_plan(
        stock_quantity=stock_qty,
        unit_cost=root_part.unit_cost,
        tooling_lead_time_days=summary.max_transition_lead_time_days,
    )

    # 5. Rework vs. Scrap optimizasyonunu hesapla
    rework_engine = ReworkOptimizerEngine()
    rework_analysis = rework_engine.evaluate_rework(
        part_number=root_part.part_number,
        unit_cost=root_part.unit_cost,
        stock_quantity=stock_qty,
        change_type=change_type,
        part_name=root_part.part_name,
    )

    # 6. Modeli zenginleştir ve sözlük olarak dön
    final_summary = summary.model_copy(
        update={
            "where_used_parents": where_used_parents,
            "recommended_strategy": strategy,
            "run_out_days": run_out_days,
            "rework_analysis": rework_analysis,
        }
    )

    result_data = final_summary.model_dump()
    result_data["change_type"] = change_type.strip().upper()
    result_data["source_system"] = "CadencePLM Simulation Engine"

    return SimulationResultDict(result_data)


# ---------------------------------------------------------------------------
# Bağımsız Çalıştırma / Stdio Protokolü
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
