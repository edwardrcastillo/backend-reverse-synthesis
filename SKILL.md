---
name: backend-reverse-synthesis
description: Protocolo determinista universal (Cero Adivinación, Multi-Stack, Sincronización de Estado y Paridad DDL) para reconstruir backends completos, esquemas SQL y contratos API a partir de código cliente huérfano (SPA, PWA, React/Vue/Next, Electron ASAR, APK/Capacitor, Sourcemaps) extraído con REA v7.0.0 o Replica. Úsese siempre que se deba recrear o auditar el servidor de una aplicación cuyo backend original no está disponible.
---

# 🏛️ Skill: Síntesis Determinista Universal de Backends desde Código Cliente (`backend-reverse-synthesis` v4.0)

## 💡 Origen, Evolución y Alcance Universal (Multi-Stack)
Cuando se utiliza **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript`, `inspect_capture`, `rea strings`, `inspect_android`) o **Replica** (`replica-recon` / `replica coderecon`) para extraer el código de una aplicación cuyo servidor original no está disponible, se obtiene el 100% de la lógica del cliente.

Sin embargo, la experiencia empírica demostró que recrear un backend "adivinando" o validando únicamente con pruebas superficiales (`HTTP 200 OK`) fracasa por **4 generaciones de fallos sistémicos**:
1. **Generación 1 (Ceguera de Contratos)**: Rutas compuestas omitidas (`URL_BASE`), moldes JSON inventados, filtros `.filter()` que descartan registros por falta de llaves foráneas y colisión primitivo vs. objeto.
2. **Generación 2 (Ceguera Inter-Procedural y MIME)**: Compuertas de permisos vacías (`permisos: {}`) que bloquean módulos enteros, callbacks nombrados (`.then(abrirEditor)`) no rastreados y wrappers de descarga (`.blob()`, `C.descargar`) que rechazan respuestas `application/json`.
3. **Generación 3 (Desincronización de Estado y Coerción de Tipos)**: Bloques SSR secundarios (`#pos-sesion`, `__NEXT_DATA__`) estáticos que pisan los datos guardados al recargar, *Echo Stubs* (`POST` que responde `ok: true` sin guardar en BD y `GET` con `[]` quemado), llaves primarias de texto (`prd_1`) que producen `NaN === NaN` (`false`) cuando el cliente aplica `Number(id)`, y despachadores polimórficos (`?tipo=...`) incompletos.
4. **Generación 4 (Asimetría Multi-Stack, Esquema SQL vs. Queries, Archivos Multipart y Efectos Cruzados)**: Consultas SQL que referencian tablas o columnas inexistentes en los `CREATE TABLE` (`ordenes_compra`, `unidad`, `contacto_vendedor`), endpoints `FormData` leídos con `req.json()` que pierden logos/imágenes subidas, rutas duplicadas en el router, asimetría de contratos de error (`200 { ok: false }` vs `4xx/5xx`), desfase de zona horaria (`toISOString()` UTC vs. fecha local), bucles de `401/CSRF` y efectos secundarios no transaccionales entre módulos.

---

## 🧭 Principios de Buenas Prácticas Universales en Reimplementación de Backends

### 1. Principio de Inmutabilidad del Cliente (`Client-First Adaptation`)
- **Regla de Oro**: En clientes compilados, firmados o distribuidos (APKs, binarios Electron/iOS, bundles minificados con SRI), **el código del cliente es inmutable**.
- Si el cliente aplica `Number(item.dataset.id)`, `parseInt(id, 10)` o aritmética sobre IDs, **el backend reconstruido DEBE definir sus llaves primarias como `INTEGER PRIMARY KEY AUTOINCREMENT`** (o proyectar IDs numéricos en sus serializadores) en lugar de inventar IDs con prefijos de texto (`usr_1`, `prd_1`). Solo se permite normalizar comparaciones `String(a) === String(b)` en el cliente cuando el código fuente del cliente es editable y ya existe una base de datos productiva con UUIDs/prefijos.

### 2. Paridad Estricta DDL $\leftrightarrow$ DML (`Zero Implicit Schema`)
- Ninguna consulta `SELECT`, `INSERT` o `UPDATE` en el servidor puede referenciar una tabla o columna que no esté explícitamente declarada en el bloque `CREATE TABLE IF NOT EXISTS` o en migraciones idempotentes `ALTER TABLE ... ADD COLUMN` al arranque del servidor.

