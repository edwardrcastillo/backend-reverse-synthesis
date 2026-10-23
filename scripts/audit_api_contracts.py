#!/usr/bin/env python3
"""
Auditor Determinista de Contratos API v3.0 (Frontend Extraído vs Backend Reconstruido)
Parte del Skill: backend-reverse-synthesis (Zero-Guessing Protocol)

Capacidades v3.0 (Anti-Ceguera Estructural y Anti-Desincronización de Estado):
1. Resolución de URL_BASE, rutas relativas y concatenaciones dinámicas.
2. Resolución inter-procedural:
   - Callbacks nombrados en promesas: .then(abrirEditor) -> analiza function abrirEditor(datos)
   - Propagación de estado compartido: C.estado() -> analiza V.<modal> = function(estado) en otros archivos
3. Extracción de propiedades de 1er y 2do nivel (ej. limite.sucursales_disponibles) e ítems en .map()/.filter().
4. Auditoría de Compuertas de Permisos (Permission Gates): extrae claves 'config_*' del frontend y prohíbe 'permisos: {}' en el backend.
5. Auditoría de Semántica MIME en Descargas (C.descargar): prohíbe que rutas de descarga devuelvan solo c.json().
6. Detección de botones huérfanos (sinPantalla: true sin handler en ConfigVentanas).
7. [NUEVO v3.0] Auditoría de Hidratación SSR Completa: verifica que TODOS los bloques <script id="..." type="application/json"> de index.html sean inyectados dinámicamente en GET /.
8. [NUEVO v3.0] Detección de Echo Stubs Sin Persistencia: verifica que todo endpoint POST de mutación escriba en SQLite (db.prepare) o KV (setKv), y prohíbe GETs con arreglos vacíos estáticos (facturas: [], codigos: [], variantes: [], unidades: []).
9. [NUEVO v3.0] Detección de Coerción Numérica sobre IDs Alfanuméricos (Number(id) -> NaN === NaN): detecta comparaciones Number(x.id) === Number(y.id) o Number(dataset.id) en el frontend cuando el backend usa PKs de texto (prd_, cat_, suc_, usr_).
10. [NUEVO v3.0] Auditoría de Despachadores Polimórficos (?tipo=...): extrae todas las claves de catálogos/reportes (ej. TIPOS en reporte.js) y verifica que cada clave sea atendida explícitamente en el backend.
"""
import argparse
import glob
import os
import re
import sys
from collections import defaultdict


def normalize_route(route: str) -> str:
    """Normaliza una ruta quitando query strings y unificando parámetros dinámicos a :id."""
    route = route.split("?")[0].strip()
    route = re.sub(r"//+", "/", route)
    route = re.sub(r":[a-zA-Z0-9_]+", ":id", route)
    route = re.sub(r"<[^>]+>", ":id", route)
    route = re.sub(r"\{[^}]+\}", ":id", route)
    if not route.startswith("/"):
        route = "/" + route
    return route


IGNORE_PROPS = {
    "length", "forEach", "map", "filter", "slice", "join", "then", "catch",
    "reduce", "some", "every", "indexOf", "includes", "trim", "toLowerCase",
    "toUpperCase", "replace", "split", "push", "pop", "shift", "splice", "concat",
    "keys", "values", "entries", "assign", "stringify", "parse", "toFixed", "toLocaleString"
}


