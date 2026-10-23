# 🔬 Origen y Caso de Estudio: Por Qué Nació `backend-reverse-synthesis`

## 1. Contexto del Problema
Al trabajar con herramientas de ingeniería inversa de vanguardia como **REA v7.0.0** y el ecosistema **REPLICA**, es posible recuperar íntegramente el frontend de una aplicación (archivos JavaScript estáticos, plantillas HTML, sourcemaps, recursos de Electron `.asar` o paquetes móviles) incluso cuando el servidor original ya no existe.

Sin embargo, al intentar **recrear el backend funcional** para que el proyecto original operara exactamente igual que en su entorno nativo, surgió una cadena de fallos que reveló un patrón claro: **la reconstrucción basada en reinterpretación humana o heurística ("adivinar") produce errores silenciosos sistemáticos.**

---

## 2. Cronología de los Fallos por Ceguera y Adivinación (Evidencia Empírica)

Durante la reconstrucción inicial del backend para el sistema POS original (`posrea`), cada vez que se implementaba un endpoint "adivinando" su estructura a partir del nombre de la ruta, ocurría alguno de estos fallos:

### Caso A: "No puedo agregar proveedor" (Discrepancia de Contrato de Guardado y Consecutivos)
- **Qué se adivinó**: Se asumió que `GET /api/proveedores/` solo debía devolver `{ ok: true, proveedores: [...] }` y que `POST /api/proveedores/guardar/` recibía campos genéricos.
- **Qué exigía realmente el código cliente (`proveedores.js` / `crud.js`)**:
  - Requería `siguiente_codigo` (`PRV-0001`) tanto en el `GET` como en el `POST` para poblar y refrescar el formulario.
  - Requería el objeto singular `proveedor` de vuelta con exactamente las mismas propiedades (`empresa_id: 23`, `sucursal_id`, `activa: true`, `estado: "Activo"`).
  - Requería el endpoint `/api/proveedores/control/` para la vista de carpetas de proveedores.

### Caso B: "No existe sucursal en esa forma" (Ceguera ante Filtros Relacionales Silenciosos)
- **Qué se adivinó**: En `GET /api/admin/sucursales/`, el servidor devolvía `{ id: 1, codigo: "S-001", nombre: "Principal", activa: true }`. A simple vista parecía completo.
- **Qué hacía el código cliente (`inventario.js`)**:
  ```javascript
  var sucursalesEmpresa = (D.sucursales || []).filter(function (s) {
    return Number(s.empresa_id) === Number(empresaId);
  });
  ```
- **Por qué falló silenciosamente**: El HTML inicial (`index.html`) hidrataba la sesión con `empresa: { id: 23 }`. Como el endpoint omitió `empresa_id: 23`, `Number(undefined)` evaluó a `NaN`, `NaN === 23` dio `false`, y el selector `<select>` de sucursal en el formulario de productos quedó vacío (`"✓ Seleccionar sucursal..."`) sin emitir ningún error HTTP ni de consola.

### Caso C: "No hay rol en agregar usuarios" (Colisión Primitivo vs. Objeto Rico)
- **Qué se adivinó**: En `GET /api/configuracion/roles/`, se devolvió un arreglo plano de cadenas: `["Dueño", "Jefe de sucursal", "Supervisor", "Cajero", "Inventario"]`.
- **Qué hacía el código cliente (`usuario.js`)**:
  - El selector personalizado iteraba sobre `rolesCargados` accediendo a `r.id`, `r.nombre`, `r.es_dueno_empresa` y `r.es_jefe_sucursal`.
  - Al recibir strings planos, `r.id` y `r.nombre` eran `undefined`, renderizando opciones vacías e inutilizando el alta de usuarios.

### Caso D: Rutas Secundarias Ocultas tras Prefijos y Concatenaciones (Ceguera de `grep` Simple)
- **Qué se adivinó**: Un listado superficial de rutas `/api/` encontró 32 endpoints principales, dando la falsa ilusión de que el backend estaba completo.
- **Qué reveló el análisis estático determinista (`audit_api_contracts.py`)**:
  - Existían **77 rutas únicas** en los 115 puntos de llamada del frontend.
  - Rutas como `/api/configuracion/eliminar/estado/`, `/api/configuracion/eliminar/formatear/` o `/api/configuracion/eliminar/borrar-todo/` estaban construidas mediante una constante local `var URL_BASE = "/api/configuracion/eliminar/";` seguida de llamadas cortas `get("estado/")` y `post("formatear/")`.
  - Rutas como `/api/caja/ventas/:id/productos/:pid/anular/` o `/api/recibir/codigos/:id/producto/` estaban formadas por múltiples concatenaciones dinámicas.
  - Endpoints como `GET /api/caja/ventas/` leían propiedades booleanas de control de permisos (`data.puede_anular`) que, si se omitían, bloqueaban botones de la interfaz.

---

## 3. Principios Rectores del Skill `backend-reverse-synthesis`

Para que ningún agente ni desarrollador vuelva a caer en el ciclo de *"probar pantalla $\rightarrow$ encontrar fallo por adivinación $\rightarrow$ parchar endpoint"*, este Skill impone 4 leyes técnicas inquebrantables:

1. **Prohibición de Inferencia Heurística**:
   Nunca se escribe un endpoint basándose únicamente en su URL. Antes de implementarlo, se inspecciona obligatoriamente:
   - El payload enviado (2º argumento de la llamada HTTP y si usa `JSON` o `FormData`).
   - El callback `.then(function(res) { ... })` completo para enumerar cada propiedad leída de `res`.
   - Los filtros `.filter()` que consumen la colección resultante.

2. **Alineación Estricta con el Bootstrap SSR (`index.html`)**:
   Toda aplicación extraída tiene un estado semilla (IDs de empresa, sucursal, usuario y permisos). El backend reconstruido debe inyectar dinámicamente ese estado en el HTML desde la base de datos real y garantizar que todos los endpoints REST utilicen exactamente los mismos IDs de tenant/sucursal.

3. **Serializadores Canónicos Únicos**:
   Una entidad (`Producto`, `Sucursal`, `Usuario`, `Rol`, `Cliente`, `Proveedor`, `Venta`) tiene **una sola función serializadora** en el servidor que incluye la unión de todas las propiedades requeridas por todas las vistas del frontend.

4. **Auditoría Automatizada Obligatoria (`audit_api_contracts.py`)**:
   Ninguna reconstrucción de backend se da por concluida hasta que `scripts/audit_api_contracts.py` reporta **100.0% de cobertura de rutas (`0 [MISSING]`)** y todas las propiedades (`Props`) e invariantes (`.filter`) están satisfechos.
