# Ricerca Tecnomat da Termux (Pixel)

CLI Python per cercare materiali e stampare:
- prezzo
- quantita disponibile
- ritiro in negozio

## 1) Setup in Termux

```bash
pkg update && pkg upgrade -y
pkg install python git -y
```

Clona il progetto e entra nella cartella.

## 2) Configura una volta sola

```bash
cp .env.example .env
```

Poi modifica `.env` con i tuoi valori reali.
Dopo `bash install_termux.sh`, la config viene salvata anche in:
- `~/.config/tecnomat/.env`
cosi non la perdi dopo `git pull` o reinstall.

## 3) Installa il comando `tecnomat` (one-shot)

```bash
bash install_termux.sh
```

## 4) Esegui una ricerca

```bash
tecnomat "silicone bagno"
```

Output atteso: elenco con nome, SKU, prezzo, disponibilita e ritiro in negozio.

Puoi scegliere quanti risultati mostrare:

```bash
tecnomat -n 20 "trapano"
```

## Aggiornamenti one-tap (Termux:Widget)

Prerequisito: installa l'app Android `Termux:Widget`.

### 1) Metti il progetto in home Termux

```bash
cp -r ~/storage/downloads/tecnomat_search ~/tecnomat_search
cd ~/tecnomat_search
```

### 2) Installa gli shortcut

```bash
bash install_termux_widget.sh
```

### 3) Usa i pulsanti da widget

Shortcut disponibili:
- `tecnomat-update` (git pull + reinstall + check)
- `tecnomat-reinstall` (reinstall comando)
- `tecnomat-healthcheck` (verifica setup + query test)

## Note importanti

- La chiave `TYPESENSE_API_KEY` deve restare server-side e privata.
- I nomi campo del tuo indice possono cambiare (es. `price` vs `prezzo`, `qty_rimini` vs `stock`):
  lo script prova piu alias comuni.
- Se vuoi risultati piu precisi per il solo negozio di Rimini, possiamo aggiungere un filtro Typesense dedicato (`filter_by`) in base ai campi reali del tuo indice.

Configurazioni opzionali utili:
- `TYPESENSE_QUERY_BY`: default `name` (es: `name,sku,mpn`)
- `TYPESENSE_FILTER_BY`: filtro Typesense puro (es: `store_id:=116`)
- `TECNOMAT_STORE_SLUG`: usato per risolvere i campi corsia store-specifici (default: `rimini`)
- `TECNOMAT_STORE_ID`: store Tecnomat per PDP SSR (Rimini: `39`)
- `TECNOMAT_STORE_COOKIE`: cookie completo opzionale del browser, per allineare la sessione reale

La corsia viene estratta in modo primario dalla PDP SSR (`In negozio: Reparto ... - Corsia XX`).
Typesense resta usato per la ricerca veloce prodotto, non per la corsia.

Per forzare Rimini:

```bash
TECNOMAT_STORE_ID=39 tecnomat --resolve-aisle-html "silicone bagno"
```

Se vuoi massima stabilita con la stessa sessione browser:

```bash
TECNOMAT_STORE_COOKIE='cookie1=...; cookie2=...' TECNOMAT_STORE_ID=39 tecnomat --resolve-aisle-html "silicone bagno"
```

Comando base:

```bash
tecnomat --resolve-aisle-html "silicone bagno"
```

Il fallback legge la PDP del prodotto e cerca il blocco `In negozio: Reparto ... - Corsia XX`.

## Enrichment corsia Rimini (consigliato)

Per avere `Corsia (Rimini)` affidabile in CLI, arricchisci l'indice con i campi:
- `corsia_rimini`
- `reparto_rimini`
- `ubicazione_rimini` (es. `VERNICI - CORSIA 22`)

### 1) Prepara il CSV

Usa il template:

```bash
cp rimini_corsie_template.csv rimini_corsie.csv
```

Formato richiesto:
- `sku,corsia,reparto`

### 2) Test senza scrivere (dry-run)

```bash
python enrich_rimini_aisles.py --csv rimini_corsie.csv --dry-run
```

### 3) Scrittura reale su Typesense

```bash
python enrich_rimini_aisles.py --csv rimini_corsie.csv
```

### 4) Verifica in CLI

```bash
tecnomat "silicone bagno"
```

Se il prodotto ha lo SKU aggiornato, vedrai `Corsia (Rimini): 22` (o il valore che hai inserito).
## Bypass DataDome con curl_cffi

Lo script utilizza `curl_cffi` per emulare il fingerprint TLS di Chrome 110, bypassando nativamente i controlli DataDome senza bisogno di pesanti browser headless.

### Requisiti
In ambiente Termux, assicurarsi di installare le librerie necessarie:
```bash
pip install curl-cffi beautifulsoup4 --break-system-packages
```
*(L'opzione `--break-system-packages` è spesso necessaria su distribuzioni moderne per permettere l'installazione di pacchetti globali con pip)*
