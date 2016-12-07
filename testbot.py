from bot_api import Bot

import time

with Bot() as bot:
    bot.do("name Automyco")
    bot.do("r 50")
    while True:
        see = bot.do("radar 5")
        if see and "Battery" in see:
            bot.do("l 50")
        else:
            bot.do("l -50")
