#!/usr/bin/env python
# -*- coding: utf-8 -*-

__all__ = []

import os
import re
import sys
import json
import tweepy
from collections import Counter

DEFAULT_SETTINGS_FILE = "settings.json"
DEFAULT_SCRATCH_FILE = "scratch.json"
DEFAULT_FAILURES_FILE = "failures.json"


def get_auth(settings_file=DEFAULT_SETTINGS_FILE):
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            settings = json.load(f)
    else:
        settings = {}

    # Get the consumer info.
    for k in ["consumer_key", "consumer_secret"]:
        if k not in settings:
            settings[k] = input("{0}: ".format(k))
    with open(settings_file, "w") as f:
        json.dump(settings, f)

    # Set up the auth.
    auth = tweepy.OAuthHandler(
        settings["consumer_key"], settings["consumer_secret"]
    )

    # Get the user info.
    if "user_token" not in settings:
        print("Go to:\n    {0}".format(auth.get_authorization_url()))
        pin = input("Enter your PIN: ")
        auth.get_access_token(pin)
        settings["user_token"] = auth.access_token
        settings["user_secret"] = auth.access_token_secret
        with open(settings_file, "w") as f:
            json.dump(settings, f)

    # Authenticate.
    auth.set_access_token(settings["user_token"], settings["user_secret"])
    return auth


class ArXivStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        with open(DEFAULT_SCRATCH_FILE, "a") as f:
            f.write(json.dumps(status._json) + "\n")
        print(status.text)


arxiv_regex = re.compile(r"([0-9]{4,5}\.[0-9]{4,5})"
                         r"|(?:arxiv\.org/(?:.+?)/(.*)\b)")
version_regex = re.compile(r"(.*?)v[0-9]*")


def _match_to_id(match):
    for token in match:
        if not len(token):
            continue
        if token.endswith(".pdf"):
            token = token[:-4]
        v = version_regex.findall(token)
        if len(v):
            return v[0]
        return token


def get_arxiv_ids(tweet):
    text = tweet["text"]
    urls = tweet.get("entities", {}).get("urls", [])
    ids = (
        arxiv_regex.findall(text) +
        [_match_to_id(i) for url in urls
         for i in arxiv_regex.findall(url.get("expanded_url", ""))]
    )

    if "retweeted_status" in tweet:
        ids += get_arxiv_ids(tweet["retweeted_status"])
    if "quoted_status" in tweet:
        ids += get_arxiv_ids(tweet["quoted_status"])

    return list(set(ids))


if "stream" in sys.argv:
    auth = get_auth()
    listener = ArXivStreamListener()
    stream = tweepy.Stream(auth=get_auth(), listener=listener)
    stream.filter(track=["arxiv"])
elif "analysis" in sys.argv:
    with open(DEFAULT_SCRATCH_FILE, "r") as f:
        tweets = [json.loads(line) for line in f]
    print("Analyzing {0} tweets...".format(len(tweets)))

    arxiv_ids = []
    for tweet in tweets:
        ids = get_arxiv_ids(tweet)
        if not len(ids):
            with open(DEFAULT_FAILURES_FILE, "a") as f:
                f.write(json.dumps(tweet) + "\n")
        arxiv_ids += ids
    print(Counter(arxiv_ids))
