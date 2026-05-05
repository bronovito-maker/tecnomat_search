#!/usr/bin/env python3
import json
import argparse
import os
import sys
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List


DEFAULT_PER_PAGE = 10


def load_dotenv(path: str = ".env") -> None:
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


def build_url(base_url: str, collection: str, query: str, per_page: int) -> str:
    base = base_url.rstrip("/")
    path = f"/collections/{collection}/documents/search"
    params = {
        "q": query,
        "query_by": "name",
        "per_page": str(per_page),
    }
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


def extract_aisle(document: Dict[str, Any], store_slug: str) -> str:
    # Campo corsia non presente nei sample attuali dell'indice.
    aisle = pick_first(
        document,
        [f"corsia_{store_slug}", "corsia", "aisle", "scaffale"],
        default="",
    )
    if aisle not in ("", "N/D"):
        return str(aisle)
    return "Non disponibile nell'indice corrente"


def format_product(document: Dict[str, Any], store_slug: str) -> str:
    name = pick_first(document, ["name", "nome"])
    sku = pick_first(document, ["sku", "codice", "id"])
    price = extract_price(document)
    qty = extract_quantity(document)
    delivery_pickup = parse_json_if_string(document.get("delivery_pickup", ""))
    pickup = ""
    if isinstance(delivery_pickup, dict) and "pickup" in delivery_pickup:
        pickup = "Si" if str(delivery_pickup["pickup"]) in ("1", "true", "True") else "No"

    url = pick_first(document, ["url", "product_url", "link"], default="")

    lines = [
        f"- Nome: {name}",
        f"  SKU: {sku}",
        f"  Prezzo: {price}",
        f"  Quantita disponibile: {qty}",
    ]
    if pickup:
        lines.append(f"  Ritiro in negozio: {pickup}")
    if url:
        lines.append(f"  URL: {url}")

    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ricerca prodotti Tecnomat via Typesense")
    parser.add_argument("query", nargs="+", help='Testo da cercare, es: "trapano avvitatore"')
    parser.add_argument(
        "-n",
        "--num-results",
        type=int,
        default=DEFAULT_PER_PAGE,
        help=f"Numero massimo risultati (default: {DEFAULT_PER_PAGE})",
    )
    args = parser.parse_args()

    per_page = max(1, min(args.num_results, 50))
    query = " ".join(args.query).strip()

    typesense_url = env("TYPESENSE_URL")
    typesense_key = env("TYPESENSE_API_KEY")
    typesense_collection = env("TYPESENSE_COLLECTION")
    store_slug = env("TECNOMAT_STORE_SLUG", required=False, default="rimini")

    url = build_url(typesense_url, typesense_collection, query, per_page)
    payload = fetch_typesense(url, typesense_key)

    hits = payload.get("hits", [])
    if not hits:
        print("Nessun prodotto trovato.")
        return

    print(f"Risultati per: {query}\n")
    for idx, hit in enumerate(hits, start=1):
        doc = hit.get("document", {})
        print(f"{idx}. {format_product(doc, store_slug)}\n")


if __name__ == "__main__":
    main()
