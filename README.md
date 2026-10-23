# 🏛️ Backend Reverse Synthesis (`backend-reverse-synthesis` v3.0)

> **Protocolo determinista, inter-procedural y de sincronización de estado (Cero Adivinación / Cero Ceguera / Cero Desincronización) para la recreación de backends a partir de código cliente extraído con REA v7.0.0 y REPLICA.**

---

## 💡 ¿Por Qué se Creó este Skill y Cómo Evolucionó a v3.0?

Cuando auditamos, rescatamos o reconstruimos aplicaciones cuyo servidor original ya no existe o es inaccesible, herramientas como **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript` sobre Electron `.asar`, `rea strings`, `inspect_android`, `inspect_capture`) y **REPLICA** (`replica-recon` / `replica coderecon`) nos permiten recuperar el código del cliente (SPA, PWA, bundles JS, aplicaciones móviles o de escritorio).

Sin embargo, durante la reconstrucción real de un sistema POS completo a partir de su frontend extraído, quedaron en evidencia **tres generaciones de defectos críticos** cuando un agente intenta recrear un backend:

### ❌ Generación 1: La Trampa de "Reinterpretar y Adivinar" (Resuelta en v1.0)
1. **Ceguera de Rutas Compuestas**: Ve las rutas estáticas obvias (`/api/clientes/`), pero ignora rutas construidas dinámicamente mediante prefijos (`URL_BASE + "estado/"`), operadores ternarios o concatenación de IDs (`"/api/ventas/" + v.id + "/productos/" + p.id + "/anular/"`).
2. **Ceguera en Filtros Relacionales Silenciosos**: El servidor devuelve sucursales como `{ id: 1, nombre: "Norte" }`, pero el frontend ejecuta `D.sucursales.filter(s => Number(s.empresa_id) === Number(empresaId))`, dejando los `<select>` vacíos sin arrojar errores.
3. **Colisión Primitivo vs. Objeto**: El servidor devuelve `roles: ["Dueño", "Cajero"]` cuando el cliente itera buscando `r.id`, `r.nombre` y `r.es_dueno_empresa`.
4. **Adivinación de Llaves JSON y Polimorfismo**: El servidor devuelve `{ ok: true, data: [...] }` cuando el cliente espera `proveedores` y `siguiente_codigo`, o ignora `{ id, eliminar: true }` en endpoints `/guardar/`.

### ❌ Generación 2: Ceguera Inter-Procedural, Compuertas de Permisos e Inversión MIME (Resuelta en v2.0)
Incluso con el 100% de las rutas creadas y respondiendo `HTTP 200`, la primera versión del auditor dejó pasar cuatro patrones que inutilizaron por completo el módulo `#configuracion`:
1. **Compuertas de Permisos Vacías (`permisos: {}`)**: El despachador `abrir(item)` evaluaba `if (!estado.permisos[item.clave]) return C.post("/api/configuracion/permiso/", ...)`. Al devolver `permisos: {}` y `200 OK` en `/permiso/`, los **16 botones del módulo no hacían absolutamente nada al hacer clic**.
2. **Indirección de Promesas y Estado Compartido**: El auditor v1.0 solo leía `.then(function(d) { ... })` anónimos inline, reportando `(sin lectura directa)` cuando el frontend usaba callbacks nombrados (`.then(abrirEditor)`, `.then(abrirVentana)`) o cuando guardaba `C._estado = d` y lo pasaba a submódulos en otros archivos (`V.empresa = function(estado)`), ocultando sub-propiedades de 2do nivel (`limite.sucursales_disponibles`, `categorias[].parent_id`, `categorias[].ruta`).
3. **Inversión Semántica MIME en Descargas (`C.descargar`)**: El wrapper `C.descargar()` verifica `if (!r.ok || tipo.indexOf("application/json") >= 0) throw Error(...)`. Devolver `200 OK` con `c.json({ ok: true })` pasaba un test básico de código HTTP, pero el cliente lo interpretaba como un fallo de negocio por ser JSON en lugar de un archivo descargable (`text/csv`, `text/html`, `application/octet-stream`).
4. **Botones Huérfanos (`sinPantalla: true`)**: Botones marcados con `sinPantalla: true` (`Moneda`, `Cliente por defecto`, `Etiqueta`) carecían de handler en `P.ConfigVentanas`.

