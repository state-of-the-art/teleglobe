 #!/usr/bin/env python3

import os, sys
import signal
import logging
import tempfile
import subprocess
import html
import traceback
import json

import settings

from telegram import Update, ForceReply, PhotoSize, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(18, GPIO.OUT) # GPIO 18 Display on/off
GPIO.setup(25, GPIO.OUT) # GPIO 25 Mixer on/off
GPIO.setup(26, GPIO.IN)  # GPIO 26 Mixer rotation feedback

from captive_portal import checkTCPConnection, runCaptivePortal
import interface
import slideshow

import time
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger("teleglobe")

def tg_error_handler(update: object, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message1 = f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>'
    message2 = f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>'
    message3 = f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>'
    message4 = f'<pre>{html.escape(tb_string)}</pre>'

    for chat_id in settings.get('developer_chat_ids'):
        context.bot.send_message(chat_id=chat_id, text='An exception was raised while handling an update', parse_mode=ParseMode.HTML)
        context.bot.send_message(chat_id=chat_id, text=message1, parse_mode=ParseMode.HTML)
        context.bot.send_message(chat_id=chat_id, text=message2, parse_mode=ParseMode.HTML)
        context.bot.send_message(chat_id=chat_id, text=message3, parse_mode=ParseMode.HTML)
        context.bot.send_message(chat_id=chat_id, text=message4, parse_mode=ParseMode.HTML)

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


def tg_help(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    update.message.reply_text("Help commands:\n\n"
        "  /start - just welcome command\n"
        "  /mixer - get or set mixer value ('' - get, '0'-'1' - set)\n"
        "  /exec_command - execute command in shell and get outputs\n"
        "  /volume - get or set audio master volume ('' - get, '0'-'100' - set)\n"
        "  /settings - get or set settings ('' - all, '<KEY>' - for key, '<KEY> <JSON> - set key value')\n"
        "\n\n"
        "Also you can send photo, video and audio to show it on the globe.\n"
        "To update teleglobe - send zip archive with new distributive."
    )


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
        update.message.reply_text("Downloading photo {0}...".format(f.file_size))
        f.download(out=tf)
        tf.flush()

        slideshow.stop()
        interface.show_black()

        update.message.reply_text("Show photo for 60 sec")
        proc = interface.show_image(tf.name, 60)

    slideshow.start()
    update.message.reply_text("Photo show done")

def tg_media_audio(update: Update, context: CallbackContext) -> None:
    """Play audio."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    if not update.message.audio:
        update.message.reply_text("ERROR: Unable to find audio in the message")
        return

    audio = update.message.audio
    f = audio.get_file()
    with tempfile.NamedTemporaryFile(suffix="file.mp3") as tf:
        update.message.reply_text("Downloading audio {0}...".format(audio.file_size))
        f.download(out=tf)
        tf.flush()

        update.message.reply_text("Play audio: {}s".format(audio.duration))
        proc = interface.play_audio(tf.name)
        proc.communicate()
    update.message.reply_text("Ok, audio played")


def tg_media_video(update: Update, context: CallbackContext) -> None:
    """Show video."""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    if update.message.video_note:
        video = update.message.video_note
    elif update.message.video:
        video = update.message.video
    else:
        update.message.reply_text("ERROR: Unable to find video in the message")
        return

    f = video.get_file()
    with tempfile.NamedTemporaryFile(suffix="file.mp4") as tf:
        update.message.reply_text("Downloading video {0}...".format(video.file_size))
        f.download(out=tf)
        tf.flush()

        slideshow.stop()
        interface.show_black()

        update.message.reply_text("Show video: {}s".format(video.duration))
        proc = interface.show_video(tf.name)
        proc.communicate()
    update.message.reply_text("Ok, video showed")
    slideshow.start()


def tg_update_archive(update: Update, context: CallbackContext) -> None:
    """Put the update.zip in working dir and allow startup script to update the TeleGlobe"""

    if update.message.from_user.username not in settings.get("admins", []):
        update.message.reply_text("ERROR: Access denied")
        return

    if not update.message.document:
        update.message.reply_text("ERROR: Unable to find document in the message")
        return

    slideshow.stop()
    interface.show_update_progress()

    f = update.message.document.get_file()
    with open("update.zip", "wb") as tf:
        f.download(out=tf)
        tf.flush()

    update.message.reply_text("Ok, restarting and updating teleglobe")

    os.kill(os.getpid(), signal.SIGINT)


def tg_mixer(update: Update, context: CallbackContext) -> None:
    """Control mixer"""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    data = update.message.text.split(' ', 1)
    if len(data) == 2:
        # Set mixer value
        GPIO.output(25, GPIO.HIGH if data[1] == "1" else GPIO.LOW)
    update.message.reply_text("Mixer is set to {0}".format(GPIO.input(25)))


def tg_exec_command(update: Update, context: CallbackContext) -> None:
    """Run command in shell"""

    if update.message.from_user.username not in settings.get("admins", []):
        update.message.reply_text("ERROR: Access denied")
        return

    proc = subprocess.run(update.message.text.split(' ', 1)[-1], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    update.message.reply_text("STDOUT: %s\n\nSTDERR: %s\n\nCODE: %s" % (proc.stdout, proc.stderr, proc.returncode))


def tg_volume(update: Update, context: CallbackContext) -> None:
    """Change master audio volume"""

    if update.message.from_user.username not in settings.get("users", []):
        update.message.reply_text("ERROR: Access denied")
        return

    try:
        vol = int(update.message.text.split(' ', 1)[-1]) % 101
        proc = subprocess.run(["amixer", "sset", "PCM,0", "{0}%,{0}%".format(vol), "unmute", "cap"])
        update.message.reply_text("Set volume to {0}%".format(vol))
    except ValueError:
        proc = subprocess.run(["amixer", "sget", "PCM,0"], stdout=subprocess.PIPE)
        # Parsing output like this:
        #  ...
        #  Front Left: blabla
        #  Front Right: Playback 8 [5%] [-26.55dB] [on]
        data = proc.stdout.rsplit(" ", 3)
        if len(data) == 4:
            update.message.reply_text("Volume is set to: {0}".format(data[1].strip('[]')))
        else:
            update.message.reply_text("Error during getting the volume value")


def tg_settings(update: Update, context: CallbackContext) -> None:
    """Display or change settings (as "key {JSON}")"""

    if update.message.from_user.username not in settings.get("admins", []):
        update.message.reply_text("ERROR: Access denied")
        return

    data = update.message.text.split(' ', 2)
    if len(data) == 3:
        # Change the setting
        try:
            value = json.loads(data[2])
            settings.set(data[1], value)
            update.message.reply_text("Setting '{0}' changed: {1}".format(data[1], value))
        except Exception as e:
            update.message.reply_text("ERROR: Unable to set setting {0}".format(e))
    elif len(data) == 2:
        # Just show the key value
        update.message.reply_text("Settings for {0}: {1}".format(data[1], settings.get(data[1])))
    else:
        # Show all the settings
        update.message.reply_text("Settings: {0}".format(json.dumps(settings.all())))


# TODO: Take photo from camera
#  raspistill --nopreview -roi 0,0,0.6,1 -o out.jpg


def checkInternet() -> bool:
    """Make sure internet is here"""
    return checkTCPConnection("google.com", 443)

def runWiFiHostAP() -> None:
    """Starting WiFi access point to serve captive portal with initial teleglobe configs"""
    interface.show_no_internet()
    runCaptivePortal()

def main() -> None:
    """Start the bot."""

    logger.info("TeleGlobe v0.5")

    logger.info("Screen size: %s", interface.screen_size())
    interface.show_black()

    if not checkInternet():
        logger.warning("No internet connection found, running WiFi AP")
        runWiFiHostAP()
        return

    interface.show_welcome()

    logger.info("Init telegram bot listener")
    updater = Updater(settings.get("telegram", {}).get("api_token"))

    dispatcher = updater.dispatcher
    dispatcher.add_error_handler(tg_error_handler)

    dispatcher.add_handler(CommandHandler("start", tg_start))
    dispatcher.add_handler(CommandHandler("mixer", tg_mixer))
    dispatcher.add_handler(CommandHandler("exec_command", tg_exec_command))
    dispatcher.add_handler(CommandHandler("volume", tg_volume))
    dispatcher.add_handler(CommandHandler("settings", tg_settings))
    dispatcher.add_handler(CommandHandler("help", tg_help))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, tg_echo))

    # Media handlers
    dispatcher.add_handler(MessageHandler(Filters.photo, tg_media_photo))
    dispatcher.add_handler(MessageHandler(Filters.audio, tg_media_audio))
    dispatcher.add_handler(MessageHandler(Filters.video | Filters.video_note, tg_media_video))
    dispatcher.add_handler(MessageHandler(Filters.document.file_extension("zip"), tg_update_archive))

    updater.start_polling()

    logger.info("Running Slideshow")
    slideshow.scan()
    slideshow.start()

    if os.path.isfile("backup.tar.gz"):
        # Update passed well, so moving the backup aside for future needs
        mod_ts = os.path.getmtime("backup.tar.gz")
        os.rename("backup.tar.gz", "backup-{}.tar.gz".format(datetime.utcfromtimestamp(mod_ts).strftime('%y%m%d%H%M%S')))

    logger.info("Entering IDLE loop")
    updater.idle()


if __name__ == '__main__':
    main()
