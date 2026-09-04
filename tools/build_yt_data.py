# -*- coding: utf-8 -*-
"""YouTube旅Vlog の Gemini 解析結果から初期 spots.json / videos.json を組み立てる一回きりのスクリプト。

使い方 (作業ディレクトリ = 解析結果の置き場):
  1) python build_yt_data.py collect <analysis_dir> <videos_selected.json>
       → raw_spots.json (座標からエリアを決めて city に入れる。merge.py はこの city 単位で名寄せする)
  2) python ~/.claude/skills/region-spot-map/assets/merge.py raw_spots.json merged/
  3) python build_yt_data.py build merged/ <videos_selected.json> <repo>/data
       → spots.json / videos.json (会場マーカー入り)
"""
import glob
import io
import json
import math
import os
import re
import sys
import unicodedata

AREAS = [
    {"id": "matsuyama", "name": "松山市街（松山城・大街道）", "color": "#e8543f"},
    {"id": "dogo",      "name": "道後温泉",                   "color": "#e0489a"},
    {"id": "imabari",   "name": "今治・しまなみ海道",          "color": "#3f7fd6"},
    {"id": "toyo",      "name": "新居浜・西条・東予",          "color": "#2f9e7d"},
    {"id": "iyo",       "name": "伊予・内子・大洲・久万高原",    "color": "#b07d2a"},
    {"id": "nanyo",     "name": "宇和島・南予",                "color": "#7b5cd6"},
    {"id": "other",     "name": "県外（しまなみ広島側・香川）",  "color": "#8a7350"},
]
CATS = {"グルメ", "カフェ・喫茶", "観光", "レトロ", "雑貨・土産", "自然", "動物", "体験", "宿", "温泉"}
# 全国チェーン (動画内で立ち寄っただけで「おすすめ」ではない) は載せない
DROP_PREFIX = ("すき家", "松屋 ", "プロント", "スターバックス", "マクドナルド", "セブン", "ローソン", "ファミリーマート")
PREF = (32.85, 34.35, 132.0, 133.75)      # 愛媛県本体のおよその範囲
BBOX = (32.6, 34.6, 131.7, 134.1)         # マージン付き (pipeline.json と同じ)
DOGO = (33.8523, 132.7863)                # 道後温泉本館

VENUE = {
    "slug": "matsuyama-shimin-kaikan", "name": "松山市民会館（回覧板 in 愛媛 会場）",
    "area": "matsuyama", "cat": "会場", "lat": 33.84089, "lng": 132.7612, "approx": False,
    "desc": "「ぽこぴーの回覧板」愛媛公演の会場（2026年10月12日・大ホール）。松山城のふもと城山公園（堀之内）内にあり、松山市駅・大街道から徒歩圏。",
    "address": "愛媛県松山市堀之内５", "url": "http://www.cul-spo.or.jp/mcph/",
    "place_id": "ChIJAQAACY7lTzURgUmFvJWhqfY",
    "sources": [{"type": "x", "url": "https://x.com/ponpokoka/status/2031704199483019571",
                 "author": "ponpokoka", "date": "2026-03-11",
                 "quote": "回覧板2026 追加開催決定‼️ 今年はこの5か所だっ！！！ 4月福島！！ 6月大分！！ 8月石川！！ 10月愛媛！！ 12月奈良！！"}],
}


def dist_km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def area_of(lat, lng, name=""):
    if dist_km((lat, lng), DOGO) <= 1.3 or "道後" in name:
        return "dogo"
    if not (PREF[0] <= lat <= PREF[1] and PREF[2] <= lng <= PREF[3]):
        return "other"
    if lng >= 133.05:          # 西条(壬生川・小松)・東予港・新居浜・四国中央
        return "toyo"
    if lat >= 33.95 and lng >= 132.85:
        return "imabari"
    if lat < 33.45:
        return "nanyo"
    if lat < 33.78 or lng < 132.62:
        return "iyo"
    return "matsuyama"


def collect(analysis_dir, videos_json):
    vids = [v["id"] for v in json.load(io.open(videos_json, encoding="utf-8"))]
    raw = []
    for vid in vids:
        p = os.path.join(analysis_dir, vid + ".json")
        if not os.path.exists(p):
            print("MISSING analysis:", vid)
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        for s in d["spots"]:
            s = dict(s)
            s["video"] = vid
            s["city_raw"] = s.get("city", "")
            s["city"] = area_of(s["lat"], s["lng"], s["name_ja"])
            raw.append(s)
    json.dump(raw, io.open("raw_spots.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("raw spots:", len(raw), Counter(s["city"] for s in raw))


def slugify(name_local, name_ja, used):
    cands = [name_local or "", name_ja]
    s = ""
    for c in cands:
        t = unicodedata.normalize("NFKD", c)
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
        if len(t) >= 3:
            s = t
            break
    s = (s or "spot")[:40].rstrip("-")
    base, n = s, 2
    while s in used:
        s = f"{base}-{n}"
        n += 1
    used.add(s)
    return s


def build(merged_dir, videos_json, out_dir):
    raw = json.load(io.open("raw_spots.json", encoding="utf-8"))
    for i, s in enumerate(raw):
        s["idx"] = i
    spots, used = [VENUE], {VENUE["slug"]}
    for area in AREAS:
        p = os.path.join(merged_dir, f"merged_{area['id']}.json")
        if not os.path.exists(p):
            continue
        merged = json.load(io.open(p, encoding="utf-8"))
        for m in merged["spots"]:
            if m["name_ja"].startswith(DROP_PREFIX):
                print("DROP chain:", m["name_ja"])
                continue
            vids, seen = [], set()
            for idx in m["members"]:
                v = raw[idx]["video"]
                if v not in seen:
                    seen.add(v)
                    vids.append(v)
            lat, lng = m["lat"], m["lng"]
            aid = area_of(lat, lng, m["name_ja"])   # 統合後の座標で再判定
            if not (BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lng <= BBOX[3]):
                print("BBOX OUT (skip):", m["name_ja"], lat, lng)
                continue
            spot = {
                "slug": slugify(m.get("name_local"), m["name_ja"], used),
                "name": m["name_ja"], "area": aid,
                "cat": m["category"] if m["category"] in CATS else "観光",
                "lat": round(lat, 5), "lng": round(lng, 5), "approx": bool(m["approx"]),
                "desc": m["desc"],
                "sources": [{"type": "youtube", "id": v} for v in vids],
            }
            if aid == "other":
                spot["out_of_pref"] = True
            spots.append(spot)
    used_areas = {s["area"] for s in spots}
    areas = [a for a in AREAS if a["id"] in used_areas]
    videos = {v["id"]: {"title": v["title"], "channel": v["channel"]}
              for v in json.load(io.open(videos_json, encoding="utf-8"))}
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"areas": areas, "spots": spots},
              io.open(os.path.join(out_dir, "spots.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(videos, io.open(os.path.join(out_dir, "videos.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print("spots:", len(spots), Counter(s["area"] for s in spots))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "collect":
        collect(sys.argv[2], sys.argv[3])
    elif cmd == "build":
        build(sys.argv[2], sys.argv[3], sys.argv[4])
