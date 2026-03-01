import base64
import datetime
import html
import json
import os
import random
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import pandas as pd
import requests

# ========================
# User Config (edit here)
# ========================
COOKIE_STR = ""  # Optional override. If empty, script reads COOKIE_FILE.
COOKIE_FILE = "human_comment/cookies.txt"  # Default cookie source file
MAX_PAGES = int(os.environ.get("X_MAX_PAGES", "5"))  # Max pages to crawl per user
PROXY = os.environ.get("X_PROXY", "").strip()  # Example: "http://127.0.0.1:17585"; empty disables proxy
USERS_FILE = "data/X.txt"  # One URL/username per line

# Output mode switch:
# 1) "single"   -> all users go into one CSV file (SINGLE_OUTPUT_FILE)
# 2) "per_user" -> each user gets an individual CSV file (twitter_<username>.csv)
OUTPUT_MODE = "single"
SINGLE_OUTPUT_FILE = os.environ.get("X_SINGLE_OUTPUT_FILE", "twitter_all_users")

# Sleep settings (anti-rate-limit)
PAGE_SLEEP_RANGE = (
    float(os.environ.get("X_PAGE_SLEEP_MIN", "3")),
    float(os.environ.get("X_PAGE_SLEEP_MAX", "7")),
)  # between pages for same user
USER_SLEEP_RANGE = (
    float(os.environ.get("X_USER_SLEEP_MIN", "15")),
    float(os.environ.get("X_USER_SLEEP_MAX", "30")),
)  # between different users
REQUEST_TIMEOUT = (10, 20)

# SearchTimeline queryId may change. Keep default + auto-refresh from web bundle.
DEFAULT_OPERATION_HASH = "NiZ1seU-Qm1TUiThEaWXKA"
AUTO_DISCOVER_OPERATION_HASH = True
SEARCH_BOOTSTRAP_URL = "https://x.com/search?q=from%3Aelonmusk&src=typed_query&f=live"

# Media download
DOWNLOAD_IMAGES = True
IMAGE_OUTPUT_DIR = "tweet_images"
MAX_IMAGES_PER_TWEET = 4

# Analysis + visualization
RUN_ANALYSIS_AFTER_CRAWL = True
ANALYSIS_INPUT_FILE = ""  # Optional override. If empty, auto-select existing output CSV.
ANALYSIS_OUTPUT_DIR = "report"
REPORT_HTML_FILE = "insights_report.html"
MAX_REPORT_ROWS = 300

# Classification dictionaries
TOOL_KEYWORDS = [
    "tool",
    "tools",
    "app",
    "agent",
    "workflow",
    "plugin",
    "extension",
    "open source",
    "opensource",
    "launch",
    "github",
    "huggingface",
    "工具",
    "开源",
    "插件",
    "发布",
    "上线",
    "产品",
    "网站",
]
EXPERIENCE_KEYWORDS = [
    "体验",
    "感受",
    "上手",
    "实测",
    "评测",
    "review",
    "tried",
    "using",
    "测试了",
    "用了",
    "好用",
    "不好用",
    "踩坑",
    "心得",
]
NEWS_PAPER_KEYWORDS = [
    "news",
    "breaking",
    "announce",
    "release",
    "paper",
    "arxiv",
    "research",
    "study",
    "新闻",
    "快讯",
    "公告",
    "论文",
    "研究",
    "白皮书",
]
TOOL_DOMAINS = {
    "github.com",
    "huggingface.co",
    "producthunt.com",
    "gitee.com",
    "npmjs.com",
    "pypi.org",
}
PAPER_DOMAINS = {
    "arxiv.org",
    "openreview.net",
    "paperswithcode.com",
    "aclweb.org",
    "acm.org",
    "ieeexplore.ieee.org",
    "nature.com",
    "science.org",
}
NEWS_DOMAINS = {
    "techcrunch.com",
    "theverge.com",
    "reuters.com",
    "bloomberg.com",
    "36kr.com",
    "huxiu.com",
    "ithome.com",
}

URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
X_STATUS_RE = re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/\d+", re.IGNORECASE)

