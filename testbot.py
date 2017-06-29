from bot_api import Bot

import time

with Bot() as bot:
    bot.do("name Automyco")
    bot.do("color 255 0 0")
    #bot.do("r 50")
    while True:
        r = bot.do("radar 1")
        if r and any(x in r for x in("Ball",) ):#"Battery","MediKit",
            v = str(1.5*float(r.split(" ",1)[0])/5)
            bot.do("tg 0")
            bot.do("tr 0")
            for i in range(10):
                r = bot.do("f 1 %s" %v)
                time.sleep(0.05)
            if r != "done":
                bot.do("tg 0")
                bot.do("tr 0")
        else:
            bot.do("tg 60")
            bot.do("tr 60")
"""        see = bot.do("radar 5")
        if see and "Ball" in see:
            bot.do("l 50")
        else:
            bot.do("l -50")"""
