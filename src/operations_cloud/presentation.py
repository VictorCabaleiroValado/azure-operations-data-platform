"""English presentation of legacy run messages; stored evidence is unchanged."""

LEGACY_MESSAGES = {
    "Archivo vacío o superior a 512 KiB.": "File is empty or exceeds 512 KiB.",
    "El archivo debe usar UTF-8.": "The file must use UTF-8.",
    "Cabecera esperada: ": "Expected header: ",
    "Máximo de 5.000 filas por archivo.": "Maximum 5,000 rows per file.",
    "Se esperan exactamente cuatro columnas.": "Exactly four columns are required.",
    "Referencia desconocida; utiliza el catálogo de demostración.": "Unknown product reference; use the demo catalog.",
    "Referencia duplicada dentro del archivo.": "Duplicate product reference within the file.",
    "Unidades: entero entre 0 y 100.000.": "Quantity: integer between 0 and 100,000.",
    "Coste: número positivo con hasta dos decimales.": "Cost: positive number with up to two decimal places.",
    "Coste fuera del intervalo permitido.": "Cost outside the allowed range.",
    "Fecha: utiliza AAAA-MM-DD.": "Date: use YYYY-MM-DD.",
    "Fecha de stock futura o anterior a 2020.": "Stock date is in the future or before 2020.",
    "CSV mal formado; revisa comillas y separadores.": "Malformed CSV; check quotes and delimiters.",
    "El archivo no contiene productos.": "The file contains no products.",
    "Todas las filas deben compartir la misma fecha de stock.": "All rows must share the same stock date.",
    "Fallo técnico tras cinco entregas; revisa Azure Monitor y reintenta.": "Technical failure after five deliveries; check Azure Monitor and retry.",
    "Empresa, proveedores, inventario y ubicaciones de demostración ficticios.": "Fictional demo company, suppliers, inventory and locations.",
    "Procesamiento no encontrado.": "Processing run not found.",
    "Máximo 512 KiB.": "Maximum 512 KiB.",
    "La demo pública de Azure acepta solo los archivos de ejemplo del almacén seleccionado. Usa el modo local para archivos propios.": "The public Azure demo accepts only sample files for the selected warehouse. Use local mode for custom files.",
    "Los reintentos manuales de Azure están reservados al operador mediante CLI.": "Manual Azure retries are restricted to the operator through the CLI.",
    "Procesamiento ocupado.": "Processing run is busy.",
    "Almacén desconocido.": "Unknown warehouse.",
    "Ejemplo no encontrado.": "Sample not found.",
    "Proveedor o almacén desconocido.": "Unknown supplier or warehouse.",
    "El archivo debe tener entre 1 byte y 512 KiB.": "The file must contain between 1 byte and 512 KiB.",
    "Corrige el archivo y vuelve a subirlo; el original se conserva.": "Correct the file and upload it again; the original is preserved.",
}


def present_run(record):
    return {
        **record,
        "errors": [
            {**error, "message": english_message(error["message"])} for error in record.get("errors", [])
        ],
    }


def english_message(message):
    if message.startswith("Cabecera esperada: "):
        return "Expected header: " + message.removeprefix("Cabecera esperada: ")
    return LEGACY_MESSAGES.get(message, message)
