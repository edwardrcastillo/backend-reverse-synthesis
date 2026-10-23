# 🏛️ Backend Reverse Synthesis (`backend-reverse-synthesis` v4.0)

> **Protocolo determinista universal (Multi-Stack, Cero Adivinación, Sincronización de Estado y Paridad DDL SQL) para la recreación de backends a partir de código cliente extraído con REA v7.0.0 y REPLICA.**

---

## 💡 ¿Por Qué Existe este Skill y Cómo Evolucionó a `v4.0`?

Cuando auditamos, rescatamos o reconstruimos aplicaciones cuyo servidor original ya no existe o es inaccesible, herramientas como **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript` sobre Electron `.asar`, `rea strings`, `inspect_android`, `inspect_capture`) y **REPLICA** (`replica-recon` / `replica coderecon`) permiten recuperar íntegramente el código del cliente (SPA, PWA, React/Vue/Next, aplicaciones móviles o de escritorio).

Sin embargo, reconstruir el backend "adivinando" o validando solo con `HTTP 200 OK` falla sistemáticamente. Este skill codifica las **18 reglas deterministas** aprendidas a lo largo de cuatro generaciones de auditoría empírica:

1. **v1.0 — Paridad de Rutas y Moldes JSON**: Resolución de `URL_BASE`, rutas concatenadas, llaves foráneas en `.filter()` (`empresa_id`, `activa`) y objetos ricos vs. primitivos.
2. **v2.0 — Análisis Inter-Procedural, Compuertas de Permisos y Descargas Binarias**: Resolución de callbacks nombrados (`.then(abrirEditor)`), estado compartido entre archivos (`C.estado()`), prohibición de `permisos: {}` y semántica MIME no-JSON en descargas (`.blob()`, `C.descargar`).
3. **v3.0 — Sincronización SSR/SPA, Prohibición de Echo Stubs, Coerción `Number(id)` y Reportes Polimórficos**: Hidratación dinámica de todos los bloques `<script type="application/json">` (`#pos-datos`, `#pos-sesion`, `#pos-modulos`), prohibición de endpoints `POST` sin persistencia en BD/KV, prevención de `NaN === NaN` en IDs alfanuméricos y cobertura total de subtipos `?tipo=...`.
4. **v4.0 — Edición Universal Multi-Stack, Paridad Esquema SQL $\leftrightarrow$ Queries, Multipart/Archivos y Transacciones Cruzadas**:
   - **Paridad DDL SQL vs. Consultas (Regla #15)**: Verifica estáticamente que toda tabla y columna referenciada en `SELECT`, `INSERT` y `UPDATE` exista realmente en los `CREATE TABLE` o `ALTER TABLE` del servidor (previene crashes `no such table` / `no such column` en producción).
   - **Detección de Rutas Duplicadas / Sombreadas (Regla #16)**: Impide que una ruta registrada dos veces en el router sombree silenciosamente la implementación real.
   - **Paridad Multipart/FormData y Persistencia de Imágenes/Logos (Regla #17)**: Detecta envíos `FormData` en el cliente y exige `parseBody` + persistencia de archivos (`logo`, `imagen`, `archivo`) en vez de `req.json()`.
   - **Portabilidad Multi-Stack y Buenas Prácticas de Arquitectura (Regla #18)**: Soporte para clientes `fetch`, `axios`, React/Vue/Vanilla y servidores Node.js (Hono/Express/Fastify), Python (FastAPI/Flask/Django) y Go; principio de inmutabilidad del cliente (`INTEGER PRIMARY KEY` cuando el cliente usa `Number(id)`), simetría de contratos de error, paginación, Auth/CSRF/CORS y zona horaria local.

---

## 📂 Estructura del Repositorio

```text
backend-reverse-synthesis/
├── SKILL.md                         # Especificación operativa v4.0 (Principios, 18 Anti-Patrones y 7 Fases)
├── README.md                        # Guía general y resumen de evolución v1.0 -> v4.0
├── docs/
│   └── ORIGEN_Y_CASO_DE_ESTUDIO.md  # Análisis forense detallado de los Casos de Estudio reales (Casos A–N)
└── scripts/
    └── audit_api_contracts.py       # Auditor estático universal v4.0 (Frontend vs. Backend + DDL SQL)
```

---

## 🚀 Uso Rápido del Auditor Determinista Universal v4.0

```bash
python3 scripts/audit_api_contracts.py \
  --frontend /ruta/al/frontend/extraido \
  --server /ruta/al/servidor/reconstruido.js
```

### Salida Real v4.0 (100% Paridad Determinista)
```text
===============================================================================================
🔬 AUDITORÍA DETERMINISTA UNIVERSAL DE CONTRATOS API v4.0 (MULTI-STACK & SCHEMA-PARITY)
===============================================================================================
Rutas API únicas en Frontend       : 79
Rutas API registradas en Servidor  : 110
Tablas SQL verificadas en DDL      : 17 tablas
Claves de Permiso detectadas       : 18 detectadas
Rutas Descarga / Multipart FormData: 4 descargas, 7 multipart
Bloques SSR JSON (<script>)        : 3 detectados (pos-datos, pos-modulos, pos-sesion)
Subtipos Polimórficos (?tipo=...)  : 18 detectados
-----------------------------------------------------------------------------------------------
...
-----------------------------------------------------------------------------------------------
📊 Cobertura de Rutas: 79/79 (100.0%)

🏆 PARIDAD DETERMINISTA v4.0 AL 100%: Rutas, DDL SQL, Multipart, SSR, Persistencia, IDs, Permisos y Reportes verificados.
```
