# Entender Azure Operations Data Platform

## La historia

Imagina una distribuidora de electrónica con cuatro almacenes: Centro, Leganés, Sanchinarro y Pedrezuela. Tres proveedores envían archivos con sus existencias, cada uno con nombres de columnas diferentes. Tu sistema recibe esos archivos, los revisa y prepara una vista común del inventario.

La empresa y los datos son ficticios. El código, las comprobaciones y los servicios desplegados sí deben verificarse de verdad.

## Las cinco piezas

1. **Portal / API:** la web donde seleccionas el almacén y subes un archivo. Una API es la parte que recibe la petición y devuelve los resultados.
2. **Blob Storage:** el lugar de Azure donde guardamos originales, estados y resultados. Piensa en archivos privados organizados por identificador.
3. **Queue Storage:** la lista de trabajos pendientes. El mensaje lleva el identificador del archivo, no todo su contenido.
4. **Container Apps Job:** el programa Python que se pone en marcha para revisar un archivo y termina al acabar.
5. **Azure Monitor:** los registros que permiten comprobar qué ejecutó el programa y por qué falló.

Un contenedor empaqueta el programa y sus dependencias. El mismo paquete sirve para la web y el procesador, con comandos de inicio distintos. Esto simplifica su mantenimiento.

## Qué significa cada estado

| Estado | Significado |
|---|---|
| En cola | El archivo está guardado y pendiente de trabajo |
| Procesando | El worker ha tomado el archivo |
| Completado | Todas las filas son válidas y el resultado está guardado |
| Rechazado | Hay errores de datos; el inventario anterior se conserva |
| Fallo técnico | Se agotaron los intentos de entrega; un operador revisa y reintenta |

Un archivo rechazado necesita una corrección. Un fallo técnico puede resolverse sin cambiar los datos, por ejemplo recuperando acceso al almacenamiento.

## Un ejemplo que puedes defender

Nexo envía ocho portátiles al inventario declarado del almacén Centro. El archivo dice ocho unidades disponibles; no es una entrega que debamos sumar cada vez que llega. Si subes el mismo archivo dos veces, el resultado sigue siendo ocho. Una nueva fotografía corregida de dieciocho unidades sustituye la anterior del mismo proveedor, almacén y fecha. Una fotografía de una fecha más antigua nunca gana a una más nueva.

El stock de proveedores diferentes se considera formado por lotes independientes. No implementamos ventas, reservas ni transferencias. Los totales usan la última fotografía válida de cada proveedor; pueden mezclar fechas y la web muestra esas fechas.

## Cómo aprenderlo en orden

1. Selecciona cada almacén en el mapa y compara los filtros con el selector de la parte superior.
2. Descarga un ejemplo; abre sus cuatro columnas y relaciona una fila con un producto.
3. Sigue el archivo en `api.py`, `service.py` y `validation.py`.
4. Prueba duplicado, error y corrección; explica por qué el total debe cambiar o permanecer igual.
5. En Azure, identifica almacenamiento, cola, portal y job. Comprueba una ejecución real y sus logs.
6. Lee `infra/main.bicep`: relaciona cada recurso con una pieza que ya hayas usado.
7. Revisa el gasto real. Una alerta avisa, pero no corta el consumo.

## Conceptos profesionales, con ejemplos

- **Idempotencia:** repetir el mismo archivo no duplica existencias.
- **Procesamiento por eventos:** el trabajo comienza porque llega un mensaje a la cola.
- **Identidad administrada:** Azure reconoce al programa y le concede permisos sin guardar una contraseña en el código.
- **Infraestructura como código:** Bicep describe los recursos para recrearlos.
- **Observabilidad:** los registros permiten explicar qué pasó con un archivo.
- **CI:** GitHub ejecuta pruebas antes de dar por válida una versión.

## Demostración de tres minutos

Selecciona Pedrezuela y muestra el inventario. Pasa a Centro, descarga el archivo con errores, súbelo y abre el resultado. Muestra la corrección y después vuelve a subirla para demostrar que no se duplica. Termina con una ejecución del job en Azure y una decisión que sepas justificar, por ejemplo separar la web del procesamiento.

La copia estática permite navegar, pero no subir. En Azure los ejemplos pasan por almacenamiento y cola reales. El modo local permite practicar con archivos propios. Consulta VERIFICATION.md antes de afirmar qué partes se han verificado en Azure.
