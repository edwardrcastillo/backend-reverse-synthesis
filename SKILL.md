---
name: backend-reverse-synthesis
description: Protocolo determinista (Cero Adivinación) para reconstruir backends completos, esquemas SQL y contratos API a partir de código cliente huérfano (SPA, PWA, Electron ASAR, APK, Sourcemaps) extraído con REA v7.0.0 o Replica. Úsese siempre que se deba recrear o auditar el servidor de una aplicación cuyo backend original no está disponible.
---

# 🏛️ Skill: Síntesis Determinista de Backends desde Código Cliente (`backend-reverse-synthesis` v2.0)

## 💡 Origen y Por Qué se Creó este Skill
Cuando se utiliza **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript`, `inspect_capture`, `rea strings`, `inspect_android`) o **Replica** (`replica-recon` / `replica coderecon`) para extraer el código de una aplicación cuyo servidor original no está disponible, se obtiene el 100% de la lógica del cliente.

Sin embargo, en la práctica se identificó un fallo sistémico recurrente: **al recrear el backend reinterpretando el código de forma heurística ("adivinando"), el agente sufre de ceguera estructural**. Asume nombres de propiedades JSON que parecen lógicos pero no coinciden con lo que el cliente desestructura, omite llaves foráneas que dejan `<select>` vacíos silenciosamente, devuelve diccionarios de permisos vacíos (`permisos: {}`) que bloquean todos los botones de la UI, responde con JSON en rutas de descarga binaria o ignora propiedades leídas por callbacks nombrados (`.then(abrirEditor)`).

Este skill nació para **erradicar de raíz los errores de ceguera y adivinación en la recreación de backends**, transformando la reconstrucción en un proceso **100% determinista y verificable mediante análisis estático inter-procedural de contratos** donde el código cliente extraído se trata como una especificación formal inmutable.

---

## ⚠️ Los 10 Anti-Patrones de Ceguera y Adivinación (Causas Raíz Prohibidas)

| # | Anti-Patrón | Síntoma en el Cliente | Regla Determinista de Prevención |
| :--- | :--- | :--- | :--- |
| **1** | **Ceguera de Rutas Dinámicas y Prefijos (`URL_BASE`)** | Rutas de modales secundarios o acciones por fila (`/:id/anular/`, `/eliminar/estado/`) devuelven `404 Not Found`. | Resolver todas las variables prefijo (`URL_BASE`, `apiBase`), ternarios (`sel ? "/a/" + id : "/b/"`) y concatenaciones antes de definir las rutas del router. |
| **2** | **Adivinación del Molde de Respuesta (`Response Shape Guessing`)** | El servidor devuelve `{ ok: true, data: [...] }`, pero el cliente lee `r.proveedores`, `r.siguiente_codigo`, `d.pedido.numero`, `r.puede_anular` o `r.total`. | Extraer estáticamente todas las lecturas `<param>.<prop>` y `<param>.<prop>.<subprop>` (ej. `limite.sucursales_disponibles`, `categorias[].parent_id`) dentro de cada callback. |
| **3** | **Descarte Silencioso en Filtros Relacionales (`Silent .filter() Drop`)** | Un `<select>` (ej. Sucursales) aparece vacío sin lanzar errores en consola porque `Number(s.empresa_id) === Number(empresaId)` evalúa `NaN === 23` (`false`). | Extraer todas las expresiones `.filter()` y `.find()` del cliente e inyectar obligatoriamente todas las llaves foráneas (`empresa_id`, `sucursal_id`, `parent_id`, `activa`, `de_recibir`) con el tipo primitivo exacto del bootstrap HTML. |
| **4** | **Colisión Primitivo vs. Objeto (`Flat Array vs. Entity Object`)** | Un combobox (ej. Roles) se despliega en blanco o con `undefined` porque el servidor envió `["Dueño", "Cajero"]` cuando el cliente itera `r.id`, `r.nombre`, `r.es_dueno_empresa`. | Inspeccionar el renderizador DOM (`.map()`, `dataset.*`, `<option>`) de cada catálogo para verificar si consume escalares u objetos ricos. |
| **5** | **Asimetría de Transporte y Polimorfismo en `/guardar/`** | Formularios con archivos (`FormData`) fallan al hacer `req.json()`, o el botón "Eliminar" no borra porque envía `{ id, eliminar: true }` al endpoint `/guardar/` en vez de llamar a `/eliminar/`. | Implementar un parser universal (`parseBody`: JSON + Multipart FormData + URLSearchParams) y verificar todas las ramas condicionales (`b.eliminar`, `b.activa`, `b.id`) en los endpoints de guardado. |
| **6** | **Desincronización de Hidratación SSR y Crash por `INSERT` Ciego** | Al recargar (`F5`), los datos desaparecen o cambian de formato; o al reintentar guardar un código/usuario existente explota con `500 UNIQUE constraint failed`. | Reemplazar el JSON quemado en el HTML (`<script id="...-data">`) con los mismos serializadores vivos de la BD, e implementar `UPSERT` en toda ruta de creación. |
| **7** | **Bloqueo por Compuerta de Permisos Vacía (`Empty Permission Gate Stub: permisos: {}`)** | **Todos los botones de un módulo (ej. `#configuracion`) no hacen nada al hacer clic**, porque el frontend evalúa `if (!estado.permisos[item.clave]) return C.post("/api/configuracion/permiso/", ...)` y el backend devolvió `permisos: {}` y `200 OK` en `/permiso/`. | Extraer todas las claves de permiso del frontend (`config_*`, `modulo_*`) y poblar el diccionario completo con `true` en el estado de sesión/configuración. Prohibido devolver `permisos: {}`. |
| **8** | **Ceguera por Indirección de Estado (`Indirect State Forwarding & Named Callbacks`)** | El auditor reporta `(sin lectura directa)` en endpoints críticos (`/general/estado/`, `/factura/`, `/eliminar/estado/`) porque el `.then(abrirEditor)` pasa una función nombrada o reenvía el objeto `estado` a submódulos en otros archivos (`V.empresa = function(estado)`). | Resolver inter-proceduralmente tanto las funciones nombradas pasadas a `.then(fnName)` como los consumidores del objeto de estado compartido (`C.estado()`, `V.<modal>(estado)`) en todos los archivos hijos. |
| **9** | **Inversión Semántica MIME en Descargas (`Download Blob vs. JSON Error Gate`)** | Los botones de "Generar catálogo" o "Descargar plantilla" fallan diciendo *"No se pudo generar el archivo"* aunque el servidor respondió `200 OK`, porque el helper `C.descargar()` interpreta `Content-Type: application/json` como un error de negocio y exige un `Blob` binario/CSV/HTML con headers `Content-Disposition`, `X-Catalogo-Archivo` y `X-Catalogo-Total`. | Auditar todos los wrappers de descarga (`r.blob()`, `C.descargar`, `Content-Disposition`) y prohibir que sus rutas en el backend devuelvan `c.json()`. Deben retornar `c.body()` con MIME de archivo y cabeceras de metadatos. |
| **10** | **Stubs Sin Persistencia y Botones Huérfanos (`Stateless POST Stubs & Dead sinPantalla Buttons`)** | Crear una promoción, combo, baja o ajuste de factura muestra "Éxito", pero al abrir "Ver historial / Ver promociones" la lista sale vacía (`[]`); o botones con `sinPantalla: true` (`Moneda`, `Cliente por defecto`, `Etiqueta`) no abren ninguna ventana. | Prohibir endpoints `POST` que devuelvan `{ ok: true }` sin escribir en SQLite; cada entidad secundaria debe tener su tabla o almacén `configuracion_kv`. Todo botón en arrays de UI debe tener un handler real en el mapa de ventanas. |

