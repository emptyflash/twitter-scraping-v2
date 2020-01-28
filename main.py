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
    "cookie": '_twitter_sess=BAh7CSIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCBm52dZvAToMY3NyZl9p%250AZCIlYmFkYTYxOWViNTdiM2M4MWY0OTVlOTA5MjdmOTRlOGM6B2lkIiU4ZjY2%250AYzI5YTdhZGE0NDI2MDNlMjA0M2IwMThlYmMyMw%253D%253D--a6151e23c827fa6018ae4213dbef144ff9966799; personalization_id="v1_iz/bqzAp5VjuGiJYpE9raQ=="; guest_id=v1%3A157985759055012300; ct0=a1e56bd7a069a92bc87d684d2ed82c4e; _ga=GA1.2.1641248728.1579857593; _gid=GA1.2.443586604.1579857593; tfw_exp=0; _gat=1',
}

def build_q(username, since, until):
    return f"from:{username} since:{since.isoformat()} until:{until.isoformat()} include:retweets"

def extract_tweets(soup):
    tweet_divs = soup.select("div.tweet")
    tweets = []
    for tweet in tweet_divs:
        id = tweet["data-tweet-id"]
        retweet_count = tweet.select_one(".ProfileTweet-action--retweet .ProfileTweet-actionCount")["data-tweet-stat-count"]
        favorite_count = tweet.select_one(".ProfileTweet-action--favorite .ProfileTweet-actionCount")["data-tweet-stat-count"]
        reply_count = tweet.select_one(".ProfileTweet-action--reply .ProfileTweet-actionCount")["data-tweet-stat-count"]
        tweets.append({
            "id": id,
            "retweet_count": retweet_count, 
            "favorite_count": favorite_count, 
            "reply_count": reply_count,
        })
    return tweets

def timeline_search(q, max_position):
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
    result = requests.get("https://twitter.com/i/search/timeline", params=params, headers=HEADERS).json()
    soup = BeautifulSoup(result["items_html"], 'html.parser')
    tweets = extract_tweets(soup)
    min_position = result["min_position"]
    has_more_items = result["has_more_items"]
    return tweets, min_position, has_more_items


def init_search(q):
    params = {
        "src": "typd",
        "f": "tweets",
        "q": q
    }
    result = requests.get("https://twitter.com/search", params=params, headers=HEADERS).json()
    soup = BeautifulSoup(result["page"], 'html.parser')
    stream = soup.select_one("div.stream-container")
    if stream is None:
        print(f"No results found for {q}")
        return set(), None
    min_position = stream["data-min-position"]
    tweets = extract_tweets(soup)
    return tweets, min_position

def get_all_tweets(username, start, end, step=datetime.timedelta(days=90)):
    since = start
    tweets = []

    while since != end:
        until = since + step
        if until > end:
            until = end

        q = build_q(username, since, until)

        init_tweets, min_position = init_search(q)
        tweets += init_tweets
        print(init_tweets)

        has_more_items = True
        while has_more_items and min_position:
            more_tweets, min_position, has_more_items = timeline_search(q, min_position)
            print(more_tweets)
            tweets += more_tweets

        since = until

    return tweets

if __name__ == "__main__":
    username = "emptyflash"
    start = datetime.date(2009, 9, 1)
    end = datetime.date.today()
    tweets = get_all_tweets(username, start, end)
    import pdb; pdb.set_trace()
    with open(f"{username}.json", 'w') as outfile:
        json.dump(tweets, outfile)
