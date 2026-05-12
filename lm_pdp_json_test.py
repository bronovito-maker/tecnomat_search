from bs4 import BeautifulSoup
from tecnomat_termux import fetch_html_ghost

url = "https://www.leroymerlin.it/prodotti/trapano-a-batteria-dexter-12vsd2-21-51c-12-v-1-5-ah-1-batteria-inclusa-82630784.html"
cookie_header = "lmit_store_id=11"

html = fetch_html_ghost(url, cookie_header=cookie_header)
if "Rimini" in html:
    print("Rimini Trovato nell'HTML!")
    idx = html.find("Rimini")
    print(html[max(0, idx-100):idx+100])
else:
    print("Rimini NON trovato. Cerco __PRELOADED_STATE__ o script data...")
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    found = False
    for s in scripts:
        if s.string and ('stock' in s.string.lower() or 'available' in s.string.lower()):
            print("Trovato potenziale script con stock (primi 200 char):")
            print(s.string[:200])
            found = True
    if not found:
        print("Nessuno script utile.")