---

## 🛠️ Herramienta Integrada de Auditoría Determinista v2.0

Este skill incluye el analizador estático inter-procedural ejecutable:
```bash
python3 /Users/edward/.gemini/config/skills/backend-reverse-synthesis/scripts/audit_api_contracts.py \
  --frontend <ruta_codigo_cliente_extraido> \
  --server <ruta_archivo_o_directorio_servidor>
```

### ¿Qué verifica `audit_api_contracts.py` v2.0?
1. Escanea recursivamente todos los archivos `.js/.ts/.jsx/.tsx/.vue/.svelte` del cliente extraído.
2. Resuelve constantes `URL_BASE`, llamadas relativas y concatenaciones dinámicas.
3. **Resolución Inter-procedural**:
   - Si un endpoint usa `.then(nombreFuncion)`, localiza `function nombreFuncion(param)` en el archivo y extrae todas las propiedades leídas sobre `param`.
   - Si un endpoint alimenta un estado compartido (`C.estado()`), rastrea todos los submódulos (`V.<id> = function(estado)`) en archivos hermanos y vincula todas las propiedades leídas al endpoint origen.
4. **Extracción de 2º Nivel e Iteradores**: Extrae tanto `param.prop.subprop` (`limite.sucursales_disponibles`) como propiedades de elementos dentro de `.map()` / `.filter()` (`categorias[].parent_id`, `tablas[].descripcion`).
5. **Auditoría de Compuertas de Permisos**: Extrae todas las claves `config_*` del frontend y **falla con código `1`** si alguna clave falta en el código del servidor (impidiendo el anti-patrón `permisos: {}`).
6. **Auditoría de Descargas (`[DOWNLOAD]`)**: Detecta rutas invocadas mediante `C.descargar()` / `window.location.href` y **falla con código `1`** si el servidor responde con `c.json()` en lugar de un cuerpo descargable (`c.body()`).
7. **Auditoría de Botones Huérfanos**: Detecta botones definidos con `sinPantalla: true` que carezcan de ventana registrada en `ConfigVentanas` y falla la auditoría.

