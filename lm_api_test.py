from tecnomat_termux import fetch_html_ghost
import json
try:
    url = "https://www.leroymerlin.it/api/bfo/stock/v1/products?productIds=82630784&storeId=11"
    html = fetch_html_ghost(url)
    print(html)
except Exception as e:
    print("Errore:", e)
