"""Build star-map.json from Japanese Wikipedia. Cached responses support resuming a run."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
API = "https://ja.wikipedia.org/w/api.php"
USER_AGENT = "WikiRace/0.5.2 (https://github.com/daodaofamas/wiki-race05)"
TARGETS = {
    "動物": 350, "植物・自然": 300, "宇宙": 250, "科学": 400, "日本の地理": 400, "世界の地理": 400,
    "日本史": 400, "世界史": 400, "食べ物": 300, "スポーツ": 350, "乗り物・技術": 350,
    "音楽・芸術": 250, "文化・ゲーム": 300, "人体・医学": 250, "建築・名所": 150, "恐竜・古生物": 150,
}
# Only topical categories are queried. Category evidence is direct membership, without traversing subcategories.
SOURCES = {
    "動物": "動物 動物学 哺乳類 鳥類 爬虫類 両生類 魚類 昆虫 無脊椎動物 軟体動物 ネコ科 イヌ科 クマ科 ウシ科 齧歯目 霊長目 昆虫の分類 チョウ 甲虫 ハチ ヘビ カメ サメ 鯨類 深海魚 海獣 カニ エビ クモ 貝類 イカ タコ スズメ目 アザラシ ペンギン目 マグロ カエル ワニ",
    "植物・自然": "植物 植物学 樹木 果樹 花 被子植物 裸子植物 菌類 森林 生態系 生息域 気象 気象現象 自然現象 地形 地質現象 岩石 自然災害 生態学 植物の形態 植物の生殖 花卉 薬用植物 山野草 草本 キク科 バラ科 イネ科 マメ科 植生 海藻 風 雲 降水 地震 火山 水文学 鉱物 環境問題",
    "宇宙": "天文学 宇宙論 銀河 恒星 太陽系 惑星 月 彗星 小惑星 星座 天体 天体物理学 天文学の概念 太陽系外惑星 宇宙探査 宇宙からの観測 宇宙望遠鏡 望遠鏡 宇宙飛行 人工衛星 アポロ計画 恒星の種類 星雲 天体観測 ブラックホール 星団 太陽 地球近傍小惑星 宇宙機 ロケット",
    "科学": "科学 物理学 物理学の概念 力学 熱力学 電磁気学 量子力学 化学 化学の概念 化学反応 数学 数学の概念 数学定数 数学用語 生物学 遺伝学 分子生物学 地球科学 科学史 統計学 元素 単位 SI単位 実験 計測 計量学 物性物理学 物理定数 幾何学 確率論 生化学 無機化学 有機化学 細胞生物学",
    "日本の地理": "日本の地理 日本の地方区分 日本の地理用語 日本の島 日本の半島 日本の湖 日本の河川 日本の山 日本の平野 日本の海峡 日本の湾 日本の山地 日本の盆地 日本の高原 日本百名山 日本二百名山 日本の国立公園 日本の国定公園 日本の都道府県 日本の都市 政令指定都市 中核市 施行時特例市 日本の海岸 日本の岬 日本の火山 日本の山脈 日本の滝 日本の自然景勝地 日本の湿原 日本の水域",
    "世界の地理": "大陸 海洋 海峡 島 大洋 海域 世界の国 国際連合加盟国 アジアの国 ヨーロッパの国 アフリカの国 北アメリカの国 南アメリカの国 オセアニアの国 カリブ海地域の国 中央アメリカの国 首都 アジアの首都 ヨーロッパの首都 アフリカの首都 北アメリカの首都 南アメリカの首都 オセアニアの首都 湾 砂漠 山脈 国境 地域 世界の地理 地政学 地理用語 地理学",
    "日本史": "日本の歴史 日本の歴史_(時代別) 日本の戦争 日本の歴史上の事件 日本の元号 日本の条約 日本の考古学 日本の文化史 幕末 明治維新 江戸時代 戦国時代_(日本) 日本の戦闘 日本の政治史 日本の法制史 縄文時代 弥生時代 古墳時代 飛鳥時代 奈良時代 平安時代 鎌倉時代 室町時代 安土桃山時代 昭和時代 明治時代 江戸幕府 日本の制度史 日本の歴史上の法令 日本の歴史文書 日本の反乱",
    "世界史": "世界の歴史 世界史 古代史 中世 近世 近代史 文明 歴史上の帝国 かつて存在した国家 戦争 革命 条約 古代ローマ 古代ギリシア 古代エジプト 大航海時代 第一次世界大戦 第二次世界大戦 ルネサンス 冷戦 中国の歴史 考古学 世界大戦 産業革命 帝国主義 植民地 宗教改革 歴史の時代区分 アジア史 ヨーロッパ史 アフリカ史 アメリカ大陸史",
    "食べ物": "食品 食材 料理 穀物 果物 野菜 香辛料 調味料 菓子 飲料 日本の料理 中華料理 パン チーズ 麺料理 米料理 食品加工 保存食 洋菓子 和菓子 飲料の種類 酒 乳製品 料理の種類 料理用語 調理法 豆類 食用油脂 卵料理 肉料理 魚介料理 スープ 発酵食品 キノコ料理",
    "スポーツ": "スポーツ スポーツ競技 球技 オリンピック競技 冬季スポーツ 陸上競技 水泳 格闘技 武道 スポーツ用語 サッカー用語 野球用語 バスケットボール用語 バレーボール用語 テニス 卓球 自転車競技 競技会 スポーツのルール スポーツ器具 体操競技 柔道 スキー スケート ラグビー ゴルフ クリケット モータースポーツ アウトドアスポーツ 各国のスポーツ",
    "乗り物・技術": "交通 乗り物 輸送機器 機械 機械工学 技術 航空機 船舶 自動車 鉄道 自転車 公共交通 情報技術 コンピュータ 電気機器 エネルギー技術 通信工学 計算機科学 産業機械 工学 工具 道具 原動機 電子工学 通信機器 車両 ハードウェア インターネット 技術史 航空 鉄道車両 交通手段 家電機器",
    "音楽・芸術": "音楽 音楽のジャンル 楽器 音楽用語 美術 芸術 美術の技法 芸術運動 絵画 彫刻 版画 写真 音楽理論 日本の伝統音楽 舞踊 クラシック音楽 鍵盤楽器 打楽器 弦楽器 管楽器 西洋美術 絵画技術 日本美術 音楽史 美術史 工芸 録音 演奏技法 絵画のジャンル 美術用語",
    "文化・ゲーム": "文化 ゲーム 遊戯 ボードゲーム カードゲーム パズル コンピュータゲームのジャンル 文学 物語 神話 祭 民俗 伝統文化 映画 アニメ 漫画 日本の文化 世界の文化 娯楽 年中行事 コンピュータゲーム 民間伝承 文学のジャンル 映画のジャンル 漫画のジャンル 民俗学 習俗 祝祭日 日本の年中行事 玩具 伝統芸能 アニメのジャンル",
    "人体・医学": "人体 解剖学 器官 臓器 医学 医療 医学用語 病気 症候 健康 生理学 人体の部位 骨 筋肉 人体の神経 ヒトの解剖学 予防医学 栄養学 歯 医療機器 救急医学 内科学 外科学 診断と治療 医学検査 呼吸器 循環器 消化器 神経系 感覚器 医療の歴史",
    "建築・名所": "建築 建築様式 建築物 塔 橋 城 宮殿 神殿 超高層建築物 世界遺産 建築史 建築用語 建築構造 観光地 日本の城 日本の塔 日本の橋 日本の観光地 建築設計 日本の世界遺産 庭園 日本庭園 記念碑 灯台 建築意匠 宗教建築物 歴史的建造物",
    "恐竜・古生物": "恐竜 古生物 古生物学 化石 中生代 古生代 新生代 絶滅した動物 絶滅した爬虫類 絶滅した哺乳類 古生代の生物 中生代の生物 新生代の生物 獣脚類 竜脚類 鳥盤類 翼竜 首長竜 魚竜 三畳紀の恐竜 ジュラ紀の恐竜 白亜紀の恐竜 恐竜の分類 化石種 先史時代の哺乳類 先史時代の爬虫類 絶滅した植物",
}
NON_TOPIC_TITLE = re.compile(r"一覧(?:$| \()|^一覧[:：]|^[0-9０-９]+年([0-9０-９]+月)?$|^ウィキペディア")
# Public categories can include biographies, products, laws, or works that only refer to the topic.
OFF_TOPIC = {
    "動物": {"IZoo", "VAAM", "トロ", "赤肉", "妊娠", "交感神経系", "第五福竜丸", "マグロ (テレビドラマ)",
           "ミッキーとあざらし", "ヒト型爬虫類", "セルキー"},
    "科学": {"競走馬の血統"},
    "日本の地理": {"湖沼水質保全特別措置法"},
    "世界の地理": {"I-94", "オーシャンズセブン", "ラグランジュ点", "警備区域 (自衛隊)", "水路部 (日本海軍)",
                "地政学ボーイズ 〜国がサラリーマンになって働く会社〜"},
    "日本史": {"2ちゃんねると5ちゃんねるの歴史"},
    "世界史": {"1980年モスクワオリンピック", "1984年ロサンゼルスオリンピック", "U-2 (航空機)", "NATOコードネーム"},
    "スポーツ": {"パチンコ", "引退"},
    "乗り物・技術": {"サイエンス・フィクション"},
    "音楽・芸術": {"Adobe Photoshop", "Drummania"},
    "文化・ゲーム": {"DTS (サウンドシステム)", "隻眼"},
    "人体・医学": {"T4作戦", "美人", "119番", "色"},
    "建築・名所": {"高さ"},
}


class Wikipedia:
    def __init__(self, cache):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.next_request = 0

    def query(self, **parameters):
        query = urllib.parse.urlencode(dict(action="query", format="json", formatversion=2, maxlag=5, **parameters))
        file = self.cache / (hashlib.sha256(query.encode()).hexdigest() + ".json")
        if file.exists():
            return json.loads(file.read_text())
        request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
        for attempt in range(6):
            time.sleep(max(0, self.next_request - time.monotonic()))
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    result = json.load(response)
                    retry_after = response.headers.get("Retry-After")
                if not result.get("error"):
                    file.write_text(json.dumps(result, ensure_ascii=False))
                    self.next_request = time.monotonic() + 0.7
                    return result
                error = result["error"]
                if error.get("code") not in ("maxlag", "ratelimited", "readonly", "cirrussearch-too-busy-error"):
                    raise RuntimeError(error)
                reason = error["code"]
            except urllib.error.HTTPError as error:
                if error.code not in (429, 502, 503, 504):
                    raise
                reason = error.code
                retry_after = error.headers.get("Retry-After")
            except (TimeoutError, urllib.error.URLError):
                reason = "connection error"
                retry_after = None
            delay = max(2, int(retry_after)) if retry_after and retry_after.isdecimal() else 4 * (attempt + 1)
            print(f"API {reason}: retry in {delay}s", flush=True)
            self.next_request = time.monotonic() + delay
        raise RuntimeError("Wikipedia API did not recover")


def original_groups():
    html = (ROOT / "index.html").read_text()
    return json.loads(html.split("const groups=", 1)[1].split(";\n", 1)[0])


def norm(title):
    return unicodedata.normalize("NFC", title.strip().replace("_", " "))


def is_article(page):
    return (page.get("ns") == 0 and page.get("pageid", 0) > 0
            and not any(key in page for key in ("missing", "invalid", "redirect"))
            and "disambiguation" not in page.get("pageprops", {})
            and not re.search(r"[|#]", page["title"]))


def collect(wiki, topic, offsets):
    categories = [name.replace("_", " ") for name in SOURCES[topic].split()]
    category_names = "|".join("Category:" + name for name in categories)
    found = {}
    for offset in offsets:
        response = wiki.query(
            generator="search", gsrnamespace=0, gsrlimit=500, gsroffset=offset,
            gsrsearch='incategory:"' + "|".join(categories) + '"', gsrsort="incoming_links_desc",
            prop="info|pageprops|categories|pageviews", ppprop="disambiguation",
            clcategories=category_names, clshow="!hidden", cllimit="max", pvipdays=14,
        )
        # Keep only candidates whose direct category evidence is present in this batch.
        for page in response.get("query", {}).get("pages", []):
            if (not is_article(page) or page.get("length", 0) < 2000
                    or NON_TOPIC_TITLE.search(page["title"]) or page["title"] in OFF_TOPIC.get(topic, ())):
                continue
            matches = len({cat["title"] for cat in page.get("categories", [])})
            if not matches:
                continue
            views = [value for value in (page.get("pageviews") or {}).values() if isinstance(value, int)]
            daily = sum(views) / len(views) if views else 0
            rank = page["index"]
            quality = 2 * math.log1p(daily) + math.log1p(page["length"]) / 2 - math.log(rank)
            found[page["pageid"]] = (norm(page["title"]), matches, quality)
    return found


def curated_ids(wiki, groups):
    all_titles = [title for titles in groups.values() for title in titles]
    ids = {}
    for i in range(0, len(all_titles), 50):
        titles = all_titles[i:i + 50]
        response = wiki.query(titles="|".join(titles), redirects=1, prop="info|pageprops", ppprop="disambiguation")
        ids.update({norm(page["title"]): page["pageid"] for page in response["query"]["pages"] if is_article(page)})
    if len(ids) != 634 or set(ids) != set(all_titles) or len(set(ids.values())) != len(ids):
        raise ValueError("The curated titles must be 634 distinct canonical articles")
    return ids


def assign(groups, reserved, candidates):
    results = {group: [(reserved[title], title) for title in titles] for group, titles in groups.items()}
    used_ids = set(reserved.values())
    used_titles = set(reserved)
    by_id = defaultdict(list)
    for group, articles in candidates.items():
        for page_id, (title, matches, quality) in articles.items():
            if group == "世界の地理" and page_id in candidates["日本の地理"]:
                continue
            if page_id not in used_ids and title not in used_titles:
                by_id[page_id].append((group, title, matches, quality))
    ordered = sorted(by_id.items(), key=lambda item: (-max(v[3] for v in item[1]), len(item[1]), item[0]))
    for page_id, options in ordered:
        options.sort(key=lambda option: (
            -option[2], (len(results[option[0]]) - len(groups[option[0]])) /
            (TARGETS[option[0]] - len(groups[option[0]])), -option[3], option[0]))
        for group, title, _, _ in options:
            if len(results[group]) < TARGETS[group] and title not in used_titles:
                results[group].append((page_id, title))
                used_titles.add(title)
                break
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "star-map.json")
    args = parser.parse_args()
    wiki = Wikipedia(args.cache)
    groups = original_groups()
    if list(groups) != list(TARGETS) or set(SOURCES) != set(groups):
        raise ValueError("Star map genres differ from the game")
    candidates = {}
    for group in groups:
        candidates[group] = collect(wiki, group, [0])
        print(f"{group}: {len(candidates[group])} candidates", flush=True)
    reserved = curated_ids(wiki, groups)
    for offset in (500, 1000, 1500):
        results = assign(groups, reserved, candidates)
        short = [group for group in groups if len(results[group]) < TARGETS[group]]
        if not short:
            break
        for group in short:
            print(f"{group}: {len(results[group])}/{TARGETS[group]}, searching at {offset}", flush=True)
            candidates[group].update(collect(wiki, group, [offset]))
    results = assign(groups, reserved, candidates)
    counts = {group: len(articles) for group, articles in results.items()}
    print(counts, flush=True)
    if counts != TARGETS:
        raise ValueError("The sources did not provide enough classified articles")
    lines = ['{"version":1,"genres":{']
    for index, (group, articles) in enumerate(results.items()):
        lines.append(json.dumps(group, ensure_ascii=False) + ':[\n' +
                     ',\n'.join(json.dumps(article, ensure_ascii=False, separators=(",", ":")) for article in articles) +
                     '\n]' + (',' if index + 1 < len(results) else ''))
    args.output.write_text("\n".join(lines) + "\n}}\n")


if __name__ == "__main__":
    main()
