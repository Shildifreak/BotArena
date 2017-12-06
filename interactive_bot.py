from bot_api import Bot


with Bot() as bot:
    while True:
        command = input("command: ")
        print(bot.do(command))
