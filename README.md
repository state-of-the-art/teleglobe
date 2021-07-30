# TeleGlobe

Telegram controlled snowglobe bot

## Requirements

* omxplayer - show video on framebuffer
* omxiv - show pictures on framebuffer ( https://github.com/HaarigerHarald/omxiv )
* Add "vt.global_cursor_default=0" to /boot/cmdline.txt to stop blicking of cursor on framebuffer
* dnsmasq & hostapd - to provide initial interface via wifi to enter the WiFi SSID and password
* unzip & tar - to support updates

## Install & run

1. Create settings.yaml in the working directory:
   ```
   ---
   telegram:
      api_token: "<PLACE TOKEN HERE>" # Telegram API key you got from Telegram's BotFather
   users: # Users can interact with the bot
     - <TELEGRAM_USERNAME>
   admins: # Admin users who can update the bot
     - <TELEGRAM_USERNAME>
   slideshow:
     directories:
       - /home/pi/Album
   ```
2. Run the bot: `./teleglobe.sh`

## Configure usb audio

Here we will configure the CM108 small usb audio device: https://learn.adafruit.com/usb-audio-cards-with-a-raspberry-pi/cm108-type

1. Make sure the system is up to date:
   ```
   $ sudo apt update
   $ sudo apt full-upgrade
   $ sudo reboot
   ```
2. Change lines in `/usr/share/alsa/alsa.conf` :
   ```
   -defaults.ctl.card 0
   -defaults.pcm.card 0
   +defaults.ctl.card 1
   +defaults.pcm.card 1
   ```
3. Make sure the volume is set to maximum:
   ```
   $ amixer sset PCM,0 100%,100% unmute cap
   ```
4. Test audio output with speaker-test:
   ```
   $ speaker-test -c 2
   ```

## Setup syncthing

1. `sudo curl -s -o /usr/share/keyrings/syncthing-archive-keyring.gpg https://syncthing.net/release-key.gpg`
2. `echo "deb [signed-by=/usr/share/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list`
3. `sudo apt update`
4. `sudo apt install syncthing`
5. `sudo systemctl enable syncthing@pi.service`
6. `sudo systemctl start syncthing@pi.service`
7. `vi .config/syncthing/config.xml` - change IP address from 127.0.0.1 to 0.0.0.0 to listen on all interfaces
8. `sudo systemctl restart syncthing@pi.service`
9. Go to IP:8384 and set admin+password and enable https
10. Now connect the required folders as "receive only"

## Setup MZDPI vga screen

1. Download MZDPI repo: `wget https://github.com/tianyoujian/MZDPI/archive/refs/heads/master.zip`
2. Rename: `mv master.zip MZDPI.zip`
3. Unpack: `unzip MZDPI.zip`
4. Change dir: `cd MZDPI-master/vga`
5. Install driver: `sudo ./mzdpi-vga-autoinstall-online`
6. Change screen rotation: `sudo vi /boot/config.txt` replace to `display_rotate=1`