def extract_props_from_block(block: str, param_name: str) -> set:
    """Extrae propiedades de 1er nivel, 2do nivel y de iteradores .map/.filter sobre param_name."""
    props = set()
    if not param_name or not block:
        return props

    # 1er y 2do nivel directo: param.prop y param.prop.subprop
    for m in re.finditer(
        rf"\b{re.escape(param_name)}\.([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?",
        block,
    ):
        p1, p2 = m.group(1), m.group(2)
        if p1 not in IGNORE_PROPS:
            props.add(p1)
            if p2 and p2 not in IGNORE_PROPS:
                props.add(f"{p1}.{p2}")

    # Alias locales: var x = param.prop || ...
    for alias_m in re.finditer(
        rf"(?:var|let|const)?\s*([a-zA-Z0-9_]+)\s*=\s*(?:\({re.escape(param_name)}\.([a-zA-Z0-9_]+)\s*\|\|\s*\[\]\)|{re.escape(param_name)}\.([a-zA-Z0-9_]+))",
        block,
    ):
        local_var = alias_m.group(1)
        source_prop = alias_m.group(2) or alias_m.group(3)
        if source_prop in IGNORE_PROPS:
            continue
        props.add(source_prop)
        for sub_m in re.finditer(rf"\b{re.escape(local_var)}\.([a-zA-Z0-9_]+)", block):
            sub_p = sub_m.group(1)
            if sub_p not in IGNORE_PROPS:
                props.add(f"{source_prop}.{sub_p}")
        for it_m in re.finditer(
            rf"\b{re.escape(local_var)}\.(?:map|filter|forEach)\(\s*function\s*\(\s*([a-zA-Z0-9_]+)",
            block,
        ):
            item_var = it_m.group(1)
            it_slice = block[it_m.end() : it_m.end() + 600]
            for item_p in re.finditer(rf"\b{re.escape(item_var)}\.([a-zA-Z0-9_]+)", it_slice):
                ip = item_p.group(1)
                if ip not in IGNORE_PROPS:
                    props.add(f"{source_prop}[].{ip}")

    return props


def find_named_function_body(content: str, fn_name: str):
    """Busca function fn_name(param) { ... } y retorna (param, body_slice)."""
    m = re.search(
        rf"function\s+{re.escape(fn_name)}\s*\(\s*([a-zA-Z0-9_]+)\s*(?:,[^)]*)?\)\s*\{{",
        content,
    )
    if not m:
        return None, None
    param = m.group(1)
    return param, content[m.end() : m.end() + 4500]


