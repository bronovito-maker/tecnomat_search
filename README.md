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
