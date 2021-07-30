#!/usr/bin/env python3

import os, sys
import logging
import subprocess
import atexit

logger = logging.getLogger(__name__)

_screen_size = {"width": 0, "height": 0}
all_processes = []

def screen_size() -> dict:
    return _screen_size

def show_black() -> None:
    """Clean screen with black background."""
    with open("/dev/fb0", 'wb') as fd:
        for _ in range(_screen_size["height"]):
            fd.write(b'\x00' * 4 * _screen_size["width"])

def show_image(path: str) -> subprocess.Popen:
    logger.info("Show image file: %s", path)
    cleanup()
    return subprocess.Popen([os.path.join(os.path.dirname(os.path.realpath(__file__)), "omxiv"), path])

def show_media(path: str) -> subprocess.Popen:
    logger.info("Show media file: %s", path)
    cleanup()
    # Show video:  ~/bbb_sunflower_1080p_60fps_normal.mp4
    return subprocess.Popen(["omxplayer", "--adev", "alsa", path])


def show_no_internet() -> subprocess.Popen:
    return show_image(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics", "no_internet.png"))

def show_welcome() -> subprocess.Popen:
    return show_image(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics", "welcome.png"))

def show_update_progress() -> subprocess.Popen:
    return show_image(os.path.join(os.path.dirname(os.path.realpath(__file__)), "pics", "update_progress.png"))

def cleanup() -> None:
    """Clean up all the running processes just in case"""
    proc = subprocess.Popen(["pkill", "omxplayer"])
    proc.communicate()
    proc = subprocess.Popen(["pkill", "omxiv"])
    proc.communicate()

# Init module

# Get framebuffer screen size
with open("/sys/class/graphics/fb0/virtual_size", "r") as fd:
    data = fd.read().strip().split(",")
    _screen_size["width"], _screen_size["height"] = int(data[0]), int(data[1])

atexit.register(cleanup)
