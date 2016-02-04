#!/usr/bin/env python

import time
import json
import logging
import re
from string import punctuation
from jarstore import JarStore
from datetime import datetime

from slackclient import SlackClient

CENTS_PER_SWEAR = 20
BOT_NAME = "swearjar"

# Globals
bad_words = {}
known_users = {}
sent_msg_id = 1
bot_user_id = 'U0L4KJ8MV'

# for keeping track of the number of swears this minute
swears_this_minute = 0
swear_minute_no = 0


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
    global bot_user_id

    if user_id in known_users:
        logging.debug("Found %s in the cache" % user_id)
        return known_users[user_id]

    logging.debug("Looking up user id [%s]" % user_id)
    user_object = json.loads(user_sc.api_call(method="users.info", user=user_id))
    if "ok" in user_object and user_object["ok"] == True:
        known_users[user_id] = user_object
        # set the ID for the bot user
        if user_object["user"]["name"] == BOT_NAME:
            bot_user_id = user_id
        return user_object
    else:
        return None


def current_jar_total():
    global jar_store
    swears = jar_store.get_swear_total()
    return "$%.2f" % (float(swears) / 100.0)


def user_id_to_name(user_id):
    user_object = get_user_info(user_id)
    if user_object:
        user_name = user_object["user"]["name"]
    else:
        user_name = user_id
    return user_name


def process_direct_message(msg):
    """Handle people talking to the bot directly with '@swearjar command'"""
    global bot_sc
    global jar_store
    global bot_user_id
    global bad_words

    # extract the command part
    user_id = msg["user"]
    user_name = user_id_to_name(user_id)
    bot_id_regexp = "<@%s>:* (.*)$" % bot_user_id
    logging.info("regexp is [%s]" % bot_id_regexp)
    p = re.compile(bot_id_regexp)
    m = p.match(msg["text"])
    reply_text = "I don't understand that (try \"help\")"
    if m:
        command = m.group(1)
        logging.info("You said [%s] to swearjar" % command)

        help_reply_text = ("Welcome to SwearJar, turning your @#$%! into $$$$\n\n"
                           "Things you can ask/tell me:\n\n"
                           "help - this text.\n"
                           "total - print the swear jar total.\n"
                           "leaders - print who is swearing the most.\n"
                           "my swearing - list all my swearing.\n"
                           "insult - Random cursing.\n"
                           "<word> is not a dirty word - remove <word> from list of naughty words.\n"
                           "<word> is a dirty word - add <word> to the list of naughty words.\n"
                           "what's the damage - list how much you owe.\n"
                           "pay $nn.nn - record that you paid some money to the swear jar."
                           )

        if command.startswith("help"):
            reply_text = help_reply_text
        elif command.startswith("total"):
            reply_text = "Swear Jar is currently owed %s" % current_jar_total()
        elif "what's the damage" in command:
            logging.debug("What's the damage for [%s]" % user_id)
            fines = jar_store.get_money_owed(user_id) / 100.0
            payments = jar_store.get_money_paid(user_id) / 100.0
            reply_text = "%s has $%.2f in files, and has paid $%.2f, so they owe $%.2f" % (user_name,
                                                                                           fines,
                                                                                           payments,
                                                                                           fines - payments)
        elif command.startswith("my swear"):
            reply_text = "Recent cursing from %s:\n\n" % user_name
            for swear in jar_store.get_swears(user_id):
                reply_text += "  %s : %s\n" % (swear[0], swear[1])
        elif command.startswith("insult"):
            reply_text = "I wasn't brave enough to implement this. Have you SEEN the list?"
        elif command.startswith("leaders"):
            reply_text = "Current profanity leaders:\n\n"
            for leader in jar_store.get_leaders():
                reply_text += "$%4.2f : %s\n" % (leader[0] / 100.0, leader[1])
        elif "is a dirty word" in command:
            tokens = tokenize_to_words(command)
            if tokens[1] == "is":
                new_word = tokens[0]
                bad_words[new_word] = True
                reply_text = "Ok, I'll add \"%s\" to the list. Try and avoid it from now on." % new_word
            else:
                reply_text = "Try saying \"foo is a dirty word\"."
        elif "is not a dirty word" in command:
            tokens = tokenize_to_words(command)
            if tokens[1] == "is":
                remove_word = tokens[0]
                if remove_word in bad_words:
                    del bad_words[remove_word]
                    reply_text = "Ok, I'll remove \"%s\" from the list." % remove_word
                else:
                    reply_text = "\"%s\" isn't a rude word." % remove_word
            else:
                reply_text = "Try saying \"foo is not a dirty word\"."
        elif command.startswith("pay "):
            # possible payment. Try and parse an amount
            payp = re.compile('pay \$([-\d\.]+)')
            paym = payp.match(command)
            if paym:
                try:
                    payment_dollars = float(paym.group(1))
                    payment_cents = int(payment_dollars * 100.0)
                    jar_store.add_payment(user_id, user_name, payment_cents)
                    reply_text = "%s paid $%.2f to the swear jar." % (user_name, payment_dollars)
                except ValueError:
                    reply_text = "I can't turn \"%s\" into a dollar amount." % command
            else:
                reply_text = "Can't parse: try \"pay $dd.dd\""
        else:
            reply_text = "I don't understand that (try \"help\")"

    bot_sc.rtm_send_message(channel=msg["channel"], message=reply_text)


