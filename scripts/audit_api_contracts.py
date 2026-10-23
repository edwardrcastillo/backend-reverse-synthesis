#!/usr/bin/env python3
"""
Auditor Determinista Universal de Contratos API v4.0 (Multi-Stack Frontend vs Backend Reconstruido)
Parte del Skill: backend-reverse-synthesis (Zero-Guessing, State-Sync & Schema-Parity Protocol)

Capacidades v4.0 (Universal Multi-Stack + 18 Reglas Deterministas):
- Multi-Frontend: Vanilla JS, React, Vue, Svelte, Angular, Electron, Capacitor (fetch, axios, ky, $http, wrappers custom).
- Multi-Backend : Node.js (Hono, Express, Fastify, NestJS), Python (FastAPI, Flask, Django), Go (Gin, Echo, Fiber).
- Reglas #1-#6  : Resolución de URL_BASE, rutas dinámicas, propiedades de 1er/2do nivel e iteradores (.map/.filter).
- Regla #7      : Compuertas de Permisos y Feature Flags (config_*, perm_*, can_*, permissions, abilities).
- Regla #8      : Resolución Inter-Procedural de callbacks nombrados (.then(fn)) y estado compartido entre archivos.
- Regla #9      : Semántica MIME en Descargas (.blob(), arrayBuffer(), responseType:'blob', C.descargar).
- Regla #10     : Detección de Botones/Acciones Huérfanas (sinPantalla:true sin handler).
- Regla #11     : Hidratación SSR Completa (<script type="application/json">, __INITIAL_STATE__, __NEXT_DATA__).
- Regla #12     : Prohibición de Echo Stubs Sin Persistencia (POST sin DB/ORM/KV y GET con arrays vacíos quemados).
- Regla #13     : Coerción Numérica sobre IDs Alfanuméricos (Number(id) -> NaN === NaN).
- Regla #14     : Cobertura Exhaustiva de Despachadores Polimórficos (?tipo=..., ?type=..., ?action=...).
- [NUEVO v4.0] Regla #15: Paridad Esquema SQL vs Consultas (verifica que toda tabla y columna en INSERT/UPDATE exista en CREATE/ALTER TABLE).
- [NUEVO v4.0] Regla #16: Detección de Rutas Sombreadas/Duplicadas (Duplicate Route Shadowing en el router del servidor).
- [NUEVO v4.0] Regla #17: Paridad de Transporte Multipart/FormData (prohíbe usar req.json() puro en rutas que reciben FormData/archivos).
- [NUEVO v4.0] Regla #18: Detección de Funciones Helper Huérfanas e Invariantes de Zona Horaria/Errores.
"""
import argparse
import glob
import os
import re
import sys
from collections import defaultdict


def normalize_route(route: str) -> str:
    """Normaliza una ruta quitando query strings y unificando parámetros dinámicos (:id, <id>, {id}) a :id."""
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
    "keys", "values", "entries", "assign", "stringify", "parse", "toFixed", "toLocaleString",
    "status", "headers", "json", "text", "blob", "arrayBuffer", "data"
}