def extract_frontend_contracts(frontend_dir: str):
    """Extrae rutas, métodos, propiedades directas/indirectas, compuertas de permisos, descargas, SSR scripts, Number(id) y ?tipo=."""
    files = []
    for ext in ("*.js", "*.ts", "*.jsx", "*.tsx", "*.vue", "*.svelte"):
        files.extend(glob.glob(os.path.join(frontend_dir, "**", ext), recursive=True))

    html_files = glob.glob(os.path.join(frontend_dir, "**", "*.html"), recursive=True)

    routes_found = defaultdict(
        lambda: {"locations": [], "response_props": set(), "methods": set(), "is_download": False}
    )
    filter_invariants = set()
    permission_keys = set()
    shared_state_props = set()
    config_ventanas_handlers = set()
    sin_pantalla_buttons = []
    ssr_json_script_ids = set()
    numeric_id_coercions = []
    polymorphic_report_types = set()

    # Extraer bloques <script id="..." type="application/json"> de los HTML
    for hpath in sorted(set(html_files)):
        try:
            with open(hpath, "r", encoding="utf-8", errors="ignore") as f:
                hcontent = f.read()
            for sm in re.finditer(
                r'<script[^>]+id=["\x27]([^"\x27]+)["\x27][^>]+type=["\x27]application/json["\x27]',
                hcontent,
            ):
                ssr_json_script_ids.add(sm.group(1))
        except Exception:
            continue

    file_contents = {}
    for path in sorted(set(files)):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                file_contents[path] = f.read()
        except Exception:
            continue

    # Primera pasada: recolectar handlers de ConfigVentanas, claves de permisos, coerciones Number(id) y tipos de reportes
    for path, content in file_contents.items():
        fname = os.path.basename(path)
        lines = content.splitlines()

        # Claves de permiso config_*
        for pk in re.findall(r"[\"\x27](config_[a-zA-Z0-9_]+)[\"\x27]", content):
            permission_keys.add(pk)

        # Extraer claves de REPORTES / CFG en reporte.js (despachador polimórfico ?tipo=...)
        if fname == "reporte.js":
            rep_m = re.search(r"var\s+REPORTES\s*=\s*\[([\s\S]+?)\];", content)
            if rep_m:
                for tm in re.finditer(r"\[\s*[\"\x27]([a-zA-Z0-9_\-]+)[\"\x27]\s*,", rep_m.group(1)):
                    polymorphic_report_types.add(tm.group(1))

        # Detectar coerciones peligrosas Number(...) sobre IDs de entidades o dataset.id / dataset.add
        for idx, line in enumerate(lines, start=1):
            if re.search(r"Number\(\s*[a-zA-Z0-9_.]+\.dataset\.(?:id|add)\s*\)", line) or re.search(
                r"Number\(\s*[a-zA-Z0-9_.]+\.(?:padre_id|parent_id|sucursal_id|usuario_id)\s*\)\s*===\s*Number\(",
                line,
            ) or re.search(
                r"\.id\s*===\s*Number\(\s*[a-zA-Z0-9_.]+\.dataset\.",
                line,
            ):
                numeric_id_coercions.append(f"{fname}:{idx} -> {line.strip()}")

        # Handlers registrados en V.<id> = function(estado) o P.ConfigVentanas.<id>
        for vm in re.finditer(
            r"(?:V|ConfigVentanas)(?:\.([a-zA-Z0-9_]+)|\[\s*[\"\x27]([^\"\x27]+)[\"\x27]\s*\])\s*=\s*function\s*\(\s*([a-zA-Z0-9_]*)\s*\)",
            content,
        ):
            vid = vm.group(1) or vm.group(2)
            param = vm.group(3)
            config_ventanas_handlers.add(vid)
            if param:
                body_slice = content[vm.end() : vm.end() + 5000]
                shared_state_props.update(extract_props_from_block(body_slice, param))

        # C.estado(...).then(function(estado) { ... })
        for em in re.finditer(
            r"C\.estado\([^)]*\)\.then\(\s*function\s*\(\s*([a-zA-Z0-9_]+)\s*\)",
            content,
        ):
            param = em.group(1)
            body_slice = content[em.end() : em.end() + 1200]
            shared_state_props.update(extract_props_from_block(body_slice, param))

        # Botones con sinPantalla: true
        for bm in re.finditer(
            r"\{\s*[^}]*id:\s*[\"\x27]([^\"\x27]+)[\"\x27][^}]*sinPantalla:\s*true[^}]*\}",
            content,
        ):
            sin_pantalla_buttons.append((bm.group(1), fname))

    # Segunda pasada: extraer rutas y contratos por endpoint
    for path, content in file_contents.items():
        fname = os.path.basename(path)
        lines = content.splitlines()

        # 1. Detectar URL_BASE locales
        base_prefixes = re.findall(
            r"(?:URL_BASE|BASE_URL|apiBase|urlBase)\s*=\s*[\"\x27](/api/[^\"\x27]+)[\"\x27]",
            content,
        )
        for prefix in base_prefixes:
            for m in re.finditer(r"\b(get|post)\(\s*[\"\x27]([^\"\x27]+)[\"\x27]", content):
                verb, sub = m.group(1).upper(), m.group(2)
                if not sub.startswith("/"):
                    full_route = normalize_route(prefix + sub)
                    lno = content[: m.start()].count("\n") + 1
                    routes_found[full_route]["locations"].append(f"{fname}:{lno}")
                    routes_found[full_route]["methods"].add(verb)

                    after_slice = content[m.end() : m.end() + 600]
                    inl = re.search(
                        r"\.then\(\s*(?:function\s*\(\s*([a-zA-Z0-9_]+)\s*\)|([a-zA-Z0-9_]+)\s*=>)",
                        after_slice,
                    )
                    if inl:
                        pname = inl.group(1) or inl.group(2)
                        routes_found[full_route]["response_props"].update(
                            extract_props_from_block(after_slice[inl.end() : inl.end() + 1200], pname)
                        )
                    named = re.search(r"\.then\(\s*([a-zA-Z0-9_]+)\s*[,)]", after_slice)
                    if named and named.group(1) != "function":
                        fn_param, fn_body = find_named_function_body(content, named.group(1))
                        if fn_param and fn_body:
                            routes_found[full_route]["response_props"].update(
                                extract_props_from_block(fn_body, fn_param)
                            )

        # 2. Detectar expresiones con "/api/..." incluyendo concatenaciones dinámicas
        pattern = re.compile(
            r"[\"\x27](/api/[a-zA-Z0-9_\-/]+)[\"\x27]"
            r"(?:\s*\+\s*(?:encodeURIComponent\([^)]+\)|[a-zA-Z0-9_.]+)\s*\+\s*[\"\x27](/[a-zA-Z0-9_\-/]*)[\"\x27])?"
            r"(?:\s*\+\s*(?:encodeURIComponent\([^)]+\)|[a-zA-Z0-9_.]+)\s*\+\s*[\"\x27](/[a-zA-Z0-9_\-/]*)[\"\x27])?"
        )

        for m in pattern.finditer(content):
            p1, p2, p3 = m.group(1), m.group(2), m.group(3)
            if p1.endswith("-"):
                continue
            raw_route = p1
            if p2:
                raw_route += "/:id" + p2
            if p3:
                raw_route += "/:id" + p3

            norm = normalize_route(raw_route)
            if norm in ("/api/", "/api/configuracion/eliminar/"):
                continue

            lno = content[: m.start()].count("\n") + 1
            routes_found[norm]["locations"].append(f"{fname}:{lno}")

            line_str = lines[lno - 1] if lno <= len(lines) else ""
            if "C.descargar" in line_str or "window.location.href" in line_str:
                routes_found[norm]["is_download"] = True
                routes_found[norm]["methods"].add("GET")
            elif any(
                k in line_str
                for k in ("C.post", "postForm", "enviarFormulario", "eliminar", "guardar", "anular", "registrar")
            ):
                routes_found[norm]["methods"].add("POST")
            elif any(k in line_str for k in ("C.get", "a.href")):
                routes_found[norm]["methods"].add("GET")

            after_slice = content[m.end() : m.end() + 900]
            then_match = re.search(
                r"\.then\(\s*(?:function\s*\(\s*([a-zA-Z0-9_]+)\s*\)|([a-zA-Z0-9_]+)\s*=>)",
                after_slice,
            )
            if then_match:
                param_name = then_match.group(1) or then_match.group(2)
                body_slice = after_slice[then_match.end() : then_match.end() + 1200]
                routes_found[norm]["response_props"].update(
                    extract_props_from_block(body_slice, param_name)
                )

            named_match = re.search(r"\.then\(\s*([a-zA-Z0-9_]+)\s*[,)]", after_slice)
            if named_match and named_match.group(1) != "function":
                fn_param, fn_body = find_named_function_body(content, named_match.group(1))
                if fn_param and fn_body:
                    routes_found[norm]["response_props"].update(
                        extract_props_from_block(fn_body, fn_param)
                    )

        # 3. Extraer invariantes .filter(...) sobre colecciones
        for fm in re.finditer(
            r"\.filter\(\s*function\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*\{([^}]{1,200})\}",
            content,
        ):
            var_name, fbody = fm.group(1), fm.group(2)
            for pm in re.finditer(rf"\b{re.escape(var_name)}\.([a-zA-Z0-9_]+)", fbody):
                prop = pm.group(1)
                if prop not in IGNORE_PROPS:
                    filter_invariants.add(f"{fname}: {var_name}.{prop}")

    if "/api/configuracion/general/estado/" in routes_found and shared_state_props:
        routes_found["/api/configuracion/general/estado/"]["response_props"].update(shared_state_props)

    dead_buttons = [
        (bid, loc) for (bid, loc) in sin_pantalla_buttons if bid not in config_ventanas_handlers
    ]

    return (
        routes_found,
        sorted(filter_invariants),
        sorted(permission_keys),
        dead_buttons,
        sorted(ssr_json_script_ids),
        numeric_id_coercions,
        sorted(polymorphic_report_types),
    )


