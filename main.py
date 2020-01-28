import asyncio
import json
import datetime

import requests

from bs4 import BeautifulSoup


HEADERS = {
    "authority": "twitter.com",
    "accept":"application/json, text/javascript, */*; q=0.01",
    "accept-language":"en-US,en;q=0.9",
    "sec-fetch-mode":"cors",
    "sec-fetch-site":"same-origin",
    "x-asset-version":"42599c",
    "x-push-state-request":"true",
    "x-requested-with":"XMLHttpRequest",
    "x-twitter-active-user":"yes",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "cookie": 'tfw_exp=0; _twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCJp1i%252BlvAToMY3NyZl9p%250AZCIlYzE0Zjc5ZWU2YWRmZWNjYTJhZWI5MGIzYWVkMTRkZTA6B2lkIiViYzY2%250AZDYzMTAyMmQwOTA5ZTNjYTIzYmU1MTk3Mzc3Nw%253D%253D--dbfff975f6af2870f066fd532e6a844efa48e597; personalization_id="v1_P0dT+vkcNh7QY2k4zSShbQ=="; guest_id=v1%3A158017122856758630; ct0=5065d7627c67660f47467afdf75921c2; _ga=GA1.2.511051134.1580171230; _gid=GA1.2.584657768.1580171230; gt=1221952930074583048; _gat=1',
}


def build_q(username, since, until):
    return f"from:{username} since:{since.isoformat()} until:{until.isoformat()} include:retweets"

def extract_tweets(soup):
    tweet_divs = soup.select("div.tweet")
    tweets = []
    for tweet in tweet_divs:
        id = tweet["data-tweet-id"]
        text = tweet.select_one("p.tweet-text").text
        reply_users = tweet.select("a[data-mentioned-user-id]")
        if reply_users is not None:
            reply_user_ids = [u["data-mentioned-user-id"] for u in reply_users]
        else:
            reply_user_ids = []

        retweet_count = tweet.select_one(".ProfileTweet-action--retweet .ProfileTweet-actionCount")["data-tweet-stat-count"]
        favorite_count = tweet.select_one(".ProfileTweet-action--favorite .ProfileTweet-actionCount")["data-tweet-stat-count"]
        reply_count = tweet.select_one(".ProfileTweet-action--reply .ProfileTweet-actionCount")["data-tweet-stat-count"]

        tweets.append({
            "id": id,
            "text": text,
            "retweet_count": retweet_count, 
            "favorite_count": favorite_count, 
            "reply_count": reply_count,
            "in_reply_to_user_ids": reply_user_ids,
        })
    return tweets

async def timeline_search(q, max_position):
    loop = asyncio.get_event_loop()
    params = {
        "vertical": "default",
        "f": "tweets",
        "q": q,
        "src": "typd",
        "include_available_features": "1",
        "include_entities": "1",
        "max_position": max_position,
        "reset_error_state": False,
    }
    response = await loop.run_in_executor(None, lambda: requests.get("https://twitter.com/i/search/timeline", params=params, headers=HEADERS))
    result = response.json()
    soup = BeautifulSoup(result["items_html"], 'html.parser')
    tweets = extract_tweets(soup)
    min_position = result["min_position"]
    has_more_items = result["has_more_items"]
    return tweets, min_position, has_more_items


async def init_search(q):
    loop = asyncio.get_event_loop()
    params = {
        "src": "typd",
        "f": "tweets",
        "q": q
    }
    response = await loop.run_in_executor(None, lambda: requests.get("https://twitter.com/search", params=params, headers=HEADERS))
    result = response.json()
    soup = BeautifulSoup(result["page"], 'html.parser')
    stream = soup.select_one("div.stream-container")
    if stream is None:
        print(f"No results found for {q}")
        return set(), None
    min_position = stream["data-min-position"]
    tweets = extract_tweets(soup)
    return tweets, min_position


async def worker(work_queue, return_queue):
    while True:
        tweets = []
        username, since, until = await work_queue.get()
        q = build_q(username, since, until)

        init_tweets, min_position = await init_search(q)
        tweets += init_tweets

        has_more_items = True
        while has_more_items and min_position:
            more_tweets, min_position, has_more_items = await timeline_search(q, min_position)
            tweets += more_tweets

        work_queue.task_done()
        print(len(tweets))
        if len(tweets) >= 50:
            delta = until - since
            day = datetime.timedelta(days=1)
            if delta == day:
                print("Found a day where there were >= 50 tweets, continuing")
                return_queue.put_nowait(tweets)
            else:
                print("Found a period with 50 tweets, seeing if there's actually more")
                queue_time_segments(work_queue, username, since, until, day)
        else:
            return_queue.put_nowait(tweets)


def queue_time_segments(queue, username, start, end, step=datetime.timedelta(days=10)):
    since = start
    while since != end:
        until = since + step
        if until > end:
            until = end
        print(username, since, until)
        queue.put_nowait((username, since, until))
        since = until


async def main(username, start, end):
    work_queue = asyncio.Queue()
    queue_time_segments(work_queue, username, start, end)

    return_queue = asyncio.Queue()
    tasks = []
    for i in range(4):
        task = asyncio.create_task(worker(work_queue, return_queue))
        tasks.append(task)

    await work_queue.join()

    for task in tasks:
        task.cancel()

    results = {}
    try:
        while True:
            tweets = return_queue.get_nowait()
            for t in tweets:
                id = t["id"]
                results[id] = t
    except asyncio.queues.QueueEmpty:
        pass

    return list(results.values())


if __name__ == "__main__":
    username = "emptyflash"
    start = datetime.date(2009, 4, 1)
    end = datetime.date.today()

    tweets = asyncio.run(main(username, start, end))
    with open(f"{username}.json", 'w') as outfile:
        json.dump(tweets, outfile)
