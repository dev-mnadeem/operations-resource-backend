"""
Check if all items from products.txt exist in the deployed Heroku DB.
Uses only Python standard library.
Handles Jazzmin-themed Django admin with robust parsing (td.field-name).
"""

import http.cookiejar
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE_URL = "https://pos-arcadian-e44c4c032373.herokuapp.com"
LOGIN_URL = f"{BASE_URL}/admin/login/"
INVENTORY_URL = f"{BASE_URL}/admin/inventory/inventoryitem/"

USERNAME = "admin"
PASSWORD = "admin1234"


class CSRFParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.csrf_token = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "input" and attrs_dict.get("name") == "csrfmiddlewaretoken":
            self.csrf_token = attrs_dict.get("value")


class InventoryTableParser(HTMLParser):
    """Robust parser for inventory item names in td or th with class field-name."""

    def __init__(self):
        super().__init__()
        self.items = []
        self._in_field_name = False
        self._current_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        css_class = attrs_dict.get("class", "")
        if (tag == "td" or tag == "th") and "field-name" in css_class:
            self._in_field_name = True
            self._current_text = ""

    def handle_endtag(self, tag):
        if self._in_field_name and (tag == "td" or tag == "th"):
            text = self._current_text.strip()
            if text:
                self.items.append(text)
            self._in_field_name = False

    def handle_data(self, data):
        if self._in_field_name:
            self._current_text += data

    def handle_entityref(self, name):
        if self._in_field_name:
            char_map = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
            self._current_text += char_map.get(name, f"&{name};")


def regex_fallback_extract(html):
    """Regex fallback to extract names if parser fails, matching td or th."""
    # Matches <td class="field-name">Item Name</td> or <th class="field-name">Item Name</th>
    pattern = re.compile(
        r'<(?:td|th)[^>]*class="[^"]*field-name[^"]*"[^>]*>(?:<a[^>]*>)?([^<]+)(?:</a>)?\s*</(?:td|th)>',
        re.IGNORECASE,
    )
    return pattern.findall(html)


class PaginatorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.max_page = 1

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a":
            href = attrs_dict.get("href", "")
            match = re.search(r"\?p=(\d+)", href)
            if match:
                page_num = int(match.group(1))
                if page_num > self.max_page:
                    self.max_page = page_num


def create_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        (
            "User-Agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
    ]
    return opener


def login(opener):
    resp = opener.open(LOGIN_URL, timeout=30)
    html = resp.read().decode("utf-8")
    parser = CSRFParser()
    parser.feed(html)
    csrf_token = parser.csrf_token
    if not csrf_token:
        match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
        if match:
            csrf_token = match.group(1)
        else:
            raise RuntimeError("Could not find CSRF token")

    data = urllib.parse.urlencode(
        {
            "csrfmiddlewaretoken": csrf_token,
            "username": USERNAME,
            "password": PASSWORD,
            "next": "/admin/",
        }
    ).encode("utf-8")

    req = urllib.request.Request(LOGIN_URL, data=data, headers={"Referer": LOGIN_URL})
    resp = opener.open(req, timeout=30)
    body = resp.read().decode("utf-8")
    if "Please enter" in body and "Log in" in body:
        raise RuntimeError("Login failed")
    print("✅ Logged in successfully")


