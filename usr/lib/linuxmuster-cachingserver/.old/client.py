#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import socket
import logging
import json
import os
import argparse
import subprocess
import time
import threading
import hashlib

from datetime import timedelta
from subprocess import PIPE

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/client.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

event = threading.Event()

def sendMessage(conn, msg):
    logging.debug(f"Send message '{msg}'")
    conn.send(msg.encode("utf-8"))

def receiveMessage(conn):
    message = conn.recv(1024).decode()
    if len(message) > 40:
        logging.debug("Receive message '" + message[:40].replace('\n', '') + "...'")
    else:
        logging.debug(f"Receive message '{message}'")
    return message

def getRegisteredServers():
    file = open("/var/lib/linuxmuster-cachingserver/servers.json", "r")
    json_result = json.load(file)
    file.close()
    return json_result

def __execute(command):
    return subprocess.run(command, stdout=PIPE, stderr=PIPE)

def connect(ip, port):
    logging.info(f"Starting new connection to {ip} on port {port}...")
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip, port))
        logging.info("Connection successful!")
        return client
    except Exception as e:
        logging.error(f"Connection to {ip} on port {port} not possible! Message: " + str(e))
        return False

def authenticate(client, key):
    sendMessage(client, "auth %s" % key)
    result = receiveMessage(client).split(" ", 1)

    if result[0] != "hello":
        logging.error(f"Authentification failed! Connection to {client.getpeername()[0]} is not possible!")
        return False

    logging.info("Authentification successful!")
    return True

def getMD5Hash(filename):
    md5_hash = hashlib.md5()
    with open(filename,"rb") as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def printFileTransferStatus(filename, filesize):
    lastFilesize = 0
    while True:
        time.sleep(5)
        currentFilesize = os.stat(filename).st_size
        percent = round((currentFilesize / filesize) * 100, 2)
        speed = (currentFilesize - lastFilesize) / 5
        remaining = round((filesize - currentFilesize) / speed, 0)
        if currentFilesize == filesize:
            break
        if event.is_set():
            break
        logging.info(f"Transfered {percent}% of '{os.path.basename(filename)}' ETA {str(timedelta(seconds=remaining))} / {round(speed / 1000 / 1000, 2)} MB/s ({currentFilesize}/{filesize})")
        lastFilesize = currentFilesize

def downloadFile(client):
    data = receiveMessage(client) # get filename and size and md5sumn
    data = data.split(" ")
    if data[0] != "send":
        logging.error("No valid answer!")
        return
    filename = data[1]
    filesize = int(data[2])
    originalMD5hash = data[3]
    counter = 0
    errorcounter = 0
    logging.info(f"Receive new file '{filename}'...")
    if not os.path.exists(os.path.split(filename)[0]):
        logging.info(f"Path '{os.path.split(filename)[0]}' does not exist. Create it...")
        os.makedirs(os.path.split(filename)[0], exist_ok=True)
    if os.path.exists(filename):
        logging.info(f"File {os.path.basename(filename)} exist. Comparing MD5-Hash...")
        currentMD5hash = getMD5Hash(filename)
        if currentMD5hash == originalMD5hash:
            logging.info(f"File {os.path.basename(filename)} does not change. Skip...")
            sendMessage(client, "skip")
            return
        else:
            logging.info(f"File {os.path.basename(filename)} is old. Download new file...")
    sendMessage(client, "ok")
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
                event.set()
                statusThread.join()
                break
            
    f.close()
    logging.info(f"File '{filename}' received. Checking file...")
    sendMessage(client, "ok")
    data = receiveMessage(client).split(" ") # get check command
    if data[0] != "check":
        logging.error("No valid answer!")
        return
    sendMessage(client, getMD5Hash(filename))
    check = receiveMessage(client)
    if check == "restart":
        logging.info(f"File '{filename}' is invalid. Download will be retried...")
        downloadFile(client)
    if check != "success":
        logging.error("No valid answer!")
        return
    logging.info(f"File '{filename}' is valid!")
    sendMessage(client, "ok")

    sendMessage(client, "posthook?")
    posthook = receiveMessage(client)
    if posthook != "no":
        logging.info(f"Running posthook: {posthook}")
        hookResult = __execute(posthook.split(" "))
        logging.info(f"Result: {hookResult}")
    else:
        logging.info("No posthook defined!")
    sendMessage(client, "done")       

    if receiveMessage(client) != "bye":
        logging.error("Server does not say bye... Now i'm sad....")
    else:
        logging.info(f"Server said bye. Terminate connection...")

    client.close()

def api(server, command):
    logging.info("--> Starting access over api")
    serversFile = getRegisteredServers()
    result = None
    if server in serversFile:
        server = serversFile[server]
        logging.info("Server found! Connecting...")
        client = connect(server["ip"], 4456)
        if client:
            if authenticate(client, server["secret"]):
                sendMessage(client, command)
                result = receiveMessage(client)
                if result == "file":
                    sendMessage(client, "ok")
                logging.info("--> Finish access over api successful!")
                client.close()
                return result

    logging.info("--> Finish access over api with error")
    return False
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--name", required=True, help="Name of satellite to send sync command(s)")
    parser.add_argument("--item", required=True, help="Item to sync")

    args = parser.parse_args()

    serversFile = getRegisteredServers()
    if args.name in serversFile:
        server = serversFile[args.name]
        logging.info("Server found! Connecting...")
        client = connect(server["ip"], 4456)
        authenticate(client, server["secret"])

        sendMessage(client, f"sync {args.item}")
        result = receiveMessage(client)
        logging.info(f"Receive result: {result}")

        logging.info("Finished!")
        client.close()
    

if __name__ == "__main__":
    main()

