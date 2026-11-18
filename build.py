#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CAN TV - Playlist Builder v5.1
"""

import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent

SOURCES = ROOT / "sources.txt"
NAMED_SOURCES = ROOT / "data" / "kanal_kaynaklari.m3u"
CATEGORIES = ROOT / "categories.json"
CONFIG = ROOT / "config.json"
OUTPUT = ROOT / "playlist.m3u"

UA = "Mozilla/5.0 (CAN-TV-Builder/5.1)"


def norm(value):
    s = str(value or "").upper().strip()
    tr_map = str.maketrans({
        "İ": "I", "Ş": "S", "Ğ": "G", "Ü": "U",
        "Ö": "O", "Ç": "C", "Â": "A", "Î": "I", "Û": "U",
    })
    s = s.translate(tr_map)
    s = re.sub(r"\b(FHD|UHD|HD|SD|4K|HEVC|H265|H264|FULL HD)\b", " ", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def channel_key(name):
    n = norm(name)
    if not n:
        return ""
    if n in {"TV8", "TV 8"}:
        return "TV8"
    if n in {"TV85", "TV8 5", "TV 8 5", "TV 85"} or re.search(r"\bTV\s*8\s*5\b", n):
        return "TV8.5"
    if n in {"BENGUTURK", "BENGU TURK"}:
        return "BENGUTURK"
    if n in {"HABERTURK", "HABER TURK"}:
        return "HABERTURK"
    if n == "TRT MUZIK":
        return "TRT MUZIK"
    if n == "TRT DIYANET":
        return "TRT DIYANET"
    if n == "TRT DIYANET COCUK":
        return "TRT DIYANET COCUK"
    if n in {"NAT GEO", "NATIONAL GEOGRAPHIC"}:
        return "NATIONAL GEOGRAPHIC"
    if n in {"NAT GEO WILD", "NAT WILD", "NATIONAL GEOGRAPHIC WILD"}:
        return "NATIONAL GEOGRAPHIC WILD"
    if n in {"ID DISCOVERY", "DISCOVERY ID", "INVESTIGATION DISCOVERY"}:
        return "DISCOVERY ID"
    if n in {"BLOOMBERG HT", "BLOOMBERGHT"}:
        return "BLOOMBERG HT"
    if n == "EKOTURK":
        return "EKOTURK"
    if n in {"LIFETIME", "LIFE TIME"}:
        return "LIFETIME"
    if n in {"KRAL FM", "KIRAL FM"}:
        return "KRAL FM"
    if n in {"KRAL POP", "KIRAL POP"}:
        return "KRAL POP"
    return n


def build_canonical_names(categories):
    result = {}
    for category, names in categories.items():
        if not isinstance(names, list):
            continue
        for name in names:
            key = channel_key(name)
            if key:
                result[key] = name
    return result


def clean_channel_name(name, categories):
    original = str(name or "").strip()
    if not original:
        return "KANAL"

    key = channel_key(original)
    canonical_names = build_canonical_names(categories)

    if key in canonical_names:
        return canonical_names[key]

    n = norm(original)

    if re.search(r"\bTV\s*8\s*5\b", n):
        return canonical_names.get("TV8.5", "TV 8.5")

    if re.search(r"\bTV\s*8\b", n):
        if not re.search(r"\bTV\s*8\s*5\b", n):
            return canonical_names.get("TV8", "TV8")

    candidates = sorted(
        canonical_names.items(),
        key=lambda x: len(norm(x[1])),
        reverse=True,
    )

    for candidate_key, candidate_name in candidates:
        candidate_norm = norm(candidate_name)
        if not candidate_norm or len(candidate_norm) < 4:
            continue
        if candidate_norm in n:
            return candidate_name

    return original


def read_sources():
    if not SOURCES.exists():
        print("[UYARI] sources.txt bulunamadı.")
        return []

    result = []
    for line in SOURCES.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        result.append(line)
    return result


def fetch(url, timeout):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_tvg_name(ext):
    match = re.search(r'tvg-name\s*=\s*"([^"]+)"', ext, flags=re.IGNORECASE)
    if match and match.group(1).strip():
        return match.group(1).strip()

    match = re.search(r"tvg-name\s*=\s*'([^']+)'", ext, flags=re.IGNORECASE)
    if match and match.group(1).strip():
        return match.group(1).strip()

    return ""


def extract_name(ext, categories=None):
    tvg_name = extract_tvg_name(ext)
    if tvg_name:
        if categories:
            return clean_channel_name(tvg_name, categories)
        return tvg_name

    if "," in ext:
        name = ext.split(",", 1)[1].strip()
        name = re.sub(r'\s+group-title=.*$', "", name, flags=re.IGNORECASE).strip()
        if categories:
            name = clean_channel_name(name, categories)
        return name or "KANAL"

    return "KANAL"


def parse_m3u(text, categories=None):
    lines = text.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("#EXTINF"):
            ext = line
            vlc_opts = []
            j = i + 1

            while j < len(lines):
                candidate = lines[j].strip()
                if not candidate:
                    j += 1
                    continue
                if candidate.startswith("#EXTVLCOPT"):
                    vlc_opts.append(candidate)
                    j += 1
                    continue
                if candidate.startswith("#"):
                    break
                break

            if j < len(lines):
                url = lines[j].strip()
                if (
                    url
                    and not url.startswith("#")
                    and (url.startswith("http://") or url.startswith("https://"))
                ):
                    name = extract_name(ext, categories)
                    result.append((name, ext, url, vlc_opts))
                    i = j + 1
                    continue

        i += 1

    return result


def make_category_index(categories):
    index = {}
    for category, names in categories.items():
        if not isinstance(names, list):
            continue
        for name in names:
            key = channel_key(name)
            if key:
                index[key] = category
    return index


def category_for(name, ext, index):
    key = channel_key(name)
    if key in index:
        return index[key]

    ext_upper = (ext or "").upper()

    if re.search(r'TVG[-_ ]?YEAR\s*=\s*["\x27]?\d{4}', ext_upper):
        return "Film"

    if "IMAGE.TMDB.ORG" in ext_upper or "IMAGE.TMDB.ORG" in (name or "").upper():
        return "Film"

    if re.search(r"\b(?:19|20)\d{2}\s*$", norm(name)):
        return "Film"

    return "Diğer"


def quality(name, ext=""):
    value = ((name or "") + " " + (ext or "")).upper()
    if re.search(r"\b(4K|UHD)\b", value):
        return 4
    if re.search(r"\b(FHD|FULL HD)\b", value):
        return 3
    if re.search(r"\bHD\b", value):
        return 2
    if re.search(r"\bSD\b", value):
        return 1
    return 0


def rewrite_ext(ext, name, group):
    tvg_id = ""
    tvg_logo = ""

    match = re.search(r'tvg-id\s*=\s*"([^"]+)"', ext, flags=re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if value and "TVG-NAME" not in value.upper() and "GROUP-TITLE" not in value.upper():
            tvg_id = value

    match = re.search(r'tvg-logo\s*=\s*"([^"]+)"', ext, flags=re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if value.startswith(("http://", "https://")):
            tvg_logo = value

    attributes = []
    if tvg_id:
        attributes.append(f'tvg-id="{tvg_id}"')
    if tvg_logo:
        attributes.append(f'tvg-logo="{tvg_logo}"')
    attributes.append(f'tvg-name="{name}"')
    attributes.append(f'group-title="{group}"')

    return "#EXTINF:-1 " + " ".join(attributes) + "," + name


def category_order(categories):
    result = {}
    number = 0
    for category in categories.keys():
        result[category] = number
        number += 1
    if "Film" not in result:
        result["Film"] = number
        number += 1
    result["Diğer"] = number
    return result


def channel_order(categories):
    result = {}
    for category, names in categories.items():
        if not isinstance(names, list):
            continue
        for number, name in enumerate(names):
            key = channel_key(name)
            if key and key not in result:
                result[key] = number
    return result


def sort_items(items, categories, index):
    cat_order = category_order(categories)
    ch_order = channel_order(categories)

    def sort_key(item):
        name, ext, url = item
        category = category_for(name, ext, index)
        category_no = cat_order.get(category, 999999)
        channel_no = ch_order.get(channel_key(name), 999999)
        return (category_no, channel_no, channel_key(name))

    return sorted(items, key=sort_key)


def cleanliness_score(name, ext):
    score = 0
    name_upper = (name or "").upper()
    ext_upper = (ext or "").upper()

    if len(name_upper) < 80:
        score += 2
    if "TVG-NAME=" not in name_upper:
        score += 1
    if "GROUP-TITLE=" not in name_upper:
        score += 1
    if ext_upper.count('"') % 2 == 0:
        score += 2
    if ext_upper.count("TVG-NAME") <= 1:
        score += 1
    return score


def better_item(new, old):
    new_name, new_ext, new_url, *new_meta = new
    old_name, old_ext, old_url, *old_meta = old

    new_priority = new_meta[0] if new_meta else 1
    old_priority = old_meta[0] if old_meta else 1

    if new_priority != old_priority:
        return new_priority > old_priority

    new_quality = quality(new_name, new_ext)
    old_quality = quality(old_name, old_ext)

    if new_quality != old_quality:
        return new_quality > old_quality

    new_clean = cleanliness_score(new_name, new_ext)
    old_clean = cleanliness_score(old_name, old_ext)

    if new_clean != old_clean:
        return new_clean > old_clean

    return False


def read_named_source(categories):
    if not NAMED_SOURCES.exists():
        print("[BİLGİ] data/kanal_kaynaklari.m3u bulunamadı.")
        return []
    try:
        text = NAMED_SOURCES.read_text(encoding="utf-8", errors="ignore")
        records = parse_m3u(text, categories)
        result = [(name, ext, url, 3, vlc_opts) for name, ext, url, vlc_opts in records]
        print(f"[NAMED] {len(result)} sabit kanal kaynağı")
        return result
    except Exception as e:
        print(f"[UYARI] kanal_kaynaklari okunamadı: {e}")
        return []


def read_normal_sources(sources, categories, timeout):
    result = []
    successful = 0
    for source in sources:
        try:
            text = fetch(source, timeout)
            records = parse_m3u(text, categories)
            for name, ext, url, vlc_opts in records:
                result.append((name, ext, url, 2, vlc_opts))
            successful += 1
            print(f"[OK] {len(records):>6} kayıt | {source}")
        except Exception as e:
            print(f"[HATA] {source}\n       {e}")
    return result, successful


def main():
    print("\n" + "=" * 70 + "\nCAN TV PLAYLIST BUILDER v5.1\n" + "=" * 70 + "\n")
    config = {}
    if CONFIG.exists():
        try:
            config = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    timeout = int(config.get("request_timeout", 30))
    if not CATEGORIES.exists():
        print("[HATA] categories.json bulunamadı.")
        return
    categories = json.loads(CATEGORIES.read_text(encoding="utf-8"))
    index = make_category_index(categories)
    sources = read_sources()
    
    named_items = read_named_source(categories)
    normal_items, successful = read_normal_sources(sources, categories, timeout)
    all_items = named_items + normal_items
    print(f"\n[TOPLAM] {len(all_items)} kayıt toplandı.")
    
    by_url = {}
    for item in all_items:
        name, ext, url, *meta = item
        if not url:
            continue
        old = by_url.get(url)
        if old is None or better_item(item, old):
            by_url[url] = item
            
    by_channel = {}
    duplicate_count = 0
    for item in by_url.values():
        name, ext, url, *meta = item
        clean_name = clean_channel_name(name, categories)
        priority = meta[0] if len(meta) >= 1 else 1
        vlc_opts = meta[1] if len(meta) >= 2 else []
        item = (clean_name, ext, url, priority, vlc_opts)
        key = channel_key(clean_name)
        if not key:
            continue
        old = by_channel.get(key)
        if old is None:
            by_channel[key] = item
        else:
            duplicate_count += 1
            if better_item(item, old):
                by_channel[key] = item
                print(f"[DUP] {clean_name}")
                
    items = list(by_channel.values())
    sort_input = [(item[0], item[1], item[2]) for item in items]
    sorted_items = sort_items(sort_input, categories, index)
    item_map = {channel_key(item[0]): item for item in items}
    final_items = [item_map[channel_key(s[0])] for s in sorted_items if channel_key(s[0]) in item_map]
    
    output = ["#EXTM3U"]
    counts = {}
    for item in final_items:
        name, ext, url, *meta = item
        vlc_opts = meta[1] if len(meta) >= 2 else []
        group = category_for(name, ext, index)
        output.append(rewrite_ext(ext, name, group))
        output.extend(vlc_opts)
        output.append(url)
        counts[group] = counts.get(group, 0) + 1
        
    OUTPUT.write_text("\n".join(output) + "\n", encoding="utf-8")
    print("\n" + "=" * 70 + "\nSONUÇ\n" + "=" * 70)
    print(f"Normal kaynak       : {len(sources)}")
    print(f"Başarılı kaynak     : {successful}")
    print(f"Named kanal         : {len(named_items)}")
    print(f"Toplam kayıt        : {len(all_items)}")
    print(f"Tekil URL           : {len(by_url)}")
    print(f"Tekil kanal         : {len(by_channel)}")
    print(f"Silinen duplicate   : {duplicate_count}\n")
    print("KATEGORİLER\n" + "-" * 70)
    for category in categories.keys():
        print(f"{category}: {counts.get(category, 0)}")
    if "Film" in counts:
        print(f"Film: {counts['Film']}")
    print(f"Diğer: {counts.get('Diğer', 0)}\nÇıktı: {OUTPUT}\n" + "=" * 70)


if __name__ == "__main__":
    main()
