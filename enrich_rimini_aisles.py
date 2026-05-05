#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple


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


def env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Errore: variabile ambiente mancante: {name}")
        sys.exit(1)
    return value


def http_json(method: str, url: str, api_key: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    headers = {
        "X-TYPESENSE-API-KEY": api_key,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def find_document_id_by_sku(base_url: str, collection: str, api_key: str, sku: str) -> Optional[str]:
    params = urllib.parse.urlencode(
        {
            "q": "*",
            "query_by": "name",
            "filter_by": f"sku:={sku}",
            "per_page": "1",
        }
    )
    url = f"{base_url}/collections/{collection}/documents/search?{params}"
    try:
        payload = http_json("GET", url, api_key)
    except Exception as e:
        print(f"Errore ricerca SKU {sku}: {e}")
        return None

    hits = payload.get("hits", [])
    if not hits:
        return None

    doc = hits[0].get("document", {})
    return str(doc.get("id", "")).strip() or None


def update_document(
    base_url: str,
    collection: str,
    api_key: str,
    document_id: str,
    corsia: str,
    reparto: str,
) -> Tuple[bool, str]:
    url = f"{base_url}/collections/{collection}/documents/{urllib.parse.quote(document_id)}"

    payload = {
        "corsia_rimini": corsia,
        "reparto_rimini": reparto,
        "ubicazione_rimini": f"{reparto} - CORSIA {corsia}" if reparto and corsia else "",
    }

    try:
        http_json("PATCH", url, api_key, body=payload)
        return True, "ok"
    except Exception as e:
        return False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichment corsie Rimini su Typesense da CSV")
    parser.add_argument("--csv", required=True, help="Percorso CSV con colonne: sku,corsia,reparto")
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa farebbe senza scrivere")
    args = parser.parse_args()

    load_dotenv()

    base_url = env("TYPESENSE_URL").rstrip("/")
    collection = env("TYPESENSE_COLLECTION")
    api_key = os.getenv("TYPESENSE_WRITE_API_KEY", "").strip() or env("TYPESENSE_API_KEY")

    total = 0
    found = 0
    updated = 0
    missing = 0
    failed = 0

    with open(args.csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"sku", "corsia", "reparto"}
        if not required.issubset({c.strip() for c in (reader.fieldnames or [])}):
            print("Errore CSV: servono colonne sku,corsia,reparto")
            sys.exit(1)

        for row in reader:
            total += 1
            sku = (row.get("sku") or "").strip()
            corsia = (row.get("corsia") or "").strip()
            reparto = (row.get("reparto") or "").strip()

            if not sku:
                failed += 1
                print(f"[RIGA {total}] SKIPPED: sku mancante")
                continue

            doc_id = find_document_id_by_sku(base_url, collection, api_key, sku)
            if not doc_id:
                missing += 1
                print(f"[SKU {sku}] NON TROVATO")
                continue

            found += 1
            if args.dry_run:
                print(f"[SKU {sku}] doc_id={doc_id} -> corsia_rimini={corsia} reparto_rimini={reparto}")
                continue

            ok, msg = update_document(base_url, collection, api_key, doc_id, corsia, reparto)
            if ok:
                updated += 1
                print(f"[SKU {sku}] aggiornato")
            else:
                failed += 1
                print(f"[SKU {sku}] ERRORE update: {msg}")

    print("\n--- Riepilogo ---")
    print(f"Righe CSV: {total}")
    print(f"SKU trovati: {found}")
    print(f"Aggiornati: {updated}{' (dry-run)' if args.dry_run else ''}")
    print(f"Non trovati: {missing}")
    print(f"Errori: {failed}")


if __name__ == "__main__":
    main()
