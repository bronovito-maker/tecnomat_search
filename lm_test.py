import re
from bs4 import BeautifulSoup
from tecnomat_termux import fetch_html_ghost

url = "https://www.leroymerlin.it/search?q=silicone+bagno"
cookie_header = "lmit_store_id=11"

html = fetch_html_ghost(url, cookie_header=cookie_header)
soup = BeautifulSoup(html, 'html.parser')
items = soup.find_all('article', class_=re.compile(r'o-thumbnail|product-card|plp-product-card'))

for item in items[:2]:
    name = item.find(['a', 'span', 'h3'], class_=re.compile(r'a-designation|product-name|title')).get_text(strip=True)
    print(f"Nome: {name}")
    print(f"All text: {item.get_text(' ', strip=True)}")
    print("---")