BEARER_TOKEN = (
    "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

requests.packages.urllib3.disable_warnings()


class TwitterUserSearchCrawler:
    def __init__(self, cookie_str, output_mode="single", single_output_file="twitter_all_users", proxy=""):
        if not cookie_str.strip():
            raise ValueError("COOKIE_STR is empty. Please configure COOKIE_STR at top of file.")

        if output_mode not in {"single", "per_user"}:
            raise ValueError("OUTPUT_MODE must be 'single' or 'per_user'.")

        self.output_mode = output_mode
        self.single_output_file = single_output_file
        self.operation_hash = DEFAULT_OPERATION_HASH
        self.cookies = self._parse_cookies(cookie_str)
        self.ct0 = self.cookies.get("ct0", "")
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.image_root = Path(IMAGE_OUTPUT_DIR)

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            ),
            "Authorization": BEARER_TOKEN,
            "x-twitter-client-language": "en",
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-csrf-token": self.ct0,
            "Accept": "*/*",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "Referer": "https://x.com/search",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5",
            "Priority": "u=1, i",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
            "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": '"139.0.3405.86"',
            "sec-ch-ua-full-version-list": (
                '"Not;A=Brand";v="99.0.0.0", "Microsoft Edge";v="139.0.3405.86", '
                '"Chromium";v="139.0.7258.67"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"19.0.0"',
            "Content-Type": "application/json",
            "x-client-transaction-id": self.generate_transaction_id(),
        }
        if AUTO_DISCOVER_OPERATION_HASH:
            self.refresh_operation_hash()

    @staticmethod
    def _parse_cookies(cookie_str):
        cookies = {}
        for item in cookie_str.split("; "):
            if "=" in item:
                k, v = item.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    @staticmethod
    def generate_transaction_id():
        timestamp = str(int(time.time() * 1000))
        rand_str = str(uuid.uuid4())
        raw = f"{timestamp}:{rand_str}"
        return base64.b64encode(raw.encode()).decode()

    def refresh_operation_hash(self):
        """
        Discover latest SearchTimeline queryId from x.com web bundle.
        Falls back to DEFAULT_OPERATION_HASH if discovery fails.
        """
        try:
            bootstrap = requests.get(
                SEARCH_BOOTSTRAP_URL,
                headers={"User-Agent": self.headers["User-Agent"]},
                cookies=self.cookies,
                timeout=REQUEST_TIMEOUT,
                verify=False,
                proxies=self.proxies,
            )
            if bootstrap.status_code != 200:
                print(f"[Warn] bootstrap page status={bootstrap.status_code}, keep default hash")
                return

            script_paths = re.findall(r"<script[^>]+src=['\"]([^'\"]+\.js[^'\"]*)['\"]", bootstrap.text)
            main_js_url = None
            for path in script_paths:
                if "/main." in path:
                    main_js_url = path if path.startswith("http") else urljoin("https://x.com", path)
                    break
            if not main_js_url:
                print("[Warn] main.js not found, keep default hash")
                return

            main_js = requests.get(
                main_js_url,
                headers={"User-Agent": self.headers["User-Agent"]},
                timeout=REQUEST_TIMEOUT,
                verify=False,
                proxies=self.proxies,
            )
            if main_js.status_code != 200:
                print(f"[Warn] main.js status={main_js.status_code}, keep default hash")
                return

            match = re.search(r'queryId:\"([^\"]+)\",operationName:\"SearchTimeline\"', main_js.text)
            if not match:
                print("[Warn] SearchTimeline queryId not found, keep default hash")
                return

            discovered = match.group(1)
            if discovered != self.operation_hash:
                print(f"[Info] operation hash updated: {self.operation_hash} -> {discovered}")
            self.operation_hash = discovered
        except Exception as exc:
            print(f"[Warn] auto-discover operation hash failed: {exc}. keep default hash")

    @staticmethod
    def get_params(raw_query, cursor=None):
        variables = {
            "rawQuery": raw_query,
            "count": 20,
            "querySource": "recent_search_click",
            "product": "Latest",
            "withGrokTranslatedBio": False,
        }
        if cursor:
            variables["cursor"] = cursor

        features = {
            "rweb_video_screen_enabled": False,
            "payments_enabled": False,
            "rweb_xchat_enabled": False,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
            "responsive_web_grok_analyze_post_followups_enabled": True,
            "responsive_web_jetfuel_frame": True,
            "responsive_web_grok_share_attachment_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "responsive_web_grok_show_grok_translated_post": False,
            "responsive_web_grok_analysis_button_from_backend": True,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_grok_image_annotation_enabled": True,
            "responsive_web_grok_imagine_annotation_enabled": True,
            "responsive_web_grok_community_note_auto_translation_is_enabled": False,
            "responsive_web_enhance_cards_enabled": False,
        }
        return {
            "variables": json.dumps(variables, separators=(",", ":")),
            "features": json.dumps(features, separators=(",", ":")),
        }

    def get(self, raw_query, cursor=None):
        url = f"https://x.com/i/api/graphql/{self.operation_hash}/SearchTimeline"
        params = self.get_params(raw_query, cursor)

        self.headers["x-client-transaction-id"] = self.generate_transaction_id()
        self.headers["Referer"] = f"https://x.com/search?q={quote(raw_query)}&src=recent_search_click&f=live"

        try:
            # SearchTimeline now responds correctly with POST. GET returns 404 in current web flow.
            response = requests.post(
                url,
                headers=self.headers,
                cookies=self.cookies,
                params=params,
                timeout=REQUEST_TIMEOUT,
                verify=False,
                proxies=self.proxies,
            )

            if response.status_code == 429:
                reset_time = int(response.headers.get("x-rate-limit-reset", time.time() + 900))
                wait_time = max(reset_time - int(time.time()), 60)
                print(f"[RateLimited] wait {wait_time}s")
                time.sleep(wait_time)
                return None

            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print("[Error] response is not JSON")
                    print(response.text[:300])
                    return None

            print(f"[Error] request failed: {response.status_code}")
            print(response.text[:200])
            return None
        except Exception as exc:
            print(f"[Error] request exception: {exc}")
            time.sleep(5)
            return None

    @staticmethod
    def get_cursor(response_json):
        try:
            instructions = response_json["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
            next_cursor = None
            for entry in instructions:
                if entry.get("type") == "TimelineAddEntries":
                    for item in entry.get("entries", []):
                        if "cursor-bottom" in item.get("entryId", ""):
                            content = item.get("content", {})
                            if content.get("cursorType") == "Bottom":
                                next_cursor = content.get("value")
                                break
                elif entry.get("type") == "TimelineReplaceEntry":
                    entry_obj = entry.get("entry", {})
                    if "cursor-bottom" in entry_obj.get("entryId", ""):
                        next_cursor = entry_obj.get("content", {}).get("value")
                        break
            return next_cursor
        except Exception as exc:
            print(f"[Error] get cursor failed: {exc}")
            return None

    @staticmethod
    def _format_time(created_at):
        try:
            dt = datetime.datetime.strptime(created_at, "%a %b %d %H:%M:%S +0000 %Y")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return created_at

    @staticmethod
    def _extract_external_urls(legacy):
        links = []
        url_entities = legacy.get("entities", {}).get("urls", [])
        for item in url_entities:
            value = item.get("expanded_url") or item.get("unwound_url") or item.get("url")
            if value:
                links.append(value)
        # keep order + de-dup
        return list(dict.fromkeys(links))

    @staticmethod
    def _normalize_image_url(url):
        if not url:
            return ""
        if "name=" in url:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}name=orig"

    def _extract_image_urls(self, legacy):
        image_urls = []
        media_sources = []
        media_sources.extend(legacy.get("entities", {}).get("media", []))
        media_sources.extend(legacy.get("extended_entities", {}).get("media", []))
        for item in media_sources:
            if item.get("type") != "photo":
                continue
            media_url = item.get("media_url_https") or item.get("media_url")
            if media_url:
                image_urls.append(self._normalize_image_url(media_url))
        return list(dict.fromkeys(image_urls))

    def _download_images_for_tweet(self, target_user, tweet_id, image_urls):
        if not DOWNLOAD_IMAGES or not image_urls:
            return []

        safe_user = re.sub(r"[^A-Za-z0-9_\\-]", "_", target_user)
        user_dir = self.image_root / safe_user
        user_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []
        headers = {"User-Agent": self.headers["User-Agent"], "Referer": "https://x.com/"}

        for idx, image_url in enumerate(image_urls[:MAX_IMAGES_PER_TWEET], start=1):
            parsed = urlparse(image_url)
            suffix = Path(parsed.path).suffix.lower() or ".jpg"
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                suffix = ".jpg"
            file_path = user_dir / f"{tweet_id}_{idx}{suffix}"
            if not file_path.exists():
                try:
                    response = requests.get(
                        image_url,
                        headers=headers,
                        timeout=REQUEST_TIMEOUT,
                        verify=False,
                        proxies=self.proxies,
                    )
                    if response.status_code == 200 and response.content:
                        file_path.write_bytes(response.content)
                    else:
                        print(f"[Warn] image download failed: {response.status_code} {image_url}")
                        continue
                except Exception as exc:
                    print(f"[Warn] image download error: {exc} ({image_url})")
                    continue
            saved_paths.append(file_path.as_posix())

        return saved_paths

    def parse_data(self, response_json, target_user):
        items = []
        try:
            instructions = response_json["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
            for entry in instructions:
                if entry.get("type") != "TimelineAddEntries":
                    continue
                for timeline_item in entry.get("entries", []):
                    entry_id = timeline_item.get("entryId", "")
                    if "tweet-" not in entry_id and "profile-conversation" not in entry_id:
                        continue

                    content = timeline_item.get("content", {}).get("itemContent", {})
                    tweet_result = content.get("tweet_results", {}).get("result", {})
                    tweet = tweet_result.get("tweet", tweet_result)

                    legacy = tweet.get("legacy")
                    core = tweet.get("core")
                    if not legacy or not core:
                        continue

                    user_legacy = core.get("user_results", {}).get("result", {}).get("legacy", {})
                    full_text = legacy.get("full_text", "")
                    note_tweet = tweet.get("note_tweet", {}).get("result", {})
                    if note_tweet.get("text"):
                        full_text = note_tweet["text"]

                    tweet_id = legacy.get("id_str") or tweet.get("rest_id") or str(uuid.uuid4())
                    tweet_link = f"https://x.com/{target_user}/status/{tweet_id}" if tweet_id else ""
                    external_urls = self._extract_external_urls(legacy)
                    image_urls = self._extract_image_urls(legacy)
                    local_images = self._download_images_for_tweet(target_user, tweet_id, image_urls)

                    items.append(
                        {
                            "发帖人": target_user,
                            "推文ID": tweet_id,
                            "推文链接": tweet_link,
                            "内容": full_text,
                            "时间": self._format_time(legacy.get("created_at", "")),
                            "点赞": legacy.get("favorite_count", 0),
                            "评论": legacy.get("reply_count", 0),
                            "转发": legacy.get("retweet_count", 0) + legacy.get("quote_count", 0),
                            "简介": user_legacy.get("description", ""),
                            "粉丝量": user_legacy.get("followers_count", 0),
                            "关注量": user_legacy.get("friends_count", 0),
                            "外部链接": " | ".join(external_urls),
                            "图片链接": " | ".join(image_urls),
                            "本地图片": " | ".join(local_images),
                        }
                    )
        except Exception as exc:
            print(f"[Error] parse failed for {target_user}: {exc}")

        return items

    def _output_name(self, target_user):
        if self.output_mode == "per_user":
            return f"twitter_{target_user}"
        return self.single_output_file

    def save_data(self, data_list, target_user):
        if not data_list:
            return

        output_name = self._output_name(target_user)
        file_path = f"./{output_name}.csv"
        df = pd.DataFrame(data_list)
        target_path = file_path
        header = not os.path.exists(target_path)
        if not header:
            try:
                existing_cols = pd.read_csv(target_path, nrows=0, encoding="utf_8_sig").columns.tolist()
            except Exception:
                existing_cols = []
            if existing_cols and existing_cols != df.columns.tolist():
                target_path = f"./{output_name}_v2.csv"
                header = not os.path.exists(target_path)
                print(
                    f"[Warn] schema mismatch for {file_path}. "
                    f"Write to {target_path} instead."
                )
        try:
            df.to_csv(target_path, index=False, mode="a", encoding="utf_8_sig", header=header)
        except PermissionError:
            # If the merged CSV is opened by Excel, fall back to per-user file so crawl can continue.
            fallback_path = f"./twitter_{target_user}.csv"
            fallback_header = not os.path.exists(fallback_path)
            print(
                f"[Warn] cannot write {target_path} (locked). "
                f"Fallback to {fallback_path}"
            )
            df.to_csv(
                fallback_path,
                index=False,
                mode="a",
                encoding="utf_8_sig",
                header=fallback_header,
            )

    def run_for_user(self, username, max_pages):
        raw_query = f"from:{username}"
        cursor = None
        page = 1
        total_saved = 0

        while page <= max_pages:
            print(f"[User:{username}] page {page}/{max_pages}, query={raw_query}")
            response = self.get(raw_query, cursor)
            if not response:
                print(f"[User:{username}] stop: request failed or rate-limited")
                break

            tweets = self.parse_data(response, target_user=username)
            if not tweets:
                print(f"[User:{username}] stop: no new tweets")
                break

            self.save_data(tweets, target_user=username)
            total_saved += len(tweets)
            print(f"[User:{username}] saved {len(tweets)} (total={total_saved})")

            next_cursor = self.get_cursor(response)
            if not next_cursor or next_cursor == cursor:
                print(f"[User:{username}] stop: reached last page")
                break

            cursor = next_cursor
            page += 1
            if page <= max_pages:
                time.sleep(random.uniform(*PAGE_SLEEP_RANGE))

        return total_saved


def extract_username(value):
    raw = value.strip().lstrip("\ufeff")
    if not raw or raw.startswith("#"):
        return None

    candidate = raw
    if raw.startswith("@"):
        candidate = raw[1:]
    elif raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            return None
        candidate = segments[0]

    candidate = candidate.strip().strip("/")
    if candidate.startswith("@"):
        candidate = candidate[1:]

    # Skip common non-username routes.
    blocked = {
        "home",
        "explore",
        "search",
        "notifications",
        "messages",
        "settings",
        "compose",
        "i",
        "tos",
        "privacy",
        "intent",
    }
    if candidate.lower() in blocked:
        return None

    if re.fullmatch(r"[A-Za-z0-9_]{1,15}", candidate):
        return candidate
    return None


def load_users(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"users file not found: {file_path}")

    users = []
    seen = set()
    with open(file_path, "r", encoding="utf-8") as fp:
        for idx, line in enumerate(fp, start=1):
            username = extract_username(line)
            if not username:
                if line.strip() and not line.strip().startswith("#"):
                    print(f"[Skip] invalid line {idx}: {line.strip()}")
                continue
            if username in seen:
                continue
            users.append(username)
            seen.add(username)

    if not users:
        raise ValueError("No valid users found in users.txt")

    return users


def load_cookie(cookie_str, cookie_file):
    if cookie_str.strip():
        return cookie_str.strip()

    if not os.path.exists(cookie_file):
        raise FileNotFoundError(
            f"cookie file not found: {cookie_file}. "
            "Set COOKIE_STR directly or provide COOKIE_FILE."
        )

    with open(cookie_file, "r", encoding="utf-8") as fp:
        content = fp.read().strip().lstrip("\ufeff")

    if not content:
        raise ValueError(f"cookie file is empty: {cookie_file}")
    return content


def split_multi_value(value):
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [item.strip() for item in text.split("|") if item.strip()]


def normalize_url(url):
    t = str(url or "").strip()
    if not t or t.lower() == "nan":
        return ""
    return t.rstrip(".,;:!?)\"]'")


def unique_keep_order(items):
    out = []
    seen = set()
    for x in items:
        v = normalize_url(x)
        if not v or v in seen:
            continue
        out.append(v)
        seen.add(v)
    return out


def urls_from_text(text):
    if text is None:
        return []
    return unique_keep_order(URL_RE.findall(str(text)))


def backfill_link_fields(df):
    if len(df) == 0:
        return df
    out = df.copy()
    for col in ["推文链接", "外部链接"]:
        if col not in out.columns:
            out[col] = ""

    tweet_vals = []
    ext_vals = []
    for _, row in out.iterrows():
        text_urls = urls_from_text(row.get("内容", ""))
        tweet = normalize_url(row.get("推文链接", ""))
        if not tweet:
            for u in text_urls:
                if X_STATUS_RE.match(u):
                    tweet = u
                    break

        merged = split_multi_value(row.get("外部链接", ""))
        merged.extend(text_urls)
        merged = unique_keep_order(merged)
        if tweet:
            merged = [u for u in merged if u != tweet]

        tweet_vals.append(tweet)
        ext_vals.append(" | ".join(merged))

    out["推文链接"] = tweet_vals
    out["外部链接"] = ext_vals
    return out


def extract_domains(urls):
    domains = set()
    for link in urls:
        try:
            host = urlparse(link).netloc.lower().replace("www.", "")
            if host:
                domains.add(host)
        except Exception:
            continue
    return domains


def contains_keyword(text, keywords):
    low = text.lower()
    return any(keyword in low for keyword in keywords)


def infer_paper_or_news_title(text, links):
    for link in links:
        if "arxiv.org/abs/" in link:
            return "arXiv " + link.split("arxiv.org/abs/", 1)[1].split("?")[0]
    cleaned = re.sub(r"https?://\\S+", "", text)
    cleaned = re.sub(r"\\s+", " ", cleaned).strip()
    return cleaned[:120]


def analyze_row(row):
    text = str(row.get("内容", "") or "")
    links = split_multi_value(row.get("外部链接", ""))
    domains = extract_domains(links)

    is_tool = contains_keyword(text, TOOL_KEYWORDS) or bool(domains & TOOL_DOMAINS)
    is_experience = contains_keyword(text, EXPERIENCE_KEYWORDS)
    is_paper = bool(domains & PAPER_DOMAINS) or ("arxiv" in text.lower()) or ("论文" in text)
    is_news = bool(domains & NEWS_DOMAINS) or contains_keyword(text, ["news", "新闻", "快讯", "公告"])
    is_news_paper = is_paper or is_news or contains_keyword(text, NEWS_PAPER_KEYWORDS)
    best_link = links[0] if links else ""
    title = infer_paper_or_news_title(text, links)

    return pd.Series(
        {
            "_is_tool": is_tool,
            "_is_experience": is_experience,
            "_is_news_paper": is_news_paper,
            "_is_paper": is_paper,
            "_best_link": best_link,
            "_paper_or_news_title": title,
        }
    )


def ensure_columns(df, columns):
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def _to_report_image_src(img_path, report_dir):
    if not img_path:
        return ""
    p = Path(img_path)
    if p.exists():
        return os.path.relpath(p, report_dir).replace("\\", "/")
    return img_path


def _render_cards(df, section_name, report_dir, max_rows):
    rows = df.head(max_rows).to_dict(orient="records")
    cards = []
    for row in rows:
        text = html.escape(str(row.get("内容", "") or ""))
        author = html.escape(str(row.get("发帖人", "") or ""))
        date = html.escape(str(row.get("时间", "") or ""))
        tweet_link = str(row.get("推文链接", "") or "")
        ext_links = split_multi_value(row.get("外部链接", ""))
        local_images = split_multi_value(row.get("本地图片", ""))
        remote_images = split_multi_value(row.get("图片链接", ""))
        images = local_images if local_images else remote_images

        link_html = ""
        if tweet_link:
            safe_tweet = html.escape(tweet_link)
            link_html += f'<a href="{safe_tweet}" target="_blank">推文链接</a>'
        for link in ext_links[:5]:
            safe = html.escape(link)
            link_html += f' <a href="{safe}" target="_blank">外链</a>'

        image_html = ""
        for img in images[:4]:
            src = html.escape(_to_report_image_src(img, report_dir))
            image_html += f'<img src="{src}" alt="tweet image" />'

        cards.append(
            f"""
            <article class="card">
              <div class="meta">{author} | {date} | {section_name}</div>
              <div class="body">{text}</div>
              <div class="links">{link_html}</div>
              <div class="images">{image_html}</div>
            </article>
            """
        )
    return "\n".join(cards)


def build_html_report(tools_df, exp_df, news_df, output_dir):
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = report_dir / REPORT_HTML_FILE

    tools_cards = _render_cards(tools_df, "工具分享", report_dir, MAX_REPORT_ROWS)
    exp_cards = _render_cards(exp_df, "使用体验", report_dir, MAX_REPORT_ROWS)
    news_cards = _render_cards(news_df, "新闻/论文", report_dir, MAX_REPORT_ROWS)

    doc = f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>X 内容筛选报告</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #132033;
      --muted: #5f6c80;
      --line: #d8dfeb;
      --primary: #0f62fe;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: radial-gradient(circle at 10% 10%, #e9f2ff, var(--bg));
      color: var(--text);
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 28px 16px 40px;
    }}
    h1 {{ margin: 0 0 8px; }}
    .sub {{ color: var(--muted); margin-bottom: 24px; }}
    h2 {{
      margin-top: 30px;
      border-left: 5px solid var(--primary);
      padding-left: 10px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      box-shadow: 0 4px 14px rgba(10, 35, 66, 0.06);
    }}
    .meta {{ color: var(--muted); font-size: 12px; margin-bottom: 8px; }}
    .body {{
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 14px;
      line-height: 1.45;
      margin-bottom: 8px;
      max-height: 220px;
      overflow: auto;
    }}
    .links a {{
      color: var(--primary);
      margin-right: 8px;
      font-size: 13px;
      text-decoration: none;
    }}
    .images {{
      margin-top: 8px;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }}
    .images img {{
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--line);
      object-fit: cover;
      min-height: 80px;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>X 推文筛选与可视化报告</h1>
    <div class="sub">工具分享、使用体验、新闻与论文三类内容自动筛选（含图片）</div>

    <h2>工具分享 ({len(tools_df)})</h2>
    <section class="grid">{tools_cards}</section>

    <h2>使用体验 ({len(exp_df)})</h2>
    <section class="grid">{exp_cards}</section>

    <h2>新闻与论文 ({len(news_df)})</h2>
    <section class="grid">{news_cards}</section>
  </main>
</body>
</html>
"""
    html_path.write_text(doc, encoding="utf-8")
    return html_path


def resolve_analysis_input():
    if ANALYSIS_INPUT_FILE:
        if os.path.exists(ANALYSIS_INPUT_FILE):
            return ANALYSIS_INPUT_FILE
        raise FileNotFoundError(f"ANALYSIS_INPUT_FILE not found: {ANALYSIS_INPUT_FILE}")

    aggregate_candidates = [
        "twitter_all_users_merged.csv",
        f"{SINGLE_OUTPUT_FILE}_v2.csv",
        f"{SINGLE_OUTPUT_FILE}.csv",
    ]
    aggregate_existing = [x for x in aggregate_candidates if os.path.exists(x)]
    fallback_existing = [f.as_posix() for f in Path(".").glob("twitter_*.csv") if f.exists()]

    candidates = aggregate_existing if aggregate_existing else fallback_existing
    if not candidates:
        raise FileNotFoundError("No input CSV found for analysis.")

    # Prefer files with richer evidence fields, then newer mtime.
    def score(path):
        evidence_non_empty = 0
        evidence_cols = 0
        rows = 0
        try:
            df = pd.read_csv(path, encoding="utf_8_sig")
            rows = len(df)
            for c in ["推文链接", "外部链接", "本地图片", "图片链接"]:
                if c in df.columns:
                    evidence_cols += 1
                    s = df[c].fillna("").astype(str).str.strip()
                    evidence_non_empty += int((s != "").sum())
        except Exception:
            pass
        mtime = os.path.getmtime(path)
        return (evidence_non_empty, evidence_cols, rows, mtime)

    best = max(candidates, key=score)
    return best


def run_analysis_and_visualization(input_csv, output_dir):
    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, encoding="utf_8_sig")
    df = ensure_columns(df, ["发帖人", "时间", "内容", "推文链接", "外部链接", "图片链接", "本地图片"])
    df = backfill_link_fields(df)

    tags = df.apply(analyze_row, axis=1)
    df = pd.concat([df, tags], axis=1)

    tools_df = df[df["_is_tool"]].copy()
    exp_df = df[df["_is_experience"]].copy()
    news_df = df[df["_is_news_paper"]].copy()

    news_df["论文/新闻链接"] = news_df["_best_link"]
    news_df["论文/新闻名称"] = news_df["_paper_or_news_title"]
    news_df["类型"] = news_df["_is_paper"].apply(lambda x: "论文" if x else "新闻")
    news_df["推文内容"] = news_df["内容"]

    tools_export = tools_df[["发帖人", "时间", "推文链接", "内容", "外部链接", "本地图片", "图片链接"]]
    exp_export = exp_df[["发帖人", "时间", "推文链接", "内容", "本地图片", "图片链接"]]
    news_export = news_df[
        ["类型", "论文/新闻链接", "论文/新闻名称", "推文内容", "发帖人", "时间", "推文链接", "本地图片", "图片链接"]
    ]

    tools_csv = report_dir / "tools_share.csv"
    exp_csv = report_dir / "experience_share.csv"
    news_csv = report_dir / "news_papers.csv"

    tools_export.to_csv(tools_csv, index=False, encoding="utf_8_sig")
    exp_export.to_csv(exp_csv, index=False, encoding="utf_8_sig")
    news_export.to_csv(news_csv, index=False, encoding="utf_8_sig")

    html_path = build_html_report(tools_df, exp_df, news_df, report_dir)
    return {
        "tools_csv": tools_csv.as_posix(),
        "experience_csv": exp_csv.as_posix(),
        "news_csv": news_csv.as_posix(),
        "html_report": html_path.as_posix(),
        "tools_count": int(len(tools_df)),
        "experience_count": int(len(exp_df)),
        "news_count": int(len(news_df)),
    }


def main():
    users = load_users(USERS_FILE)
    cookie_value = load_cookie(COOKIE_STR, COOKIE_FILE)
    crawler = TwitterUserSearchCrawler(
        cookie_str=cookie_value,
        output_mode=OUTPUT_MODE,
        single_output_file=SINGLE_OUTPUT_FILE,
        proxy=PROXY,
    )

    print(f"Loaded {len(users)} users from {USERS_FILE}")
    for idx, username in enumerate(users, start=1):
        print(f"\n=== [{idx}/{len(users)}] Start user: {username} ===")
        try:
            saved = crawler.run_for_user(username=username, max_pages=MAX_PAGES)
            print(f"=== [{idx}/{len(users)}] Done user: {username}, saved={saved} ===")
        except Exception as exc:
            # Skip this user and continue with next one.
            print(f"[SkipUser] {username} failed: {exc}")

        if idx < len(users):
            sleep_s = random.uniform(*USER_SLEEP_RANGE)
            print(f"Sleep before next user: {sleep_s:.1f}s")
            time.sleep(sleep_s)

    print("\nAll users finished.")

    if RUN_ANALYSIS_AFTER_CRAWL:
        try:
            input_csv = resolve_analysis_input()
            result = run_analysis_and_visualization(input_csv=input_csv, output_dir=ANALYSIS_OUTPUT_DIR)
            print(
                "[Analysis] done:",
                f"tools={result['tools_count']},",
                f"experience={result['experience_count']},",
                f"news/paper={result['news_count']}",
            )
            print(
                "[Analysis] files:",
                result["tools_csv"],
                result["experience_csv"],
                result["news_csv"],
                result["html_report"],
            )
        except Exception as exc:
            print(f"[Warn] analysis failed: {exc}")


if __name__ == "__main__":
    main()
