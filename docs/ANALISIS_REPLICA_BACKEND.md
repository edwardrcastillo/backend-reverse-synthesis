# 🔬 Auditoría Forense de los Módulos de Backend en la Suite `Replica` vs. `backend-reverse-synthesis` v4.0

**Fecha de Auditoría:** 23 de Octubre de 2026  
**Objetivo:** Preservar el análisis técnico profundo de la arquitectura de backend de la suite **Replica** (`replica-recon`, `replica-architect`, `replica-backend`), identificar sus puntos ciegos estructurales frente a escenarios de reconstrucción o cableado de backends, y definir la ruta de convergencia con **`backend-reverse-synthesis` v4.0**.

---

## 1. Mapa de Componentes de Backend en la Suite `Replica`

La responsabilidad de inferir, diseñar y construir el backend dentro de la suite `Replica` (`/Users/edward/.gemini/config/plugins/replica/`) está fragmentada en **3 sub-skills**:

| Fase | Sub-Skill / Archivo | Líneas | Rol Declarado | Herramienta CLI |
| :--- | :--- | :---: | :--- | :--- |
| **1. Reconocimiento** | [`skills/replica-recon/coderecon.py`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-recon/coderecon.py) | 552 | Extraer rutas, entidades de datos y endpoints HTTP de un código fuente o paquete extraído (ASAR/APK/PWA) hacia `replica/recon.md`. | Sí (`coderecon.py`) |
| **2. Arquitectura** | [`skills/replica-architect/SKILL.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-architect/SKILL.md) + [`architecture.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-architect/architecture.md) | 115 + 42 | Elegir el stack tecnológico, transformar las entidades de `recon.md` en DDL SQL con índices y reglas RLS, y listar las rutas API por flujo. | ❌ **Ninguna** |
| **3. Implementación** | [`skills/replica-backend/SKILL.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-backend/SKILL.md) | 90 | Implementar autenticación, migraciones de base de datos, pagos con Stripe, emails (Resend), jobs en segundo plano, integraciones OAuth y checklist de seguridad. | ❌ **Ninguna** |

---

## 2. Los 5 Puntos Ciegos Críticos de `Replica` en el Eje Backend

### Punto Ciego #1: Sesgo *Greenfield SaaS* (`Clean-Room`) vs. Síntesis de Contratos API
* **Evidencia en Código:** [`skills/replica-backend/SKILL.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-backend/SKILL.md#L1-L90) y [`rules/replica-clean-room.md`](file:///Users/edward/.gemini/config/plugins/replica/rules/replica-clean-room.md#L1-L32).
* **Análisis Técnico:**
  * `Replica` fue concebida bajo una filosofía de **clonación comercial Clean-Room desde cero**: observar una app pública, reescribir un frontend nuevo en `/replica-build` (inicialmente con datos falsos o estado local) y luego usar `/replica-backend` para conectarle una infraestructura SaaS estándar (**Next.js + Supabase + Stripe Checkout + Resend + Google OAuth**).
  * Consecuencia directa: [`replica-backend/SKILL.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-backend/SKILL.md) es una lista de verificación de **90 líneas** centrada en cómo configurar webhooks de Stripe (`checkout.session.completed`, `invoice.payment_failed`), verificar el dominio DNS en Resend y pasar la verificación OAuth de Google.
  * **Falla incluso en su propio flujo nativo:** Cuando el usuario ejecuta `/replica-build` (que construye pantallas sobre datos simulados) y luego invoca `/replica-backend`, **no existe ningún paso ni instrucción en `replica-backend` para escanear los `fetch()`, formularios o estados que `/replica-build` creó** y garantizar que el backend devuelva las llaves JSON exactas que la interfaz espera.

### Punto Ciego #2: Ausencia Total de Herramientas Ejecutables en Arquitectura y Backend
* **Evidencia en Código:** Inspección del directorio `/Users/edward/.gemini/config/plugins/replica/skills/` y [`bin/replica`](file:///Users/edward/.gemini/config/plugins/replica/bin/replica).
* **Análisis Técnico:**
  * Mientras los módulos visuales y comerciales de `Replica` cuentan con scripts deterministas en Python (`contrast.py` en `replica-design`, `parity.py` e `imgdiff.py` en `replica-diff`, `sweep.py` en `replica-brand`, `reviews.py` en `replica-entrepreneur`, `listing.py` en `replica-launch`), **tanto `replica-architect` como `replica-backend` carecen por completo de scripts verificadores**.
  * Toda la calidad del backend queda delegada a que el LLM siga instrucciones en prosa ("*validate every input at the boundary with a schema (Zod, Valibot, Pydantic)*"), sin un auditor estático ni pruebas automatizadas de contrato que bloqueen errores antes de dar por terminada la fase.

### Punto Ciego #3: Truncamiento Silencioso y Regex Ingenuo en `coderecon.py`
* **Evidencia en Código:** [`skills/replica-recon/coderecon.py`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-recon/coderecon.py#L204-L263) y [`coderecon.py#L455-L465`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-recon/coderecon.py#L455-L465).
* **Hallazgos Exactos Línea por Línea:**
  1. **Truncamiento duro a 25 endpoints (`L461`):**
     ```python
     # skills/replica-recon/coderecon.py, línea 461:
     for ep in self.endpoints[:25]:
         lines.append(f"| `{ep.method}` | `{ep.path}` | `{ep.source_file}` |")
     ```
     En un sistema real como `posrea` (que posee **79 endpoints únicos**), `coderecon.py` **descarta silenciosamente 54 endpoints (el 68% de la superficie del servidor)** al escribir `replica/recon.md`. Como `replica-architect` lee `replica/recon.md` para planificar la API, esos 54 endpoints jamás llegan a diseñarse ni implementarse (`404 Not Found` garantizado).
  2. **Ceguera ante clientes HTTP personalizados y concatenación (`L204-L228`):**
     `_detect_endpoints()` solo busca literales estáticos simples dentro de `fetch('/api/...')` y `axios.(get|post|put|patch|delete)('...')`. Ignora:
     * Wrappers de aplicación (`P.api()`, `C.get()`, `C.post()`, `C.postForm()`, `C.descargar()`).
     * Prefijos de ruta base (`var URL_BASE = "/api/configuracion"` + `C.get("/empresa/")`).
     * Despachadores polimórficos por query string (`GET /api/reportes/?tipo=ventas` con 18 subtipos distintos).
  3. **Ceguera de modelo de datos en JavaScript puro (`L229-L263`):**
     `_detect_entities()` únicamente busca `interface Nombre { ... }` (TypeScript), `model Nombre { ... }` (Prisma) o `CREATE TABLE` (SQL). Cuando analiza un frontend en JavaScript puro (SPA, PWA, bundles de Webpack/Vite o código extraído de un ASAR/APK sin `.d.ts`), **detecta 0 entidades** y cae en el fallback quemado de la línea `456`:
     ```python
     lines.append("| `StateEntity` | `id, createdAt, payload` | `inferred` | `read/write` |")
     ```
  4. **Ceguera total de lectura de respuesta (`.then(d => ...)`):**
     `coderecon.py` extrae la URL del endpoint pero **no analiza qué propiedades lee el cliente de la respuesta JSON** (ni callbacks inline, ni funciones nombradas como `.then(abrirEditor)`, ni estado compartido `P.datos`).

### Punto Ciego #4: Regla Dogmática de `UUID` en `replica-architect` (Inductor Directo de `NaN === NaN`)
* **Evidencia en Código:** [`skills/replica-architect/SKILL.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-architect/SKILL.md#L48).
* **Análisis Técnico:**
  * La línea 48 de `replica-architect/SKILL.md` ordena de forma absoluta para todas las tablas:
    > *"`id uuid primary key default gen_random_uuid()`, `created_at timestamptz not null default now()` on every table."*
  * Si el código frontend (ya sea existente o generado con patrones clásicos de DOM) utiliza `Number(item.dataset.id)` o `Number(a.sucursal_id) === Number(s.id)` para cruzar llaves foráneas, inyectar UUIDs (`"550e8400-e29b-..."`) o IDs con prefijo (`"prd_1"`) provoca que `Number(id)` evalúe a `NaN`. En JavaScript, `NaN === NaN` es siempre `false`, rompiendo silenciosamente selectores, filtros de sucursal, carritos de compra y modales de edición (**Antipatrón #13 de `backend-reverse-synthesis`**).

### Punto Ciego #5: Ceguera ante SSR Hydration, Echo Stubs, Semántica MIME Inversa, Multipart y Paridad SQL DDL-to-Query
Ninguno de los tres módulos de `Replica` contempla las siguientes verificaciones críticas de producción:
1. **Sincronización de Hidratación SSR Completa:** Si el HTML inicial inyecta múltiples bloques JSON (`#pos-datos`, `#pos-sesion`, `#pos-modulos`) y nodos estáticos del shell (`#sidebar-empresa`), `Replica` no verifica que el servidor actualice todos los bloques en `GET /` ni que las mutaciones `POST` sincronicen el estado en memoria del cliente.
2. **Detección de Echo Stubs (`return { ok: true }` sin SQL):** `Replica` no audita si un controlador `POST`/`PUT`/`DELETE` realmente ejecuta `INSERT`/`UPDATE`/`DELETE` en la base de datos o si es un stub vacío dejado por el agente durante el prototipado.
3. **Semántica MIME Inversa en Descargas:** No distingue endpoints de descarga binaria/CSV que lanzan excepción en el cliente si reciben `Content-Type: application/json`.
4. **Persistencia Multipart (`FormData` + Archivos):** No verifica que las subidas de archivos (`logo`, `imagen`, `archivo` CSV) usen un parser multipart real y persistan el contenido en lugar de ignorar los campos `File`/`Blob`.
5. **Paridad Esquema SQL $\leftrightarrow$ Consultas (`DDL-to-Query Parity`):** No verifica estáticamente que todas las tablas y columnas referenciadas en las consultas SQL de las rutas existan realmente en las sentencias `CREATE TABLE` / `ALTER TABLE`.

---

## 3. Matriz Comparativa: `Replica` vs. `backend-reverse-synthesis` v4.0

| Capacidad / Garantía de Ingeniería | Suite `Replica` (`recon` + `architect` + `backend`) | `backend-reverse-synthesis` v4.0 |
| :--- | :--- | :--- |
| **Propósito Primario** | Clonar una app comercial desde cero (*Clean-Room SaaS*) con stack propio (Next.js + Supabase + Stripe). | Reconstruir o auditar un backend **100% compatible al milímetro** con cualquier frontend existente o nuevo. |
| **Límite de Endpoints Extraídos** | Truncado a **25 endpoints** en `coderecon.py` (`self.endpoints[:25]`). | **Sin límite** (extrajo y verificó 79/79 endpoints en `posrea`). |
| **Detección de Wrappers HTTP y Prefijos** | ❌ Solo `fetch()` y `axios.*()` literales simples. | ✅ Soporta wrappers personalizados (`C.get`, `P.api`, `apiClient`), prefijos `URL_BASE` y rutas dinámicas. |
| **Resolución Inter-Procedural de Respuestas** | ❌ No inspecciona qué campos lee el cliente de la respuesta. | ✅ Resuelve `.then(fn)` inline, funciones nombradas (`abrirEditor`) y estado compartido entre archivos (`V.empresa(estado)`). |
| **Auditoría de Compuertas de Permisos (`RBAC`)** | ❌ No extrae claves de permisos del cliente. | ✅ Extrae todas las llaves `config_*`, `caja_*`, `inventario_*` del cliente y exige su presencia en el servidor. |
| **Cobertura de Despachadores Polimórficos (`?tipo=...`)** | ❌ Ignora subtipos por query string. | ✅ Extrae catálogos como `REPORTES` (18 subtipos) y verifica que cada rama exista en el backend. |
| **Auditoría de Descargas Binarias y Multipart** | ❌ No distingue JSON de descargas o `FormData`. | ✅ Verifica cabeceras MIME no-JSON en descargas y persistencia real en rutas `FormData`. |
| **Detección de *Echo Stubs* (`POST` sin DB)** | ❌ No audita el cuerpo de las rutas del servidor. | ✅ Detecta y bloquea rutas `POST`/`PUT`/`DELETE` que devuelven `{ ok: true }` sin escribir en base de datos. |
| **Detección de `NaN === NaN` (`Number(id)` vs UUID/String)** | ❌ Induce el bug al obligar `id uuid` en todas las tablas. | ✅ Detecta coerción `Number(*.id)` en el cliente cuando el servidor usa IDs alfanuméricos/UUIDs. |
| **Paridad SQL `CREATE TABLE` $\leftrightarrow$ `SELECT/INSERT`** | ❌ Sin verificación estática de esquema contra consultas. | ✅ Cruza el AST de DDL (`CREATE`/`ALTER`) contra todas las tablas y columnas usadas en queries SQL. |
| **Detección de Rutas Duplicadas (*Route Shadowing*)** | ❌ No verifica colisiones `(METHOD, path)` en el servidor. | ✅ Falla con `[FAIL]` si una ruta está declarada más de una vez en el servidor. |

---

## 4. Ruta de Convergencia: Cómo Sinergizar Ambos Skills

1. **Cuando se reconstruye el servidor para un cliente existente (PWA, SPA, Electron ASAR, APK Capacitor):**
   * Usar **exclusivamente `backend-reverse-synthesis` v4.0** y su auditor [`scripts/audit_api_contracts.py`](file:///Users/edward/.gemini/config/skills/backend-reverse-synthesis/scripts/audit_api_contracts.py).
2. **Cuando se construye un clon desde cero con la suite `Replica` (`/replica-recon` $\rightarrow$ `/replica-architect` $\rightarrow$ `/replica-build` $\rightarrow$ `/replica-backend`):**
   * Al terminar `/replica-build` y `/replica-backend`, **ejecutar `audit_api_contracts.py` v4.0 de `backend-reverse-synthesis` como compuerta de calidad obligatoria** antes de pasar a `/replica-test` o `/replica-diff`. Esto garantiza que el código frontend escrito en `/replica-build` y el servidor escrito en `/replica-backend` tengan paridad 100% de rutas, llaves JSON, esquemas SQL, permisos y tipos de IDs.
3. **Mejoras Recomendadas para `Replica` (Parche Local o Upstream):**
   * Eliminar el truncamiento `self.endpoints[:25]` en [`skills/replica-recon/coderecon.py`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-recon/coderecon.py#L461).
   * Reemplazar la regla dogmática de `id uuid` en [`skills/replica-architect/SKILL.md`](file:///Users/edward/.gemini/config/plugins/replica/skills/replica-architect/SKILL.md#L48) por una regla sensible al contrato del cliente (enteros autoincrementales si el cliente usa `Number(id)`, o UUID/TEXT solo si el cliente compara con `String(a) === String(b)`).
   * Integrar [`audit_api_contracts.py`](file:///Users/edward/.gemini/config/skills/backend-reverse-synthesis/scripts/audit_api_contracts.py) dentro del flujo de `/replica-backend`.
