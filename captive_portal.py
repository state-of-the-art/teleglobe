#!/usr/bin/env python3

import sys, os
import logging
import socket
import subprocess
import time
import tempfile

logger = logging.getLogger(__name__)

def checkTCPConnection(address: str, port: int, retry:int = 3) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for ret in range(0, retry):
        try:
            if sock.connect_ex((address, port)) == 0:
                logger.info('Check TCP connection to %s:%d OK', address, port)
                return True
            else:
                logger.warning('Check TCP connection to %s:%d FAIL (retry %d from %d)', address, port, ret, retry)
        except Exception as e:
            logger.warning('Check TCP connection to %s:%d FAIL (retry %d from %d): %s', address, port, ret, retry, e)

    return False

def _exec(cmd: list) -> subprocess.Popen:
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _exec_wait(cmd: list) -> (str, bool):
    ret = _exec(cmd)
    (stdout, stderr) = ret.communicate()
    if ret.wait() != 0:
        logger.error('Failed to execute command')
        logger.error('STDOUT: %s\n\nSTDERR: %s', stdout, stderr)
        return False
    return stdout

def wpaNetworksChange(action: bool = True) -> None:
    out = _exec_wait(['wpa_cli', '-i', 'wlan0', 'list_network'])
    if out == False:
        raise Exception('Unable to get networks list')
    for line in out.splitlines()[1:]:
        data = line.split()
        if len(data) == 4 and ((b'DISABLED' if action else b'CURRENT') in data[3]):
            if _exec_wait(['wpa_cli', '-i', 'wlan0', ('enable_network' if action else 'disable_network'), data[0]]) == False:
                raise Exception('Unable to %s network %s' % (data, ('enable' if action else 'disable')))

def runCaptivePortal() -> None:
    dnsmasq = None
    hostapd = None
    captive = None

    try:
        wpaNetworksChange(False)

        if _exec_wait(['sudo', 'ip', 'link', 'set', 'dev', 'wlan0', 'down']) == False:
            raise Exception('Unable to shutdown the wlan0 interface')

        if _exec_wait(['sudo', 'ip', 'addr', 'flush', 'dev', 'wlan0']) == False:
            raise Exception('Unable to flush IP address for the interface')

        if _exec_wait(['sudo', 'ip', 'addr', 'add', '192.168.0.1/24', 'dev', 'wlan0']) == False:
            raise Exception('Unable to set required IP address for the interface')

        # Stop dnsmasq service
        _exec_wait(['sudo', 'systemctl', 'stop', 'dnsmasq'])

        # Run dsmasq
        dnsmasq = _exec(['sudo', 'dnsmasq', '--no-daemon', '--interface', 'wlan0', '--listen-address', '192.168.0.1', '--no-hosts', '--bind-interfaces', '--domain-needed', '--bogus-priv', '--dhcp-leasefile=/run/dnsmasq/dnsmasq.leases', '--dhcp-range', '192.168.0.50,192.168.0.150,12h', '--dhcp-option', '114,http://setup.teleglobe/', '--dhcp-option', 'option:router,192.168.0.1', '--dhcp-authoritative', '--address', '/#/192.168.0.1'])

        # Run simple http server
        captive = _exec(['sudo', sys.executable, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'captive_portal_webapp.py')])

        # Create hostapd config
        tf = tempfile.NamedTemporaryFile(suffix="hostapd.conf")
        tf.write("\n".join([
            'country_code=US',
            'interface=wlan0',
            'driver=nl80211',
            'ssid=teleglobe',
            'hw_mode=g',
            'channel=6',
            'ieee80211n=1',
            'wmm_enabled=1',
            'ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]',
            'macaddr_acl=0',
            'auth_algs=1',
            'ignore_broadcast_ssid=0',
            'wpa=0', # 2
            # Require no password - dangerous, need some additional sniffing protection
            #'wpa_key_mgmt=WPA-PSK',
            #'wpa_passphrase=teleglobe',
            'rsn_pairwise=CCMP',
        ]).encode())
        tf.flush()

        # Run hostapd
        hostapd = _exec(['sudo', 'hostapd', tf.name])

        while True:
            if hostapd.poll() != None:
                logger.error('hostapd exited: STDOUT:%s \n\nSTDERR:%s', *hostapd.communicate())
                hostapd = None
            if dnsmasq.poll() != None:
                logger.error('dnsmasq exited: STDOUT:%s \n\nSTDERR:%s', dnsmasq.communicate())
                dnsmasq = None
            if captive.poll() != None:
                logger.error('captive_portal exited: STDOUT:%s \n\nSTDERR:%s', captive.communicate())
                captive = None
            if hostapd == None and dnsmasq == None and captive == None:
                raise Exception('All the apps stopped')
            time.sleep(1)
    except (Exception, KeyboardInterrupt) as e:
        logger.error('ERROR: %s', e)
    finally:
        #if captive and captive.poll() == None:
        #    print(_exec(['sudo', 'kill', '-9', str(captive.pid)]).communicate())
        #    print('captive interrupted: STDOUT:%s \n\nSTDERR:%s' % captive.communicate())

        #if hostapd and hostapd.poll() == None:
        #    print(_exec(['sudo', 'kill', '-9', str(hostapd.pid)]).communicate())
        #    print('hostapd interrupted: STDOUT:%s \n\nSTDERR:%s' % hostapd.communicate())

        #if dnsmasq and dnsmasq.poll() == None:
        #    print(_exec(['sudo', 'kill', '-9', str(dnsmasq.pid)]).communicate())
        #    print('dnsmasq interrupted: STDOUT:%s \n\nSTDERR:%s' % dnsmasq.communicate())

        #_exec_wait(['sudo', 'systemctl', 'start', 'dnsmasq'])

        #if _exec_wait(['sudo', 'ip', 'link', 'set', 'dev', 'wlan0', 'down']) == False:
        #    raise Exception('Unable to shutdown the wlan0 interface')

        #wpaNetworksChange(True)

        #if _exec_wait(['sudo', 'ip', 'link', 'set', 'dev', 'wlan0', 'up']) == False:
        #    raise Exception('Unable to startup the wlan0 interface')

        logger.warning("REBOOT in 30s")
        time.sleep(30)
        logger.warning("REBOOT NOW")
        # _exec_wait(["sudo", "reboot"])

