#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import socket
import logging
import hashlib
import os
import threading
import time
import json

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/client.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

def getSatelliteConfig():
    return json.load(open("/var/lib/linuxmuster-cachingserver/server.json", "r"))

def getMD5Hash(filename):
    md5_hash = hashlib.md5()
    with open(filename,"rb") as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def send(client, message):
    client.send(message.encode())

def receive(client):
    return client.recv(1024).decode()

def printFileTransferStatus(filename, filesize):
    while True:
        time.sleep(5)
        currentFilesize = os.stat(filename).st_size
        percent = round((currentFilesize / filesize) * 100, 2)
        if currentFilesize == filesize:
            break
        logging.info(f"Transfered {percent}% of '{filename}' ({currentFilesize}/{filesize})")

def main():
    config = getSatelliteConfig()
    host = config["server_name"] + "." + config["server_domain"]
    port = config["server_port"]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))

    send(client, "auth " + config["key"])
    if receive(client) != "ok":
        logging.error("No valid answer!")

    send(client, "get images")
    finished = False
    while not finished:
        data = receive(client).split(" ") # get filename and size
        if data[0] == "finished":
            finished = True
            logging.info(f"All files transfered!")
            send(client, "ok")
            break
        if data[0] != "send":
            logging.error("No valid answer!")
            break
        filename = data[1]
        filesize = int(data[2])
        counter = 0
        errorcounter = 0
        logging.info(f"Receive new file '{filename}'...")
        send(client, "ok")
        if not os.path.exists(os.path.split(filename)[0]):
            logging.info(f"Path '{os.path.split(filename)[0]}' does not exist. Create it...")
            os.makedirs(os.path.split(filename)[0], exist_ok=True)
        f = open(filename, "wb")
        if filesize == 0:
            f.write(b"")
        else:
            statusThread = threading.Thread(target=printFileTransferStatus, args=(filename, filesize))
            statusThread.daemon = True
            statusThread.start()
            while True:
                data = client.recv(1024)
                f.write(data)
                counter += len(data)
                if len(data) == 0:
                    errorcounter += 1
                if counter == filesize:
                    break
                if errorcounter > 10:
                    logging.error(f"Error while receiving file {filename}")
                    break
                
        f.close()
        logging.info(f"File '{filename}' received. Checking file...")
        send(client, "ok")
        data = receive(client).split(" ") # get check command
        if data[0] != "check":
            logging.error("No valid answer!")
            break
        send(client, getMD5Hash(filename))
        check = receive(client)
        if check == "restart":
            logging.info(f"File '{filename}' is invalid. Download will be retried...")
            continue
        if check != "success":
            logging.error("No valid answer!")
            break
        logging.info(f"File '{filename}' is valid!")
        send(client, "ok")

    if receive(client) != "bye":
        logging.error("Server does not say bye... Now i'm sad....")
    else:
        logging.info(f"Server said bye. Terminate connection...")

    client.close()

    

if __name__ == "__main__":
    logging.info("======= STARTED =======")
    try:
        main()
    finally:
        logging.info("======= FINISHED =======")
        