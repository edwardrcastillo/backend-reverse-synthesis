# 🔬 Origen y Caso de Estudio: Evolución de `backend-reverse-synthesis` (`v1.0` $\rightarrow$ `v4.0`)

## 1. Contexto del Problema
Al trabajar con herramientas de ingeniería inversa como **REA v7.0.0** y **REPLICA**, es posible recuperar íntegramente el frontend de una aplicación (archivos JavaScript, plantillas HTML, sourcemaps, paquetes Electron `.asar` o APKs) cuando el servidor original ya no existe.

Sin embargo, al recrear el backend funcional desde cero, documentamos **14 casos empíricos reales (Casos A–N)** que demostraron por qué la reconstrucción heurística ("adivinar") y las pruebas superficiales (`HTTP 200`) producen fallos silenciosos sistemáticos.

---

## 2. Cronología Completa de Casos Forenses (Casos A–N)

### Generación 1: Ceguera de Contratos Básicos (`v1.0`)
- **Caso A ("No puedo agregar proveedor")**: El servidor devolvía `{ ok: true, proveedores: [...] }`, pero el cliente exigía `siguiente_codigo` (`PR-001`), el objeto singular `proveedor` de vuelta y la ruta `/api/proveedores/control/`.
- **Caso B ("No existe sucursal en esa forma")**: `inventario.js` filtraba `D.sucursales.filter(s => Number(s.empresa_id) === Number(empresaId))`. Al omitir `empresa_id: 23` en `GET /api/admin/sucursales/`, `NaN === 23` dio `false` y vació el `<select>` sin arrojar errores.
- **Caso C ("No hay rol en agregar usuarios")**: El servidor envió un arreglo plano `["Dueño", "Cajero"]` cuando `usuario.js` iteraba leyendo objetos `{ id, nombre, es_dueno_empresa, permisos }` y el árbol `modulos`.
- **Caso D (Rutas Ocultas tras Prefijos)**: Un `grep` simple detectaba 32 rutas, ocultando 47 rutas adicionales construidas con `var URL_BASE = "/api/configuracion/eliminar/"` y concatenaciones dinámicas.

### Generación 2: Ceguera Inter-Procedural, Compuertas de Permisos y Descargas (`v2.0`)
- **Caso E ("El módulo de configuración solo muestra botones pero no hace nada")**: `GET /api/configuracion/general/estado/` devolvía `permisos: {}`. En `configuracion.js`, `if (!estado.permisos[item.clave])` evaluaba `true` para los 16 botones, desviando la ejecución a `/api/configuracion/permiso/` y bloqueando el 100% del módulo.
- **Caso F (Callbacks Nombrados y Estado Compartido)**: El auditor v1.0 solo leía `.then(function(d){...})` inline y reportaba `(sin lectura directa)` cuando el frontend hacía `.then(abrirEditor)` o pasaba `estado` a submódulos en otros archivos (`V.sucursales = function(estado)`), pasando por alto `limite.sucursales_disponibles`, `categorias[].parent_id` y `categorias[].ruta`.
- **Caso G (Inversión Semántica MIME en `C.descargar`)**: El wrapper `C.descargar()` lanza excepción si `Content-Type` contiene `application/json`. Responder `200 OK` con `c.json({ ok: true })` pasaba un test HTTP simple pero rompía todas las descargas de catálogos, plantillas y backups.
- **Caso H (Botones Huérfanos `sinPantalla: true` y Caché de Service Worker)**: Los botones `Moneda`, `Cliente por defecto` y `Etiqueta` tenían `sinPantalla: true` sin modal asociado, y `sw.js` retenía scripts antiguos por usar *Cache-First* con `ignoreSearch: true`.

