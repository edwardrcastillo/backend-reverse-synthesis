---
name: backend-reverse-synthesis
description: Protocolo determinista (Cero Adivinación) para reconstruir backends completos, esquemas SQL y contratos API a partir de código cliente huérfano (SPA, PWA, Electron ASAR, APK, Sourcemaps) extraído con REA v7.0.0 o Replica. Úsese siempre que se deba recrear o auditar el servidor de una aplicación cuyo backend original no está disponible.
---

# 🏛️ Skill: Síntesis Determinista de Backends desde Código Cliente (`backend-reverse-synthesis` v3.0)

## 💡 Origen y Por Qué se Creó este Skill
Cuando se utiliza **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript`, `inspect_capture`, `rea strings`, `inspect_android`) o **Replica** (`replica-recon` / `replica coderecon`) para extraer el código de una aplicación cuyo servidor original no está disponible, se obtiene el 100% de la lógica del cliente.

Sin embargo, en la práctica se identificó un fallo sistémico recurrente: **al recrear el backend reinterpretando el código de forma heurística ("adivinando"), el agente sufre de ceguera estructural y desincronización de estado**. Asume nombres de propiedades JSON que parecen lógicos pero no coinciden con lo que el cliente desestructura, deja bloques `<script type="application/json">` estáticos de la captura original que pisan los cambios guardados al recargar (`#pos-sesion`), implementa *Echo Stubs* (`POST` que responde `{ ok: true }` sin persistir en SQLite y `GET` que devuelve `[]`), usa llaves primarias alfanuméricas (`prd_1`, `cat_1`, `suc_1`) cuando el frontend aplica `Number(dataset.id)` produciendo `NaN === NaN` (`false`), o deja despachadores polimórficos (`?tipo=...`) incompletos.

Este skill nació para **erradicar de raíz los errores de ceguera, adivinación y desincronización en la recreación de backends**, transformando la reconstrucción en un proceso **100% determinista y verificable mediante análisis estático inter-procedural de contratos** donde el código cliente extraído se trata como una especificación formal inmutable.

---

## ⚠️ Los 14 Anti-Patrones de Ceguera, Adivinación y Desincronización (Causas Raíz Prohibidas)

