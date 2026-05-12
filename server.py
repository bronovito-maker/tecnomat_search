from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import uvicorn

import uvicorn
import google.generativeai as genai
import json
import time

# Carichiamo le variabili d'ambiente
load_dotenv(".env")
# Se presente, carica anche eventuali config globali
load_dotenv(os.path.expanduser("~/.config/tecnomat/.env"))

# Configurazione Gemini
GEMINI_API_KEY = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro-latest')
else:
    model = None

def ai_analyze_query(query: str):
    """Analizza la query con l'IA per suggerire termini tecnici e kit."""
    if not model:
        return None
    
    prompt = f"""
    Sei un assistente tecnico esperto di bricolage e ferramenta (Nikituttofare). 
    Analizza questa ricerca di un utente: '{query}'.
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON con queste chiavi:
    - 'search_terms': una lista di max 3 termini tecnici precisi per trovare i prodotti necessari in ferramenta.
    - 'advice': un consiglio tecnico breve (max 20 parole).
    - 'kit': una lista di 2-3 articoli complementari utili per questo specifico lavoro.
    
    Se la query è un singolo prodotto semplice (es. 'trapano'), suggerisci accessori o varianti tecniche.
    Se la query è un progetto (es. 'montare mensola'), suggerisci i componenti necessari.
    """
    
    try:
        # Aggiungiamo un timeout di 5 secondi per l'IA
        response = model.generate_content(prompt, request_options={"timeout": 5000})
        # Pulizia dell'output per estrarre il JSON (rimuove eventuali markdown ```json)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        return json.loads(text)
    except Exception as e:
        print(f"Errore Gemini: {e}")
        return None

# Importiamo le funzioni core dal nostro script esistente
from tecnomat_termux import search_tecnomat, search_leroy_merlin, parse_price

app = FastAPI(
    title="Nikituttofare Scraper API",
    description="API per la ricerca parallela su Tecnomat e Leroy Merlin per Rimini e dintorni",
    version="1.0.0"
)

# Configurazione CORS molto permissiva (permette al tuo sito di accedere alle API)
# Puoi restringere allow_origins a ["https://www.nikituttofare.com"] quando andrai in produzione
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modifica questo in produzione!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Nikituttofare API is running"}

@app.get("/api/search")
def api_search(
    q: str = Query(..., description="Testo da cercare"),
    negozio: str = Query("mix", description="Filtra per negozio: tecnomat, leroy, mix"),
    n: int = Query(5, description="Numero di risultati per negozio"),
    show_zero: bool = Query(False, description="Mostra anche prodotti esauriti"),
    sort_price: bool = Query(False, description="Ordina tutti i risultati per prezzo")
):
    t0 = time.time()
    print(f"[DIAG][API] start q='{q}' negozio={negozio} n={n} show_zero={show_zero} sort_price={sort_price}")

    query = q.strip()
    if not query:
        print("[DIAG][API] empty_query")
        return {"results": [], "error": "Query vuota"}

    # Analisi IA (opzionale e parallela se possibile, ma facciamola semplice per ora)
    ai_insights = ai_analyze_query(query)

    all_results = []
    
    # Usiamo lo stesso pool di thread per interrogare le fonti in parallelo
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        if negozio in ["tecnomat", "mix"]:
            futures.append(executor.submit(search_tecnomat, query, n, show_zero))
        if negozio in ["leroy", "mix"]:
            futures.append(executor.submit(search_leroy_merlin, query, n, show_zero))
        
        for future in as_completed(futures):
            try:
                batch = future.result()
                source = batch[0]["source"] if batch else "EMPTY"
                print(f"[DIAG][API] provider_done source={source} count={len(batch)}")
                all_results.extend(batch)
            except Exception as e:
                # Se una fonte fallisce, continuiamo con l'altra
                print(f"[DIAG][API] provider_error type={type(e).__name__} detail={e}")
                pass

    if sort_price and all_results:
        all_results.sort(key=lambda x: parse_price(x["price"]))
    else:
        # Default: Ordiniamo in base al negozio (Tecnomat prima)
        all_results.sort(key=lambda x: 0 if x["source"] == "TECNOMAT" else 1)

    elapsed_ms = int((time.time() - t0) * 1000)
    print(f"[DIAG][API] done count={len(all_results)} elapsed_ms={elapsed_ms}")

    return {
        "query": query,
        "negozio": negozio,
        "ai_insights": ai_insights,
        "count": len(all_results),
        "results": all_results
    }

if __name__ == "__main__":
    # Avvia il server localmente sulla porta 8000
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