### Generación 3: Desincronización SSR/SPA, Echo Stubs, Coerción `Number(id)` y Reportes (`v3.0`)
- **Caso I ("Modifiqué el nombre de la empresa pero el menú izquierdo sigue diciendo SITIO DE PRUEBA")**: `nucleo/utilidades.js` hidrata primero `#pos-datos` y luego sobrescribe `datos.sesion` con `#pos-sesion`. Como `GET /` solo reemplazaba `#pos-datos` y dejaba `#pos-sesion` y `<span id="sidebar-empresa">` con el texto estático de la captura original, el cambio guardado en SQLite era pisado en cada recarga.
- **Caso J (Echo Stubs Sin Persistencia)**: Endpoints como `POST /api/configuracion/roles/guardar/`, `POST /api/caja/pendientes/`, `POST /api/recibir/registrar/` y `POST /api/inventario/productos/:id/variantes/` respondían `{ ok: true }` sin escribir en SQLite ni `configuracion_kv`, mientras sus `GET` devolvían `[]` quemado.
- **Caso K (Coerción Numérica `Number(id)` $\rightarrow$ `NaN === NaN`)**: El backend generaba llaves primarias de texto (`prd_1`, `cat_1`, `suc_1`, `usr_1`), mientras que `inventario.js`, `selector_categoria.js`, `compras.js`, `usuario.js` y `admin_usuario.js` ejecutaban `Number(item.dataset.id)` o `Number(a.sucursal_id) === Number(s.id)`, evaluando `NaN === NaN` (`false`) e impidiendo seleccionar productos, categorías o sucursales.
- **Caso L (Despachador Polimórfico Incompleto en Reportes)**: `reporte.js` define 18 tipos de reportes (`?tipo=...`), pero el servidor solo implementaba 4 y devolvía `filas: []` en los 14 restantes.

### Generación 4: Paridad Esquema SQL vs. Queries, Archivos Multipart y Portabilidad Multi-Stack (`v4.0`)
- **Caso M (Desfase Esquema DDL vs. Consultas SQL en Tiempo de Ejecución)**:
  - `GET /api/reportes/?tipo=apertura` consultaba `SELECT * FROM caja_sesiones` cuando la tabla en `db.js` se llamaba `turnos_caja`.
  - `GET /api/reportes/?tipo=proveedor` consultaba `p.vendedor` en `proveedores`, columna que no existía en el `CREATE TABLE proveedores`.
  - `POST /api/recibir/codigos/:id/producto/` hacía `INSERT INTO productos (..., unidad, ...)` sin que `unidad` estuviera en el DDL de `productos`, y `ordenes_compra` no tenía `CREATE TABLE IF NOT EXISTS` en el arranque.
- **Caso N (Pérdida de Archivos en Formularios Multipart `FormData`)**:
  - `Mi empresa` y `Editar factura` enviaban el archivo `logo` mediante `FormData` (`C.postForm`), y `inventario.js` enviaba `imagen_data`, `descripcion`, `atributos` y `variantes`. El servidor ignoraba el archivo `logo` y los metadatos extendidos del producto.

---

## 3. Cómo `audit_api_contracts.py` v4.0 Previene los Casos A–N de Forma Determinista
1. **Reglas #1–#8**: Resolución inter-procedural de rutas, prefijos `URL_BASE`, callbacks nombrados, estado compartido, propiedades de 1er/2do nivel y compuertas de permisos.
2. **Reglas #9–#10**: Validación de rutas `[DOWNLOAD]` (prohibido devolver solo JSON) y detección de botones `sinPantalla: true` sin handler.
3. **Reglas #11–#14**: Verificación de todos los bloques SSR `<script type="application/json">`, prohibición de *Echo Stubs* (`POST` sin persistencia y `GET` con `[]` fijo), detección de `Number(id)` sobre PKs alfanuméricas y cobertura de los 18 subtipos `?tipo=`.
4. **Reglas #15–#18 (Nuevas en v4.0)**:
   - **Paridad DDL SQL $\leftrightarrow$ Consultas**: Extrae todas las tablas y columnas de `CREATE TABLE` y `ALTER TABLE` y falla si cualquier `SELECT`, `INSERT` o `UPDATE` referencia una tabla o columna inexistente.
   - **Detección de Rutas Duplicadas**: Falla si un endpoint se declara más de una vez en el router.
   - **Auditoría Multipart/FormData**: Verifica que las rutas que reciben `FormData` no usen `req.json()` puro y procesen los archivos subidos.
