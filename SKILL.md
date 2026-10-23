---
name: backend-reverse-synthesis
description: Protocolo determinista (Cero Adivinación) para reconstruir backends completos, esquemas SQL y contratos API a partir de código cliente huérfano (SPA, PWA, Electron ASAR, APK, Sourcemaps) extraído con REA v7.0.0 o Replica. Úsese siempre que se deba recrear o auditar el servidor de una aplicación cuyo backend original no está disponible.
---

# 🏛️ Skill: Síntesis Determinista de Backends desde Código Cliente (`backend-reverse-synthesis`)

## 💡 Origen y Por Qué se Creó este Skill
Cuando se utiliza **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript`, `inspect_capture`, `rea strings`, `inspect_android`) o **Replica** (`replica-recon` / `replica coderecon`) para extraer el código de una aplicación cuyo servidor original no está disponible, se obtiene el 100% de la lógica del cliente.

Sin embargo, en la práctica se identificó un fallo sistémico recurrente: **al recrear el backend reinterpretando el código de forma heurística ("adivinando"), el agente sufre de ceguera estructural**. Asume nombres de propiedades JSON que parecen lógicos pero no coinciden con lo que el cliente desestructura, omite llaves foráneas que dejan `<select>` vacíos silenciosamente, ignora rutas construidas por concatenación y devuelve arrays planos donde la interfaz exige objetos ricos.

Este skill nació para **erradicar de raíz los errores de ceguera y adivinación en la recreación de backends**, transformando la reconstrucción en un proceso **100% determinista y verificable mediante análisis estático de contratos** donde el código cliente extraído se trata como una especificación formal inmutable.

---

## ⚠️ Los 6 Anti-Patrones de Ceguera y Adivinación (Causas Raíz Prohibidas)

| # | Anti-Patrón | Síntoma en el Cliente | Regla Determinista de Prevención |
| :--- | :--- | :--- | :--- |
| **1** | **Ceguera de Rutas Dinámicas y Prefijos (`URL_BASE`)** | Rutas de modales secundarios o acciones por fila (`/:id/anular/`, `/eliminar/estado/`) devuelven `404 Not Found`. | Resolver todas las variables prefijo (`URL_BASE`, `apiBase`), ternarios (`sel ? "/a/" + id : "/b/"`) y concatenaciones antes de definir las rutas del router. |
| **2** | **Adivinación del Molde de Respuesta (`Response Shape Guessing`)** | El servidor devuelve `{ ok: true, data: [...] }`, pero el cliente lee `r.proveedores`, `r.siguiente_codigo`, `d.pedido.numero`, `r.puede_anular` o `r.total`. | Extraer estáticamente todas las lecturas `<param>.<prop>` dentro de los callbacks `.then(function(r){...})` o asignaciones `await` para cada endpoint. |
| **3** | **Descarte Silencioso en Filtros Relacionales (`Silent .filter() Drop`)** | Un `<select>` (ej. Sucursales) aparece vacío sin lanzar errores en consola porque `Number(s.empresa_id) === Number(empresaId)` evalúa `NaN === 23` (`false`). | Extraer todas las expresiones `.filter()` y `.find()` del cliente e inyectar obligatoriamente todas las llaves foráneas (`empresa_id`, `sucursal_id`, `activa`, `de_recibir`) con el tipo primitivo exacto del bootstrap HTML. |
| **4** | **Colisión Primitivo vs. Objeto (`Flat Array vs. Entity Object`)** | Un combobox (ej. Roles) se despliega en blanco o con `undefined` porque el servidor envió `["Dueño", "Cajero"]` cuando el cliente itera `r.id`, `r.nombre`, `r.es_dueno_empresa`. | Inspeccionar el renderizador DOM (`.map()`, `dataset.*`, `<option>`) de cada catálogo para verificar si consume escalares u objetos ricos. |
| **5** | **Asimetría de Transporte y Polimorfismo en `/guardar/`** | Formularios con archivos (`FormData`) fallan al hacer `req.json()`, o el botón "Eliminar" no borra porque envía `{ id, eliminar: true }` al endpoint `/guardar/` en vez de llamar a `/eliminar/`. | Implementar un parser universal (`parseBody`: JSON + Multipart FormData + URLSearchParams) y verificar todas las ramas condicionales (`b.eliminar`, `b.activa`, `b.id`) en los endpoints de guardado. |
| **6** | **Desincronización de Hidratación SSR y Crash por `INSERT` Ciego** | Al recargar (`F5`), los datos desaparecen o cambian de formato; o al reintentar guardar un código/usuario existente explota con `500 UNIQUE constraint failed`. | Reemplazar el JSON quemado en el HTML (`<script id="...-data">`) con los mismos serializadores vivos de la BD, e implementar `UPSERT` en toda ruta de creación. |

---

## 🛠️ Herramienta Integrada de Auditoría Determinista

Este skill incluye el analizador estático ejecutable:
```bash
python3 /Users/edward/.gemini/config/skills/backend-reverse-synthesis/scripts/audit_api_contracts.py \
  --frontend <ruta_codigo_cliente_extraido> \
  --server <ruta_archivo_o_directorio_servidor>
