from bot_api import Bot

import time

def f(zahl):
    """ -1 <= zahl <= 1 """
    if zahl >= 0:
        return 1
    return 2*zahl**3+1

def ff(zahl):
    """ -1 <= zahl <= 1 """
    return 50*f(zahl)*(1-0.4*abs(zahl))

l = ff
def r(zahl):
    return l(-zahl)

with Bot() as bot:
    bot.do("name Maxbot")
    direction = 0
    change = 1 # 1 oder -1
    T = 0.2
    t = time.time()
    shouldchange = False
    canchange = True
    while True:
        bot.do("r %i" %r(direction))
        bot.do("l %i" %l(direction))
        dt = t-time.time()
        t = time.time()
        if dt > 0:
            time.sleep(dt)
        see = bot.do("radar 5")
        if see and "Battery" in see:
            shouldchange = True
            #change *= -1
            #direction *= 0.8
            direction =0.1
            change = -1
            #if direction > 0:
            #    change = -1
            #else:
            #    change = 1
        oldd = direction
        direction += change * 0.12
        if oldd*direction <= 0:
            canchange = True
        if canchange and shouldchange:
            change *=-1
            canchange = False
            shouldchange = False
        #if abs(direction) > 1:
            #change *= -1
        direction = min(1,max(-1,direction))