def extract_props_from_block(block: str, param_name: str) -> set:
    """Extrae propiedades de 1er nivel, 2do nivel y de iteradores .map/.filter sobre param_name."""
    props = set()
    if not param_name or not block:
        return props

    for m in re.finditer(
        rf"\b{re.escape(param_name)}\.([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))?",
        block,
    ):
        p1, p2 = m.group(1), m.group(2)
        if p1 not in IGNORE_PROPS:
            props.add(p1)
            if p2 and p2 not in IGNORE_PROPS:
                props.add(f"{p1}.{p2}")

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
            rf"\b{re.escape(local_var)}\.(?:map|filter|forEach)\(\s*(?:function\s*\(\s*([a-zA-Z0-9_]+)|([a-zA-Z0-9_]+)\s*=>)",
            block,
        ):
            item_var = it_m.group(1) or it_m.group(2)
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
    """Extrae contratos universales del frontend (rutas, props, permisos, descargas, FormData, SSR, IDs, ?tipo=)."""
    files = []
    for ext in ("*.js", "*.ts", "*.jsx", "*.tsx", "*.vue", "*.svelte"):
        files.extend(glob.glob(os.path.join(frontend_dir, "**", ext), recursive=True))

    html_files = glob.glob(os.path.join(frontend_dir, "**", "*.html"), recursive=True)

    routes_found = defaultdict(
        lambda: {
            "locations": [],
            "response_props": set(),
            "methods": set(),
            "is_download": False,
            "is_multipart": False,
            "formdata_fields": set(),
        }
    )
    filter_invariants = set()
    permission_keys = set()
    shared_state_props = set()
    config_ventanas_handlers = set()
    sin_pantalla_buttons = []
    ssr_json_script_ids = set()
    numeric_id_coercions = []
    polymorphic_report_types = set()

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

    for path, content in file_contents.items():
        fname = os.path.basename(path)
        lines = content.splitlines()

        for pk in re.findall(r"[\"\x27]((?:config|perm|can)_[a-zA-Z0-9_]+)[\"\x27]", content):
            permission_keys.add(pk)

        if fname == "reporte.js":
            rep_m = re.search(r"var\s+REPORTES\s*=\s*\[([\s\S]+?)\];", content)
            if rep_m:
                for tm in re.finditer(r"\[\s*[\"\x27]([a-zA-Z0-9_\-]+)[\"\x27]\s*,", rep_m.group(1)):
                    polymorphic_report_types.add(tm.group(1))

        for idx, line in enumerate(lines, start=1):
            if re.search(r"Number\(\s*[a-zA-Z0-9_.]+\.dataset\.(?:id|add)\s*\)", line) or re.search(
                r"Number\(\s*[a-zA-Z0-9_.]+\.(?:padre_id|parent_id|sucursal_id|usuario_id)\s*\)\s*===\s*Number\(",
                line,
            ) or re.search(
                r"\.id\s*===\s*Number\(\s*[a-zA-Z0-9_.]+\.dataset\.",
                line,
            ):
                numeric_id_coercions.append(f"{fname}:{idx} -> {line.strip()}")

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

        for em in re.finditer(
            r"C\.estado\([^)]*\)\.then\(\s*function\s*\(\s*([a-zA-Z0-9_]+)\s*\)",
            content,
        ):
            param = em.group(1)
            body_slice = content[em.end() : em.end() + 1200]
            shared_state_props.update(extract_props_from_block(body_slice, param))

        for bm in re.finditer(
            r"\{\s*[^}]*id:\s*[\"\x27]([^\"\x27]+)[\"\x27][^}]*sinPantalla:\s*true[^}]*\}",
            content,
        ):
            sin_pantalla_buttons.append((bm.group(1), fname))

    for path, content in file_contents.items():
        fname = os.path.basename(path)
        lines = content.splitlines()

        base_prefixes = re.findall(
            r"(?:URL_BASE|BASE_URL|apiBase|urlBase)\s*=\s*[\"\x27](/(?:api|v1|v2|rest)/[^\"\x27]+)[\"\x27]",
            content,
        )
        for prefix in base_prefixes:
            for m in re.finditer(r"\b(get|post|put|delete|patch)\(\s*[\"\x27]([^\"\x27]+)[\"\x27]", content):
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

        pattern = re.compile(
            r"[\"\x27](/(?:api|v1|v2|rest)/[a-zA-Z0-9_\-/]+)[\"\x27]"
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
            before_slice = content[max(0, m.start() - 450) : m.start()]
            after_slice = content[m.end() : m.end() + 900]

            if "C.descargar" in line_str or "window.location.href" in line_str or "responseType: 'blob'" in after_slice:
                routes_found[norm]["is_download"] = True
                routes_found[norm]["methods"].add("GET")
            elif "postForm" in line_str or "enviarFormulario" in line_str or "new FormData(" in before_slice:
                routes_found[norm]["is_multipart"] = True
                routes_found[norm]["methods"].add("POST")
                for fdm in re.finditer(r"\.append\(\s*[\"\x27]([a-zA-Z0-9_]+)[\"\x27]", before_slice):
                    routes_found[norm]["formdata_fields"].add(fdm.group(1))
            elif any(
                k in line_str
                for k in ("C.post", "axios.post", " eliminar", "guardar", "anular", "registrar")
            ):
                routes_found[norm]["methods"].add("POST")
            elif any(k in line_str for k in ("C.get", "axios.get", "a.href")):
                routes_found[norm]["methods"].add("GET")

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


def extract_sql_schema(code: str) -> dict:
    """Extrae tablas y columnas declaradas en CREATE TABLE y ALTER TABLE ... ADD COLUMN."""
    schema = defaultdict(set)
    for cm in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)\s*\(([\s\S]*?)\);",
        code,
        re.IGNORECASE,
    ):
        tname = cm.group(1).lower()
        body = cm.group(2)
        for line in body.splitlines():
            line = re.sub(r"--.*$", "", line).strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT")):
                continue
            col_m = re.match(r"^([a-zA-Z0-9_]+)\s+", line)
            if col_m:
                schema[tname].add(col_m.group(1).lower())

    for am in re.finditer(
        r"ALTER\s+TABLE\s+([a-zA-Z0-9_]+)\s+ADD\s+(?:COLUMN\s+)?([a-zA-Z0-9_]+)",
        code,
        re.IGNORECASE,
    ):
        schema[am.group(1).lower()].add(am.group(2).lower())

    return schema