### 3. Transaccionalidad de Efectos Secundarios Cruzados (`Cross-Module ACID`)
- Toda operación que afecte más de una entidad de negocio debe ejecutarse dentro de una transacción atómica (`BEGIN IMMEDIATE ... COMMIT` en SQLite, o `db.$transaction` / `with session.begin()`):
  - **Venta / Cobro**: Insertar factura + insertar renglones + descontar `stock` de productos/variantes + acumular en sesión/turno de caja + registrar en bitácora de actividad.
  - **Anulación / Devolución**: Marcar venta o renglón como anulado + **restaurar `stock`** + descontar del corte de caja.
  - **Recepción / Orden de Compra**: Insertar orden + incrementar `stock` + actualizar `precio_compra` y `precio_venta`.
  - **Baja / Merma**: Descontar `stock` validando disponibilidad previa + insertar registro en historial de bajas.

---

## ⚠️ Los 18 Anti-Patrones Universales Prohibidos (Matriz de Prevención)

| # | Anti-Patrón | Síntoma en el Cliente | Regla Determinista de Prevención |
| :--- | :--- | :--- | :--- |
| **1** | **Ceguera de Rutas Dinámicas (`URL_BASE` / Ternarios)** | Acciones por fila o sub-modales devuelven `404 Not Found`. | Resolver constantes prefijo (`URL_BASE`, `apiBase`, `baseURL`), ternarios y concatenaciones antes de definir el router. |
| **2** | **Adivinación del Molde JSON (`Response Shape Guessing`)** | La vista queda en blanco porque el servidor devuelve `{ data }` y el cliente lee `r.proveedores` o `r.siguiente_codigo`. | Extraer estáticamente todas las lecturas `<param>.<prop>` y `<param>.<prop>.<subprop>` de los callbacks. |
| **3** | **Descarte Silencioso en `.filter()` (`Silent Filter Drop`)** | Selectores `<select>` o tablas aparecen vacíos sin error en consola porque falta una llave foránea (`empresa_id`, `activa`). | Extraer todos los `.filter()` y `.find()` del cliente e inyectar todas las llaves foráneas con el tipo primitivo exacto del bootstrap. |
| **4** | **Colisión Primitivo vs. Objeto (`Scalar vs. Object`)** | Comboboxes muestran `undefined` porque el servidor envió `["Dueño"]` en vez de `[{ id, nombre, es_dueno_empresa }]`. | Inspeccionar `.map()`, `dataset.*` y `<option>` en el cliente para verificar si espera escalares u objetos ricos. |
| **5** | **Polimorfismo de Mutación en `/guardar/`** | El botón "Eliminar" o "Activar/Desactivar" no funciona porque envía `{ id, eliminar: true }` o `{ id, activa: false }` al endpoint de guardado. | Soportar todas las ramas condicionales (`eliminar`, `anular`, `activa`, `activo`, `estado`) dentro de los endpoints de mutación. |
| **6** | **Crash por `INSERT` Ciego Sin `UPSERT`** | Guardar un registro con código o llave natural existente lanza `500 UNIQUE constraint failed`. | Usar `ON CONFLICT DO UPDATE` o verificar existencia previa antes de insertar. |
| **7** | **Compuerta de Permisos / Feature Flags Vacía (`permisos: {}`)** | **Todos los botones de un módulo no hacen nada**, porque `!estado.permisos[clave]` desvía el flujo. | Extraer todas las claves (`config_*`, `perm_*`, `can_*`, `permissions`, `abilities`) y poblarlas en `true` para el rol administrador. |
| **8** | **Ceguera Inter-Procedural (`.then(fnNombrada)` y Estado Compartido)** | El auditor reporta `(sin lectura directa)` porque el callback es una función nombrada o pasa el estado a otros archivos. | Resolver cuerpos de funciones nombradas y rastrear consumidores del estado compartido (`C.estado()`, stores de Redux/Zustand/Pinia). |
| **9** | **Inversión Semántica MIME en Descargas (`.blob()`, `C.descargar`)** | Descargar PDF/CSV/XLSX/Backup lanza error aunque responda `200 OK`, porque el cliente rechaza `application/json`. | Rutas de descarga deben responder con `c.body()` / `StreamingResponse` (`text/csv`, `application/pdf`, `application/octet-stream`) y `Content-Disposition`. |
| **10** | **Botones o Acciones Huérfanas (`Dead UI Actions`)** | Botones de configuración o perfil (`Mi perfil`, `Moneda`) no abren modal o no llaman a ningún endpoint al guardar. | Verificar que cada acción de UI esté conectada a su modal y a un endpoint `POST` real. |
| **11** | **Hidratación SSR Incompleta (`Partial SSR Hydration`)** | Se guarda un cambio en BD, pero al recargar o mirar el header/sidebar sigue apareciendo `"SITIO DE PRUEBA"`. | Inyectar dinámicamente **todos** los bloques `<script type="application/json">` (`#pos-datos`, `#pos-sesion`, `#pos-modulos`, `__NEXT_DATA__`) y nodos del shell en `GET /`. |
| **12** | **Echo Stubs Sin Persistencia (`Stateless POST & Empty GET`)** | Guardar dice *"Éxito"*, pero al reabrir la ventana la lista vuelve a estar vacía (`[]`). | Prohibido que un `POST` carezca de escritura en BD/KV o que un `GET` retorne colecciones vacías literales (`facturas: []`, `codigos: []`, `variantes: []`). |
| **13** | **Coerción Numérica de IDs Alfanuméricos (`Number(id)` $\rightarrow$ `NaN === NaN`)** | Clics en tarjetas de productos, categorías o usuarios no hacen nada porque `Number("prd_1") === Number("prd_1")` es `false`. | Usar PKs enteras en el backend si el cliente aplica `Number(id)` (preferido), o normalizar comparaciones a `String(a) === String(b)`. |
| **14** | **Despachadores Polimórficos Incompletos (`?tipo=...`, `?action=...`)** | 4 reportes muestran datos y 14 salen en blanco porque el servidor tiene un fallback genérico `filas: []`. | Extraer todos los valores del catálogo polimórfico del cliente e implementar cada rama con las propiedades exactas de su normalizador. |
| **15** | **Desfase Esquema SQL vs. Consultas (`Schema-to-Query Drift`)** | Endpoints que pasan pruebas básicas explotan en producción con `SQLiteError: no such table` o `no such column`. | Auditar estáticamente que toda tabla y columna usada en `SELECT`/`INSERT`/`UPDATE` exista en `CREATE TABLE` o `ALTER TABLE`. |
| **16** | **Sombreado de Rutas Duplicadas (`Duplicate Route Shadowing`)** | Un endpoint devuelve datos viejos o incompletos porque una definición temprana de la misma ruta en el archivo sombrea la nueva. | Auditar que cada par `(MÉTODO, ruta_normalizada)` se registre una única vez en el servidor. |
| **17** | **Asimetría Multipart/FormData y Pérdida de Archivos (`File/Media Drop`)** | Subir un logo, avatar, imagen de producto o CSV falla o se ignora porque el servidor usa `req.json()` o descarta el `File`/DataURL. | Usar un parser universal (`parseBody`: JSON + Multipart + URLSearchParams), convertir o servir archivos subidos (`data:` URL o `/uploads/`) y persistirlos en BD. |
| **18** | **Asimetría de Errores, Paginación, Auth/CSRF y Zona Horaria (`Protocol & Temporal Drift`)** | Errores 400 rompen clientes que esperan `200 { ok: false }` (o viceversa); tablas paginadas dicen `NaN`; o ventas nocturnas pasan al día siguiente por usar UTC (`toISOString()`). | Alinear el formato de error al wrapper HTTP del cliente, proveer metadatos de paginación (`count`, `results`, `total`), configurar cookies/CORS/CSRF y usar hora local del negocio en cortes diarios. |

