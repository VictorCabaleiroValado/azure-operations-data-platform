"""Normalize three supplier formats. A snapshot is accepted completely or rejected."""

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .catalog import PRODUCT_BY_SKU, SUPPLIER_BY_ID

MAX_BYTES = 512 * 1024
MAX_ROWS = 5000


def validate(content: bytes, supplier: str, today: date | None = None) -> dict:
    errors, rows, seen = [], [], set()
    today = today or date.today()
    if not content or len(content) > MAX_BYTES:
        return {
            "rows": [],
            "errors": [{"line": 0, "message": "Archivo vacío o superior a 512 KiB."}],
            "row_count": 0,
        }
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"rows": [], "errors": [{"line": 0, "message": "El archivo debe usar UTF-8."}], "row_count": 0}
    spec = SUPPLIER_BY_ID[supplier]
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=spec["delimiter"], strict=True)
    dates = set()
    count = 0
    try:
        header = next(reader, [])
        if header != spec["fields"]:
            return {
                "rows": [],
                "errors": [
                    {"line": 1, "message": "Cabecera esperada: " + spec["delimiter"].join(spec["fields"])}
                ],
                "row_count": 0,
            }
        for values in reader:
            if not values:
                continue
            count += 1
            if count > MAX_ROWS:
                errors.append({"line": reader.line_num, "message": "Máximo de 5.000 filas por archivo."})
                break
            try:
                if len(values) != 4:
                    raise ValueError("Se esperan exactamente cuatro columnas.")
                sku, quantity, cost, stamp = [v.strip() for v in values]
                if sku not in PRODUCT_BY_SKU:
                    raise ValueError("Referencia desconocida; utiliza el catálogo de demostración.")
                if sku in seen:
                    raise ValueError("Referencia duplicada dentro del archivo.")
                seen.add(sku)
                if not re.fullmatch(r"\d{1,6}", quantity) or int(quantity) > 100000:
                    raise ValueError("Unidades: entero entre 0 y 100.000.")
                if not re.fullmatch(r"\d{1,6}([.,]\d{1,2})?", cost):
                    raise ValueError("Coste: número positivo con hasta dos decimales.")
                cents = int(Decimal(cost.replace(",", ".")) * 100)
                if not 1 <= cents <= 100000000:
                    raise ValueError("Coste fuera del intervalo permitido.")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
                    raise ValueError("Fecha: utiliza AAAA-MM-DD.")
                observed = date.fromisoformat(stamp)
                if observed > today or observed < date(2020, 1, 1):
                    raise ValueError("Fecha de stock futura o anterior a 2020.")
                dates.add(stamp)
                product = PRODUCT_BY_SKU[sku]
                rows.append(
                    {
                        "sku": sku,
                        "product": product["name"],
                        "category": product["category"],
                        "quantity": int(quantity),
                        "unit_cost_cents": cents,
                        "snapshot_date": stamp,
                    }
                )
            except (ValueError, InvalidOperation) as exc:
                errors.append({"line": reader.line_num, "message": str(exc)})
    except csv.Error:
        errors.append({"line": reader.line_num, "message": "CSV mal formado; revisa comillas y separadores."})
    if count == 0:
        errors.append({"line": 2, "message": "El archivo no contiene productos."})
    if len(dates) > 1:
        errors.append({"line": 0, "message": "Todas las filas deben compartir la misma fecha de stock."})
    return {"rows": [] if errors else rows, "errors": errors, "row_count": count}
