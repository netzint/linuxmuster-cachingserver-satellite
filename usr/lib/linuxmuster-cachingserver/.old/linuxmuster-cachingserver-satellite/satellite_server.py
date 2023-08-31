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
import threading
import hashlib
import os

import sys

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/server.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

sys.path.insert(0, '/usr/lib/linuxmuster-cachingserver-satellite/')
from satellite_client import api as cachingserver_api

def error(conn, addr, msg):
    logging.error(msg)
    conn.close()
    logging.error(f"Connection with {addr} terminated!")

def getMD5Hash(filename):
    md5_hash = hashlib.md5()
    with open(filename,"rb") as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def sendMessage(conn, msg):
    if len(msg) > 40:
        logging.debug(f"[{conn.getpeername()[0]}] Send message '" + msg[:40].replace('\n', '') + "...'")
    else:
        logging.debug(f"[{conn.getpeername()[0]}] Send message '{msg}'")
    conn.send(msg.encode("utf-8"))

def sendFile(conn, filename):
    logging.info(f"Sending file '{filename}'")
    successful = False
    logging.info(f"Calculating MD5 sum for '{filename}'")
    md5hash = getMD5Hash(filename)
    filesize = os.stat(filename).st_size
    tryCounter = 0
    while not successful:
        if tryCounter > 5:
            return False
        sendMessage(conn, f"send {filename} {filesize} {md5hash}")
        r = receiveMessage(conn)
        if r == "skip":
            logging.info(f"File on target system is already the same!")
            successful = True
            return successful
        if r != "ok":
            return False
        with open(filename, "rb") as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                conn.send(chunk)
        if receiveMessage(conn) != "ok":
            return False
        sendMessage(conn, f"check {filename}")
        if receiveMessage(conn) != md5hash:
            logging.info(f"File '{filename}' not valid on target system... Try again!")
            tryCounter += 1
            sendMessage(conn, "restart")
        else:
            sendMessage(conn, "success")
        if receiveMessage(conn) != "ok":
            return False
        successful = True
    return successful

def getSatelliteConfig():
    return json.load(open("/var/lib/linuxmuster-cachingserver/server.json", "r"))

def receiveMessage(conn):
    try:
        message = conn.recv(1024).decode()
    except:
        return None
    logging.debug(f"[{conn.getpeername()[0]}] Receive message '{message}'")
    return message

def main():
    host = "0.0.0.0"
    port = 4456
    logging.info(f"Starting Cachingserver-Satellite-Server on {host}:{port}")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()

    satelliteConfig = getSatelliteConfig()

    logging.info("Server started!")

    while True:
        conn, addr = server.accept()
        logging.debug(f"New connection from {addr}")

        message = receiveMessage(conn)
        if message == None:
            error(conn, addr, f"[{addr[0]}] Invalid message reveived!")
            continue

        message = message.split(" ", 1)
        if message[0] == "auth":
            if message[1] == satelliteConfig["key"]:
                logging.info(f"[{addr[0]}] Authenification successful!")
                sendMessage(conn, "hello")
            else:
                error(conn, addr, f"[{addr[0]}] Authenification failed! Reset connection!")
                continue
            
        message = receiveMessage(conn).split(" ", 1)
        if message == None:
            error(conn, addr, f"[{addr[0]}] Invalid message reveived!")
            continue

        if message[0] == "ping":
            sendMessage(conn, "pong")
        elif message[0] == "sync":
            threading.Thread(target=cachingserver_api, args=(message[1],)).start()
            sendMessage(conn, "done")
        elif message[0] == "file-status":
            sendMessage(conn, "file")
            if receiveMessage == "ok":
                sendFile(conn, "/var/lib/linuxmuster-cachingserver/cached_filehashes.json")

        conn.close()



if __name__ == "__main__":
    logging.info("======= STARTED =======")
    try:
        main()
    except UnicodeDecodeError:
        logging.info("======= INVALID CONNECTION - RESTARTED =======")
        main()
    except KeyboardInterrupt:
        logging.info("======= STOPPED (by user) =======")
        exit(0)
    except Exception as e:
        logging.info("======= STOPPED (by error) =======")
        logging.error(e)
        exit(1)