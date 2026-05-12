from tecnomat_termux import fetch_html_ghost
import re
html = fetch_html_ghost("https://www.leroymerlin.it/prodotti/trapano-a-percussione-a-batteria-dexter-dt-cd-18-68-li-i-bl-18-v-2-ah-2-batterie-in-valigetta-in-plastica-92008060.html")
urls = re.findall(r'https://[^"]+api[^"]+', html)
for u in set(urls): print(u)
