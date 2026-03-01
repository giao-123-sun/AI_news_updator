import argparse
import json
from datetime import datetime, timezone

import x_user_crawler as crawler_mod


def extract_tweets(response_json):
    rows = []
    instructions = (
        response_json.get("data", {})
        .get("search_by_raw_query", {})
        .get("search_timeline", {})
        .get("timeline", {})
        .get("instructions", [])
    )
    for entry in instructions:
        if entry.get("type") != "TimelineAddEntries":
            continue
        for item in entry.get("entries", []):
            entry_id = item.get("entryId", "")
            if "tweet-" not in entry_id and "profile-conversation" not in entry_id:
                continue

            content = item.get("content", {}).get("itemContent", {})
            tweet_result = content.get("tweet_results", {}).get("result", {})
            tweet = tweet_result.get("tweet", tweet_result)
            legacy = tweet.get("legacy")
            if not legacy:
                continue

            core = tweet.get("core", {})
            user_legacy = (
                core.get("user_results", {}).get("result", {}).get("legacy", {})
            )
            tweet_id = legacy.get("id_str") or tweet.get("rest_id")
            parent_id = legacy.get("in_reply_to_status_id_str")
            rows.append(
                {
                    "tweet_id": tweet_id,
                    "is_reply": bool(parent_id),
                    "parent_id": parent_id,
                    "in_reply_to_screen_name": legacy.get("in_reply_to_screen_name"),
                    "author": user_legacy.get("screen_name", ""),
                    "text": (legacy.get("full_text") or "")[:280],
                }
            )
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Probe crawl capability: original/reply/comment coverage."
    )
    parser.add_argument("--users-limit", type=int, default=10)
    parser.add_argument(
        "--output", default="data/capability_test_results.json"
    )
    parser.add_argument(
        "--no-proxy", action="store_true", help="Ignore configured proxy."
    )
    args = parser.parse_args()

    users = crawler_mod.load_users(crawler_mod.USERS_FILE)
    cookie = crawler_mod.load_cookie(crawler_mod.COOKIE_STR, crawler_mod.COOKIE_FILE)
    proxy = "" if args.no_proxy else crawler_mod.PROXY
    crawler = crawler_mod.TwitterUserSearchCrawler(
        cookie_str=cookie,
        output_mode="single",
        single_output_file="capability_probe_tmp",
        proxy=proxy,
    )

    targets = users[: max(1, args.users_limit)]
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proxy_used": bool(proxy),
        "tested_users": [],
        "reply_detection": {},
        "reply_parent_fetch_test": {},
        "comments_fetch_test": {},
    }

    all_replies = []
    for user in targets:
        resp = crawler.get(f"from:{user}")
        if not resp:
            summary["tested_users"].append({"user": user, "status": "failed"})
            continue

        rows = extract_tweets(resp)
        reply_rows = [x for x in rows if x["is_reply"]]
        ids = {x["tweet_id"] for x in rows if x.get("tweet_id")}
        in_page_parent = [x for x in reply_rows if x.get("parent_id") in ids]
        for x in reply_rows:
            all_replies.append({"user": user, **x})

        summary["tested_users"].append(
            {
                "user": user,
                "status": "ok",
                "tweets_on_first_page": len(rows),
                "reply_count": len(reply_rows),
                "reply_ratio": round((len(reply_rows) / len(rows)), 4) if rows else 0,
                "reply_parent_also_in_same_page": len(in_page_parent),
            }
        )

    summary["reply_detection"] = {
        "users_tested_ok": sum(1 for x in summary["tested_users"] if x["status"] == "ok"),
        "total_reply_samples": len(all_replies),
        "sample_replies": all_replies[:5],
    }

    if all_replies:
        sample_reply = all_replies[0]
        parent_id = sample_reply["parent_id"]
        conv_resp = crawler.get(f"conversation_id:{parent_id}")
        conv_rows = extract_tweets(conv_resp) if conv_resp else []
        summary["reply_parent_fetch_test"] = {
            "sample_reply": sample_reply,
            "conversation_query": f"conversation_id:{parent_id}",
            "conversation_result_count": len(conv_rows),
            "contains_parent_id": any(x.get("tweet_id") == parent_id for x in conv_rows),
            "unique_authors": sorted(
                list({x.get("author", "") for x in conv_rows if x.get("author")})
            )[:20],
            "sample_conversation_rows": conv_rows[:5],
        }

    non_reply_target = None
    for user in targets:
        resp = crawler.get(f"from:{user}")
        if not resp:
            continue
        rows = extract_tweets(resp)
        first_post = next((x for x in rows if not x["is_reply"]), None)
        if first_post:
            non_reply_target = {"user": user, **first_post}
            break

    if non_reply_target:
        post_id = non_reply_target["tweet_id"]
        conv_resp = crawler.get(f"conversation_id:{post_id}")
        conv_rows = extract_tweets(conv_resp) if conv_resp else []
        direct_replies = [x for x in conv_rows if x.get("parent_id") == post_id]
        summary["comments_fetch_test"] = {
            "target_post": non_reply_target,
            "conversation_query": f"conversation_id:{post_id}",
            "conversation_result_count": len(conv_rows),
            "direct_reply_count": len(direct_replies),
            "contains_target_post": any(x.get("tweet_id") == post_id for x in conv_rows),
            "sample_direct_replies": direct_replies[:5],
            "sample_rows": conv_rows[:8],
        }

    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)

    print(args.output)
    print(
        "users_ok=",
        summary["reply_detection"].get("users_tested_ok", 0),
        "reply_samples=",
        summary["reply_detection"].get("total_reply_samples", 0),
        "direct_comment_samples=",
        summary.get("comments_fetch_test", {}).get("direct_reply_count", 0),
    )


if __name__ == "__main__":
    main()
