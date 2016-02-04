# swearjar-slack-bot

This is a simple bot that monitors channels it's in and maintains a swear jar total 
for unsavory language (defined to be the words in ```bad-words.txt```).

Copy ```settings.json.template``` to ```settings.json``` and edit to fill in your bot and user keys
(the user key maybe isn't necessary but I haven't had time to fix it), then run ```swearjar.py```.

Invite ```@swearjar``` to a channel. Type ```@swearjar: help``` to get a list of commands.
