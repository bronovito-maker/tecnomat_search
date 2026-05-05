#!/usr/bin/env python3
import json
import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


DEFAULT_PER_PAGE = 10


def print_quick_tips() -> None:
    print("Suggerimenti rapidi:")
    print('  tecnomat "silicone bagno"')
    print('  tecnomat -n 20 "trapano"')
    print('  tecnomat --show-zero-stock "trapano"')
    print("  tecnomat -h")
    print("")


def load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def env(name: str, required: bool = True, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if required and not value:
        print(f"Errore: variabile ambiente mancante: {name}")
        sys.exit(1)
    return value


def build_url(
    base_url: str,
    collection: str,
    query: str,
    per_page: int,
    page: int = 1,
    query_by: str = "name",
    filter_by: str = "",
) -> str:
    base = base_url.rstrip("/")
    path = f"/collections/{collection}/documents/search"
    params = {
        "q": query,
        "query_by": query_by,
        "per_page": str(per_page),
        "page": str(page),
    }
    if filter_by:
        params["filter_by"] = filter_by
    return f"{base}{path}?{urllib.parse.urlencode(params)}"


def fetch_typesense(url: str, api_key: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "X-TYPESENSE-API-KEY": api_key,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            details = e.read().decode("utf-8")
        except Exception:
            details = str(e)
        print(f"Errore HTTP {e.code}: {details}")
        sys.exit(2)
    except Exception as e:
        print(f"Errore durante la ricerca: {e}")
        sys.exit(2)


def pick_first(document: Dict[str, Any], keys: List[str], default: Any = "N/D") -> Any:
    for key in keys:
        if key in document and document[key] not in (None, ""):
            return document[key]
    return default


def parse_json_if_string(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def get_nested_value(obj: Any, path: List[str]) -> Any:
    cur = obj
    for part in path:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
            continue
        return None
    return cur


def format_eur(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    text = f"{amount:.2f}".replace(".", ",")
    return f"EUR {text}"


def extract_price(document: Dict[str, Any]) -> str:
    price_obj = document.get("price")
    if isinstance(price_obj, dict):
        eur = price_obj.get("EUR")
        if isinstance(eur, dict):
            for key in ["default_formated", "group_6_formated"]:
                if eur.get(key):
                    return str(eur[key])
            for key in ["default", "group_6"]:
                if key in eur and eur[key] not in (None, ""):
                    return format_eur(eur[key])
    seller = document.get("seller_offer_116")
    if isinstance(seller, dict) and seller.get("price") not in (None, ""):
        return format_eur(seller["price"])
    return str(pick_first(document, ["price", "prezzo", "prezzo_vendita"]))


def extract_quantity(document: Dict[str, Any]) -> str:
    seller = document.get("seller_offer_116")
    if isinstance(seller, dict) and seller.get("qty") not in (None, ""):
        return str(seller["qty"])
    return str(
        pick_first(
            document,
            [
                "stock_store",
                "stock",
                "qty",
                "quantita_disponibile",
                "disponibilita",
            ],
        )
    )


def parse_quantity_value(document: Dict[str, Any]) -> int:
    seller = document.get("seller_offer_116")
    if isinstance(seller, dict) and seller.get("qty") not in (None, ""):
        try:
            return int(float(str(seller["qty"])))
        except Exception:
            return -1
    for key in ["stock_store", "stock", "qty", "quantita_disponibile"]:
        value = document.get(key)
        if value not in (None, ""):
            try:
                return int(float(str(value)))
            except Exception:
                continue
    return -1


def extract_aisle(document: Dict[str, Any], store_slug: str) -> str:
    direct = [
        f"corsia_{store_slug}",
        f"aisle_{store_slug}",
        "corsia",
        "aisle",
        "aisle_number",
        "location_aisle",
        "scaffale",
    ]
    aisle = pick_first(document, direct, default="")
    if aisle not in ("", "N/D", None):
        return str(aisle)

    nested_paths = [
        ["store_specific_data", store_slug, "location_aisle"],
        ["store_specific_data", store_slug, "aisle_number"],
        ["availability_by_store", store_slug, "location_aisle"],
        ["availability_by_store", store_slug, "aisle_number"],
        ["stores", store_slug, "location_aisle"],
        ["stores", store_slug, "aisle_number"],
    ]
    for key in ["store_specific_data", "availability_by_store", "stores"]:
        if key in document:
            document[key] = parse_json_if_string(document[key])
    for path in nested_paths:
        value = get_nested_value(document, path)
        if value not in (None, ""):
            return str(value)

    return "Non disponibile nell'indice corrente"


def build_store_cookie(base_cookie: str, store_id: str) -> str:
    parts = []
    if base_cookie:
        parts.append(base_cookie.strip().strip(";"))
    if store_id:
        parts.append(f"bricoman_retailer_shop_id={store_id}")
        parts.append(f"bricoman_previous_shop_id={store_id}")
    return "; ".join([p for p in parts if p])


def fetch_product_html(url: str, cookie_header: str = "", retries: int = 2) -> str:
    base_headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    last_exc: Exception | None = None
    for i in range(retries + 1):
        headers = dict(base_headers)
        if cookie_header:
            headers["Cookie"] = cookie_header
            
        try:
            if curl_requests:
                # Il Fantasma TLS: bypass DataDome impersonando Chrome 110
                response = curl_requests.get(url, headers=headers, impersonate="chrome110", timeout=15)
                if response.status_code == 200:
                    return response.text
                else:
                    raise RuntimeError(f"HTTP {response.status_code}")
            else:
                # Fallback standard se curl_cffi non è installato
                req = urllib.request.Request(url, method="GET", headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    return response.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_exc = e
            if i < retries:
                time.sleep(0.5)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Errore sconosciuto fetch_product_html")


def extract_aisle_from_html(html: str) -> str:
    # 1. Filtro Antigravity: Controllo indisponibilità totale
    html_lower = html.lower()
    if "non è disponibile in questo negozio" in html_lower or "ci dispiace" in html_lower:
        return "Esaurito (Non disponibile a Rimini)"

    if BeautifulSoup:
        soup = BeautifulSoup(html, 'html.parser')
        
        # 2. Caccia all'ubicazione
        lane_div = soup.find('div', class_='product-heading-lane')
        if lane_div:
            value_div = lane_div.find('div', class_='product-heading__elem-label__value')
            if value_div:
                raw_text = value_div.get_text(separator=" ", strip=True)
                
                # Cerca prima la Corsia specifica
                match_corsia = re.search(r'Corsia\s+(\d+)', raw_text, re.IGNORECASE)
                if match_corsia:
                    return match_corsia.group(1)
                
                # Se non c'è corsia, pulisci il testo e restituisci il Reparto/Perimetro
                clean_test = re.sub(r'\s+', ' ', raw_text).strip()
                return f"Solo Reparto: {clean_test}"

        return "Ubicazione non dichiarata nel DOM"

    # Fallback regex se BeautifulSoup non è installato
    lane_block = re.search(
        r'<div[^>]*class="[^"]*product-heading-lane[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    scope = lane_block.group(1) if lane_block else html

    match = re.search(r"Corsia\s*([A-Za-z0-9\-_/]+)", scope, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    match_reparto = re.search(
        r'In negozio:\s*</div>\s*<div[^>]*class="[^"]*product-heading__elem-label__value[^"]*"[^>]*>\s*([^<]+)\s*</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match_reparto:
        clean_text = re.sub(r"\s+", " ", match_reparto.group(1)).strip()
        return f"Solo Reparto: {clean_text}"

    return "Ubicazione non trovata"


def resolve_aisle_with_html_fallback(document: Dict[str, Any], store_slug: str, cookie_header: str = "") -> str:
    aisle = extract_aisle(document, store_slug)
    if aisle != "Non disponibile nell'indice corrente":
        return aisle

    url = str(pick_first(document, ["url", "product_url", "link"], default="")).strip()
    if not url:
        return aisle

    try:
        html = fetch_product_html(url, cookie_header=cookie_header)
        parsed = extract_aisle_from_html(html)
        if parsed:
            return parsed
    except Exception:
        return aisle

    return aisle


def resolve_aisle_from_pdp(document: Dict[str, Any], cookie_header: str = "") -> str:
    url = str(pick_first(document, ["url", "product_url", "link"], default="")).strip()
    if not url:
        return "URL prodotto non disponibile"
    try:
        html = fetch_product_html(url, cookie_header=cookie_header)
    except Exception as e:
        return f"Non disponibile (errore fetch PDP: {e})"

    return extract_aisle_from_html(html)


def format_product(document: Dict[str, Any], store_slug: str, aisle: str) -> str:
    name = pick_first(document, ["name", "nome"])
    price = extract_price(document)
    qty = extract_quantity(document)

    url = pick_first(document, ["url", "product_url", "link"], default="")

    lines = [
        f"- Nome: {name}",
        f"  Prezzo: {price}",
        f"  Quantita disponibile: {qty}",
        f"  Corsia ({store_slug.title()}): {aisle}",
    ]
    if url:
        lines.append(f"  URL: {url}")

    return "\n".join(lines)


def main() -> None:
    # Priority:
    # 1) repo-local .env
    # 2) persistent user config ~/.config/tecnomat/.env
    load_dotenv(".env")
    load_dotenv(os.path.expanduser("~/.config/tecnomat/.env"))
    parser = argparse.ArgumentParser(description="Ricerca prodotti Tecnomat via Typesense")
    parser.add_argument("query", nargs="+", help='Testo da cercare, es: "trapano avvitatore"')
    parser.add_argument(
        "-n",
        "--num-results",
        type=int,
        default=DEFAULT_PER_PAGE,
        help=f"Numero massimo risultati (default: {DEFAULT_PER_PAGE})",
    )
    parser.add_argument(
        "--show-zero-stock",
        action="store_true",
        help="Mostra anche prodotti con quantita disponibile uguale a 0",
    )
    parser.add_argument(
        "--debug-fields",
        action="store_true",
        help="Stampa il JSON raw del primo hit per ispezionare i campi reali dell'indice",
    )
    parser.add_argument(
        "--resolve-aisle-html",
        action="store_true",
        help="Se la corsia non e in Typesense, prova a estrarla dalla pagina prodotto (SSR)",
    )
    args = parser.parse_args()

    per_page = max(1, min(args.num_results, 50))
    fetch_per_page = min(50, max(per_page, 20))
    query = " ".join(args.query).strip()

    typesense_url = env("TYPESENSE_URL")
    typesense_key = env("TYPESENSE_API_KEY")
    typesense_collection = env("TYPESENSE_COLLECTION")
    store_slug = env("TECNOMAT_STORE_SLUG", required=False, default="rimini")
    query_by = env("TYPESENSE_QUERY_BY", required=False, default="name")
    filter_by = env("TYPESENSE_FILTER_BY", required=False, default="")
    store_cookie = env("TECNOMAT_STORE_COOKIE", required=False, default="")
    store_id = env("TECNOMAT_STORE_ID", required=False, default="")
    effective_cookie = build_store_cookie(store_cookie, store_id)

    hits = []
    max_pages = 10
    for page in range(1, max_pages + 1):
        url = build_url(
            typesense_url,
            typesense_collection,
            query,
            fetch_per_page,
            page=page,
            query_by=query_by,
            filter_by=filter_by,
        )
        payload = fetch_typesense(url, typesense_key)
        page_hits = payload.get("hits", [])
        if not page_hits:
            break
        if not args.show_zero_stock:
            page_hits = [h for h in page_hits if parse_quantity_value(h.get("document", {})) != 0]
        hits.extend(page_hits)
        if len(hits) >= per_page:
            break
    hits = hits[:per_page]

    if not hits:
        print("Nessun prodotto trovato con disponibilita > 0.")
        print("")
        print_quick_tips()
        return

    print(f"Risultati per: {query}\n")
    for idx, hit in enumerate(hits, start=1):
        doc = hit.get("document", {})
        # Fonte primaria: PDP SSR (piu stabile del solo indice Typesense per la corsia)
        aisle = resolve_aisle_from_pdp(doc, cookie_header=effective_cookie)
        print(f"{idx}. {format_product(doc, store_slug, aisle)}\n")

    if args.debug_fields:
        first_doc = hits[0].get("document", {})
        print("--- DEBUG FIRST HIT (RAW DOCUMENT) ---")
        print(json.dumps(first_doc, ensure_ascii=False, indent=2, sort_keys=True))
        print("--- END DEBUG ---")

    print_quick_tips()


if __name__ == "__main__":
    main()
