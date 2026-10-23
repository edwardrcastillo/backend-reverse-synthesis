#!/usr/bin/env python3
"""
Auditor Determinista de Contratos API (Frontend Extraído vs Backend Reconstruido)
Parte del Skill: backend-reverse-synthesis (Zero-Guessing Protocol)
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


def extract_frontend_contracts(frontend_dir: str):
    """Extrae rutas, métodos inferidos, propiedades leídas en .then() e invariantes .filter()."""
    files = []
    for ext in ("*.js", "*.ts", "*.jsx", "*.tsx", "*.vue", "*.svelte"):
        files.extend(glob.glob(os.path.join(frontend_dir, "**", ext), recursive=True))

    routes_found = defaultdict(lambda: {"locations": [], "response_props": set(), "methods": set()})
    filter_invariants = set()

    for path in sorted(set(files)):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        fname = os.path.basename(path)
        lines = content.splitlines()

        # 1. Detectar URL_BASE locales (ej. var URL_BASE = "/api/configuracion/eliminar/";)
        base_prefixes = re.findall(
            r"(?:URL_BASE|BASE_URL|apiBase|urlBase)\s*=\s*[\"\x27](/api/[^\"\x27]+)[\"\x27]",
            content,
        )
        for prefix in base_prefixes:
            # Buscar llamadas get("subruta/") o post("subruta/")
            for m in re.finditer(r"\b(get|post)\(\s*[\"\x27]([^\"\x27]+)[\"\x27]", content):
                verb, sub = m.group(1).upper(), m.group(2)
                if not sub.startswith("/"):
                    full_route = normalize_route(prefix + sub)
                    lno = content[: m.start()].count("\n") + 1
                    routes_found[full_route]["locations"].append(f"{fname}:{lno}")
                    routes_found[full_route]["methods"].add(verb)

        # 2. Detectar expresiones con "/api/..." incluyendo concatenaciones dinámicas
        pattern = re.compile(
            r"[\"\x27](/api/[a-zA-Z0-9_\-/]+)[\"\x27]"
            r"(?:\s*\+\s*(?:encodeURIComponent\([^)]+\)|[a-zA-Z0-9_.]+)\s*\+\s*[\"\x27](/[a-zA-Z0-9_\-/]*)[\"\x27])?"
            r"(?:\s*\+\s*(?:encodeURIComponent\([^)]+\)|[a-zA-Z0-9_.]+)\s*\+\s*[\"\x27](/[a-zA-Z0-9_\-/]*)[\"\x27])?"
        )

        for m in pattern.finditer(content):
            p1, p2, p3 = m.group(1), m.group(2), m.group(3)
            # Ignorar prefijos truncados que terminan en guion o son URL_BASE
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

            # Inferir método según contexto en la misma línea
            line_str = lines[lno - 1] if lno <= len(lines) else ""
            if any(k in line_str for k in ("C.post", "postForm", "enviarFormulario", "eliminar", "guardar", "anular", "registrar")):
                routes_found[norm]["methods"].add("POST")
            elif any(k in line_str for k in ("C.get", "window.location.href", "a.href")):
                routes_found[norm]["methods"].add("GET")

            # Extraer bloque .then(function(param) { ... }) cercano para descubrir propiedades leídas
            after_slice = content[m.end() : m.end() + 900]
            then_match = re.search(
                r"\.then\(\s*(?:function\s*\(\s*([a-zA-Z0-9_]+)\s*\)|([a-zA-Z0-9_]+)\s*=>)",
                after_slice,
            )
            if then_match:
                param_name = then_match.group(1) or then_match.group(2)
                body_slice = after_slice[then_match.end() : then_match.end() + 700]
                for prop_m in re.finditer(rf"\b{re.escape(param_name)}\.([a-zA-Z0-9_]+)", body_slice):
                    prop = prop_m.group(1)
                    if prop not in ("length", "forEach", "map", "filter", "slice", "join", "then"):
                        routes_found[norm]["response_props"].add(prop)

        # 3. Extraer invariantes .filter(...) sobre colecciones
        for fm in re.finditer(
            r"\.filter\(\s*function\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*\{([^}]{1,200})\}",
            content,
        ):
            var_name, fbody = fm.group(1), fm.group(2)
            for pm in re.finditer(rf"\b{re.escape(var_name)}\.([a-zA-Z0-9_]+)", fbody):
                prop = pm.group(1)
                if prop not in ("toLowerCase", "indexOf", "includes", "trim"):
                    filter_invariants.add(f"{fname}: {var_name}.{prop}")

    return routes_found, sorted(filter_invariants)


def extract_backend_routes(server_path: str):
    """Extrae todas las rutas registradas en el servidor reconstruido."""
    if os.path.isdir(server_path):
        files = glob.glob(os.path.join(server_path, "**", "*.js"), recursive=True) + glob.glob(
            os.path.join(server_path, "**", "*.py"), recursive=True
        )
    else:
        files = [server_path]

    server_routes = defaultdict(set)
    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        for m in re.finditer(
            r"(?:app|router)\.(get|post|put|delete|all|patch)\(\s*[\"\x27]([^\"\x27]+)[\"\x27]",
            code,
        ):
            method, r = m.group(1).upper(), normalize_route(m.group(2))
            server_routes[r].add(method)

    return server_routes


def main():
    parser = argparse.ArgumentParser(description="Audita paridad determinista entre Frontend y Backend.")
    parser.add_argument("--frontend", required=True, help="Directorio del código frontend extraído")
    parser.add_argument("--server", required=True, help="Archivo o directorio del servidor backend")
    args = parser.parse_args()

    fe_routes, invariants = extract_frontend_contracts(args.frontend)
    be_routes = extract_backend_routes(args.server)

    print("=" * 80)
    print("🔬 AUDITORÍA DETERMINISTA DE CONTRATOS API (ZERO-GUESSING PROTOCOL)")
    print("=" * 80)
    print(f"Rutas API únicas en Frontend : {len(fe_routes)}")
    print(f"Rutas API registradas Server : {len(be_routes)}")
    print("-" * 80)

    missing = []
    matched = 0

    for route in sorted(fe_routes.keys()):
        info = fe_routes[route]
        locs = ", ".join(sorted(set(info["locations"]))[:2])
        props = ", ".join(sorted(info["response_props"])) or "(sin lectura directa)"
        if route in be_routes:
            matched += 1
            srv_methods = "/".join(sorted(be_routes[route]))
            print(f"  [OK]      {srv_methods:8} {route:45} | Props: {props} | {locs}")
        else:
            missing.append((route, info))
            print(f"  [MISSING] {'---':8} {route:45} | Props: {props} | {locs}")

    print("-" * 80)
    print(f"📊 Cobertura de Rutas: {matched}/{len(fe_routes)} ({(matched / max(1, len(fe_routes))) * 100:.1f}%)")

    if invariants:
        print("\n🔗 INVARIANTES DE FILTRADO RELACIONAL DETECTADOS EN FRONTEND (.filter):")
        for inv in invariants[:25]:
            print(f"  • {inv}")

    if missing:
        print(f"\n❌ ERROR: Faltan {len(missing)} rutas en el backend.")
        sys.exit(1)
    else:
        print("\n🏆 PARIDAD DE RUTAS AL 100%: Ninguna llamada del frontend carece de endpoint.")
        sys.exit(0)


if __name__ == "__main__":
    main()