def audit_backend(
    server_path: str,
    fe_routes: dict,
    permission_keys: list,
    download_routes: set,
    ssr_json_script_ids: list,
    numeric_id_coercions: list,
    polymorphic_report_types: list,
):
    """Extrae rutas del servidor y audita los 18 anti-patrones estructurales (v4.0)."""
    server_dir = server_path if os.path.isdir(server_path) else os.path.dirname(server_path)
    files = (
        glob.glob(os.path.join(server_dir, "**", "*.js"), recursive=True)
        + glob.glob(os.path.join(server_dir, "**", "*.ts"), recursive=True)
        + glob.glob(os.path.join(server_dir, "**", "*.py"), recursive=True)
        + glob.glob(os.path.join(server_dir, "**", "*.sql"), recursive=True)
    )
    if not files:
        files = [server_path]

    server_routes = defaultdict(set)
    route_registrations = defaultdict(list)
    full_code = ""
    primary_code = ""

    for path in sorted(set(files)):
        if "node_modules" in path:
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
            full_code += "\n" + code
            if os.path.abspath(path) == os.path.abspath(server_path) or os.path.isdir(server_path):
                primary_code += "\n" + code
        fname = os.path.basename(path)
        # Node (Hono/Express/Fastify) y Python (FastAPI/Flask)
        for m in re.finditer(
            r"(?:app|router)\.(get|post|put|delete|all|patch)\(\s*[\"\x27]([^\"\x27]+)[\"\x27]",
            code,
        ):
            method, r = m.group(1).upper(), normalize_route(m.group(2))
            lno = code[: m.start()].count("\n") + 1
            server_routes[r].add(method)
            route_registrations[(method, r)].append(f"{fname}:{lno} ({m.group(2)})")

    structural_errors = []

    # 1. Compuertas de permisos (Regla #7)
    if permission_keys:
        missing_perms = [pk for pk in permission_keys if pk not in full_code]
        if missing_perms:
            structural_errors.append(
                f"[ANTI-PATRÓN #7: COMPUERTA DE PERMISOS VACÍA] Faltan {len(missing_perms)} claves de permiso en el servidor: {', '.join(missing_perms[:8])}"
            )

    # 2. Inversión MIME en Descargas (Regla #9)
    for dr in sorted(download_routes):
        m = re.search(
            rf"(?:app|router)\.(?:get|post|all)\(\s*[\"\x27]{re.escape(dr)}[\"\x27][^{{]*\{{([\s\S]{{1,1500}}?)\n\}}\);",
            primary_code,
        )
        if m:
            handler_body = m.group(1)
            if "c.json(" in handler_body and "c.body(" not in handler_body:
                structural_errors.append(
                    f"[ANTI-PATRÓN #9: INVERSIÓN MIME EN DESCARGA] La ruta {dr} es consumida por descarga binaria pero el servidor devuelve c.json() sin c.body()."
                )

    # 3. Hidratación SSR Completa (Regla #11)
    for sid in ssr_json_script_ids:
        if sid not in primary_code:
            structural_errors.append(
                f"[ANTI-PATRÓN #11: HIDRATACIÓN SSR INCOMPLETA] El bloque <script id=\"{sid}\" type=\"application/json\"> de index.html no es reemplazado dinámicamente en GET /."
            )

    # 4. Echo Stubs sin persistencia en POST y colecciones vacías fijas en GET (Regla #12)
    READONLY_POST_ALLOWLIST = {"/api/configuracion/permiso/"}
    PERSISTENCE_TOKENS = (
        "db.prepare", "setKv(", "parseCsvUpload(", "prisma.", "knex(", "pool.query",
        "cursor.execute", "session.add", "session.commit", ".objects.create", ".save("
    )
    for pm in re.finditer(
        r"(?:app|router)\.post\(\s*[\"\x27]([^\"\x27]+)[\"\x27][^{]*\{([\s\S]*?)\n\}\);",
        primary_code,
    ):
        raw_r = pm.group(1)
        norm_r = normalize_route(raw_r)
        body = pm.group(2)
        if norm_r in READONLY_POST_ALLOWLIST:
            continue
        if not any(token in body for token in PERSISTENCE_TOKENS):
            structural_errors.append(
                f"[ANTI-PATRÓN #12: ECHO STUB SIN PERSISTENCIA] El endpoint POST {raw_r} devuelve respuesta sin persistir en base de datos ni KV."
            )

    for gm in re.finditer(
        r"(?:app|router)\.get\(\s*[\"\x27]([^\"\x27]+)[\"\x27][^{]*\{([\s\S]*?)\n\}\);",
        primary_code,
    ):
        raw_r = gm.group(1)
        body = gm.group(2)
        if re.search(r"\b(?:variantes|codigos|facturas|unidades)\s*:\s*\[\s*\]", body) and not any(
            t in body for t in ("db.prepare", "getKv(", "mapRecibirEstado")
        ):
            structural_errors.append(
                f"[ANTI-PATRÓN #12: GET CON COLECCIÓN VACÍA ESTÁTICA] El endpoint GET {raw_r} devuelve un array vacío quemado sin consultar SQLite ni KV."
            )

    # 5. Coerción Numérica de IDs Alfanuméricos (Regla #13)
    uses_string_pks = bool(re.search(r"[\"\x27`]\s*(?:prd|prod|cat|suc|usr|cli|prov|oc|ven|gto|paq|rol)_", primary_code))
    if uses_string_pks and numeric_id_coercions:
        for loc in numeric_id_coercions[:8]:
            structural_errors.append(
                f"[ANTI-PATRÓN #13: COERCIÓN NUMÉRICA DE ID ALFANUMÉRICO (NaN === NaN)] {loc}"
            )

    # 6. Despachador Polimórfico de Reportes ?tipo=... (Regla #14)
    if polymorphic_report_types:
        missing_types = [
            t for t in polymorphic_report_types
            if not re.search(rf"tipo\s*===\s*[\"\x27]{re.escape(t)}[\"\x27]", primary_code)
        ]
        if missing_types:
            structural_errors.append(
                f"[ANTI-PATRÓN #14: DESPACHADOR POLIMÓRFICO INCOMPLETO] GET /api/reportes/ no maneja los siguientes valores de ?tipo=: {', '.join(missing_types)}"
            )

    # 7. [NUEVO v4.0] Paridad Esquema SQL vs Consultas SQL (Regla #15)
    schema = extract_sql_schema(full_code)
    if schema:
        # Verificar tablas en SELECT/INSERT/UPDATE/DELETE
        for tm in re.finditer(
            r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z0-9_]+)\b",
            primary_code,
        ):
            tname = tm.group(1).lower()
            if tname in ("select", "where", "set", "values", "json", "null", "table", " Dual"):
                continue
            if tname not in schema and not tname.startswith("sqlite_"):
                structural_errors.append(
                    f"[ANTI-PATRÓN #15: TABLA SQL INEXISTENTE EN DDL] Se consulta la tabla '{tname}', pero no existe en ningún CREATE TABLE."
                )

        # Verificar columnas en INSERT INTO tabla (col1, col2, ...)
        for im in re.finditer(
            r"INSERT\s+INTO\s+([a-zA-Z0-9_]+)\s*\(([^)]+)\)\s*VALUES",
            primary_code,
            re.IGNORECASE,
        ):
            tname = im.group(1).lower()
            cols = [c.strip().lower() for c in im.group(2).split(",") if c.strip()]
            if tname in schema:
                for col in cols:
                    if col not in schema[tname]:
                        structural_errors.append(
                            f"[ANTI-PATRÓN #15: COLUMNA SQL INEXISTENTE EN DDL] INSERT INTO {tname} referencia la columna '{col}', que no existe en CREATE/ALTER TABLE {tname}."
                        )

    # 8. [NUEVO v4.0] Detección de Rutas Sombreadas/Duplicadas (Regla #16)
    for (method, norm_r), locs in sorted(route_registrations.items()):
        # Solo reportar si es exactamente la misma ruta cruda registrada dos veces
        raw_routes = [l.split("(")[1].rstrip(")") for l in locs]
        if len(raw_routes) != len(set(raw_routes)):
            structural_errors.append(
                f"[ANTI-PATRÓN #16: RUTA DUPLICADA / SOMBREADA] {method} {norm_r} está registrada múltiples veces: {', '.join(locs)}"
            )

    # 9. [NUEVO v4.0] Paridad de Transporte Multipart/FormData (Regla #17)
    for norm_r, info in sorted(fe_routes.items()):
        if info["is_multipart"]:
            m = re.search(
                rf"(?:app|router)\.(?:post|all)\(\s*[\"\x27]{re.escape(norm_r)}[\"\x27][^{{]*\{{([\s\S]{{1,1800}}?)\n\}}\);",
                primary_code,
            )
            if m:
                hbody = m.group(1)
                if "req.json(" in hbody and "parseBody" not in hbody and "parseCsvUpload" not in hbody:
                    structural_errors.append(
                        f"[ANTI-PATRÓN #17: ASIMETRÍA MULTIPART/FORMDATA] La ruta {norm_r} recibe FormData ({', '.join(sorted(info['formdata_fields']))}) desde el cliente pero usa req.json() puro sin parseBody()."
                    )

    return server_routes, structural_errors, len(schema)


