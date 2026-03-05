from pathlib import Path

from bs4 import BeautifulSoup, Tag

FILES = ["67071.htm", "67383.htm", "68273.htm", "69533.htm"]

for f in FILES:
    soup = BeautifulSoup(Path("data/BULLETINS/" + f).read_bytes(), "html.parser")
    print("---", f)
    for span in soup.find_all("span", class_="style28"):
        if not isinstance(span, Tag):
            continue
        txt = span.get_text(strip=True)
        if "Rédacteur" in txt or "Pour en savoir" in txt:
            td = span.find_parent("td")
            if isinstance(td, Tag):
                nxt = td.find_next_sibling("td")
                if isinstance(nxt, Tag):
                    print(f"  {txt!r}")
                    print(f"    => {nxt.get_text(' ', strip=True)[:200]}")
