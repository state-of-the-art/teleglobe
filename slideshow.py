#!/usr/bin/env python3

import os
import fsnotify
import threading
import time
import atexit
import random
import logging

logger = logging.getLogger(__name__)

import interface
import settings

_slideshow_active = False
_slideshow_thread = None
_watcher = None
_watcher_thread = None
_album_paths = set()
_current_album_paths = []

def make_paths_random() -> list:
    """Makes random list out of the known album paths"""
    global _current_album_paths
    _current_album_paths = random.sample(list(range(len(_album_paths))), len(_album_paths))

def init() -> None:
    """Initialize the background thread"""
    global _slideshow_thread
    if _slideshow_thread is not None and _slideshow_thread.is_alive():
        return

    _slideshow_thread = threading.Thread(target=_background_slideshow)
    _slideshow_thread.start()

def start() -> None:
    """Starts the slideshow"""
    global _slideshow_active
    _slideshow_active = True
    init()
    logger.info("Slideshow started")

def stop() -> None:
    """Stops the slideshow"""
    global _slideshow_active
    _slideshow_active = False
    logger.info("Slideshow stopped")

def _background_slideshow() -> None:
    """Works in a loop while active"""
    global _slideshow_active, _current_album_paths
    logger.info("Started slideshow background routine")
    while _slideshow_active:
        if not _current_album_paths:
            make_paths_random()
        path = list(_album_paths)[_current_album_paths.pop()]
        if path.endswith(tuple(interface.SUPPORTED_IMAGES)):
            interface.show_image(path, settings.get("slideshow", {}).get("image_display_time", 15), True)
        elif path.endswith(tuple(interface.SUPPORTED_VIDEOS)):
            wait_sec = settings.get("slideshow", {}).get("video_display_time", 30)
            volume = settings.get("slideshow", {}).get("video_volume", 0)
            interface.show_video(path, wait_sec, volume)
        else:
            log.error("Unable to find the supported format for %s", path)

    logger.info("Slideshow background routine completed")


# Init module

def scan() -> None:
    """Start scanning of the files in album directories"""
    global _watcher, _watcher_thread, _album_paths

    logger.info("Start scanning")

    dirs = settings.get("slideshow", {}).get("directories")
    supported_exts = tuple( "." + s for s in interface.SUPPORTED_IMAGES.union(interface.SUPPORTED_VIDEOS) )

    # Setup fsnotify directory watcher
    if _watcher is None and dirs:
        # TODO - move to module init
        atexit.register(stop)
        logger.info("Creating fsnotify watcher")
        _watcher = fsnotify.Watcher()
        _watcher.accepted_file_extensions = supported_exts

        _watcher.target_time_for_single_scan = 2.0
        _watcher.target_time_for_notification = 4.0

        _watcher.set_tracked_paths(dirs)

        def start_watching():
            for change_enum, change_path in _watcher.iter_changes():
                if change_enum == fsnotify.Change.added:
                    _album_paths.add(change_path)
                    _current_album_paths.append(len(_album_paths))
                    logger.info('Added file: %s', change_path)
                elif change_enum == fsnotify.Change.deleted:
                    _current_album_paths.remove(len(_album_paths))
                    _album_paths.remove(change_path)
                    logger.info('Deleted file: %s', change_path)

        _watcher_thread = threading.Thread(target=start_watching)
        _watcher_thread.daemon = True
        _watcher_thread.start()

        atexit.register(_watcher.dispose)

    # Locate the supported files in the album directories
    for directory in dirs:
        logger.info("Processing album directory %s", directory)
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if not filename.endswith(supported_exts):
                    continue
                path = os.path.join(root, filename)
                _album_paths.add(path)
        logger.info("Files in the list: %d", len(_album_paths))

scan()
