import re
from bs4 import BeautifulSoup
from tecnomat_termux import fetch_html_ghost

url = "https://www.leroymerlin.it/prodotti/trapano-a-batteria-dexter-12vsd2-21-51c-12-v-1-5-ah-1-batteria-inclusa-82630784.html"
cookie_header = "lmit_store_id=11"

html = fetch_html_ghost(url, cookie_header=cookie_header)
soup = BeautifulSoup(html, 'html.parser')
all_text = soup.get_text(" ", strip=True)
print("Risultato PDP:")
matches = re.findall(r'.{0,40}disponibil.{0,40}', all_text, re.IGNORECASE)
for m in matches:
    print(m.strip())
