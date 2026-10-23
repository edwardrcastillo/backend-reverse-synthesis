# 🔬 Origen y Caso de Estudio: Por Qué Nació y Evolucionó `backend-reverse-synthesis` (v2.0)

## 1. Contexto del Problema
Al trabajar con herramientas de ingeniería inversa de vanguardia como **REA v7.0.0** y el ecosistema **REPLICA**, es posible recuperar íntegramente el frontend de una aplicación (archivos JavaScript estáticos, plantillas HTML, sourcemaps, recursos de Electron `.asar` o paquetes móviles) incluso cuando el servidor original ya no existe.

Sin embargo, al intentar **recrear el backend funcional** para que el proyecto original operara exactamente igual que en su entorno nativo, surgió una cadena de fallos en dos etapas que reveló un patrón claro: **la reconstrucción basada en reinterpretación heurística ("adivinar") y las pruebas superficiales (`HTTP 200`) producen fallos silenciosos sistemáticos.**

---

## 2. Cronología de los Fallos por Ceguera y Adivinación (Evidencia Empírica)

### Caso A: "No puedo agregar proveedor" (Discrepancia de Contrato de Guardado y Consecutivos)
- **Qué se adivinó**: Se asumió que `GET /api/proveedores/` solo debía devolver `{ ok: true, proveedores: [...] }` y que `POST /api/proveedores/guardar/` recibía campos genéricos.
- **Qué exigía realmente el código cliente (`proveedores.js` / `crud.js`)**:
  - Requería `siguiente_codigo` (`PR-001`) tanto en el `GET` como en el `POST` para poblar y refrescar el formulario.
  - Requería el objeto singular `proveedor` de vuelta con exactamente las mismas propiedades (`empresa_id: 23`, `sucursal_id`, `activa: true`, `estado: "Activo"`).
  - Requería el endpoint `/api/proveedores/control/` para la vista de carpetas de proveedores.

### Caso B: "No existe sucursal en esa forma" (Ceguera ante Filtros Relacionales Silenciosos)
- **Qué se adivinó**: En `GET /api/admin/sucursales/`, el servidor devolvía `{ id: 1, codigo: "S-001", nombre: "Principal", activa: true }`.
- **Qué hacía el código cliente (`inventario.js`)**:
  ```javascript
  var sucursalesEmpresa = (D.sucursales || []).filter(function (s) {
    return Number(s.empresa_id) === Number(empresaId);
  });
  ```
- **Por qué falló silenciosamente**: El HTML inicial (`index.html`) hidrataba la sesión con `empresa: { id: 23 }`. Como el endpoint omitió `empresa_id: 23`, `Number(undefined)` evaluó a `NaN`, `NaN === 23` dio `false`, y el selector `<select>` de sucursal quedó vacío sin emitir ningún error HTTP ni de consola.

### Caso C: "No hay rol en agregar usuarios" (Colisión Primitivo vs. Objeto Rico)
- **Qué se adivinó**: En `GET /api/configuracion/roles/`, se devolvió un arreglo plano de cadenas: `["Dueño", "Jefe de sucursal", "Supervisor", "Cajero", "Inventario"]`.
- **Qué hacía el código cliente (`usuario.js`)**:
  - El selector personalizado iteraba sobre `rolesCargados` accediendo a `r.id`, `r.nombre`, `r.es_dueno_empresa` y `r.es_jefe_sucursal`, además de requerir el árbol `modulos` con `opciones` para el editor de permisos.

### Caso D: Rutas Secundarias Ocultas tras Prefijos y Concatenaciones (Ceguera de `grep` Simple)
- **Qué se adivinó**: Un listado superficial de rutas `/api/` encontró 32 endpoints principales, cuando en realidad existían **78 rutas únicas** construidas mediante prefijos locales (`var URL_BASE = "/api/configuracion/eliminar/";`) y concatenaciones dinámicas (`"/api/caja/ventas/" + v.id + "/productos/" + p.id + "/anular/"`).

### Caso E: "El módulo de configuración solo muestra botones pero no hace nada" (Bloqueo por Compuerta de Permisos Vacía)
- **Qué ocurrió en v1.0**: El endpoint `GET /api/configuracion/general/estado/` existía, devolvía `200 OK` y tenía la clave `permisos: {}`.
- **Qué hacía realmente `configuracion.js`**:
  ```javascript
  function abrir(item) {
    C.estado(true).then(function (estado) {
      if (!estado.permisos[item.clave]) {
        return C.post("/api/configuracion/permiso/", { clave: item.clave }).catch(C.error);
      }
      var fn = P.ConfigVentanas[item.id];
      if (fn) return fn(estado, item);
    }, C.error);
  }
  ```