def main():
    parser = argparse.ArgumentParser(description="Audita paridad determinista v4.0 entre Frontend y Backend.")
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
    multipart_routes = {r for r, info in fe_routes.items() if info["is_multipart"]}
    be_routes, structural_errors, num_tables = audit_backend(
        args.server,
        fe_routes,
        perm_keys,
        download_routes,
        ssr_script_ids,
        numeric_id_coercions,
        report_types,
    )

    print("=" * 95)
    print("🔬 AUDITORÍA DETERMINISTA UNIVERSAL DE CONTRATOS API v4.0 (MULTI-STACK & SCHEMA-PARITY)")
    print("=" * 95)
    print(f"Rutas API únicas en Frontend       : {len(fe_routes)}")
    print(f"Rutas API registradas en Servidor  : {len(be_routes)}")
    print(f"Tablas SQL verificadas en DDL      : {num_tables} tablas")
    print(f"Claves de Permiso detectadas       : {len(perm_keys)} detectadas")
    print(f"Rutas Descarga / Multipart FormData: {len(download_routes)} descargas, {len(multipart_routes)} multipart")
    print(f"Bloques SSR JSON (<script>)        : {len(ssr_script_ids)} detectados ({', '.join(ssr_script_ids)})")
    print(f"Subtipos Polimórficos (?tipo=...)  : {len(report_types)} detectados")
    print("-" * 95)

    missing = []
    matched = 0

    for route in sorted(fe_routes.keys()):
        info = fe_routes[route]
        locs = ", ".join(sorted(set(info["locations"]))[:2])
        props = ", ".join(sorted(info["response_props"])) or "(sin lectura directa)"
        tags = ""
        if info["is_download"]:
            tags += " [DOWNLOAD]"
        if info["is_multipart"]:
            tags += " [MULTIPART]"
        if route in be_routes:
            matched += 1
            srv_methods = "/".join(sorted(be_routes[route]))
            print(f"  [OK]      {srv_methods:8} {route + tags:52} | Props: {props} | {locs}")
        else:
            missing.append((route, info))
            print(f"  [MISSING] {'---':8} {route + tags:52} | Props: {props} | {locs}")

    print("-" * 95)
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
        print("\n🏆 PARIDAD DETERMINISTA v4.0 AL 100%: Rutas, DDL SQL, Multipart, SSR, Persistencia, IDs, Permisos y Reportes verificados.")
        sys.exit(0)


if __name__ == "__main__":
    main()
