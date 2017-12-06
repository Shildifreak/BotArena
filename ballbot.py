from bot_api import Bot


with Bot() as bot:
	do = bot.do
	do("l 50")
	while True:
		see = do("radar 5")
		if see and "Ball" in see:
			do("r 50")
		else:
			do("r -50")
