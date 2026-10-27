"""Build a curated entry point over the same daily data and tested UI."""
from pathlib import Path

from bs4 import BeautifulSoup


def write_cop31_entry(static_dir: Path) -> Path:
    soup = BeautifulSoup((static_dir / "index.html").read_text(encoding="utf-8"), "html.parser")
    soup.title.string = "GREEN · COP31 | 全球气候情报"
    base = soup.new_tag("base", href="../")
    soup.head.insert(1, base)
    soup.body["data-edition"] = "cop31"
    section_order = ("map", "today", "chinaCarbon", "singapore", "analytics", "database")
    allowed = set(section_order)
    # Keep hidden DOM contracts for shared UI compatibility; their datasets and
    # scripts are not loaded. Only six curated sections are publicly displayed.
    for node in soup.select("main > section, main > div"):
        if node.get("id") not in allowed:
            node["data-cop31-excluded"] = ""
            node["hidden"] = ""
    for node in soup.select(".carbon-company-database, .mode-toggle"):
        node["data-cop31-excluded"] = ""
        node["hidden"] = ""
    for node in list(soup.select("nav a")):
        if node.get("href", "").removeprefix("#") not in allowed:
            node.decompose()
    for node in soup.select('a[href^="#"]'):
        node["href"] = "./cop31/" + node["href"]
    for node in list(soup.select("script[src], link[rel=stylesheet]")):
        asset = node.get("src", node.get("href", ""))
        if "/bth-" in asset or "/innovation-" in asset:
            node.decompose()
    logo = soup.select_one(".cop31-brand")
    logo["href"] = "https://cop31.tr/"
    logo["target"] = "_blank"
    logo["rel"] = "noopener noreferrer"
    logo["aria-label"] = "COP31 official website"
    for section_id in reversed(section_order):
        soup.main.insert(0, soup.find(id=section_id).extract())
    banner = soup.new_tag("section", attrs={"class": "cop31-intro", "aria-label": "COP31"})
    banner.append(BeautifulSoup('<p>COP31 · ANTALYA · 9–20 NOV 2026</p><h1 data-i18n="cop31Title">全球气候情报</h1>', "html.parser"))
    soup.main.insert(0, banner)
    credit = soup.new_tag("p", attrs={"class": "cop31-credit", "data-i18n": "cop31Independent"})
    credit.string = "格润独立研究展示页 · 非 COP31 官方网站"
    soup.footer.append(credit)
    path = static_dir / "cop31" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(soup), encoding="utf-8")
    return path
