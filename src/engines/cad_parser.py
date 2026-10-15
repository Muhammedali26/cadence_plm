"""
src/engines/cad_parser.py
=========================
3D CAD / ISO 10303-21 STEP Metadata Ayrıştırıcısı.

Kurallar (.antigravityrules §1 & §2):
- Ağır C++ kütüphaneleri (OpenCASCADE vb.) kurmak yerine, ISO 10303-21 STEP
  AP203/AP214 formatını metin tabanlı (PRODUCT_DEFINITION,
  NEXT_ASSEMBLY_USAGE_OCCURRENCE) ayrıştıran saf ve deterministik Python motoru.
- Sıfır LLM, sıfır FastAPI bağımlılığı.
- Çıktı doğrudan `list[BOMItem]` formatındadır.
- `Any` tipi kesinlikle yasaktır.
"""

from __future__ import annotations

from collections import defaultdict
import io
import os
from pathlib import Path
import re

import pandas as pd

from src.core.exceptions import BOMStructureError
from src.schemas.bom import BOMItem

# ---------------------------------------------------------------------------
# Varsayılan Veri Yolları
# ---------------------------------------------------------------------------

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_SAMPLE_EBOM_PATH: Path = _PROJECT_ROOT / "data" / "sample_ebom.csv"


def _split_step_arguments(arg_str: str) -> list[str]:
    """
    STEP entity argümanlarını virgüllerden bölerek ayrıştırır.
    Tırnak içindeki ('...') ve parantez içindeki ((...)) virgülleri korur.
    """
    args: list[str] = []
    current: list[str] = []
    in_quote: bool = False
    depth: int = 0
    i = 0
    n = len(arg_str)

    while i < n:
        ch = arg_str[i]
        if ch == "'":
            # Çift tek tırnak (STEP kaçış karakteri '')
            if in_quote and i + 1 < n and arg_str[i + 1] == "'":
                current.append("'")
                i += 2
                continue
            in_quote = not in_quote
            current.append(ch)
        elif not in_quote:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        else:
            current.append(ch)
        i += 1

    if current:
        args.append("".join(current).strip())
    return args


def _clean_step_literal(val: str) -> str:
    """Tek tırnaklı STEP metin değerini temizler."""
    val = val.strip()
    if val.startswith("'") and val.endswith("'"):
        val = val[1:-1]
    return val.replace("''", "'").strip()


def _clean_ref_id(ref: str) -> str:
    """'#123' formatındaki referansı '123' olarak döner."""
    return ref.strip().lstrip("#")