---

## 🛠️ Herramienta Integrada de Auditoría Determinista Universal v4.0

Ejecuta el analizador estático multi-stack antes de dar por completado cualquier backend:
```bash
python3 /Users/edward/.gemini/config/skills/backend-reverse-synthesis/scripts/audit_api_contracts.py \
  --frontend <ruta_codigo_cliente_extraido> \
  --server <ruta_archivo_o_directorio_servidor>
```

### ¿Qué verifica automáticamente `audit_api_contracts.py` v4.0?
1. **Cobertura de Rutas y Métodos (Multi-Stack)**: Soporta `fetch`, `axios`, `C.get/post/postForm/descargar`, `P.api`, `URL_BASE` en el cliente, y Hono/Express/Fastify/FastAPI/Flask en el servidor.
2. **Propiedades de 1er/2do Nivel, Iteradores e Indirección Inter-Procedural**: Rastrea `.then(fnNombrada)` y estado compartido entre múltiples archivos (`C.estado()`, `V.<modal>`).
3. **Compuertas de Permisos (`config_*`, `perm_*`, `can_*`)**: Falla si alguna clave de permiso del cliente no está declarada en el servidor.
4. **Rutas `[DOWNLOAD]` y `[MULTIPART]`**:
   - Falla si una ruta `[DOWNLOAD]` devuelve solo `c.json()` sin `c.body()`.
   - Falla si una ruta `[MULTIPART]` (que recibe `FormData` con archivos/campos) usa `req.json()` puro en lugar de `parseBody()`.
