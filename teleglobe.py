#!/usr/bin/env python3

import os, sys
import signal
import logging
import tempfile
import subprocess
import yaml

with open("settings.yaml", "r") as fd:
    settings = yaml.load(fd, yaml.Loader)

from telegram import Update, ForceReply, PhotoSize
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(18, GPIO.OUT) # GPIO 18 Display on/off
GPIO.setup(25, GPIO.OUT) # GPIO 25 Mixer on/off
GPIO.setup(26, GPIO.IN)  # GPIO 26 Mixer rotation feedback

from captive_portal import checkTCPConnection, runCaptivePortal
import interface

import time
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger("teleglobe")

def tg_start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
        reply_markup=ForceReply(selective=True),
    )


def tg_help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    update.message.reply_text('Help!')


def tg_echo(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    update.message.reply_text(update.message.text)


def tg_media_photo(update: Update, context: CallbackContext) -> None:
    """Show photo on the display."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    if not update.message.photo:
        update.message.reply_text("ERROR: Unable to find photo in the message")
        return

    screen_size = interface.screen_size()
    best_image = PhotoSize("", "", 0, 0)
    for img in update.message.photo:
        # We need the image bigger then choosen one
        if img.width < best_image.width and img.height < best_image.height:
            continue
        # The image should be not too big then the screen
        if img.width > screen_size["width"] or img.height > screen_size["height"]:
            if best_image.width >= screen_size["width"] or best_image.height >= screen_size["height"]:
                continue # the image is already good enough for the screen
            best_image = img

    if best_image.width == 0 or best_image.height == 0:
        update.message.reply_text("ERROR: Incorrect image size:", best_image)
        return

    f = best_image.get_file()
    with tempfile.NamedTemporaryFile(suffix="file.jpg") as tf:
        f.download(out=tf)
        tf.flush()

        interface.show_black()

        proc = interface.show_image(tf.name)
        try:
            update.message.reply_text("Ok, showing photo for 15 sec")
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.terminate()

        try:
            outs, errs = proc.communicate(5)
            logger.error("STDOUT: %s, STDERR: %s", outs, errs)
        except subprocess.TimeoutExpired:
            proc.kill()

    update.message.reply_text("Photo show done")


def tg_media_video(update: Update, context: CallbackContext) -> None:
    """Show video or play audio."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    update.message.reply_text("Ok, playing media file")

def tg_update_archive(update: Update, context: CallbackContext) -> None:
    """Put the update.zip in working dir and allow startup script to update the TeleGlobe"""

    if update.message.from_user.username not in settings.get("admins", []):
        update.message.reply_text("ERROR: Access denied")
        return

    # TODO: put update.zip into working directory
    if not update.message.document:
        update.message.reply_text("ERROR: Unable to find document in the message")
        return

    interface.show_update_progress()

    f = update.message.document.get_file()
    with open("update.zip", "wb") as tf:
        f.download(out=tf)
        tf.flush()

    update.message.reply_text("Ok, restarting and updating teleglobe")

    os.kill(os.getpid(), signal.SIGINT)


def checkInternet() -> bool:
    """Make sure internet is here"""
    return checkTCPConnection("google.com", 443)

def runWiFiHostAP() -> None:
    """Starting WiFi access point to serve captive portal with initial teleglobe configs"""
    interface.show_no_internet()
    runCaptivePortal()

def main() -> None:
    """Start the bot."""

    logger.info("TeleGlobe v0.1")

    logger.info("Screen size: %s", interface.screen_size())
    interface.show_black()

    if not checkInternet():
        logger.warning("No internet connection found, running WiFi AP")
        runWiFiHostAP()
        return

    interface.show_welcome()

    # Create the Updater and pass it your bot's token.
    logger.info("Init telegram bot listener")
    updater = Updater(settings.get("telegram", {}).get("api_token"))

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", tg_start))
    dispatcher.add_handler(CommandHandler("help", tg_help_command))

    # on non command i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, tg_echo))

    # Media handlers
    dispatcher.add_handler(MessageHandler(Filters.photo, tg_media_photo))
    dispatcher.add_handler(MessageHandler(Filters.audio | Filters.video, tg_media_video))
    dispatcher.add_handler(MessageHandler(Filters.document.file_extension("zip"), tg_update_archive))

    # Start the Bot
    updater.start_polling()

    if os.path.isfile("backup.tar.gz"):
        # Update passed well, so moving the backup aside for future needs
        mod_ts = os.path.getmtime("backup.tar.gz")
        os.rename("backup.tar.gz", "backup-{}.tar.gz".format(datetime.utcfromtimestamp(mod_ts).strftime('%y%m%d%H%M%S')))

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    logger.info("Entering IDLE loop")
    updater.idle()


if __name__ == '__main__':
    main()
