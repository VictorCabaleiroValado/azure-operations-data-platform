"""Fictional company reference data. Coordinates are approximate demo locations."""

WAREHOUSES = [
    {
        "id": "centro",
        "name": "Madrid Centro",
        "area": "Centro",
        "lat": 40.4169,
        "lon": -3.7038,
        "code": "MAD-01",
    },
    {
        "id": "leganes",
        "name": "Leganés",
        "area": "Leganés",
        "lat": 40.3270,
        "lon": -3.7653,
        "code": "MAD-02",
    },
    {
        "id": "sanchinarro",
        "name": "Sanchinarro",
        "area": "Sanchinarro",
        "lat": 40.4943,
        "lon": -3.6598,
        "code": "MAD-03",
    },
    {
        "id": "pedrezuela",
        "name": "Pedrezuela",
        "area": "Pedrezuela",
        "lat": 40.7424,
        "lon": -3.6001,
        "code": "MAD-04",
    },
]
SUPPLIERS = [
    {
        "id": "nexo",
        "name": "Nexo Electronics",
        "delimiter": ",",
        "fields": ["referencia", "unidades", "coste_eur", "fecha_stock"],
    },
    {
        "id": "iberia",
        "name": "Iberia Components",
        "delimiter": ";",
        "fields": ["sku", "stock", "precio_eur", "fecha"],
    },
    {
        "id": "circuito",
        "name": "Digital Circuit",
        "delimiter": ",",
        "fields": ["product_code", "quantity", "unit_cost_eur", "snapshot_date"],
    },
]
PRODUCTS = [
    {"sku": "EL-101", "name": "Office Laptop 14", "category": "Computing", "cost_cents": 64900},
    {"sku": "EL-102", "name": "27-inch IPS Monitor", "category": "Computing", "cost_cents": 17900},
    {"sku": "EL-103", "name": "Work Mini PC", "category": "Computing", "cost_cents": 38900},
    {"sku": "EL-201", "name": "USB-C Dock", "category": "Accessories", "cost_cents": 6900},
    {"sku": "EL-202", "name": "Wireless Keyboard", "category": "Accessories", "cost_cents": 2900},
    {"sku": "EL-203", "name": "Ergonomic Mouse", "category": "Accessories", "cost_cents": 2400},
    {"sku": "EL-301", "name": "SSD 1 TB", "category": "Components", "cost_cents": 7900},
    {"sku": "EL-302", "name": "16 GB RAM", "category": "Components", "cost_cents": 3900},
    {"sku": "EL-303", "name": "Network Adapter", "category": "Components", "cost_cents": 1900},
    {"sku": "EL-401", "name": "USB Headset", "category": "Audio", "cost_cents": 3400},
    {"sku": "EL-402", "name": "Desktop Speaker", "category": "Audio", "cost_cents": 4500},
    {"sku": "EL-403", "name": "USB Microphone", "category": "Audio", "cost_cents": 5900},
]
WAREHOUSE_IDS = {w["id"] for w in WAREHOUSES}
SUPPLIER_BY_ID = {s["id"]: s for s in SUPPLIERS}
PRODUCT_BY_SKU = {p["sku"]: p for p in PRODUCTS}