| # | Anti-Patrón | Síntoma en el Cliente | Regla Determinista de Prevención |
| :--- | :--- | :--- | :--- |
| **1** | **Ceguera de Rutas Dinámicas y Prefijos (`URL_BASE`)** | Rutas de modales secundarios o acciones por fila (`/:id/anular/`, `/eliminar/estado/`) devuelven `404 Not Found`. | Resolver todas las variables prefijo (`URL_BASE`, `apiBase`), ternarios (`sel ? "/a/" + id : "/b/"`) y concatenaciones antes de definir las rutas del router. |
| **2** | **Adivinación del Molde de Respuesta (`Response Shape Guessing`)** | El servidor devuelve `{ ok: true, data: [...] }`, pero el cliente lee `r.proveedores`, `r.siguiente_codigo`, `d.pedido.numero`, `r.puede_anular` o `r.total`. | Extraer estáticamente todas las lecturas `<param>.<prop>` y `<param>.<prop>.<subprop>` (ej. `limite.sucursales_disponibles`, `categorias[].parent_id`) dentro de cada callback. |
| **3** | **Descarte Silencioso en Filtros Relacionales (`Silent .filter() Drop`)** | Un `<select>` (ej. Sucursales) aparece vacío sin lanzar errores en consola porque `Number(s.empresa_id) === Number(empresaId)` evalúa `NaN === 23` (`false`). | Extraer todas las expresiones `.filter()` y `.find()` del cliente e inyectar obligatoriamente todas las llaves foráneas (`empresa_id`, `sucursal_id`, `parent_id`, `activa`, `de_recibir`) con el tipo primitivo exacto del bootstrap HTML. |
| **4** | **Colisión Primitivo vs. Objeto (`Flat Array vs. Entity Object`)** | Un combobox (ej. Roles) se despliega en blanco o con `undefined` porque el servidor envió `["Dueño", "Cajero"]` cuando el cliente itera `r.id`, `r.nombre`, `r.es_dueno_empresa`. | Inspeccionar el renderizador DOM (`.map()`, `dataset.*`, `<option>`) de cada catálogo para verificar si consume escalares u objetos ricos. |
| **5** | **Asimetría de Transporte y Polimorfismo en `/guardar/`** | Formularios con archivos (`FormData`) fallan al hacer `req.json()`, o el botón "Eliminar" no borra porque envía `{ id, eliminar: true }` al endpoint `/guardar/` en vez de llamar a `/eliminar/`. | Implementar un parser universal (`parseBody`: JSON + Multipart FormData + URLSearchParams) y verificar todas las ramas condicionales (`b.eliminar`, `b.activa`, `b.id`) en los endpoints de guardado. |
| **6** | **Crash por `INSERT` Ciego Sin `UPSERT`** | Al reintentar guardar un código, rol o usuario existente explota con `500 UNIQUE constraint failed`. | Implementar `UPSERT` (`ON CONFLICT DO UPDATE` o verificación previa de existencia) en toda ruta de creación/guardado. |
| **7** | **Bloqueo por Compuerta de Permisos Vacía (`Empty Permission Gate Stub: permisos: {}`)** | **Todos los botones de un módulo (ej. `#configuracion`) no hacen nada al hacer clic**, porque el frontend evalúa `if (!estado.permisos[item.clave]) return C.post("/api/configuracion/permiso/", ...)` y el backend devolvió `permisos: {}`. | Extraer todas las claves de permiso del frontend (`config_*`, `modulo_*`) y poblar el diccionario completo con `true` en el estado de sesión/configuración. Prohibido devolver `permisos: {}`. |
| **8** | **Ceguera por Indirección de Estado (`Indirect State Forwarding & Named Callbacks`)** | El auditor reporta `(sin lectura directa)` en endpoints críticos (`/general/estado/`, `/factura/`, `/eliminar/estado/`) porque el `.then(abrirEditor)` pasa una función nombrada o reenvía el objeto `estado` a submódulos en otros archivos (`V.empresa = function(estado)`). | Resolver inter-proceduralmente tanto las funciones nombradas pasadas a `.then(fnName)` como los consumidores del objeto de estado compartido (`C.estado()`, `V.<modal>(estado)`) en todos los archivos hijos. |
| **9** | **Inversión Semántica MIME en Descargas (`Download Blob vs. JSON Error Gate`)** | Los botones de "Generar catálogo" o "Descargar plantilla" fallan diciendo *"No se pudo generar el archivo"* aunque el servidor respondió `200 OK`, porque el helper `C.descargar()` interpreta `Content-Type: application/json` como un error de negocio. | Auditar todos los wrappers de descarga (`r.blob()`, `C.descargar`, `Content-Disposition`) y prohibir que sus rutas en el backend devuelvan `c.json()`. Deben retornar `c.body()` con MIME de archivo y cabeceras de metadatos. |
| **10** | **Botones Huérfanos (`Dead sinPantalla Buttons`)** | Botones con `sinPantalla: true` (`Moneda`, `Cliente por defecto`, `Etiqueta`, `Mi perfil`) muestran un mensaje informativo o abren un modal cuyos cambios no se envían a ningún endpoint. | Todo botón en arreglos de UI o menús del shell debe contar con su ventana interactiva y su ruta `POST` de persistencia conectada. |
| **11** | **Hidratación SSR Incompleta y Artefactos Estáticos de Captura (`Partial SSR Hydration`)** | Se modifica "Mi empresa" o "Sucursal", el cambio se guarda en SQLite, pero **el menú lateral izquierdo sigue diciendo `"SITIO DE PRUEBA"`** porque `GET /` solo reemplazó `<script id="pos-datos">` y dejó `<script id="pos-sesion">` y los `<span>` del HTML con los textos estáticos de la captura original. | `GET /` debe reemplazar dinámicamente **todos** los bloques `<script id="..." type="application/json">` (`#pos-datos`, `#pos-sesion`, `#pos-modulos`) y los nodos estáticos del shell (`#sidebar-empresa`, `#sidebar-sucursal`, `#sidebar-usuario`, `#sidebar-rol`), y los mutadores del cliente deben sincronizar `P.datos.*` y el DOM en vivo. |
| **12** | **Mutación Sin Persistencia ("Echo Stubs") y `GET` con Arreglos Vacíos Estáticos** | Guardar un rol, factura pendiente, recepción de producto, categoría de gasto o variante muestra *"Guardado exitosamente"*, pero al volver a abrir la ventana los cambios desaparecen porque el `POST` solo hacía `return c.json({ ok: true })` y el `GET` devolvía `[]` quemado. | **Prohibido** que un endpoint `POST` de negocio carezca de escritura en SQLite (`db.prepare`) o KV (`setKv`), y **prohibido** que un `GET` retorne colecciones vacías literales (`facturas: []`, `codigos: []`, `variantes: []`, `unidades: []`) sin consultar la base de datos. |
| **13** | **Coerción Numérica de IDs Alfanuméricos (`Number(id)` $\rightarrow$ `NaN === NaN`)** | Hacer clic en una tarjeta de producto en `#inventario`, abrir el árbol de categorías en `#configuracion`, agregar un producto en `#compras` o editar una sucursal/usuario en `#admin_usuario` **no hace absolutamente nada**, porque el backend genera IDs de texto (`prd_1`, `cat_1`, `suc_1`) y el frontend evalúa `Number(item.dataset.id)` o `Number(a.sucursal_id) === Number(s.id)`, lo que produce `NaN === NaN` (`false`). | Si el backend utiliza llaves primarias alfanuméricas, auditar todas las expresiones `Number(*.dataset.id)`, `Number(*.dataset.add)` y `Number(*.id)` del frontend y normalizarlas a comparaciones `String(a) === String(b)`. |
| **14** | **Despachadores Polimórficos Incompletos (`Incomplete ?tipo= Dispatchers`)** | En el módulo `#reporte`, 4 tarjetas muestran datos pero las otras 14 tarjetas abren tablas vacías (`No hay registros`) porque `GET /api/reportes/?tipo=...` solo implementó un subconjunto de casos y dejó un fallback `filas: []`. | Extraer estáticamente el catálogo completo de subtipos del cliente (`REPORTES` / `CFG` en `reporte.js`) y exigir que cada valor de `tipo` tenga su rama de consulta e hidratación con los nombres de columna exactos de `normalize(id, raw)`. |

