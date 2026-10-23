# 🏛️ Backend Reverse Synthesis (`backend-reverse-synthesis` v2.0)

> **Protocolo determinista e inter-procedural (Cero Adivinación / Cero Ceguera) para la recreación de backends a partir de código cliente extraído con REA v7.0.0 y REPLICA.**

---

## 💡 ¿Por Qué se Creó este Skill y Cómo Evolucionó a v2.0?

Cuando auditamos, rescatamos o reconstruimos aplicaciones cuyo servidor original ya no existe o es inaccesible, herramientas como **REA v7.0.0** (`inspect_sourcemap`, `analyze_javascript` sobre Electron `.asar`, `rea strings`, `inspect_android`, `inspect_capture`) y **REPLICA** (`replica-recon` / `replica coderecon`) nos permiten recuperar el código del cliente (SPA, PWA, bundles JS, aplicaciones móviles o de escritorio).

Sin embargo, durante la reconstrucción real de un sistema POS completo a partir de su frontend extraído, quedaron en evidencia **dos generaciones de defectos críticos** cuando un agente intenta recrear un backend:

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
4. **Botones Huérfanos (`sinPantalla: true`) y Stubs Sin Persistencia**: Botones marcados con `sinPantalla: true` (`Moneda`, `Cliente por defecto`, `Etiqueta`) o endpoints `POST` que no persistían en SQLite daban la ilusión de que la interfaz estaba rota.

---

## 📂 Estructura del Repositorio

```text
backend-reverse-synthesis/
├── SKILL.md                         # Instrucciones operativas v2.0 del Skill (10 Anti-Patrones + 5 Fases)
├── README.md                        # Documentación general y guía rápida
├── docs/
│   └── ORIGEN_Y_CASO_DE_ESTUDIO.md  # Análisis forense detallado de los Casos A–H que dieron origen al Skill
└── scripts/
    └── audit_api_contracts.py       # Auditor estático inter-procedural v2.0 (Frontend vs. Backend)
```

---

## 🚀 Uso Rápido del Auditor Determinista v2.0

```bash
python3 scripts/audit_api_contracts.py \
  --frontend /ruta/al/frontend/extraido \
  --server /ruta/al/servidor/reconstruido.js
```

### Ejemplo de Salida Real v2.0 (100% Paridad Determinista)
```text
==========================================================================================
🔬 AUDITORÍA DETERMINISTA DE CONTRATOS API v2.0 (ZERO-GUESSING PROTOCOL)
==========================================================================================
Rutas API únicas en Frontend       : 78
Rutas API registradas en Servidor  : 90
Claves de Permiso (config_*)       : 18 detectadas
Rutas de Descarga Binaria/Archivo  : 4 detectadas
------------------------------------------------------------------------------------------
  [OK]      ALL      /api/configuracion/catalogo/generar/ [DOWNLOAD]  | Props: nombre, total | configuracion_general.js:467
  [OK]      GET      /api/configuracion/eliminar/estado/              | Props: compartidas_empresa, modo, tablas, tablas[].descripcion, tablas[].icono, tablas[].nombre, tablas[].tabla | configuracion_eliminar.js:79
  [OK]      GET      /api/configuracion/factura/                      | Props: config, sucursales | configuracion_ventas.js:349
  [OK]      GET      /api/configuracion/general/estado/               | Props: categorias, categorias[].parent_id, empresa, empresa.nombre, es_dueno, limite, limite.max_sucursales, limite.sucursales_disponibles, limite.sucursales_usadas, permisos, sucursal_sesion, sucursales, tipos_identificacion | configuracion.js:96
...
------------------------------------------------------------------------------------------
📊 Cobertura de Rutas: 78/78 (100.0%)

🏆 PARIDAD DETERMINISTA AL 100%: Rutas, propiedades anidadas, permisos, descargas y botones verificados.
```

---

## 📄 Documentación Adicional
Consulta [`docs/ORIGEN_Y_CASO_DE_ESTUDIO.md`](docs/ORIGEN_Y_CASO_DE_ESTUDIO.md) para ver el desglose técnico completo de los casos de estudio reales (Casos A–H) y cómo este protocolo v2.0 los previene de forma determinista.