class CADParser:
    """
    ISO 10303-21 STEP AP203/AP214 CAD montaj dosyalarını hafif ve saf
    Python ile ayrıştıran çekirdek sınıf.
    """

    def __init__(self, ebom_reference_path: Path | str | None = _SAMPLE_EBOM_PATH) -> None:
        self.ebom_reference_path: Path | None = (
            Path(ebom_reference_path) if ebom_reference_path is not None else None
        )
        self._cost_lookup: dict[str, tuple[float, str, str | None]] = {}
        self._load_reference_catalog()

    def _load_reference_catalog(self) -> None:
        """Mevcut kurumsal EBOM verisi varsa maliyet ve tedarikçi bilgilerini önbelleğe alır."""
        if self.ebom_reference_path and self.ebom_reference_path.exists():
            try:
                df = pd.read_csv(self.ebom_reference_path)
                for _, row in df.iterrows():
                    pn = str(row["part_number"]).strip()
                    cost = round(float(row.get("unit_cost", 0.0)), 2)
                    sup = str(row.get("supplier_id", "CAD-INTERNAL")).strip()
                    tlg = (
                        str(row["tooling_id"]).strip()
                        if "tooling_id" in df.columns and not pd.isna(row.get("tooling_id"))
                        else None
                    )
                    self._cost_lookup[pn] = (cost, sup, tlg)
            except Exception:
                pass

    def parse_step_assembly(
        self,
        step_file_content: str | Path | io.StringIO,
        default_unit_cost: float = 0.0,
        default_supplier_id: str = "CAD-STEP-AP214",
    ) -> list[BOMItem]:
        """
        CAD STEP AP214 dosyasındaki montaj ilişkilerini, parça isimlerini ve revizyon
        etiketlerini okuyup doğrudan BOMItem listesi döner.

        Parameters
        ----------
        step_file_content : str | Path | io.StringIO
            STEP dosyasının metin içeriği veya dosya yolu.
        default_unit_cost : float
            Katalogda bulunmayan parçalar için varsayılan birim maliyet USD.
        default_supplier_id : str
            Katalogda bulunmayan parçalar için varsayılan tedarikçi kimliği.

        Returns
        -------
        list[BOMItem]
            Hiyerarşik montaj yapısını temsil eden BOMItem listesi.

        Raises
        ------
        BOMStructureError
            Geçersiz, boş veya tanınmayan STEP dosyalarında.
        """
        raw_text: str
        if isinstance(step_file_content, Path) or (
            isinstance(step_file_content, str) and os.path.isfile(step_file_content)
        ):
            raw_text = Path(step_file_content).read_text(encoding="utf-8", errors="replace")
        elif isinstance(step_file_content, io.StringIO):
            raw_text = step_file_content.getvalue()
        else:
            raw_text = str(step_file_content)

        if not raw_text or "ISO-10303-21" not in raw_text:
            raise BOMStructureError(
                "Geçersiz veya boş STEP AP214 dosyası: 'ISO-10303-21' başlığı bulunamadı.",
                detail="STEP dosya formatı ISO 10303-21 standardına uygun olmalıdır.",
            )

        # C-tarzı yorumları temizle (/* ... */)
        cleaned_text = re.sub(r"/\*.*?\*/", "", raw_text, flags=re.DOTALL)

        # Varlıkları eşleştir (#<id> = <NAME>(<args>);)
        entity_regex = re.compile(
            r"#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*\((.*?)\);",
            re.DOTALL,
        )
        entities = entity_regex.findall(cleaned_text)

        if not entities:
            raise BOMStructureError(
                "STEP dosyasında işlenebilir DATA entity kaydı bulunamadı.",
                detail="DATA bölümü boş veya bozuk.",
            )

        # 1. Aşama: Haritalamaları topla
        products: dict[str, tuple[str, str]] = {}  # prod_id -> (part_number, part_name)
        formations: dict[str, tuple[str, str]] = {}  # form_id -> (revision, prod_id)
        definitions: dict[str, str] = {}  # def_id -> form_id
        occurrences: list[tuple[str, str]] = []  # (parent_def_id, child_def_id)

        for eid, etype, raw_args in entities:
            args = _split_step_arguments(raw_args)

            if etype == "PRODUCT":
                pn = _clean_step_literal(args[0])
                name = _clean_step_literal(args[1]) if len(args) > 1 else pn
                products[eid] = (pn, name)

            elif etype in (
                "PRODUCT_DEFINITION_FORMATION",
                "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE",
            ):
                rev = _clean_step_literal(args[0])
                prod_ref = _clean_ref_id(args[2]) if len(args) > 2 else ""
                formations[eid] = (rev, prod_ref)

            elif etype == "PRODUCT_DEFINITION":
                form_ref = _clean_ref_id(args[2]) if len(args) > 2 else ""
                definitions[eid] = form_ref

            elif etype in (
                "NEXT_ASSEMBLY_USAGE_OCCURRENCE",
                "QUANTIFIED_ASSEMBLY_USAGE_OCCURRENCE",
            ):
                parent_ref = _clean_ref_id(args[3]) if len(args) > 3 else ""
                child_ref = _clean_ref_id(args[4]) if len(args) > 4 else ""
                occurrences.append((parent_ref, child_ref))

        # 2. Aşama: PRODUCT_DEFINITION -> (part_number, part_name, revision) eşlemesi
        def_to_part: dict[str, tuple[str, str, str]] = {}
        for def_id, form_id in definitions.items():
            if form_id in formations:
                rev, prod_id = formations[form_id]
                if prod_id in products:
                    pn, name = products[prod_id]
                    def_to_part[def_id] = (pn, name, rev)

        # 3. Aşama: Ebeveyn-Çocuk ilişkilerini ve miktarları hesapla
        child_parents: dict[str, str] = {}
        usage_counts: dict[tuple[str, str], float] = defaultdict(float)

        for parent_ref, child_ref in occurrences:
            if parent_ref in def_to_part and child_ref in def_to_part:
                parent_pn = def_to_part[parent_ref][0]
                child_pn = def_to_part[child_ref][0]
                child_parents[child_pn] = parent_pn
                usage_counts[(parent_pn, child_pn)] += 1.0

        # 4. Aşama: Tüm parçaları BOMItem modellerine dönüştür
        part_metadata: dict[str, tuple[str, str]] = {}
        for pn, name, rev in def_to_part.values():
            part_metadata[pn] = (name, rev)

        for prod_id, (pn, name) in products.items():
            if pn not in part_metadata:
                part_metadata[pn] = (name, "A")

        bom_items: list[BOMItem] = []

        for pn, (name, rev) in part_metadata.items():
            parent_pn = child_parents.get(pn)

            # Miktarı belirle: üst parçası varsa kullanım adedi, kök parça ise 1.0
            if parent_pn is not None:
                qty = usage_counts.get((parent_pn, pn), 1.0)
            else:
                qty = 1.0

            # Katalogdan maliyet ve tedarikçi zenginleştirmesi
            if pn in self._cost_lookup:
                cost, sup, tlg = self._cost_lookup[pn]
            else:
                cost = default_unit_cost
                sup = default_supplier_id
                tlg = None

            item = BOMItem(
                part_number=pn,
                part_name=name,
                revision=rev,
                parent_part_number=parent_pn,
                quantity=max(qty, 1.0),
                unit_cost=cost,
                supplier_id=sup,
                tooling_id=tlg,
            )
            bom_items.append(item)

        # Kök parçalar en başta olacak şekilde sırala (parent_part_number None olanlar önce)
        bom_items.sort(key=lambda x: (0 if x.parent_part_number is None else 1, x.part_number))

        return bom_items

    # Kullanıcı ve script esnekliği için alias
    parse_step_file = parse_step_assembly


# ---------------------------------------------------------------------------
# Modül Düzeyi Kısayol Fonksiyonları ve Alias'lar
# ---------------------------------------------------------------------------

_default_parser = CADParser()


def parse_step_assembly(step_file_content: str | Path | io.StringIO) -> list[BOMItem]:
    """
    ISO 10303-21 STEP montaj dosyasını hafif metin tabanlı motorla ayrıştırarak
    BOMItem listesi döner.

    Parameters
    ----------
    step_file_content : str | Path | io.StringIO
        STEP dosya içeriği veya dosya yolu.

    Returns
    -------
    list[BOMItem]
        Çıkarılan BOM parçaları.
    """
    return _default_parser.parse_step_assembly(step_file_content)


# Kullanıcı scriptleri ve harici çağrılar için alias'lar
CADStepParser = CADParser
parse_step_file = parse_step_assembly
