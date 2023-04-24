#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright 2023 David Guillen Fandos <david@davidgf.net>

# This bot is very CPU hungry, it's better to run it with a high niceness

import telebot, argparse, requests, io, logging, random, os

parser = argparse.ArgumentParser(prog='whatdidyousaybot')
parser.add_argument('--token', dest='token', required=True, help='Bot token')
parser.add_argument('--whisper-binary', dest='whisperbin', required=True, help='Path to the whisper binary (or binary name if in PATH)')
parser.add_argument('--whisper-model', dest='whispermod', required=True, help='Path to the gg whisper model to use')
parser.add_argument('--logfile', dest='logfile', default='/tmp/wdys.log', help='Log file path')
parser.add_argument('--threads', dest='nthreads', type=int, default=2, help='Thread count to use for inference')
parser.add_argument('--allowed-chats', dest='allowedc', required=True, help='Comma separated list of chat IDs where the bot is allowed to work')
args = parser.parse_args()

bot = telebot.TeleBot(args.token)

allowedchats = [int(x) for x in args.allowedc.split(",")]

logging.basicConfig(
	filename=args.logfile, level=logging.INFO,
	format='%(asctime)s %(levelname)-8s %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S')

MAX_FILE_SIZE = 1024*1024
MAX_DURATION  = 5*60

WELCOMEMSG = """
Hola! Aquest és un bot que transcriu audios en català a text.
Si l'afegeixes a un grup de Telegra, o li envies un audio, t'en transcriurà el contingut en text pla.
Màgia oi!? No! És whisper.cpp!
"""

TOOBIG="La nota d'audio és massa gran!"
TOOLNG="La nota d'audio és massa llarga!"
BADAUD="Oops, sembla que no puc entendre aquesta nota de veu"
SOMEERR="Oops, he tingut un error intern, em sap greu!"
NOTALL="Perdona, aquest bot no té permís per a funcionar en aquest chat! (contacta amb @davidgf)"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	logging.info("Hello to user %d" % message.chat.id)
	bot.send_message(message.chat.id, WELCOMEMSG)

@bot.message_handler(content_types=['voice'])
def echo_all(message):
	# If it's too big:
	if message.chat.id not in allowedchats:
		logging.warning("Unallowed chat with userid %d" % message.chat.id)
		bot.reply_to(message, NOTALL)
	elif message.voice.file_size > MAX_FILE_SIZE:
		logging.warning("File to big sent by user %d" % message.chat.id)
		bot.reply_to(message, TOOBIG)
	elif message.voice.duration > MAX_DURATION:
		logging.warning("Voice not too long from user %d" % message.chat.id)
		bot.reply_to(message, TOOLNG)
	else:
		logging.info("Got a voice note from user %d (%s)" % (message.chat.id, str(message.from_user.username)))

		bfn = "/tmp/%d" % random.randint(0, 1<<32)
		opfn = bfn + ".opus"
		wafn = bfn + ".wav"
		txfn = bfn + ".txt"

		downinfo = bot.get_file(message.voice.file_id)
		url = 'https://api.telegram.org/file/bot{0}/{1}'.format(args.token, downinfo.file_path)

		try:
			# Download the voice note and store the opus file on disk
			content = requests.get(url).content
			with open(opfn, "wb") as ofd:
				ofd.write(content)

			# Decode opus to 16KHz wave (as required by whisper)
			if os.system("opusdec --force-wav --rate 16000 %s %s" % (opfn, wafn)):
				bot.reply_to(message, BADAUD)
				os.unlink(opfn)
				return
			os.unlink(opfn)
			
			if os.system("%s -l ca -m %s -f %s -p 1 -t %d --output-txt --output-file %s" % (args.whisperbin, args.whispermod, wafn, args.nthreads, bfn)):
				bot.reply_to(message, BADAUD)
				os.unlink(wafn)
				return
			os.unlink(wafn)

			cnt = open(txfn).read()
			bot.reply_to(message, cnt)
			os.unlink(txfn)

		except Exception as e:
			logging.error("Got an exception " + str(e))
			bot.reply_to(message, SOMEERR)

bot.polling(True)

