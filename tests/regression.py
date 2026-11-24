"""Browser regressions for Wiki Race. Run with python3 tests/regression.py."""
import functools
import http.server
import json
import os
import pathlib
import re
import threading
import unittest
import urllib.parse

from playwright.sync_api import Error, expect, sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Representative MediaWiki responses for controlled browser tests.
PAGES = {
    "富士山": """
        <div class="mw-parser-output">
        <p onmouseover="" style="opacity:0">富士山は
        <a href="./山梨県">山梨県</a>と<a href="./日本">日本</a>にある。
        <a href="https://example.invalid/wiki/日本">外部URL</a>
        <a href="ftp://ja.wikipedia.org/wiki/日本">別プロトコル</a></p>
        <object>埋め込み</object><svg><text>図</text></svg>
        <template><p>テンプレート</p></template></div>
        """,
    "山梨県": '<p>山梨県には<a href="./富士山">富士山</a>があり、<a href="./日本">日本</a>に位置する。</p>',
    "日本": '<p>日本の山には<a href="./富士山">富士山</a>がある。</p>',
}
REDIRECTS = {"富士": "富士山"}
DISAMBIGUATION = {"プリン"}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


class WikiRaceRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=ROOT)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or None,
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.fail_parse = set()
        self.missing_parse = set()
        self.held_titles = set()
        self.held_routes = []
        self.calls = []
        self.context = self.browser.new_context()
        self.context.route("https://ja.wikipedia.org/w/api.php?**", self.wiki)
        self.page = self.context.new_page()
        self.page.clock.install()
        self.page.goto(self.url)
        self.page.set_default_timeout(5000)

    def tearDown(self):
        for route in self.held_routes:
            try:
                route.abort()
            except Error:
                pass  # The browser may have already cancelled the request.
        self.context.close()

    def wiki(self, route):
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(route.request.url).query))
        self.calls.append(params)
        if params["action"] == "query":
            titles = params["titles"].split("|")
            redirects = [{"from": t, "to": REDIRECTS[t]} for t in titles if t in REDIRECTS]
            resolved = [REDIRECTS.get(t, t) for t in titles]
            pages = [
                {"title": t, "ns": 0, "pageprops": {"disambiguation": ""}}
                if t in DISAMBIGUATION else {"title": t, "ns": 0, **({} if t in PAGES else {"missing": True})}
                for t in dict.fromkeys(resolved)
            ]
            route.fulfill(json={"query": {"redirects": redirects, "pages": pages}})
            return
        title = params["page"]
        if title in self.fail_parse:
            route.fulfill(status=503)
        elif title in self.missing_parse:
            route.fulfill(json={"error": {"code": "missingtitle"}})
        elif title in self.held_titles:
            self.held_routes.append(route)
        else:
            self.fulfill_article(route, title)

    @staticmethod
    def fulfill_article(route, title):
        route.fulfill(json={"parse": {
            "title": title, "text": PAGES[title], "revid": 42,
            "links": [{"title": name, "ns": 0, "exists": True} for name in PAGES],
        }})

    def start(self, a="富士山", b="日本"):
        self.page.locator("summary").click()
        self.page.locator("#customStart").fill(a)
        self.page.locator("#customGoal").fill(b)
        self.page.locator("#custom").click()

    def set_challenge(self, a, b):
        # Control the selected pair without changing article loading or error behavior.
        self.page.evaluate("""([a,b]) => {
            extra = ['富士山', '日本'];
            useExpanded = true;
            challenge = {a, b, category:'テスト', kind:'expanded'};
            showChallenge();
        }""", [a, b])

    def ready(self, title):
        expect(self.page.locator("#articleTitle")).to_have_text(title)
        expect(self.page.locator("#transit")).to_be_hidden()
        expect(self.page.locator("#error")).to_be_hidden()

    def test_curated_count_and_replaced_titles(self):
        self.assertEqual(self.page.evaluate("curated.length"), 634)
        self.assertIn("カスタードプディング", self.page.evaluate("groups['食べ物']"))
        self.assertNotIn("プリン", self.page.evaluate("curated"))

    def test_invalid_random_pair_rerolls_batched_and_caches_resolution(self):
        self.set_challenge("富士山", "プリン")
        self.page.evaluate("makeChallenge = () => ({a:'富士山', b:'日本', kind:'expanded'})")
        self.page.locator("#play").click()
        self.ready("富士山")
        expect(self.page.locator("#target")).to_have_text("日本")
        self.assertEqual([q["titles"] for q in self.calls if q["action"] == "query"],
                         ["富士山|プリン", "日本"])
        self.page.locator("#restart").click()
        self.ready("富士山")
        self.assertEqual(len(self.calls), 3)

    def test_same_canonical_article_is_rejected(self):
        self.start("富士", "富士山")
        expect(self.page.locator("#error")).to_contain_text("同じ記事")
        expect(self.page.locator("#moves")).to_have_text("0")
        self.assertFalse(any(q["action"] == "parse" for q in self.calls))
        self.page.locator("#errorHome").click()
        expect(self.page.locator("#menu")).to_be_visible()

    def test_missing_custom_article_has_an_article_error(self):
        self.start("富士山", "存在しない記事")
        expect(self.page.locator("#error")).to_contain_text("記事が見つかりません")
        expect(self.page.locator("#retry")).to_be_hidden()
        expect(self.page.locator("#errorHome")).to_be_visible()

    def test_reroll_exhaustion_returns_to_top(self):
        self.set_challenge("富士山", "プリン")
        self.page.evaluate("makeChallenge = () => null")
        self.page.locator("#play").click()
        expect(self.page.locator("#error")).to_contain_text("選び直せません")
        self.page.locator("#errorHome").click()
        expect(self.page.locator("#menu")).to_be_visible()

    def test_parse_missing_rerolls_but_network_failure_does_not(self):
        self.set_challenge("山梨県", "日本")
        self.page.evaluate("makeChallenge = () => ({a:'富士山', b:'日本', kind:'expanded'})")
        self.missing_parse.add("山梨県")
        self.fail_parse.add("富士山")
        self.page.locator("#play").click()
        expect(self.page.locator("#error")).to_contain_text("HTTP 503")
        self.assertEqual([q["page"] for q in self.calls if q["action"] == "parse"], ["山梨県", "富士山"])
        self.fail_parse.clear()
        self.page.locator("#retry").click()
        self.ready("富士山")
        expect(self.page.locator("#moves")).to_have_text("0")

    def test_failed_move_and_double_click_keep_history_until_success(self):
        self.start()
        self.ready("富士山")
        self.fail_parse.add("山梨県")
        self.page.locator(".wiki-link", has_text="山梨県").evaluate("(el) => {el.click(); el.click()}")
        expect(self.page.locator("#error")).to_contain_text("HTTP 503")
        expect(self.page.locator("#moves")).to_have_text("0")
        expect(self.page.locator("#trail")).not_to_contain_text("山梨県")
        self.assertEqual(sum(q.get("page") == "山梨県" for q in self.calls), 1)
        self.fail_parse.clear()
        self.page.locator("#retry").click()
        self.ready("山梨県")
        expect(self.page.locator("#moves")).to_have_text("1")
        expect(self.page.locator("#trail")).to_contain_text("山梨県")

    def test_timeout_and_cancellation_do_not_commit_old_article(self):
        self.start()
        self.ready("富士山")
        self.held_titles.add("山梨県")
        self.page.locator(".wiki-link", has_text="山梨県").click()
        self.page.wait_for_function("!document.querySelector('#transit').hidden")
        self.page.clock.fast_forward(26000)
        expect(self.page.locator("#error")).to_contain_text("時間内")
        expect(self.page.locator("#moves")).to_have_text("0")
        self.page.locator("#retry").click()
        self.page.locator("#cancelTransit").click()
        expect(self.page.locator("#error")).to_contain_text("中止")
        expect(self.page.locator("#articleTitle")).to_have_text("富士山")
        self.page.get_by_role("button", name="日本", exact=True).click()
        expect(self.page.locator("#win")).to_be_visible()
        expect(self.page.locator("#result")).to_contain_text("1クリック")

    def test_delayed_article_render_cannot_update_restarted_game(self):
        self.start()
        self.ready("富士山")
        self.page.evaluate("""() => {
            const original = prepareArticle;
            prepareArticle = async (page, demo, signal) => {
                if (page.title === '山梨県') await new Promise(resolve=>window.resumeOldArticle=resolve);
                return original(page, demo, signal);
            };
        }""")
        self.page.get_by_role("button", name="山梨県", exact=True).click()
        self.page.wait_for_function("typeof window.resumeOldArticle === 'function'")
        self.page.locator("#cancelTransit").click()
        self.page.get_by_role("button", name="日本", exact=True).click()
        self.page.evaluate("window.resumeOldArticle()")
        expect(self.page.locator("#win")).to_be_visible()
        expect(self.page.locator("#articleTitle")).to_have_text("日本")
        expect(self.page.locator("#trail")).not_to_contain_text("山梨県")

    def test_list_is_lazy_and_article_projection_drops_unsafe_markup(self):
        self.start()
        self.ready("富士山")
        expect(self.page.locator("#links .linkchip")).to_have_count(0)
        expect(self.page.locator("#articleText button")).to_have_count(2)
        expect(self.page.locator("#articleText [onmouseover], #articleText [style], #articleText a, #articleText object, #articleText svg, #articleText template")).to_have_count(0)
        self.page.locator("#tabLinks").click()
        expect(self.page.locator("#links .linkchip")).to_have_count(2)
        self.page.locator("#links").get_by_role("button", name="山梨県").click()
        self.ready("山梨県")
        expect(self.page.locator("#links .linkchip")).to_have_count(0)

    def test_blackhole_masks_lazily_created_list_and_resets_in_classic(self):
        self.page.locator("[data-mode=blackhole]").click()
        self.start()
        self.ready("富士山")
        self.page.clock.fast_forward(181000)
        expect(self.page.locator("#erosionPercent")).to_have_text("100%")
        self.page.locator("#tabLinks").click()
        expect(self.page.locator("#links .linkchip").first).to_have_text(re.compile("^■+$"))
        self.page.locator("#home").click()
        self.page.locator("[data-mode=classic]").click()
        self.page.locator("#custom").click()
        self.ready("富士山")
        expect(self.page.locator("#articleText .wiki-link", has_text="山梨県")).to_be_visible()
        self.page.locator("#tabLinks").click()
        expect(self.page.locator("#links .linkchip", has_text="山梨県")).to_be_visible()

    def test_mobile_targets_fit_320px_and_existing_best_survives(self):
        self.page.set_viewport_size({"width": 320, "height": 568})
        record_key = 'wikirace:v2:'+json.dumps(["富士山","日本","easy"], ensure_ascii=False, separators=(",",":"))
        self.page.evaluate("(key) => localStorage.setItem(key, JSON.stringify({moves:1, ms:1}))", record_key)
        self.start()
        self.ready("富士山")
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 320)
        for selector in ("#restart", "#home", "#tabText", "#tabLinks"):
            box = self.page.locator(selector).bounding_box()
            self.assertGreaterEqual(box["width"], 44, selector)
            self.assertGreaterEqual(box["height"], 44, selector)
        self.page.locator("#articleText").get_by_role("button", name="日本").click()
        expect(self.page.locator("#win")).to_be_visible()
        expect(self.page.locator("#resultPreview")).to_be_visible()
        self.assertEqual(self.page.evaluate("(k) => JSON.parse(localStorage.getItem(k))", record_key), {"moves":1, "ms":1})

    def test_existing_expanded_pool_survives_reload_and_switching(self):
        self.page.evaluate("""() => localStorage.setItem('wikirace:v4:star-pool', JSON.stringify(['明石海峡大橋']))""")
        self.page.reload()
        expect(self.page.locator("#poolNote")).to_contain_text("635 / 5,000種類・拡張星図")
        self.page.locator("#togglePool").click()
        expect(self.page.locator("#poolNote")).to_contain_text("厳選 634語")
        self.page.locator("#togglePool").click()
        expect(self.page.locator("#poolNote")).to_contain_text("635 / 5,000種類・拡張星図")


if __name__ == "__main__":
    unittest.main(verbosity=2)