def process_message(msg):
    global bot_sc
    global sent_msg_id
    global jar_store
    global swears_this_minute
    global swear_minute_no

    if "type" in msg:
        if msg["type"] == "message" and "text" in msg:

            # Check for messages directly to the bot
            if bot_user_id and "<@%s>" % bot_user_id in msg["text"]:
                logging.info("Message to the bot [%s]" % msg["text"])
                process_direct_message(msg)
            else:
                if bot_user_id and msg["user"] == bot_user_id:
                    # Don't ding the bot for swearing.
                    pass
                else:
                    # Check for swear words
                    swear_words = find_swearing(msg["text"])
                    if len(swear_words) > 0:

                        user_name = user_id_to_name(msg["user"])
                        # Add to the swear jar
                        for swear_word in swear_words:
                            jar_store.add_swear(msg["user"], user_name, swear_word, CENTS_PER_SWEAR)
                        if "millenial" in swear_words or "millennial" in swear_words:
                            reply_text = ("OMG! #sogross that you said *%s*! I can't even..."
                                          " :peach: :pizza: :turtle: :bear: :yellow_heart:" % " ".join(swear_words))
                        else:
                            reply_text = "Oooo - %s said *%s* :cry:. Swear Jar is up to %s" % (user_name,
                                                                                               " ".join(swear_words),
                                                                                               current_jar_total())
                        bot_sc.rtm_send_message(channel=msg["channel"], message=reply_text)
                        sent_msg_id += 1

                        # Now add a reaction to the message
                        bot_sc.api_call(method="reactions.add",
                                        channel=msg["channel"],
                                        name="poop",
                                        timestamp=msg["ts"])

                        # check if we need to call on the captain
                        this_minute_no = datetime.now().minute
                        logging.info("minute: %d, %d count: %d" % (this_minute_no, swear_minute_no, swears_this_minute))
                        if this_minute_no != swear_minute_no:
                            # reset count
                            swear_minute_no = this_minute_no
                            swears_this_minute = 0
                        else:
                            swears_this_minute += 1
                            if swears_this_minute >= 5:
                                # OK, we need to step in
                                attachments = [
                                    {
                                        "fallback": "Hey! Too much swearing",
                                        "color": "#FF0000",
                                        "pretext": "",
                                        "image_url": "https://raw.githubusercontent.com/andrewkreid/swearjar-slack-bot/master/language.gif"
                                    }
                                ]
                                resp = bot_sc.api_call(method="chat.postMessage",
                                                       channel=msg["channel"],
                                                       text="Hey! Calm it down (>5 swears in the last minute)!",
                                                       as_user=True,
                                                       attachments=json.dumps(attachments))
                                logging.debug(json.dumps(attachments))
                                logging.debug(resp)
                                swears_this_minute = 0

        elif msg["type"] == "presence_change" and "user" in msg:
            # We get one of these after we start the bot saying the bot has joined the channel.
            #  We use this to find out the bot's user ID
            user_name = user_id_to_name(msg["user"])
            logging.debug("user %s(%s)'s status changed to %s" % (msg["user"], user_name, msg["presence"]))


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
            try:
                messages = bot_sc.rtm_read()
                for message in messages:
                    logging.debug(message)
                    process_message(message)
                time.sleep(1)
            except Exception, e:
                logging.error("Something Failed")
                logging.error(e)
    else:
        logging.error("Connection Failed, invalid token")