- **Por qué falló silenciosamente**: Al ser `estado.permisos` un objeto vacío `{}`, `!estado.permisos[item.clave]` evaluó a `true` para los **16 botones**, desviando la ejecución a `POST /api/configuracion/permiso/` (que devolvía `200 OK` en vez de rechazar) y terminando sin abrir jamás ninguna ventana modal.

### Caso F: Ceguera Inter-Procedural en `.then(fnNombrada)` y Estado Compartido (`C.estado()`)
- **Por qué el auditor v1.0 no vio las propiedades de Configuración**:
  - La v1.0 solo inspeccionaba funciones anónimas inline (`.then(function(d) { ... })`).
  - En `configuracion.js`, `C.estado()` guardaba `C._estado = d` y pasaba `estado` a funciones en **otros archivos** (`V.empresa = function(estado)`, `V.sucursales = function(estado)`), mientras que `configuracion_ventas.js` y `configuracion_eliminar.js` pasaban referencias a funciones nombradas (`.then(abrirEditor)`, `.then(abrirVentana)`).
  - Como consecuencia, la v1.0 reportó `Props: (sin lectura directa)` y no advirtió que `V.sucursales` exigía `limite.sucursales_disponibles`, `limite.sucursales_usadas`, `limite.max_sucursales` y ` V.categorias` exigía `c.parent_id` y `c.ruta`.

### Caso G: Inversión Semántica MIME en Wrappers de Descarga (`C.descargar`)
- **Qué ocurrió**: Las rutas `/api/configuracion/catalogo/generar/` y `/api/configuracion/plantilla/generar/` respondían `200 OK` con `c.json({ ok: true, nombre: "catalogo.pdf" })`.
- **Por qué falló**: El helper `C.descargar()` contiene la guarda inversa:
  ```javascript
  var tipo = r.headers.get("Content-Type") || "";
  if (!r.ok || tipo.indexOf("application/json") >= 0) {
    return r.json().then(function (d) { throw new Error(d.error || "No se pudo generar el archivo."); });
  }
  ```
  Para `C.descargar()`, **recibir JSON significa error de negocio**; requiere un cuerpo de archivo (`text/csv`, `text/html`, `application/octet-stream`) y las cabeceras `Content-Disposition`, `X-Catalogo-Archivo` y `X-Catalogo-Total`.

### Caso H: Botones Huérfanos (`sinPantalla: true`) y Caché de Service Worker (`sw.js`)
- Los botones `Moneda`, `Cliente por defecto` y `Etiqueta` tenían `sinPantalla: true` y carecían de modal en `P.ConfigVentanas`.
- Además, el Service Worker (`sw.js`) aplicaba *Cache-First* con `ignoreSearch: true` sobre `/static/`, impidiendo que el navegador descargara las correcciones de JavaScript hasta cambiar la estrategia a *Network-First* y actualizar `VERSION`.

---

## 3. Reglas Deterministas de `audit_api_contracts.py` v2.0

Para impedir que cualquiera de los Casos A–H vuelva a ocurrir en futuras reconstrucciones:
1. **Resolución Inter-Procedural**: El auditor resuelve funciones nombradas pasadas a `.then(fn)` y rastrea consumidores de estado compartido (`C.estado()`, `V.<id>(estado)`) entre múltiples archivos.
2. **Extracción de 1er y 2do Nivel + Iteradores**: Extrae `limite.sucursales_disponibles`, `categorias[].parent_id`, `tablas[].descripcion`, etc.
3. **Bloqueo de Compuertas de Permisos Vacías**: Extrae todas las claves `config_*` del frontend y falla con `exit(1)` si alguna no está definida en el servidor.
4. **Bloqueo de Respuestas JSON en Rutas `[DOWNLOAD]`**: Falla con `exit(1)` si una ruta invocada por `C.descargar()` devuelve `c.json()` sin `c.body()`.
5. **Bloqueo de Botones Huérfanos**: Falla con `exit(1)` si un botón con `sinPantalla: true` carece de handler en `ConfigVentanas`.
