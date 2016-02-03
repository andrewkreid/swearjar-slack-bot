#!/usr/bin/env python

import time
import json
import logging
from string import punctuation
from jarstore import JarStore

from slackclient import SlackClient

CENTS_PER_SWEAR = 20

# Globals
bad_words = {}
known_users = {}
sent_msg_id = 1


def tokenize_to_words(msg_text):
    tokens = []
    for w in msg_text.split():
        tokens.append(w.lower().strip(punctuation))
    return tokens


def find_swearing(msg_text):
    """Find swear words in msg_text. Return a list of found words"""
    global bad_words
    global sent_msg_id
    retval = []
    words = tokenize_to_words(msg_text)
    for w in words:
        if w in bad_words:
            retval.append(w)
    return retval


def get_user_info(user_id):
    """Return the info for a user. Cached in known_users."""
    global known_users
    global user_sc
    global user_token

    if user_id in known_users:
        logging.debug("Found %s in the cache" % user_id)
        return known_users[user_id]

    logging.debug("Looking up user id [%s]" % user_id)
    user_object = json.loads(user_sc.api_call(method="users.info", user=user_id))
    print user_object
    print type(user_object)
    if "ok" in user_object and user_object["ok"] == True:
        known_users[user_id] = user_object
        return user_object
    else:
        return None


def current_jar_total():
    global jar_store
    swears = jar_store.get_swear_total()
    return "$%.2f" % (float(swears) * CENTS_PER_SWEAR / 100.0)


def process_message(msg):
    global bot_sc
    global sent_msg_id
    global jar_store

    if "type" in msg:
        if msg["type"] == "message" and "text" in msg:
            swear_words = find_swearing(msg["text"])
            if len(swear_words) > 0:

                user_object = get_user_info(msg["user"])
                if user_object:
                    user_name = user_object["user"]["name"]
                else:
                    user_name = msg["user"]

                # Add to the swear jar
                for swear_word in swear_words:
                    jar_store.add_swear(msg["user"], user_name, swear_word)
                # send a reply (TODO: send picture with web API)
                bot_sc.rtm_send_message(channel=msg["channel"],
                                        message="Oooo - %s said %s. Swear Jar is up to %s" % (user_name,
                                                                                              " ".join(swear_words),
                                                                                              current_jar_total()))
                sent_msg_id += 1


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)

    # Load settings
    with open("settings.json") as fd:
        settings_json = json.load(fd)
        bot_token = settings_json["bot_token"]
        user_token = settings_json["user_token"]

    with open("bad-words.txt") as fd:
        for word in fd:
            bad_words[word.strip()] = True

    jar_store = JarStore("swearjar.sqlite")
    jar_store.open_db()

    logging.info("bot token is [%s]" % bot_token)
    logging.info("user token is [%s]" % user_token)

    bot_sc = SlackClient(bot_token)
    user_sc = SlackClient(user_token)
    if bot_sc.rtm_connect():
        while True:
            messages = bot_sc.rtm_read()
            for message in messages:
                logging.debug(message)
                process_message(message)
            time.sleep(3)
    else:
        logging.error("Connection Failed, invalid token")