def get_all_inventory_items(opener):
    all_items = []

    # First page
    url = f"{INVENTORY_URL}"
    resp = opener.open(url, timeout=30)
    html = resp.read().decode("utf-8")

    item_parser = InventoryTableParser()
    item_parser.feed(html)
    items = item_parser.items

    if not items:
        # Try regex fallback
        items = regex_fallback_extract(html)

    all_items.extend(items)
    print(f"  Page 1: {len(items)} items")

    pag_parser = PaginatorParser()
    pag_parser.feed(html)
    max_page = pag_parser.max_page
    print(f"  Total pages detected: {max_page}")

    # Fetch remaining pages
    for page in range(2, max_page + 1):
        url = f"{INVENTORY_URL}?p={page}"
        try:
            resp = opener.open(url, timeout=30)
            html = resp.read().decode("utf-8")

            p = InventoryTableParser()
            p.feed(html)
            p_items = p.items
            if not p_items:
                p_items = regex_fallback_extract(html)

            all_items.extend(p_items)
            if page % 10 == 0 or page == max_page:
                print(
                    f"  Processed through page {page} (Total items: {len(all_items)})"
                )
        except Exception as e:
            print(f"  ❌ Error fetching page {page}: {e}")

    return all_items


def parse_products_file(filepath):
    """Parse products.txt to extract unique product names, skipping headers."""
    products = set()
    section_headers = {
        "ASIAN FUSION SECTION",
        "BAR SECTION",
        "CONTINENTAL SECTION",
        "DESSERT SECTION",
        "FRONT OF HOUSE SECTION",
        "PIZZA SECTION",
        "STAFF FOOD",
    }
    # Matches lines that look like category headers (e.g., "MEATS:", "VEGETABLES:")
    category_pattern = re.compile(r"^[A-Z][A-Z\s/\-\(\)&]*[:]?$")

    with Path(filepath).open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line in section_headers:
                continue
            if category_pattern.match(line):
                # Check if it's actually just a product name that is ALL CAPS
                # If it ends with a colon, it's definitely a category
                if line.endswith(":"):
                    continue
                # If it's short and all caps, likely a category
                if len(line) < 15 and line.isupper():
                    continue
            products.add(line)

    return products


def normalize(name):
    """Normalize names for matching."""
    name = name.lower().strip()
    # Remove branch suffix (BRXXX)
    name = re.sub(r"\s*\(br\d+\)\s*$", "", name)
    # Remove everything except alphanumeric and spaces
    name = re.sub(r"[^a-z0-9\s]", "", name)
    # Collapse spaces
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def main():
    products = parse_products_file("products.txt")
    print(f"📋 Found {len(products)} unique products in products.txt")

    opener = create_opener()
    try:
        login(opener)
    except Exception as e:
        print(f"❌ Login Error: {e}")
        return

    db_items_raw = get_all_inventory_items(opener)
    print(f"\n📦 Total items fetched from DB: {len(db_items_raw)}")

    # Group DB items by normalized name
    db_normalized = {}
    for item in db_items_raw:
        n = normalize(item)
        if n:
            if n not in db_normalized:
                db_normalized[n] = set()
            db_normalized[n].add(item)

    # Compare
    missing = []
    found = []

    # Sort for consistent output
    sorted_products = sorted(products)

    for product in sorted_products:
        p_norm = normalize(product)
        if p_norm in db_normalized:
            # Pick the most similar looking name from the DB set
            db_orig = sorted(db_normalized[p_norm])[0]
            if product == db_orig:
                found.append(product)
            else:
                found.append(f"{product} → {db_orig}")
        else:
            # Fuzzy match (containment)
            fuzzy_match = None
            for db_n in db_normalized:
                if p_norm and db_n and (p_norm in db_n or db_n in p_norm):
                    fuzzy_match = sorted(db_normalized[db_n])[0]
                    break

            if fuzzy_match:
                found.append(f"{product} ≈ {fuzzy_match}")
            else:
                missing.append(product)

    print(f"\n{'=' * 60}")
    print(f"✅ Found in DB: {len(found)}/{len(products)}")
    print(f"❌ Missing from DB: {len(missing)}/{len(products)}")
    print(f"{'=' * 60}")

    if missing:
        print(f"\n🔴 MISSING ITEMS ({len(missing)}):")
        for i, item in enumerate(sorted(missing), 1):
            print(f"  {i:3d}. {item}")

    print("\n🟢 COMPARISON COMPLETED")


if __name__ == "__main__":
    main()