def audit_backend(
    server_path: str,
    permission_keys: list,
    download_routes: set,
    ssr_json_script_ids: list,
    numeric_id_coercions: list,
    polymorphic_report_types: list,
):
    """Extrae rutas del servidor y audita los 14 anti-patrones estructurales (v3.0)."""
    if os.path.isdir(server_path):
        files = glob.glob(os.path.join(server_path, "**", "*.js"), recursive=True) + glob.glob(
            os.path.join(server_path, "**", "*.py"), recursive=True
        )
    else:
        files = [server_path]

    server_routes = defaultdict(set)
    full_code = ""
    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
            full_code += "\n" + code
        for m in re.finditer(
            r"(?:app|router)\.(get|post|put|delete|all|patch)\(\s*[\"\x27]([^\"\x27]+)[\"\x27]",
            code,
        ):
            method, r = m.group(1).upper(), normalize_route(m.group(2))
            server_routes[r].add(method)

    structural_errors = []

    # 1. Auditar compuertas de permisos: prohibir permisos: {} en /api/configuracion/general/estado/
    if permission_keys:
        missing_perms = [pk for pk in permission_keys if pk not in full_code]
        if missing_perms:
            structural_errors.append(
                f"[ANTI-PATRÓN #7: COMPUERTA DE PERMISOS VACÍA] Faltan {len(missing_perms)} claves de permiso en el servidor: {', '.join(missing_perms[:8])}"
            )

    # 2. Auditar rutas de descarga (C.descargar rechaza Content-Type: application/json)
    for dr in sorted(download_routes):
        m = re.search(
            rf"(?:app|router)\.(?:get|post|all)\(\s*[\"\x27]{re.escape(dr)}[\"\x27][^{{]*\{{([\s\S]{{1,1500}}?)\n\}}\);",
            full_code,
        )
        if m:
            handler_body = m.group(1)
            if "c.json(" in handler_body and "c.body(" not in handler_body:
                structural_errors.append(
                    f"[ANTI-PATRÓN #9: INVERSIÓN MIME EN DESCARGA] La ruta {dr} es consumida por C.descargar() pero el servidor devuelve c.json() sin c.body() binario/CSV."
                )

    # 3. [NUEVO v3.0] Auditar Hidratación SSR Completa (<script id="..." type="application/json">)
    for sid in ssr_json_script_ids:
        if sid not in full_code:
            structural_errors.append(
                f"[ANTI-PATRÓN #11: HIDRATACIÓN SSR INCOMPLETA] El bloque <script id=\"{sid}\" type=\"application/json\"> de index.html no es reemplazado dinámicamente por el servidor en GET /."
            )

    # 4. [NUEVO v3.0] Auditar Echo Stubs sin persistencia en POST y colecciones vacías fijas en GET
    READONLY_POST_ALLOWLIST = {"/api/configuracion/permiso/"}
    for pm in re.finditer(
        r"(?:app|router)\.post\(\s*[\"\x27]([^\"\x27]+)[\"\x27][^{]*\{([\s\S]*?)\n\}\);",
        full_code,
    ):
        raw_r = pm.group(1)
        norm_r = normalize_route(raw_r)
        body = pm.group(2)
        if norm_r in READONLY_POST_ALLOWLIST:
            continue
        has_persistence = any(
            token in body
            for token in ("db.prepare", "setKv(", "parseCsvUpload(")
        )
        if not has_persistence:
            structural_errors.append(
                f"[ANTI-PATRÓN #12: ECHO STUB SIN PERSISTENCIA] El endpoint POST {raw_r} devuelve respuesta exitosa sin persistir en SQLite (db.prepare) ni en KV (setKv)."
            )

    # Verificar que no existan retornos estáticos vacíos en GET (ej. variantes: [], codigos: [], facturas: [], unidades: [])
    for gm in re.finditer(
        r"(?:app|router)\.get\(\s*[\"\x27]([^\"\x27]+)[\"\x27][^{]*\{([\s\S]*?)\n\}\);",
        full_code,
    ):
        raw_r = gm.group(1)
        body = gm.group(2)
        if re.search(r"\b(?:variantes|codigos|facturas|unidades)\s*:\s*\[\s*\]", body) and not any(
            t in body for t in ("db.prepare", "getKv(", "mapRecibirEstado")
        ):
            structural_errors.append(
                f"[ANTI-PATRÓN #12: GET CON COLECCIÓN VACÍA ESTÁTICA] El endpoint GET {raw_r} devuelve un array vacío quemado sin consultar SQLite ni KV."
            )

    # 5. [NUEVO v3.0] Auditar Coerción Numérica de IDs Alfanuméricos (Number(id) -> NaN === NaN)
    uses_string_pks = bool(re.search(r"[\"\x27`]\s*(?:prd|prod|cat|suc|usr|cli|prov|oc|ven|gto|paq|rol)_", full_code))
    if uses_string_pks and numeric_id_coercions:
        for loc in numeric_id_coercions[:8]:
            structural_errors.append(
                f"[ANTI-PATRÓN #13: COERCIÓN NUMÉRICA DE ID ALFANUMÉRICO (NaN === NaN)] {loc}"
            )

    # 6. [NUEVO v3.0] Auditar Despachador Polimórfico de Reportes (?tipo=...)
    if polymorphic_report_types:
        missing_types = [
            t for t in polymorphic_report_types
            if not re.search(rf"tipo\s*===\s*[\"\x27]{re.escape(t)}[\"\x27]", full_code)
        ]
        if missing_types:
            structural_errors.append(
                f"[ANTI-PATRÓN #14: DESPACHADOR POLIMÓRFICO INCOMPLETO] GET /api/reportes/ no maneja los siguientes valores de ?tipo=: {', '.join(missing_types)}"
            )

    return server_routes, structural_errors


