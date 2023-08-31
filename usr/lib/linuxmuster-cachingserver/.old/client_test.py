#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import logging

from modules.sockethelper import SocketHepler

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/client_test.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

def main():
    socket = SocketHepler("localhost", 4455)
    client = socket.connect("12345")
    client.upload("/root/test.txt")

if __name__ == "__main__":
    try:
        main()
    except ConnectionResetError:
        logging.error(f"Connection to server failed! Please check logfiles on server!")
    except ConnectionRefusedError:
        logging.error(f"Connection to server failed! Please check if server is reachable!")