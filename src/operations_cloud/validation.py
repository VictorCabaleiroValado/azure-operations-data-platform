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
            "errors": [{"line": 0, "message": "File is empty or exceeds 512 KiB."}],
            "row_count": 0,
        }
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"rows": [], "errors": [{"line": 0, "message": "The file must use UTF-8."}], "row_count": 0}
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
                    {"line": 1, "message": "Expected header: " + spec["delimiter"].join(spec["fields"])}
                ],
                "row_count": 0,
            }
        for values in reader:
            if not values:
                continue
            count += 1
            if count > MAX_ROWS:
                errors.append({"line": reader.line_num, "message": "Maximum 5,000 rows per file."})
                break
            try:
                if len(values) != 4:
                    raise ValueError("Exactly four columns are required.")
                sku, quantity, cost, stamp = [v.strip() for v in values]
                if sku not in PRODUCT_BY_SKU:
                    raise ValueError("Unknown product reference; use the demo catalog.")
                if sku in seen:
                    raise ValueError("Duplicate product reference within the file.")
                seen.add(sku)
                if not re.fullmatch(r"\d{1,6}", quantity) or int(quantity) > 100000:
                    raise ValueError("Quantity: integer between 0 and 100,000.")
                if not re.fullmatch(r"\d{1,6}([.,]\d{1,2})?", cost):
                    raise ValueError("Cost: positive number with up to two decimal places.")
                cents = int(Decimal(cost.replace(",", ".")) * 100)
                if not 1 <= cents <= 100000000:
                    raise ValueError("Cost outside the allowed range.")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
                    raise ValueError("Date: use YYYY-MM-DD.")
                observed = date.fromisoformat(stamp)
                if observed > today or observed < date(2020, 1, 1):
                    raise ValueError("Stock date is in the future or before 2020.")
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
        errors.append({"line": reader.line_num, "message": "Malformed CSV; check quotes and delimiters."})
    if count == 0:
        errors.append({"line": 2, "message": "The file contains no products."})
    if len(dates) > 1:
        errors.append({"line": 0, "message": "All rows must share the same stock date."})
    return {"rows": [] if errors else rows, "errors": errors, "row_count": count}