---

## 📋 Protocolo de Ejecución en 5 Fases (Paso a Paso)

### Fase 1: Extracción de Superficie de Red, Compuertas de Permisos y Wrappers HTTP
Antes de escribir una sola línea del servidor:
1. **Identificar el Bootstrap / Hidratación Inicial**:
   - Buscar en `index.html` o archivos de arranque (`datos.js`, `shell.js`) bloques `<script type="application/json">` (`empresa_id = 23`, `sucursal_id`, `permisos`).
2. **Clasificar Wrappers HTTP por Tipo de Respuesta Esperada**:
   - **Wrappers JSON** (`P.api`, `C.get`, `C.post`, `C.postForm`): esperan `Content-Type: application/json` con `{ ok: true, ... }`.
   - **Wrappers de Descarga (`C.descargar`, `blob()`)**: **rechazan** `application/json` como error; exigen `Content-Type` de archivo (`text/csv`, `text/html`, `application/octet-stream`) y cabeceras `Content-Disposition`, `X-Catalogo-Archivo`, `X-Catalogo-Total`.
   - **Compuertas de Permiso Negativas (`/permiso/`)**: rutas que el frontend llama solo cuando `!estado.permisos[clave]` esperando un rechazo o que nunca deben alcanzarse si el rol Dueño/Admin tiene el mapa `permisos` completo en `true`.

### Fase 2: Extracción Determinista del Mapa de Contratos (v2.0)
1. Ejecutar `audit_api_contracts.py` v2.0 apuntando al directorio del frontend y al servidor.
2. Ninguna ruta crítica de estado (`/estado/`, `/factura/`, `/datos/`) puede quedar con `Props: (sin lectura directa)` si pasa su respuesta a una función auxiliar; verificar todas las propiedades de 1er y 2do nivel reportadas por el auditor.

### Fase 3: Diseño de Serializadores Canónicos y Almacenes de Persistencia
1. Definir funciones serializadoras canónicas en el servidor que incluyan **todos** los alias de 1er y 2do nivel (ej. `padre_id` **y** `parent_id` + `ruta` en categorías; `max_sucursales`, `sucursales_usadas` y `sucursales_disponibles` en `limite`).
2. Crear tablas reales en SQLite (o una tabla `configuracion_kv (clave TEXT PRIMARY KEY, valor_json TEXT)`) para toda funcionalidad de configuración, paquetes, bajas y preferencias. **Prohibido** dejar endpoints `GET` devolviendo arrays vacíos fijos (`[]`) cuando existe un `POST` de guardado asociado.

### Fase 4: Verificación de Interactividad UI (Cero Botones Muertos)
1. Inspeccionar todos los arreglos de botones/acciones de la interfaz (ej. `COLUMNAS` en `configuracion.js`).
2. Verificar que cada `id` de botón tenga una función asociada en el registro de ventanas (`P.ConfigVentanas[id]`) o un manejador de acción directa (`abrirPendiente`). Si un botón tiene `sinPantalla: true`, implementar su modal de configuración correspondiente antes de dar por terminado el módulo.

### Fase 5: Gate de Calidad Doble (Estático + Aserción de Payload en Vivo)
1. **Gate Estático**: `audit_api_contracts.py` debe reportar `100.0%` de cobertura de rutas y `0 violaciones estructurales` (0 permisos faltantes, 0 descargas con JSON, 0 botones huérfanos).
2. **Gate Dinámico de Payload (`test_pos_api.sh`)**: El script de pruebas no debe limitarse a verificar `HTTP 200`; debe inspeccionar el cuerpo JSON y las cabeceras HTTP para confirmar:
   - Presencia de claves en `permisos` (`config_empresa: true`, etc.) y sub-propiedades (`limite.sucursales_disponibles`).
   - `Content-Type` distinto de `application/json` en rutas `[DOWNLOAD]`.
   - Ciclo completo `POST` (guardar) $\rightarrow$ `GET` (consultar) verificando que el registro persiste en SQLite.
   - Si existe un Service Worker (`sw.js`) con estrategia *Cache-First* sobre `/static/`, actualizar la constante `VERSION` y cambiar a *Network-First* con fallback a caché para evitar que el navegador sirva scripts antiguos tras una corrección.
