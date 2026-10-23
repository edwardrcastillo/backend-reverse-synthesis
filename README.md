# 🏛️ Backend Reverse Synthesis (`backend-reverse-synthesis`)

> **Protocolo determinista (Cero Adivinación / Cero Ceguera) para la recreación de backends a partir de código cliente extraído con REA v7.0.0 y REPLICA.**

---

## 💡 ¿Por Qué se Creó este Skill?

Cuando auditamos, rescatamos o reconstruimos aplicaciones cuyo servidor original ya no existe o es inaccesible, herramientas como **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript` sobre Electron `.asar`, `rea strings`, `inspect_android`, `inspect_capture`) y **REPLICA** (`replica-recon` / `replica coderecon`) nos permiten recuperar el código del cliente (SPA, PWA, bundles JS, aplicaciones móviles o de escritorio).

Sin embargo, durante la reconstrucción real de un sistema POS completo a partir de su frontend extraído, quedó en evidencia un **defecto crítico en la forma en que los agentes de IA abordan la recreación de un backend**:

### ❌ El Problema: La Trampa de "Reinterpretar y Adivinar"
Cuando un agente lee superficialmente las llamadas del cliente (`fetch`, `P.api`, `axios`) e intenta **adivinar o reinterpretar heurísticamente** qué debe responder el servidor:
1. **Sufre de Ceguera de Rutas Compuestas**: Ve las rutas estáticas obvias (`/api/clientes/`), pero ignora rutas construidas dinámicamente mediante prefijos (`URL_BASE + "estado/"`), operadores ternarios o concatenación de IDs (`"/api/ventas/" + v.id + "/productos/" + p.id + "/anular/"`).
2. **Sufre de Ceguera en Filtros Relacionales Silenciosos**: El servidor devuelve sucursales como `{ id: 1, nombre: "Norte" }`, pero el frontend ejecuta silenciosamente:
   ```javascript
   D.sucursales.filter(function(s) { return Number(s.empresa_id) === Number(empresaId); });
   ```
   Como el backend omitió `empresa_id: 23`, la comparación evalúa `NaN === 23` (`false`) y **deja los selectores (`<select>`) vacíos sin arrojar un solo error en consola ni en red**.
3. **Adivina Tipos de Colección Incorrectos**: El servidor devuelve `roles: ["Dueño", "Cajero"]` pensando que es una lista de nombres, mientras que el combobox del cliente itera buscando `r.id`, `r.nombre` y `r.es_dueno_empresa`, renderizando opciones en blanco.
4. **Adivina Nombres de Llaves JSON**: El servidor devuelve `{ ok: true, data: [...] }`, pero el cliente espera `{ ok: true, proveedores: [...], siguiente_codigo: "PRV-0002" }`, rompiendo el alta de registros.
5. **Ignora el Polimorfismo de Guardado/Borrado y `FormData`**: Muchos clientes envían `{ id, eliminar: true }` al mismo endpoint `/guardar/` o alternan entre `application/json` y `multipart/form-data`.

### ✅ La Solución: Síntesis Determinista Guiada por el Contrato del Cliente
Este skill se creó para prohibir la adivinación heurística y sustituirla por un **pipeline determinista de 5 fases** respaldado por análisis estático automatizado ([`scripts/audit_api_contracts.py`](scripts/audit_api_contracts.py)):
- **El código cliente extraído con REA/REPLICA no se "reinterpreta": se compila como una especificación formal.**
- Cada ruta, cada propiedad leída en `.then(function(r) { ... })` y cada predicado `.filter(function(x) { ... })` se extrae automáticamente y se contrasta contra el servidor hasta lograr **100% de paridad verificada**.

---

## 📂 Estructura del Repositorio

```text
backend-reverse-synthesis/
├── SKILL.md                         # Instrucciones operativas del Skill para Antigravity / Claude Code
├── README.md                        # Documentación general y guía rápida
├── docs/
│   └── ORIGEN_Y_CASO_DE_ESTUDIO.md  # Análisis forense detallado de los fallos que dieron origen al Skill
└── scripts/
    └── audit_api_contracts.py       # Auditor estático determinista (Frontend vs. Backend)
```

---

## 🚀 Uso Rápido del Auditor Determinista

```bash
python3 scripts/audit_api_contracts.py \
  --frontend /ruta/al/frontend/extraido \
  --server /ruta/al/servidor/reconstruido.js
```

### Ejemplo de Salida Real (100% Paridad)
```text
================================================================================
🔬 AUDITORÍA DETERMINISTA DE CONTRATOS API (ZERO-GUESSING PROTOCOL)
================================================================================
Rutas API únicas en Frontend : 77
Rutas API registradas Server : 89
--------------------------------------------------------------------------------
  [OK]      GET      /api/admin/sucursales/                        | Props: sucursales | admin_usuario.js:844
  [OK]      GET      /api/caja/ventas/                             | Props: puede_anular, ventas | caja.js:28, caja_modales.js:241
  [OK]      GET      /api/clientes/                                | Props: siguiente_codigo | cliente.js:38
  [OK]      GET/POST /api/compras/pedidos/                         | Props: pedido, pedidos, productos | compras.js:30, compras.js:413
  [OK]      POST     /api/configuracion/bajas/registrar/           | Props: mensaje, stock, titulo | configuracion_ventas.js:93
...
--------------------------------------------------------------------------------
📊 Cobertura de Rutas: 77/77 (100.0%)

🔗 INVARIANTES DE FILTRADO RELACIONAL DETECTADOS EN FRONTEND (.filter):
  • admin_usuario.js: s.empresa_id
  • caja.js: s.activa
  • caja.js: s.empresa_id
  • cliente.js: s.activa

🏆 PARIDAD DE RUTAS AL 100%: Ninguna llamada del frontend carece de endpoint.
```

---

## 🔗 Integración con REA v7.0.0 y REPLICA

1. **Extracción Forense (`rea-reverse-engineering` / `replica-recon`)**:
   - Extrae sourcemaps, bundles JS, paquetes Electron `.asar` o APKs con `rea` / `replica coderecon`.
2. **Síntesis Determinista (`backend-reverse-synthesis`)**:
   - Ejecuta `audit_api_contracts.py` sobre el código extraído, construye los serializadores canónicos respetando los invariantes `.filter()` y el bootstrap HTML, y verifica `0 [MISSING]` antes de desplegar.
3. **Pruebas E2E (`replica-test`)**:
   - Valida todos los flujos de usuario con sesión real contra el backend reconstruido.

---

## 📄 Documentación Adicional
Consulta [`docs/ORIGEN_Y_CASO_DE_ESTUDIO.md`](docs/ORIGEN_Y_CASO_DE_ESTUDIO.md) para ver el desglose técnico completo de los patrones de ceguera y adivinación detectados durante la reconstrucción de un sistema POS real y cómo este protocolo los resuelve de forma definitiva.