---

## 🛠️ Herramienta Integrada de Auditoría Determinista v3.0

Este skill incluye el analizador estático inter-procedural ejecutable:
```bash
python3 /Users/edward/.gemini/config/skills/backend-reverse-synthesis/scripts/audit_api_contracts.py \
  --frontend <ruta_codigo_cliente_extraido> \
  --server <ruta_archivo_o_directorio_servidor>
```

### ¿Qué verifica `audit_api_contracts.py` v3.0?
1. Escanea recursivamente todos los archivos `.js/.ts/.jsx/.tsx/.vue/.svelte` y `.html` del cliente extraído.
2. Resuelve constantes `URL_BASE`, llamadas relativas y concatenaciones dinámicas.
3. **Resolución Inter-procedural**:
   - Si un endpoint usa `.then(nombreFuncion)`, localiza `function nombreFuncion(param)` en el archivo y extrae todas las propiedades leídas sobre `param`.
   - Si un endpoint alimenta un estado compartido (`C.estado()`), rastrea todos los submódulos (`V.<id> = function(estado)`) en archivos hermanos y vincula todas las propiedades leídas al endpoint origen.
4. **Extracción de 2º Nivel e Iteradores**: Extrae tanto `param.prop.subprop` (`limite.sucursales_disponibles`) como propiedades de elementos dentro de `.map()` / `.filter()` (`categorias[].parent_id`, `tablas[].descripcion`).
5. **Auditoría de Compuertas de Permisos (Anti-Patrón #7)**: Extrae todas las claves `config_*` del frontend y **falla con código `1`** si alguna clave falta en el código del servidor.
6. **Auditoría de Descargas `[DOWNLOAD]` (Anti-Patrón #9)**: Detecta rutas invocadas mediante `C.descargar()` / `window.location.href` y **falla con código `1`** si el servidor responde con `c.json()` en lugar de `c.body()`.
7. **Auditoría de Botones Huérfanos (Anti-Patrón #10)**: Detecta botones definidos con `sinPantalla: true` que carezcan de ventana registrada en `ConfigVentanas`.
8. **[NUEVO v3.0] Auditoría de Hidratación SSR Completa (Anti-Patrón #11)**: Extrae todos los `<script id="..." type="application/json">` de los archivos `.html` y **falla con código `1`** si alguno no es reemplazado dinámicamente en el servidor (`GET /`).
9. **[NUEVO v3.0] Detección de Echo Stubs Sin Persistencia (Anti-Patrón #12)**: Analiza el cuerpo de cada `app.post(...)` y `app.get(...)` en el servidor y **falla con código `1`** si algún `POST` no persiste en SQLite (`db.prepare`) o KV (`setKv`), o si algún `GET` devuelve arreglos vacíos quemados (`variantes: []`, `codigos: []`, `facturas: []`, `unidades: []`).
10. **[NUEVO v3.0] Detección de Coerción Numérica sobre IDs Alfanuméricos (Anti-Patrón #13)**: Si el servidor emplea IDs con prefijos de texto (`prd_`, `cat_`, `suc_`, `usr_`), escanea todo el frontend buscando `Number(*.dataset.id)`, `Number(*.dataset.add)` o `Number(*.sucursal_id) === Number(*.id)` y **falla con código `1`** indicando archivo y línea exacta.
11. **[NUEVO v3.0] Auditoría de Despachadores Polimórficos `?tipo=...` (Anti-Patrón #14)**: Extrae los 18 subtipos de `REPORTES` en `reporte.js` y **falla con código `1`** si alguno no está implementado explícitamente en `GET /api/reportes/`.

---

## 📋 Protocolo de Ejecución en 6 Fases (Paso a Paso)

### Fase 1: Auditoría de Hidratación SSR y Artefactos de Captura (`index.html`)
1. Enumerar **todos** los bloques `<script id="..." type="application/json">` en `index.html` (`#pos-datos`, `#pos-sesion`, `#pos-modulos`) y todos los nodos DOM con datos de sesión quemados en la captura (`#sidebar-empresa`, `#sidebar-sucursal`, `#sidebar-usuario`, `#sidebar-rol`).
2. Asegurar que `GET /` reemplace **todos** los bloques JSON y nodos del shell desde SQLite, y que `obtenerPosDatos()` no contenga colecciones estáticas quemadas (categorías, usuarios, sucursales, gastos, recepciones, promociones).

### Fase 2: Normalización de Tipos de Llaves Primarias (`String(id)` vs `Number(id)`)
1. Verificar si las tablas SQLite usan IDs enteros o alfanuméricos (`prd_...`, `cat_...`, `suc_...`).
2. Si existen IDs alfanuméricos, barrer todas las vistas del cliente para reemplazar `Number(el.dataset.id)` y `Number(x.id) === Number(y.id)` por `String(...) === String(...)`.

### Fase 3: Extracción Determinista del Mapa de Contratos y Despachadores Polimórficos (v3.0)
1. Ejecutar `audit_api_contracts.py` v3.0 apuntando al directorio del frontend y al servidor.
2. Verificar tanto las propiedades directas/indirectas de cada ruta como todos los subtipos de endpoints polimórficos (`?tipo=...`) y sus normalizadores en el cliente (`normalize(id, raw)`).

### Fase 4: Eliminación Total de Echo Stubs y Sincronización Cruzada entre Módulos
1. Todo endpoint `POST` debe persistir en tablas SQLite o en `configuracion_kv`, y su correspondiente `GET` debe leer de la misma fuente.
2. Cuando un módulo modifica configuración compartida (ej. `Editar factura` guarda `factura_config`, `Categorías` modifica `categorias`, `Mi empresa` modifica `empresa`), el endpoint consumidor en otros módulos (`GET /api/configuracion/factura/venta/:id/` en `#caja`, `P.datos.categorias` en `#inventario`, `P.datos.sesion` en el shell) debe recibir los datos actualizados en vivo.

### Fase 5: Verificación de Interactividad UI (Cero Botones Muertos)
1. Inspeccionar todos los arreglos de botones/acciones de la interfaz (`COLUMNAS` en `configuracion.js`, menú de usuario `#accion-perfil` en `shell.js`) y asegurar que cada acción abra su modal y persista sus cambios en el servidor.

### Fase 6: Gate de Calidad Doble (Estático v3.0 + Aserción de Roundtrip en Vivo)
1. **Gate Estático**: `audit_api_contracts.py` v3.0 debe reportar `100.0%` de cobertura de rutas y `0 violaciones estructurales`.
2. **Gate Dinámico (`test_pos_api.sh`)**: Debe probar ciclos completos `POST` (guardar) $\rightarrow$ `GET` (verificar persistencia real), hidratación SSR completa (`#pos-datos`, `#pos-sesion`, `#pos-modulos`, `#sidebar-*`), descargas binarias no-JSON y los 18 subtipos de reportes.
3. Incrementar siempre `VERSION` en `sw.js` y los query strings `?v=...` en `index.html` al desplegar.
