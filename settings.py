#!/usr/bin/env python3

import yaml
import json

with open("settings.yaml", "r") as fd:
    _settings = yaml.load(fd, yaml.Loader)

def all() -> any:
    """Return all the settings"""
    return _settings

def get(key: str, default: any = None) -> any:
    """Returns the settings key value"""
    return _settings.get(key, default)

def set(key: str, data: any) -> None:
    """Set the key value and save the new settings file"""
    _settings[key] = data
    with open("settings.yaml", "w") as fd:
        yaml.dump(_settings, fd)
