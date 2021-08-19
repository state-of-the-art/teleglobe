#!/usr/bin/env python3

import os, sys
import logging
import subprocess
import atexit

logger = logging.getLogger(__name__)

_screen_size = {"width": 0, "height": 0}
_audio_detected = False

SUPPORTED_IMAGES = {
    "jpg", "jpeg",
    "png",
    "bmp",
    "gif",
    "tiff",
}

SUPPORTED_VIDEOS = {
    "mp4", "m4v",
    "mkv",
    "avi",
    "webm",
    "mts", "m2ts", "ts",
}

def screen_size() -> dict:
    return _screen_size

def show_black() -> None:
    """Clean screen with black background."""
    with open("/dev/fb0", 'wb') as fd:
        for _ in range(_screen_size["height"]):
            fd.write(b'\x00' * 4 * _screen_size["width"])

def show_image(path: str, wait_sec: int = 0, center: bool = False) -> subprocess.Popen:
    """Shows still/animated image on the display"""
    # TODO: modify omxiv "center" to fill most of the screen: https://www.raspberrypi.org/forums/viewtopic.php?t=256348
    # TODO: modify omxiv to control the image position and make animated movement
    logger.info("Show image file: %s", path)
    cleanup_display()
    proc = subprocess.Popen([os.path.join(os.path.dirname(os.path.realpath(__file__)), "omxiv"),
        "--blank", "-T", "blend",
        "--aspect", "center" if center else "letterbox",
        path,
    ])
    if wait_sec > 0:
        try:
            proc.wait(wait_sec)
        except subprocess.TimeoutExpired:
            proc.terminate()

        try:
            outs, errs = proc.communicate(1)
            logger.debug("STDOUT: %s, STDERR: %s", outs, errs)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate(1)
            logger.error("STDOUT: %s, STDERR: %s", outs, errs)
    return proc

def show_video(path: str, wait_sec: int = 0, volume: int = 100) -> subprocess.Popen:
    logger.info("Show video file: %s", path)
    cleanup_display()
    # If no audio available omxplayer will not play anything
    if _audio_detected:
        proc = subprocess.Popen(["omxplayer",
            "--adev", "alsa", "--vol", str(volume*60-6000), path,
        ])
    else:
        proc = subprocess.Popen(["omxplayer",
            path,
        ])
    if wait_sec > 0:
        try:
            proc.wait(wait_sec)
        except subprocess.TimeoutExpired:
            proc.terminate()

        try:
            outs, errs = proc.communicate(1)
            logger.debug("STDOUT: %s, STDERR: %s", outs, errs)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate(1)
            logger.error("STDOUT: %s, STDERR: %s", outs, errs)
    return proc

def play_audio(path: str, wait_sec: int = 0, volume: int = 100) -> (None, subprocess.Popen):
    logger.info("Play audio file: %s", path)
    cleanup_audio()

    if not _audio_detected:
        logger.info("ERROR: Unable to play audio file due to no sound card available")
        return None

    # We need symlink to not be killed by the slideshow display process cleaning
    if os.path.exists("./omxaudio"):
        os.unlink("./omxaudio")
    os.symlink("/usr/bin/omxplayer.bin", "./omxaudio")

    proc = subprocess.Popen(["./omxaudio",
        "--adev", "alsa", "--vol", str(volume*60-6000), path,
    ])
    if wait_sec > 0:
        try:
            proc.wait(wait_sec)
        except subprocess.TimeoutExpired:
            proc.terminate()

        try:
            outs, errs = proc.communicate(1)
            logger.debug("STDOUT: %s, STDERR: %s", outs, errs)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate(1)
            logger.error("STDOUT: %s, STDERR: %s", outs, errs)
    return proc

def show_no_internet() -> subprocess.Popen:
    return show_image(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics", "no_internet.png"))

def show_welcome() -> subprocess.Popen:
    return show_image(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics", "welcome.png"))

def show_update_progress() -> subprocess.Popen:
    return show_image(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics", "update_progress.png"))

def cleanup_display() -> None:
    """Clean up display running processes"""
    proc = subprocess.Popen(["pkill", "omxplayer"])
    proc.communicate()
    proc = subprocess.Popen(["pkill", "omxiv"])
    proc.communicate()

def cleanup_audio() -> None:
    """Clean up audio running processes"""
    proc = subprocess.Popen(["pkill", "omxaudio"])
    proc.communicate()

def cleanup() -> None:
    """Clean up all the running processes"""
    cleanup_display()
    cleanup_audio()

# Init module

# Get framebuffer screen size
with open("/sys/class/graphics/fb0/virtual_size", "r") as fd:
    data = fd.read().strip().split(",")
    _screen_size["width"], _screen_size["height"] = int(data[0]), int(data[1])

atexit.register(cleanup)

# Check audio is available
_audio_detected = os.system("amixer") == 0