### ❌ Generación 3: Desincronización SSR/SPA, Echo Stubs, Coerción `Number(id)` y Reportes Polimórficos (Resuelta en v3.0)
Al probar cambios de extremo a extremo entre módulos, se descubrieron cuatro patrones estructurales adicionales:
1. **Hidratación SSR Incompleta (`#pos-datos` vs `#pos-sesion`)**: El usuario cambiaba el nombre de la empresa en `#configuracion -> Mi empresa`, se guardaba en SQLite, pero **el menú izquierdo seguía mostrando `"SITIO DE PRUEBA"`** porque `GET /` solo reemplazaba `<script id="pos-datos">` y dejaba `<script id="pos-sesion">` estático de la captura original (que `nucleo/utilidades.js` lee después, pisando `datos.sesion`).
2. **Echo Stubs Sin Persistencia (`POST` que finge guardar y `GET` con `[]` quemado)**: Endpoints como `/api/configuracion/roles/guardar/`, `/api/caja/pendientes/`, `/api/recibir/registrar/`, `/api/gastos/categorias/` o `/api/inventario/productos/:id/variantes/` respondían `{ ok: true }` sin escribir en SQLite ni `configuracion_kv`, mientras sus `GET` devolvían arreglos vacíos fijos.
3. **Coerción Numérica sobre Llaves Primarias Alfanuméricas (`Number(id)` $\rightarrow$ `NaN === NaN`)**: El backend generaba IDs de texto (`prd_...`, `cat_...`, `suc_...`, `usr_...`), mientras que `inventario.js`, `selector_categoria.js`, `compras.js`, `usuario.js` y `admin_usuario.js` ejecutaban `Number(item.dataset.id)` o `Number(a.sucursal_id) === Number(s.id)`, evaluando `NaN === NaN` (`false`) y rompiendo silenciosamente la selección de tarjetas y categorías.
4. **Despachadores Polimórficos Incompletos (`?tipo=...`)**: `GET /api/reportes/` solo atendía 4 de los 18 subtipos definidos en `REPORTES` (`reporte.js`), devolviendo `filas: []` en los 14 restantes.

---

## 📂 Estructura del Repositorio

```text
backend-reverse-synthesis/
├── SKILL.md                         # Instrucciones operativas v3.0 del Skill (14 Anti-Patrones + 6 Fases)
├── README.md                        # Documentación general y guía rápida v3.0
├── docs/
│   └── ORIGEN_Y_CASO_DE_ESTUDIO.md  # Análisis forense detallado de los Casos de Estudio reales
└── scripts/
    └── audit_api_contracts.py       # Auditor estático inter-procedural v3.0 (Frontend vs. Backend)
```

---

## 🚀 Uso Rápido del Auditor Determinista v3.0

```bash
python3 scripts/audit_api_contracts.py \
  --frontend /ruta/al/frontend/extraido \
  --server /ruta/al/servidor/reconstruido.js
```

### Ejemplo de Salida Real v3.0 (100% Paridad Determinista)
```text
==========================================================================================
🔬 AUDITORÍA DETERMINISTA DE CONTRATOS API v3.0 (ZERO-GUESSING & STATE-SYNC PROTOCOL)
==========================================================================================
Rutas API únicas en Frontend       : 79
Rutas API registradas en Servidor  : 91
Claves de Permiso (config_*)       : 18 detectadas
Rutas de Descarga Binaria/Archivo  : 4 detectadas
Bloques SSR JSON (<script>)        : 3 detectados (pos-datos, pos-modulos, pos-sesion)
Subtipos Polimórficos (?tipo=...)  : 18 detectados en reportes
------------------------------------------------------------------------------------------
...
------------------------------------------------------------------------------------------
📊 Cobertura de Rutas: 79/79 (100.0%)

🏆 PARIDAD DETERMINISTA v3.0 AL 100%: Rutas, SSR, persistencia SQL/KV, IDs alfanuméricos, permisos y reportes verificados.
```
