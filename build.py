#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""
CAN TV - Playlist Builder v6

Özellikler:

* categories.json sırasını birebir korur
* categories.json içindeki kanal sırasını korur
* data/kanal_kaynaklari.m3u en yüksek önceliğe sahiptir
* sources.txt kaynaklarının sırasını öncelik olarak kullanır
* Aynı URL'yi tekrar etmez
* Aynı kanalı farklı isimlerle tekrar etmez
* TV8 / TV 8 -> TV8
* TV8.5 / TV 8.5 / TV8 5 -> TV8.5
* BENGUTURK / BENGÜTÜRK -> BENGUTURK
* HABERTURK / HABER TÜRK -> HABERTURK
* Bozuk EXTINF kayıtlarını mümkün olduğunca düzeltir
* Kaliteli kaynağı tercih eder
* Named channel kaynaklarına öncelik verir
* Kontrollü Film tespiti yapar
* Film ve Diğer kategorilerini otomatik oluşturur
* Diğer kategorisini her zaman sona koyar
  """

import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(**file**).resolve().parent

SOURCES = ROOT / "sources.txt"
NAMED_SOURCES = ROOT / "data" / "kanal_kaynaklari.m3u"
CATEGORIES = ROOT / "categories.json"
CONFIG = ROOT / "config.json"
OUTPUT = ROOT / "playlist.m3u"

UA = "Mozilla/5.0 (CAN-TV-Builder/6.0)"

# ============================================================

# NORMALIZE

# ============================================================

def norm(value):

```
s = str(value or "").upper().strip()

tr_map = str.maketrans({
    "İ": "I",
    "Ş": "S",
    "Ğ": "G",
    "Ü": "U",
    "Ö": "O",
    "Ç": "C",
    "Â": "A",
    "Î": "I",
    "Û": "U",
})

s = s.translate(tr_map)

# Kalite bilgilerini kaldır
s = re.sub(
    r"\b(FHD|UHD|HD|SD|4K|HEVC|H265|H264|FULL HD)\b",
    " ",
    s,
)

# Noktalama işaretlerini boşluğa çevir
s = re.sub(
    r"[^A-Z0-9]+",
    " ",
    s,
)

return re.sub(
    r"\s+",
    " ",
    s,
).strip()
```

# ============================================================

# CANONICAL CHANNEL KEY

# ============================================================

def channel_key(name):

```
n = norm(name)

if not n:
    return ""

# --------------------------------------------------------
# TV8.5 ÖNCE KONTROL EDİLİR
# --------------------------------------------------------

if n in {
    "TV85",
    "TV8 5",
    "TV 8 5",
    "TV 85",
}:
    return "TV8.5"

if re.search(
    r"\bTV\s*8\s*5\b",
    n,
):
    return "TV8.5"

# --------------------------------------------------------
# TV8
# --------------------------------------------------------

if n in {
    "TV8",
    "TV 8",
}:
    return "TV8"

# --------------------------------------------------------
# BENGÜTÜRK
# --------------------------------------------------------

if n in {
    "BENGUTURK",
    "BENGU TURK",
}:
    return "BENGUTURK"

# --------------------------------------------------------
# HABERTÜRK
# --------------------------------------------------------

if n in {
    "HABERTURK",
    "HABER TURK",
}:
    return "HABERTURK"

# --------------------------------------------------------
# TRT MÜZİK
# --------------------------------------------------------

if n == "TRT MUZIK":
    return "TRT MUZIK"

# --------------------------------------------------------
# TRT DİYANET
# --------------------------------------------------------

if n == "TRT DIYANET":
    return "TRT DIYANET"

# --------------------------------------------------------
# TRT DİYANET ÇOCUK
# --------------------------------------------------------

if n == "TRT DIYANET COCUK":
    return "TRT DIYANET COCUK"

# --------------------------------------------------------
# NATIONAL GEOGRAPHIC
# --------------------------------------------------------

if n in {
    "NAT GEO",
    "NATIONAL GEOGRAPHIC",
}:
    return "NATIONAL GEOGRAPHIC"

# --------------------------------------------------------
# NATIONAL GEOGRAPHIC WILD
# --------------------------------------------------------

if n in {
    "NAT GEO WILD",
    "NAT WILD",
    "NATIONAL GEOGRAPHIC WILD",
}:
    return "NATIONAL GEOGRAPHIC WILD"

# --------------------------------------------------------
# DISCOVERY ID
# --------------------------------------------------------

if n in {
    "ID DISCOVERY",
    "DISCOVERY ID",
    "INVESTIGATION DISCOVERY",
}:
    return "DISCOVERY ID"

# --------------------------------------------------------
# BLOOMBERG
# --------------------------------------------------------

if n in {
    "BLOOMBERG HT",
    "BLOOMBERGHT",
}:
    return "BLOOMBERG HT"

# --------------------------------------------------------
# EKOTÜRK
# --------------------------------------------------------

if n == "EKOTURK":
    return "EKOTURK"

# --------------------------------------------------------
# LIFETIME
# --------------------------------------------------------

if n in {
    "LIFETIME",
    "LIFE TIME",
}:
    return "LIFETIME"

# --------------------------------------------------------
# KRAL FM
# --------------------------------------------------------

if n in {
    "KRAL FM",
    "KIRAL FM",
}:
    return "KRAL FM"

# --------------------------------------------------------
# KRAL POP
# --------------------------------------------------------

if n in {
    "KRAL POP",
    "KIRAL POP",
}:
    return "KRAL POP"

return n
```

# ============================================================

# KATEGORİLERDEN KANONİK İSİM BUL

# ============================================================

def build_canonical_names(categories):

```
result = {}

for category, names in categories.items():

    if not isinstance(names, list):
        continue

    for name in names:

        key = channel_key(name)

        if key and key not in result:
            result[key] = name

return result
```

# ============================================================

# KANAL İSMİ TEMİZLE

# ============================================================

def clean_channel_name(
name,
canonical_names,
):

```
original = str(name or "").strip()

if not original:
    return "KANAL"

key = channel_key(original)

# Tam eşleşme
if key in canonical_names:
    return canonical_names[key]

n = norm(original)

# --------------------------------------------------------
# TV8.5
# --------------------------------------------------------

if re.search(
    r"\bTV\s*8\s*5\b",
    n,
):
    return canonical_names.get(
        "TV8.5",
        "TV 8.5",
    )

# --------------------------------------------------------
# TV8
# --------------------------------------------------------

if re.search(
    r"\bTV\s*8\b",
    n,
):
    if not re.search(
        r"\bTV\s*8\s*5\b",
        n,
    ):
        return canonical_names.get(
            "TV8",
            "TV8",
        )

# --------------------------------------------------------
# Kategori listesindeki isimlerden
# metin içinde geçenleri ara.
#
# Uzun isimler önce aranır.
# --------------------------------------------------------

candidates = sorted(
    canonical_names.items(),
    key=lambda x: len(norm(x[1])),
    reverse=True,
)

for candidate_key, candidate_name in candidates:

    candidate_norm = norm(candidate_name)

    if not candidate_norm:
        continue

    if len(candidate_norm) < 4:
        continue

    # Tam kelime sınırı
    pattern = (
        r"(?<![A-Z0-9])"
        + re.escape(candidate_norm)
        + r"(?![A-Z0-9])"
    )

    if re.search(
        pattern,
        n,
    ):
        return candidate_name

return original
```

# ============================================================

# SOURCES.TXT OKU

# ============================================================

def read_sources():

```
if not SOURCES.exists():

    print(
        "[UYARI] sources.txt bulunamadı."
    )

    return []

result = []

lines = SOURCES.read_text(
    encoding="utf-8",
    errors="ignore",
).splitlines()

for line_number, line in enumerate(
    lines,
    start=1,
):

    line = line.strip()

    if not line:
        continue

    if line.startswith("#"):
        continue

    result.append(
        (
            line,
            line_number,
        )
    )

return result
```

# ============================================================

# FETCH

# ============================================================

def fetch(
url,
timeout,
):

```
req = Request(
    url,
    headers={
        "User-Agent": UA,
        "Accept": "*/*",
    },
)

with urlopen(
    req,
    timeout=timeout,
) as response:

    return response.read().decode(
        "utf-8",
        errors="ignore",
    )
```

# ============================================================

# EXTINF'TEN TVG-NAME

# ============================================================

def extract_tvg_name(ext):

```
match = re.search(
    r'tvg-name\s*=\s*"([^"]+)"',
    ext,
    flags=re.IGNORECASE,
)

if match:

    value = match.group(1).strip()

    if value:
        return value

match = re.search(
    r"tvg-name\s*=\s*'([^']+)'",
    ext,
    flags=re.IGNORECASE,
)

if match:

    value = match.group(1).strip()

    if value:
        return value

return ""
```

# ============================================================

# EXTINF'TEN İSİM

# ============================================================

def extract_name(
ext,
canonical_names=None,
):

```
tvg_name = extract_tvg_name(ext)

if tvg_name:

    if canonical_names:

        return clean_channel_name(
            tvg_name,
            canonical_names,
        )

    return tvg_name

if "," in ext:

    name = ext.split(
        ",",
        1,
    )[1].strip()

    name = re.sub(
        r'\s+group-title=.*$',
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()

    if canonical_names:

        name = clean_channel_name(
            name,
            canonical_names,
        )

    return name or "KANAL"

return "KANAL"
```

# ============================================================

# M3U PARSER

# ============================================================

def parse_m3u(
text,
canonical_names=None,
):

```
lines = text.splitlines()

result = []

i = 0

while i < len(lines):

    line = lines[i].strip()

    if line.startswith(
        "#EXTINF"
    ):

        ext = line

        j = i + 1

        while j < len(lines):

            candidate = lines[j].strip()

            if candidate:
                break

            j += 1

        if j < len(lines):

            url = lines[j].strip()

            if (
                url
                and not url.startswith("#")
                and (
                    url.startswith("http://")
                    or url.startswith("https://")
                )
            ):

                name = extract_name(
                    ext,
                    canonical_names,
                )

                result.append(
                    (
                        name,
                        ext,
                        url,
                    )
                )

                i = j + 1

                continue

    i += 1

return result
```

# ============================================================

# KATEGORİ INDEX

# ============================================================

def make_category_index(
categories,
):

```
index = {}

for category, names in categories.items():

    if not isinstance(names, list):
        continue

    for name in names:

        key = channel_key(name)

        if key and key not in index:

            index[key] = category

return index
```

# ============================================================

# KATEGORİ

# ============================================================

def category_for(
name,
ext,
index,
):

```
key = channel_key(name)

# Önce categories.json
if key in index:
    return index[key]

ext_upper = (
    ext or ""
).upper()

name_upper = (
    name or ""
).upper()

# --------------------------------------------------------
# FILM
# --------------------------------------------------------

# tvg-year
if re.search(
    r'tvg[-_ ]?year\s*=\s*["\']?\d{4}',
    ext_upper,
):
    return "Film"

# TMDB logo
if "IMAGE.TMDB.ORG" in ext_upper:
    return "Film"

if "IMAGE.TMDB.ORG" in name_upper:
    return "Film"

# Film isminde yıl
#
# Örnek:
# Avatar 2009
# Titanic 1997
#
if re.search(
    r"\b(?:19|20)\d{2}\s*$",
    norm(name),
):
    return "Film"

# --------------------------------------------------------
# DİĞER
# --------------------------------------------------------

return "Diğer"
```

# ============================================================

# QUALITY

# ============================================================

def quality(
name,
ext="",
):

```
value = (
    (name or "")
    + " "
    + (ext or "")
).upper()

if re.search(
    r"\b(4K|UHD)\b",
    value,
):
    return 4

if re.search(
    r"\b(FHD|FULL HD)\b",
    value,
):
    return 3

if re.search(
    r"\bHD\b",
    value,
):
    return 2

if re.search(
    r"\bSD\b",
    value,
):
    return 1

return 0
```

# ============================================================

# EXTINF TEMİZLE

# ============================================================

def rewrite_ext(
ext,
name,
group,
):

```
tvg_id = ""
tvg_logo = ""

# --------------------------------------------------------
# TVG-ID
# --------------------------------------------------------

match = re.search(
    r'tvg-id\s*=\s*"([^"]+)"',
    ext,
    flags=re.IGNORECASE,
)

if match:

    value = match.group(1).strip()

    if (
        value
        and "TVG-NAME" not in value.upper()
        and "GROUP-TITLE" not in value.upper()
    ):
        tvg_id = value

# --------------------------------------------------------
# TVG-LOGO
# --------------------------------------------------------

match = re.search(
    r'tvg-logo\s*=\s*"([^"]+)"',
    ext,
    flags=re.IGNORECASE,
)

if match:

    value = match.group(1).strip()

    if value.startswith(
        (
            "http://",
            "https://",
        )
    ):
        tvg_logo = value

# --------------------------------------------------------
# YENİ TEMİZ EXTINF
# --------------------------------------------------------

attributes = []

if tvg_id:

    attributes.append(
        f'tvg-id="{tvg_id}"'
    )

if tvg_logo:

    attributes.append(
        f'tvg-logo="{tvg_logo}"'
    )

attributes.append(
    f'tvg-name="{name}"'
)

attributes.append(
    f'group-title="{group}"'
)

return (
    "#EXTINF:-1 "
    + " ".join(attributes)
    + ","
    + name
)
```

# ============================================================

# KATEGORİ SIRASI

# ============================================================

def category_order(
categories,
):

```
result = {}

number = 0

# categories.json sırası
for category in categories.keys():

    # Diğer'i aşağıda özel olarak ele alacağız
    if category == "Diğer":
        continue

    result[category] = number

    number += 1

# Film yoksa kategori sırasına ekle
if "Film" not in result:

    result["Film"] = number

    number += 1

# Diğer HER ZAMAN EN SON
result["Diğer"] = number

return result
```

# ============================================================

# KANAL SIRASI

# ============================================================

def channel_order(
categories,
):

```
result = {}

for category, names in categories.items():

    if not isinstance(names, list):
        continue

    for number, name in enumerate(names):

        key = channel_key(name)

        if key and key not in result:

            result[key] = number

return result
```

# ============================================================

# SIRALA

# ============================================================

def sort_items(
items,
categories,
index,
):

```
cat_order = category_order(
    categories
)

ch_order = channel_order(
    categories
)

def sort_key(item):

    name, ext, url = item

    category = category_for(
        name,
        ext,
        index,
    )

    category_no = cat_order.get(
        category,
        999999,
    )

    channel_no = ch_order.get(
        channel_key(name),
        999999,
    )

    # categories.json'da olan kanal:
    # önce kategori,
    # sonra listedeki sıra.
    #
    # categories.json'da olmayan:
    # alfabetik olarak kendi kategorisinde.
    return (
        category_no,
        channel_no,
        channel_key(name),
    )

return sorted(
    items,
    key=sort_key,
)
```

# ============================================================

# DAHA İYİ KAYIT

# ============================================================

def better_item(
new,
old,
):

```
new_name, new_ext, new_url, *new_meta = new
old_name, old_ext, old_url, *old_meta = old

# --------------------------------------------------------
# 1. KAYNAK ÖNCELİĞİ
# --------------------------------------------------------

new_priority = (
    new_meta[0]
    if new_meta
    else 1
)

old_priority = (
    old_meta[0]
    if old_meta
    else 1
)

if new_priority != old_priority:

    return (
        new_priority
        > old_priority
    )

# --------------------------------------------------------
# 2. KALİTE
# --------------------------------------------------------

new_quality = quality(
    new_name,
    new_ext,
)

old_quality = quality(
    old_name,
    old_ext,
)

if new_quality != old_quality:

    return (
        new_quality
        > old_quality
    )

# --------------------------------------------------------
# 3. TEMİZ METADATA
# --------------------------------------------------------

new_clean = cleanliness_score(
    new_name,
    new_ext,
)

old_clean = cleanliness_score(
    old_name,
    old_ext,
)

if new_clean != old_clean:

    return (
        new_clean
        > old_clean
    )

# --------------------------------------------------------
# 4. İLK GELEN KAYIT
# --------------------------------------------------------

return False
```

# ============================================================

# TEMİZLİK PUANI

# ============================================================

def cleanliness_score(
name,
ext,
):

```
score = 0

name_upper = (
    name or ""
).upper()

ext_upper = (
    ext or ""
).upper()

if len(name_upper) < 80:
    score += 2

if "TVG-NAME=" not in name_upper:
    score += 1

if "GROUP-TITLE=" not in name_upper:
    score += 1

if ext_upper.count('"') % 2 == 0:
    score += 2

if ext_upper.count(
    "TVG-NAME"
) <= 1:
    score += 1

return score
```

# ============================================================

# NAMED SOURCE OKU

# ============================================================

def read_named_source(
canonical_names,
):

```
if not NAMED_SOURCES.exists():

    print(
        "[BİLGİ] data/kanal_kaynaklari.m3u bulunamadı."
    )

    return []

try:

    text = NAMED_SOURCES.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    records = parse_m3u(
        text,
        canonical_names,
    )

    result = []

    for name, ext, url in records:

        result.append(
            (
                name,
                ext,
                url,
                3,
                0,
            )
        )

    print(
        f"[NAMED] {len(result)} sabit kanal kaynağı"
    )

    return result

except Exception as e:

    print(
        f"[UYARI] kanal_kaynaklari okunamadı: {e}"
    )

    return []
```

# ============================================================

# NORMAL SOURCES

# ============================================================

def read_normal_sources(
sources,
canonical_names,
timeout,
):

```
result = []

successful = 0

for source_index, (
    source,
    source_line,
) in enumerate(
    sources,
    start=1,
):

    try:

        text = fetch(
            source,
            timeout,
        )

        records = parse_m3u(
            text,
            canonical_names,
        )

        for name, ext, url in records:

            # ------------------------------------------------
            # Kaynak sırası:
            #
            # İlk kaynak = 2.000000
            # İkinci kaynak = 1.999999
            #
            # Böylece sources.txt'nin ilk kaynağı
            # daha öncelikli olur.
            # ------------------------------------------------

            priority = (
                2_000_000
                - source_index
            )

            result.append(
                (
                    name,
                    ext,
                    url,
                    priority,
                    source_index,
                )
            )

        successful += 1

        print(
            f"[OK] {len(records):>6} kayıt | "
            f"Kaynak #{source_index} | "
            f"{source}"
        )

    except Exception as e:

        print(
            f"[HATA] Kaynak #{source_index}"
        )

        print(
            f"       {source}"
        )

        print(
            f"       {e}"
        )

return (
    result,
    successful,
)
```

# ============================================================

# MAIN

# ============================================================

def main():

```
print()
print("=" * 70)
print("CAN TV PLAYLIST BUILDER v6")
print("=" * 70)
print()

# ========================================================
# CONFIG
# ========================================================

if CONFIG.exists():

    try:

        config = json.loads(
            CONFIG.read_text(
                encoding="utf-8",
            )
        )

    except Exception:

        config = {}

else:

    config = {}

timeout = int(
    config.get(
        "request_timeout",
        15,
    )
)

# ========================================================
# CATEGORIES
# ========================================================

if not CATEGORIES.exists():

    print(
        "[HATA] categories.json bulunamadı."
    )

    return

try:

    categories = json.loads(
        CATEGORIES.read_text(
            encoding="utf-8",
        )
    )

except Exception as e:

    print(
        f"[HATA] categories.json okunamadı: {e}"
    )

    return

if not isinstance(
    categories,
    dict,
):

    print(
        "[HATA] categories.json sözlük formatında olmalı."
    )

    return

# Bir kez oluşturuyoruz.
canonical_names = (
    build_canonical_names(
        categories
    )
)

index = make_category_index(
    categories
)

# ========================================================
# SOURCES
# ========================================================

sources = read_sources()

if not sources:

    print(
        "[UYARI] sources.txt boş veya bulunamadı."
    )

# ========================================================
# NAMED SOURCES
# ========================================================

named_items = read_named_source(
    canonical_names
)

# ========================================================
# NORMAL SOURCES
# ========================================================

normal_items, successful = (
    read_normal_sources(
        sources,
        canonical_names,
        timeout,
    )
)

# ========================================================
# TÜM KAYITLAR
# ========================================================

all_items = (
    named_items
    + normal_items
)

print()

print(
    f"[TOPLAM] {len(all_items)} kayıt toplandı."
)

# ========================================================
# 1. URL DUPLICATE
# ========================================================

by_url = {}

url_duplicate_count = 0

for item in all_items:

    name, ext, url, *meta = item

    if not url:
        continue

    old = by_url.get(url)

    if old is None:

        by_url[url] = item

    else:

        url_duplicate_count += 1

        if better_item(
            item,
            old,
        ):

            by_url[url] = item

# ========================================================
# 2. CHANNEL DUPLICATE
# ========================================================

by_channel = {}

channel_duplicate_count = 0

for item in by_url.values():

    name, ext, url, *meta = item

    # İsmi yeniden temizle
    clean_name = clean_channel_name(
        name,
        canonical_names,
    )

    item = (
        clean_name,
        ext,
        url,
        *(meta or [1]),
    )

    key = channel_key(
        clean_name
    )

    if not key:
        continue

    old = by_channel.get(key)

    if old is None:

        by_channel[key] = item

    else:

        channel_duplicate_count += 1

        if better_item(
            item,
            old,
        ):

            by_channel[key] = item

# ========================================================
# 3. TEKİL LİSTE
# ========================================================

items = list(
    by_channel.values()
)

# ========================================================
# 4. SIRALAMA
# ========================================================

sort_input = [
    (
        item[0],
        item[1],
        item[2],
    )
    for item in items
]

sorted_items = sort_items(
    sort_input,
    categories,
    index,
)

# ========================================================
# 5. GERÇEK KAYITLARLA EŞLEŞTİR
# ========================================================

item_map = {}

for item in items:

    key = channel_key(
        item[0]
    )

    if key:
        item_map[key] = item

final_items = []

for simple_item in sorted_items:

    key = channel_key(
        simple_item[0]
    )

    original_item = item_map.get(
        key
    )

    if original_item:

        final_items.append(
            original_item
        )

# ========================================================
# OUTPUT
# ========================================================

output = [
    "#EXTM3U"
]

counts = {}

for item in final_items:

    name, ext, url, *meta = item

    group = category_for(
        name,
        ext,
        index,
    )

    output.append(
        rewrite_ext(
            ext,
            name,
            group,
        )
    )

    output.append(
        url
    )

    counts[group] = (
        counts.get(
            group,
            0,
        )
        \+ 1
    )

OUTPUT.write_text(
    "\n".join(output)
    + "\n",
    encoding="utf-8",
)

# ========================================================
# SONUÇ
# ========================================================

print()
print("=" * 70)
print("SONUÇ")
print("=" * 70)

print(
    f"Normal kaynak       : {len(sources)}"
)

print(
    f"Başarılı kaynak     : {successful}"
)

print(
    f"Named kanal         : {len(named_items)}"
)

print(
    f"Toplam kayıt        : {len(all_items)}"
)

print(
    f"Tekil URL           : {len(by_url)}"
)

print(
    f"URL duplicate       : {url_duplicate_count}"
)

print(
    f"Tekil kanal         : {len(by_channel)}"
)

print(
    f"Kanal duplicate     : {channel_duplicate_count}"
)

print()

print("KATEGORİLER")
print("-" * 70)

# categories.json sırası
printed = set()

for category in categories.keys():

    print(
        f"{category}: "
        f"{counts.get(category, 0)}"
    )

    printed.add(category)

# Film yoksa bile göster
if "Film" not in printed:

    print(
        f"Film: {counts.get('Film', 0)}"
    )

# Diğer her zaman göster
if "Diğer" not in printed:

    print(
        f"Diğer: {counts.get('Diğer', 0)}"
    )

print()

print(
    f"Çıktı: {OUTPUT}"
)

print("=" * 70)
```

# ============================================================

# RUN

# ============================================================

if **name** == "**main**":
main()
