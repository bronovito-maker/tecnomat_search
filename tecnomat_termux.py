#!/usr/bin/env python3
import json
import argparse
import os
import re
import sys
import time
import subprocess
import urllib.parse
import urllib.request
import random
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

DEFAULT_PER_PAGE = 5

def print_quick_tips() -> None:
    print("\nSuggerimenti rapidi:")
    print('  tecnomat "silicone bagno"')
    print('  tecnomat -n 10 "trapano"')
    print('  tecnomat --negozio leroy "trapano"')
    print('  tecnomat --show-zero-stock "trapano"')
    print('  tecnomat --sort-price "trapano"')
    print("  tecnomat -h\n")

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

def format_eur(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    text = f"{amount:.2f}".replace(".", ",")
    return f"€ {text}"

def parse_price(price_str: str) -> float:
    """Estrae un valore numerico float da una stringa prezzo per l'ordinamento."""
    if not price_str or price_str == "N/D":
        return float('inf')
    try:
        # Rimuove tutto tranne numeri e virgola/punto
        clean = re.sub(r'[^\d,\.]', '', price_str).replace(',', '.')
        return float(clean)
    except:
        return float('inf')

# --- CORE NETWORK MAGIC (TLS GHOST) ---
def fetch_html_ghost(url: str, cookie_header: str = "", retries: int = 2, timeout: int = 15) -> str:
    """Usa curl_cffi per ingannare DataDome e altri WAF simulando Chrome 120 su Android."""
    time.sleep(random.uniform(0.5, 1.5))
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
    
    last_exc = None
    for i in range(retries + 1):
        headers = dict(base_headers)
        if cookie_header:
            headers["Cookie"] = cookie_header
            
        try:
            if curl_requests:
                response = curl_requests.get(url, headers=headers, impersonate="chrome120", timeout=timeout)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 410: # Spesso usato per contenuti rimossi o bot blocks
                    raise RuntimeError(f"HTTP 410 (Blocked or Gone)")
                else:
                    raise RuntimeError(f"HTTP {response.status_code}")
            else:
                print("Debug: curl_cffi non trovato, uso urllib (rischio ban elevato)")
                req = urllib.request.Request(url, method="GET", headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_exc = e
            if i < retries:
                time.sleep(1.0)
                continue
            raise
    raise last_exc or RuntimeError("Errore sconosciuto fetch_html_ghost")

# Cache globale per la collezione Tecnomat
_TECNOMAT_COLLECTION_CACHE = None

def discover_tecnomat_collection() -> str:
    """Tenta di scoprire l'attuale collection Typesense dalla home di Tecnomat."""
    global _TECNOMAT_COLLECTION_CACHE
    try:
        # Se abbiamo già una cache, usiamola
        if _TECNOMAT_COLLECTION_CACHE:
            return _TECNOMAT_COLLECTION_CACHE
            
        print("🔍 Auto-detecting Tecnomat collection...")
        html = fetch_html_ghost("https://www.tecnomat.it/")
        
        # Cerchiamo il pattern tm_prod_products_1_ seguito da numeri
        match = re.search(r'tm_prod_products_1_\d+', html)
        if match:
            col = match.group(0)
            _TECNOMAT_COLLECTION_CACHE = col
            print(f"✅ Trovata collection: {col}")
            return col
            
        # Fallback se non troviamo nulla
        return os.getenv("TYPESENSE_COLLECTION", "tm_prod_products_1_129")
    except Exception as e:
        print(f"⚠️ Errore auto-discovery: {e}")
        return os.getenv("TYPESENSE_COLLECTION", "tm_prod_products_1_129")

# --- TECNOMAT PROVIDER ---
def search_tecnomat(query: str, num_results: int, show_zero: bool) -> List[Dict[str, str]]:
    global _TECNOMAT_COLLECTION_CACHE
    try:
        url_base = env("TYPESENSE_URL")
        api_key = env("TYPESENSE_API_KEY")
        store_id = env("TECNOMAT_STORE_ID", required=False, default="39")
        query_by = env("TYPESENSE_QUERY_BY", required=False, default="name")
        
        # Auto-discovery della collection
        collection = discover_tecnomat_collection()
        
        ts_url = f"{url_base.rstrip('/')}/collections/{collection}/documents/search"
        params = {"q": query, "query_by": query_by, "per_page": str(num_results * 3)} # Più risultati per filtrare stock 0
        full_url = f"{ts_url}?{urllib.parse.urlencode(params)}"
        
        req = urllib.request.Request(full_url, headers={"X-TYPESENSE-API-KEY": api_key, "Accept": "application/json"})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Se 404, probabilmente la collezione è scaduta. Svuotiamo la cache e riproviamo una volta.
                print("🔄 Collection scaduta, riprovo auto-detection...")
                _TECNOMAT_COLLECTION_CACHE = None
                collection = discover_tecnomat_collection()
                ts_url = f"{url_base.rstrip('/')}/collections/{collection}/documents/search"
                full_url = f"{ts_url}?{urllib.parse.urlencode(params)}"
                req = urllib.request.Request(full_url, headers={"X-TYPESENSE-API-KEY": api_key, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
            else:
                raise

        results = []
        cookie_header = f"bricoman_retailer_shop_id={store_id}; bricoman_previous_shop_id={store_id}"
        
        def process_hit(hit):
            doc = hit.get("document", {})
            pdp_url = doc.get("product_url") or doc.get("url", "")
            
            price = "N/D"
            price_obj = doc.get("price", {})
            if isinstance(price_obj, dict) and price_obj.get("EUR"):
                price = format_eur(price_obj["EUR"].get("default", 0))

            aisle = str(doc.get("aisle", "Ubicazione non trovata"))
            stock = "0"
            
            if pdp_url:
                try:
                    # Timeout breve e zero retries: se il PDP non risponde subito, usiamo il fallback
                    html = fetch_html_ghost(pdp_url, cookie_header=cookie_header, retries=0, timeout=5)
                    html_lower = html.lower()
                    
                    if "non è disponibile in questo negozio" in html_lower:
                        return None
                        
                    if BeautifulSoup:
                        soup = BeautifulSoup(html, 'html.parser')
                        text_all = soup.get_text(separator=" ", strip=True)
                        
                        match_stock = re.search(r'Disponibilità in negozio[^\d]*(\d+)', text_all, re.IGNORECASE)
                        if match_stock:
                            stock = match_stock.group(1)
                            
                        match_bf = re.search(r'(Corsia\s+[A-Za-z0-9]+|Reparto\s+.*?Perimetro\s+(?:[SD]X|destro|sinistro)|Reparto\s+[A-Za-z0-9\s]+|UTENSILERIA|EDILIZIA|FALEGNAMERIA|PIASTRELLE|SANITARI)', text_all, re.IGNORECASE)
                        if match_bf:
                            raw_aisle = match_bf.group(1).strip()
                            raw_aisle = re.sub(r'\s+', ' ', raw_aisle)
                            aisle = raw_aisle.title()
                except Exception:
                    # Fallback sui dati Typesense se il PDP fallisce
                    stock = str(doc.get("stock_store", "0"))
                    
            if not show_zero and stock == "0":
                return None
                
            return {
                "source": "TECNOMAT",
                "name": doc.get("name", "Prodotto Sconosciuto"),
                "price": price,
                "stock": stock,
                "location": aisle,
                "url": pdp_url
            }

        with ThreadPoolExecutor(max_workers=10) as executor:
            # Sottomettiamo tutti i task
            futures = [executor.submit(process_hit, hit) for hit in data.get("hits", [])]
            for future in futures:
                res = future.result() # Manteniamo l'ordine originale di Typesense (rilevanza)
                if res:
                    results.append(res)
                if len(results) >= num_results:
                    break
                    
        return results
    except Exception as e:
        print(f"Debug Tecnomat Error: {e}")
        return []

# --- LEROY MERLIN PROVIDER ---
def search_leroy_merlin(query: str, num_results: int, show_zero: bool) -> List[Dict[str, Any]]:
    try:
        base_url = env("LEROY_MERLIN_BASE_URL", required=False, default="https://www.leroymerlin.it")
        store_id = env("LEROY_MERLIN_STORE_ID", required=False, default="11")
        
        search_url = f"{base_url}/search?q={urllib.parse.quote(query)}"
        cookie_header = f"lmit_store_id={store_id}"
        
        html = fetch_html_ghost(search_url, cookie_header=cookie_header)
            
        results = []
        if BeautifulSoup:
            soup = BeautifulSoup(html, 'html.parser')
            # Selettori verificati: Leroy Merlin usa molto 'article' per i prodotti
            items = soup.find_all('article', class_=re.compile(r'o-thumbnail|product-card|plp-product-card'))
            
            if not items:
                # Fallback su div se article fallisce
                items = soup.select('div[class*="product-card"]')

            for item in items:
                name_tag = item.find(['a', 'span', 'h3'], class_=re.compile(r'a-designation|product-name|title'))
                price_container = item.find(class_=re.compile(r'm-price|price-infos|amount|price'))
                stock_tag = item.find(class_=re.compile(r'stock-status|availability'))
                link_tag = item.find('a', href=True)
                
                if name_tag and link_tag:
                    name = name_tag.get_text(strip=True)
                    if len(name) < 5: continue
                    
                    price = "N/D"
                    if price_container:
                        price_text = price_container.get_text(" ", strip=True)
                        raw_price = re.sub(r'\s+', ' ', price_text).replace(" ,", ",").strip()
                        
                        # Estraiamo solo l'ultimo prezzo valido (esclude prezzi barrati precedenti)
                        matches = re.findall(r'[\d\.,]+\s*€', raw_price)
                        if matches:
                            price = matches[-1].strip()
                            if not price.startswith("€"):
                                price = f"€ {price.replace('€', '').strip()}"
                        else:
                            price = raw_price
                            if "€" not in price: price = f"€ {price}"
                        
                    stock_text = stock_tag.get_text(strip=True) if stock_tag else "Vedi sito"
                    
                    item_text = item.get_text(" ", strip=True)
                    # Escludiamo prodotti Marketplace o non direttamente venduti da Leroy Merlin
                    is_marketplace = "Venduto da LEROY MERLIN" not in item_text
                    
                    # Consideriamo "zero stock" tutto ciò che non è ritirabile subito
                    is_zero = is_marketplace or any(x in stock_text.lower() for x in [
                        "non disponibile", "esaurito", "giorni", 
                        "consegna", "domicilio", "spedito"
                    ])
                    
                    if not show_zero and is_zero:
                        continue
                        
                    results.append({
                        "source": "LEROY MERLIN",
                        "name": name,
                        "price": price,
                        "stock": stock_text,
                        "location": "Vedi sito web",
                        "url": urllib.parse.urljoin(base_url, link_tag['href'])
                    })
                    
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return []

# --- MAIN ENGINE ---
def main() -> None:
    load_dotenv(".env")
    load_dotenv(os.path.expanduser("~/.config/tecnomat/.env"))
    
    parser = argparse.ArgumentParser(description="Multi-Scraper per Tecnomat & Leroy Merlin (Bypass DataDome integrato)")
    parser.add_argument("query", nargs="*", help='Testo da cercare')
    parser.add_argument("-n", "--num-results", type=int, default=DEFAULT_PER_PAGE, help=f"Risultati per negozio")
    parser.add_argument("--show-zero-stock", action="store_true", help="Mostra anche prodotti esauriti")
    parser.add_argument("--sort-price", action="store_true", help="Ordina tutti i risultati per prezzo")
    parser.add_argument("--negozio", choices=["tecnomat", "leroy", "mix"], default="mix", help="Filtra la ricerca per negozio: tecnomat, leroy o mix (default: mix)")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        try: query = input("Inserisci il prodotto da cercare: ").strip()
        except: sys.exit(0)
            
    if not query:
        sys.exit(1)

    print(f"\nCercando '{query}' a Rimini e dintorni...\n")

    all_results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        if args.negozio in ["tecnomat", "mix"]:
            futures.append(executor.submit(search_tecnomat, query, args.num_results, args.show_zero_stock))
        if args.negozio in ["leroy", "mix"]:
            futures.append(executor.submit(search_leroy_merlin, query, args.num_results, args.show_zero_stock))
        
        for future in as_completed(futures):
            all_results.extend(future.result())

    if not all_results:
        print("Nessun risultato trovato.")
    else:
        if args.sort_price:
            all_results.sort(key=lambda x: parse_price(x["price"]))
        else:
            # Raggruppa per fonte di default
            all_results.sort(key=lambda x: 0 if x["source"] == "TECNOMAT" else 1)
        
        for prod in all_results:
            print(f"[{prod['source']}] {prod['name']}")
            print(f"  Prezzo: {prod['price']}")
            print(f"  Stock:  {prod['stock']}")
            if prod['source'] != "LEROY MERLIN":
                print(f"  Ubicaz: {prod['location']}")
            print(f"  Link:   {prod['url']}")
            print("-" * 40)

    print_quick_tips()

if __name__ == "__main__":
    main()
