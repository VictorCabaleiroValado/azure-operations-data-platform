# Entender el proyecto

## Qué construimos

Una web para comparar mediciones de velocidad de internet en dos zonas: Madrid y Fayetteville. Elegimos estas zonas por tu trayectoria en Madrid y Arkansas. Los datos son públicos, de Ookla, y corresponden a dos trimestres de 2024.

La web responde: ¿qué velocidades se registraron?, ¿dónde aparecen mediciones más lentas?, ¿qué cambia entre los dos trimestres? No detecta averías en directo ni demuestra por qué cambió una conexión.

## Las tres piezas

| Paso | Qué hace | Servicio de Azure | Código que debes leer |
|---|---|---|---|
| 1. Procesar | Descarga datos, selecciona las zonas y comprueba errores | Container Apps Job | `src/telecom_cloud/pipeline.py` |
| 2. Guardar | Conserva el archivo de datos para que lo lea la web | Blob Storage | `src/telecom_cloud/storage.py` |
| 3. Mostrar | Recibe los filtros, consulta los datos y entrega la web | Una Container App para API y web | `src/telecom_cloud/api.py` y `web/` |

**Un contenedor** es un paquete con tu programa y lo necesario para ejecutarlo. **Una API** recibe una petición, por ejemplo «Madrid, móvil, cuarto trimestre», y devuelve los resultados. **Blob Storage** guarda archivos. **SQLite** permite consultar con SQL un archivo de datos; no es un servidor Azure SQL.

El job se ejecuta cuando lo lanzas. La aplicación web es el componente al que entra el visitante. Son dos usos distintos del mismo código empaquetado.

## Qué aporta cloud computing

El objetivo del despliegue es que Azure ejecute el programa y sirva la web sin depender de que tu portátil esté encendido. Además aprenderás a configurar permisos, consultar errores y controlar el consumo.

- **Azure Monitor:** consultar los registros para entender qué ocurrió.
- **Managed identities:** permitir que el job escriba datos y que la web los lea, sin guardar contraseñas en el código.
- **Bicep:** escribir la configuración de Azure en un archivo reproducible.
- **Container Registry:** guardar el paquete de la aplicación. GitHub Actions lo construye y trata de subirlo al registro de Azure.

Estas herramientas apoyan el proyecto; no son cuatro aplicaciones más que tengas que desarrollar.

## Lo que está funcionando y lo que falta

La demo pública de GitHub Pages utiliza una copia de los datos. El procesamiento local, las consultas y las pruebas de CI están verificados. Azure for Students está activo. El despliegue de la aplicación en Azure todavía no está terminado: el primer flujo de construcción de imagen falló en el inicio de sesión de Azure.

Por tanto, hoy puedes mostrar la demo y explicar el diseño. Solo podremos decir «ejecutado en Azure» cuando comprobemos allí la carga de datos y la web. La demo gratuita seguirá disponible como copia estática.

## Aprenderlo en orden

1. **Usa la web.** Selecciona Madrid y después Fayetteville. Explica Mbps (velocidad) y ms (latencia). Cambia el mínimo de pruebas y observa qué puntos desaparecen.
2. **Sigue un dato.** Abre `config.json`, identifica las zonas y los trimestres, y busca cómo `pipeline.py` los utiliza. Lee en `model.py` las comprobaciones antes de guardar.
3. **Sigue una consulta.** Busca `/api/explore` en `api.py`: los filtros del usuario terminan en una consulta SQL. La web representa la respuesta.
4. **Reconoce los recursos.** En el portal de Azure localiza el job, el almacenamiento y la app cuando estén desplegados. Relaciona cada uno con los tres pasos.
5. **Comprueba un fallo y el coste.** Ejecuta las pruebas de datos inválidos, consulta los registros del job y revisa el consumo real en Azure.

Después puedes estudiar los detalles de versiones de datos, permisos federados y recuperación en `ARCHITECTURE.md` y `RUNBOOK.md`. No necesitas empezar por ahí.

## Cómo explicarlo en una entrevista

«Mi formación es de telecomunicaciones y ahora trabajo con datos. Elegí mediciones públicas de internet en Madrid y Fayetteville para practicar un flujo completo en Azure: procesar con Python, guardar los resultados y servir una web. Puedo filtrar por zona, tipo de conexión y trimestre. Separé la tarea que actualiza datos de la aplicación que los consulta.»

Añade siempre el estado real del despliegue. No memorices una lista de servicios: demuestra una decisión, una consulta y una comprobación. Si te preguntan por herramientas de IA, explica con honestidad cómo las usaste y qué has comprendido y verificado tú.

## Azure for Students y el coste

Usamos la suscripción de estudiante del proyecto, con crédito de 100 USD por hasta 12 meses según la oferta. El crédito no significa que cada recurso sea gratis: el registro de contenedores, el almacenamiento y la ejecución pueden consumirlo. Hay una alerta de 5 USD/mes; una alerta no detiene el gasto. Conservamos el límite de gasto de la oferta y no cambiamos a pago por uso.