5. **Hidratación SSR Completa**: Verifica que todos los bloques `<script id="..." type="application/json">` del HTML sean inyectados dinámicamente.
6. **Cero Echo Stubs**: Falla si un endpoint `POST` no invoca primitivas de persistencia (`db.prepare`, `setKv`, `prisma.`, `knex`, `pool.query`, `cursor.execute`, `session.add`, `.save()`) o si un `GET` devuelve arreglos vacíos quemados.
7. **Detección de `NaN === NaN` en IDs**: Falla si el servidor usa PKs alfanuméricas y el cliente aplica `Number(dataset.id)` o `Number(x.id) === Number(y.id)`.
8. **Paridad DDL $\leftrightarrow$ SQL (Regla #15)**: Extrae todas las tablas y columnas de `CREATE TABLE` y `ALTER TABLE` y **falla con código `1`** si alguna consulta SQL referencia una tabla o columna inexistente.
9. **Detección de Rutas Duplicadas (Regla #16)**: Falla si una misma ruta y método HTTP está registrada más de una vez en el servidor.
10. **Cobertura Polimórfica `?tipo=...` (Regla #14)**: Verifica que todos los subtipos de reportes/catálogos estén implementados.

---

## 📋 Protocolo Operativo en 7 Fases para Cualquier Reconstrucción de Backend

1. **Fase 1 — Reconocimiento de Transporte, Errores, Auth y Bootstrap SSR**:
   - Inspeccionar el wrapper HTTP central del cliente (`fetch`/`axios` interceptor) para determinar:
     - Prefijo de rutas (`/api/`, `/v1/`), cabeceras de autenticación (`Cookie`, `Authorization: Bearer`, `X-CSRFToken`) y manejo de errores (`HTTP 200 { ok: false, error }` vs `HTTP 4xx { detail, message }`).
     - Bloques de hidratación inicial en HTML (`<script type="application/json">`, `window.__INITIAL_STATE__`) y estrategia de caché en Service Worker (`sw.js`).
2. **Fase 2 — Diseño del Esquema DDL Canónico y Estrategia de Primary Keys**:
   - Si el cliente usa `Number(id)` o `parseInt(id)`, diseñar tablas con `INTEGER PRIMARY KEY AUTOINCREMENT`. Si usa UUIDs o strings, asegurar comparaciones `String(a) === String(b)`.
   - Declarar todas las tablas y columnas requeridas en `CREATE TABLE IF NOT EXISTS` + migraciones aditivas `ALTER TABLE ... ADD COLUMN`.
3. **Fase 3 — Ejecución del Auditor Estático `audit_api_contracts.py` v4.0**:
   - Extraer el mapa completo de rutas, propiedades de 1er/2do nivel, rutas `[DOWNLOAD]`, rutas `[MULTIPART]`, permisos y despachadores `?tipo=`.
4. **Fase 4 — Implementación de Serializadores, Archivos Multipart y Transacciones Cruzadas**:
   - Implementar un parser universal `parseBody(c)` (JSON + Multipart FormData + URLSearchParams) y soporte de archivos/imágenes (`fileToDataUrl` o directorio estático `/uploads/`).
   - Envolver operaciones compuestas (Ventas + Stock + Turno; Compras + Stock; Anulaciones + Devolución de Stock) en transacciones atómicas.
5. **Fase 5 — Sincronización de Estado Reactivo (BD $\leftrightarrow$ SSR $\leftrightarrow$ Memoria SPA $\leftrightarrow$ DOM)**:
   - Asegurar que toda mutación en configuración, perfil, sucursales, categorías o catálogos actualice tanto la BD como el objeto global en memoria del cliente y los nodos visibles del shell.
6. **Fase 6 — Gate Estático v4.0 (`0 violaciones estructurales`)**:
   - Ejecutar `audit_api_contracts.py` v4.0 hasta obtener `100.0%` de cobertura de rutas y `0 violaciones estructurales` (DDL SQL, Multipart, SSR, Persistencia, IDs, Permisos y Reportes).
7. **Fase 7 — Gate Dinámico E2E de Roundtrip (`POST -> GET`) y Cache Busting**:
   - Ejecutar pruebas automatizadas contra el servidor en vivo verificando que cada `POST` persista datos reales observables en el siguiente `GET`, que las descargas devuelvan MIME binario/CSV y que la versión del Service Worker (`sw.js`) haya sido incrementada.