def main():
    parser = argparse.ArgumentParser(description="Audita paridad determinista v3.0 entre Frontend y Backend.")
    parser.add_argument("--frontend", required=True, help="Directorio del código frontend extraído")
    parser.add_argument("--server", required=True, help="Archivo o directorio del servidor backend")
    args = parser.parse_args()

    (
        fe_routes,
        invariants,
        perm_keys,
        dead_buttons,
        ssr_script_ids,
        numeric_id_coercions,
        report_types,
    ) = extract_frontend_contracts(args.frontend)
    download_routes = {r for r, info in fe_routes.items() if info["is_download"]}
    be_routes, structural_errors = audit_backend(
        args.server,
        perm_keys,
        download_routes,
        ssr_script_ids,
        numeric_id_coercions,
        report_types,
    )

    print("=" * 90)
    print("🔬 AUDITORÍA DETERMINISTA DE CONTRATOS API v3.0 (ZERO-GUESSING & STATE-SYNC PROTOCOL)")
    print("=" * 90)
    print(f"Rutas API únicas en Frontend       : {len(fe_routes)}")
    print(f"Rutas API registradas en Servidor  : {len(be_routes)}")
    print(f"Claves de Permiso (config_*)       : {len(perm_keys)} detectadas")
    print(f"Rutas de Descarga Binaria/Archivo  : {len(download_routes)} detectadas")
    print(f"Bloques SSR JSON (<script>)        : {len(ssr_script_ids)} detectados ({', '.join(ssr_script_ids)})")
    print(f"Subtipos Polimórficos (?tipo=...)  : {len(report_types)} detectados en reportes")
    print("-" * 90)

    missing = []
    matched = 0

    for route in sorted(fe_routes.keys()):
        info = fe_routes[route]
        locs = ", ".join(sorted(set(info["locations"]))[:2])
        props = ", ".join(sorted(info["response_props"])) or "(sin lectura directa)"
        dl_tag = " [DOWNLOAD]" if info["is_download"] else ""
        if route in be_routes:
            matched += 1
            srv_methods = "/".join(sorted(be_routes[route]))
            print(f"  [OK]      {srv_methods:8} {route + dl_tag:48} | Props: {props} | {locs}")
        else:
            missing.append((route, info))
            print(f"  [MISSING] {'---':8} {route + dl_tag:48} | Props: {props} | {locs}")

    print("-" * 90)
    print(f"📊 Cobertura de Rutas: {matched}/{len(fe_routes)} ({(matched / max(1, len(fe_routes))) * 100:.1f}%)")

    if dead_buttons:
        for bid, loc in dead_buttons:
            structural_errors.append(
                f"[ANTI-PATRÓN #10: BOTÓN HUÉRFANO] El botón '{bid}' ({loc}) tiene sinPantalla:true y carece de handler en P.ConfigVentanas."
            )

    if structural_errors:
        print("\n🚨 VIOLACIONES ESTRUCTURALES DETECTADAS:")
        for err in structural_errors:
            print(f"  ❌ {err}")

    if missing or structural_errors:
        print(f"\n❌ AUDITORÍA FALLIDA: {len(missing)} rutas faltantes, {len(structural_errors)} violaciones estructurales.")
        sys.exit(1)
    else:
        print("\n🏆 PARIDAD DETERMINISTA v3.0 AL 100%: Rutas, SSR, persistencia SQL/KV, IDs alfanuméricos, permisos y reportes verificados.")
        sys.exit(0)


if __name__ == "__main__":
    main()