```

### ¿Qué hace `audit_api_contracts.py`?
1. Escanea recursivamente todos los archivos `.js/.ts/.jsx/.tsx/.vue/.svelte` del cliente extraído con REA o Replica.
2. Resuelve constantes `URL_BASE` y llamadas relativas (`get("estado/")`, `post("formatear/")`).
3. Normaliza concatenaciones dinámicas (`"/api/ventas/" + v.id + "/productos/" + p.id + "/anular/"` $\rightarrow$ `/api/ventas/:id/productos/:id/anular/`).
4. Analiza el cuerpo de cada `.then(function(r) { ... })` para listar las propiedades exactas (`Props`) que el cliente exige en el JSON de respuesta.
5. Extrae todos los predicados `.filter(function(x) { ... })` para revelar las llaves foráneas e invariantes booleanos que las entidades deben poseer.
6. Compara el inventario completo contra las rutas registradas en el servidor y falla con código `!= 0` si falta **cualquier** endpoint.

---

## 📋 Protocolo de Ejecución en 5 Fases (Paso a Paso)

### Fase 1: Extracción de Superficie de Red y Estado Inicial (REA / Replica)
Antes de escribir una sola línea del servidor:
1. **Extraer el Código Cliente**:
   - Usar **REA v7.0.0** (`rea sourcemap`, `rea strings`, `analyze_javascript` sobre paquetes Electron `.asar`, `inspect_android` sobre APKs) o **Replica** (`replica coderecon`).
2. **Identificar el Bootstrap / Hidratación Inicial**:
   - Buscar en `index.html` o archivos de arranque (`datos.js`, `shell.js`, `app.js`) bloques `<script type="application/json">` o asignaciones a `window.*` (ej. `empresa: { id: 23 }`, `sucursal_actual`, `permisos`).
   - Documentar los IDs semilla (`empresa_id = 23`, `sucursal_id = 1`, etc.). Toda entidad creada o devuelta por el backend **debe** pertenecer a estos IDs de tenant/sucursal para no ser descartada por los filtros del cliente.
3. **Identificar todos los Clientes HTTP / Wrappers**:
   - Localizar funciones envolventes (`fetch`, `axios`, `P.api`, `C.get`, `C.post`, `C.postForm`, `C.descargar`, `enviarFormulario`, `window.location.href`).

### Fase 2: Extracción Determinista del Mapa de Contratos
1. Ejecutar `audit_api_contracts.py` apuntando al directorio del frontend (y a un archivo de servidor vacío o preliminar).
2. Para cada ruta detectada, clasificar:
   - **Método(s) HTTP**: Si un mismo endpoint se usa para consultar y crear (ej. `GET /api/caja/turno/` y `POST /api/caja/turno/`, o `GET/POST /api/gastos/categorias/`), registrar ambos métodos o usar `app.all()` con bifurcación por `c.req.method`.
   - **Propiedades de Salida (`Props`)**: Toda clave listada en la columna `Props` del auditor es **obligatoria** en el `return c.json({ ok: true, ... })`.
   - **Acciones Polimórficas**: Verificar si los endpoints `*/guardar/` reciben `{ eliminar: true }`, `{ activa: false }` o `{ id: ... }` para ejecutar `DELETE` o `UPDATE` en lugar de `INSERT`.

### Fase 3: Diseño de Serializadores Canónicos por Entidad
Nunca construir objetos JSON ad-hoc distintos en cada ruta. Definir en la parte superior del servidor **funciones serializadoras canónicas** que incluyan todos los alias e invariantes relacionales que distintos módulos del frontend puedan leer:
- Ejemplo para **Sucursal**: `{ id, empresa_id: 23, codigo, nombre, direccion, telefono, jefe, activa: Boolean, estado: 'Activa', usuarios: Number, ventas_hoy: Number }`.
- Ejemplo para **Producto**: `{ id, empresa_id: 23, sucursal_id, sucursal, codigo, nombre, categoria, proveedor_id, proveedor, precio: Number, precio_venta: Number, precio_compra: Number, stock: Number, stock_minimo: Number, unidad, es_multiple: Boolean, de_recibir: Boolean, activo: Boolean, estado: 'Activo' }`.
- Ejemplo para **Rol**: `{ id, nombre, nivel, es_dueno_empresa: Boolean, es_jefe_sucursal: Boolean, usuarios: Number, cantidad_permisos: Number, permisos: Object }`.
- Usar estos mismos serializadores tanto en la hidratación de `GET /` (`index.html`) como en los endpoints `GET` y `POST` de la API.

### Fase 4: Parser Universal de Entrada e Idempotencia (`UPSERT`)
1. **Parser Híbrido (`parseBody`)**:
   Todo endpoint `POST` debe leer el cuerpo mediante un helper que detecte `content-type`:
   - Si es `multipart/form-data` o `application/x-www-form-urlencoded`, extraer los campos con `await c.req.parseBody()`.
   - Si es `application/json`, extraer con `await c.req.json()`.
2. **Escritura Idempotente (`UPSERT`)**:
   - Antes de ejecutar `INSERT INTO` en tablas con restricciones `UNIQUE` (`codigo`, `username`, `documento`, `rnc`), verificar si ya existe un registro con esa llave natural o clave primaria (`id`).
   - Si existe, ejecutar `UPDATE` y devolver el registro actualizado con `200 OK`, evitando errores `500 SQLiteError: UNIQUE constraint failed`.
3. **Generadores de Consecutivos (`siguiente_codigo` / `numero`)**:
   - Cuando el cliente espera autocompletar el siguiente folio (`siguiente_codigo` en clientes/proveedores, `numero` en compras/facturas), calcularlo dinámicamente desde el conteo o máximo actual de la tabla (`CLI-0001`, `PRV-0001`, `PED-0001`, `FAC-000001`) y devolverlo tanto en el `GET` de listado como en el `POST` de guardado.

### Fase 5: Gate de Calidad y Verificación 100%
1. Ejecutar nuevamente `audit_api_contracts.py` y confirmar:
   - `📊 Cobertura de Rutas: N/N (100.0%)`
   - `0 [MISSING]`
2. Ejecutar una suite de pruebas de integración (`curl` / script bash) que autentique una sesión real y verifique respuesta `200 OK` y estructura JSON válida en todos los grupos funcionales (Núcleo, Catálogos, Transacciones, Configuración, Reportes y Exportaciones).
