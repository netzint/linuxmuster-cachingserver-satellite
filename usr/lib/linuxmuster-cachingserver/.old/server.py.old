#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import socket
import logging
import threading
import json
import hashlib
import os
import glob
import time

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/server.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

def getMD5Hash(filename):
    md5_hash = hashlib.md5()
    with open(filename,"rb") as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def handle_client(client, client_address):

    def send(message):
        logging.info(f"[{client.getpeername()[0]}] Sending message '{message}'")
        client.send(message.encode())
    
    def receive():
        return client.recv(1024).decode()

    def sendFile(filename):
        logging.info(f"[{client.getpeername()[0]}] Sending file '{filename}'")
        successful = False
        logging.info(f"[{client.getpeername()[0]}] Calculating MD5 sum for '{filename}'")
        md5hash = getMD5Hash(filename)
        filesize = os.stat(filename).st_size
        tryCounter = 0
        while not successful:
            if tryCounter > 5:
                return False
            send(f"send {filename} {filesize} {md5hash}")
            r = receive()
            if r == "skip":
                logging.info(f"[{client.getpeername()[0]}] File on target system is already the same!")
                successful = True
                return successful
            if r != "ok":
                return False
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    client.send(chunk)
            if receive() != "ok":
                return False
            send(f"check {filename}")
            if receive() != md5hash:
                logging.info(f"[{client.getpeername()[0]}] File '{filename}' not valid on target system... Try again!")
                tryCounter += 1
                send("restart")
            else:
                send("success")
            if receive() != "ok":
                return False
            successful = True
        return successful
    
    def sendFiles(pattern):
        for filename in glob.glob(pattern, recursive=True):
            if os.path.isfile(filename):
                logging.info(f"[{client.getpeername()[0]}] Found file {filename}!")
                if not sendFile(filename):
                    return False
        return True

    clientInfo = False

    while True:
        try:
            data = client.recv(1024)
            if not data:
                logging.info(f"[{client_address[0]}] Connection terminated!")
                break

            data = data.decode().split(" ")
            logging.info(f"[{client_address[0]}] Receive command '{data[0]}'")
            if data[0] == "ping":
                send("pong")
            elif data[0] == "auth":
                clientInfo = checkIfServerIsRegistered(client_address[0], data[1])
                if not clientInfo:
                    logging.info(f"[{client_address[0]}] Client not authorized!")
                    break
                logging.info(f"[{client_address[0]}] Client authorized successfully!")
                send("ok")
            elif data[0] == "get":
                if not clientInfo:
                    logging.info(f"[{client_address[0]}] Client not authorized!")
                    break
                if data[1] in getServerActions():
                    action = getServerActions()[data[1]]
                    logging.info(f"[{client_address[0]}] Client request files for '{data[1]}'")
                    if ";" in action["pattern"]:
                        for pattern in action["pattern"].split(";"):
                            pattern = pattern.replace("#school#", clientInfo["school"])
                            logging.info(f"[{client_address[0]}] Sending files for pattern '{pattern}'")
                            if not sendFiles(pattern):
                                logging.error(f"[{client_address[0]}] Error sending file '{pattern}'")
                                break
                    else:
                        pattern = action["pattern"].replace("#school#", clientInfo["school"])
                        if not sendFiles(pattern):
                            logging.error(f"[{client_address[0]}] Error sending file '{pattern}'")
                            break
                    send("finished")
                    if receive() != "posthook?":
                        return False
                    posthook = action["posthook"] if "posthook" in action else "no"
                    send(posthook)
                    if receive() != "done":
                        logging.error(f"[{client_address[0]}] Client said posthook failed!")
                    else:
                        logging.info(f"[{client_address[0]}] Client said posthook was successful!")
                    send("bye")
                else:
                    send("sorry")
                    logging.info(f"[{client_address[0]}] Client send invalid action!")
                    break

        except Exception as e:
            logging.error(f"Error: {e}")
            break
    
    logging.info(f"[{client_address[0]}] Connection closed!")
    client.close()

def checkIfServerIsRegistered(ip, secret):
    servers = json.load(open("/var/lib/linuxmuster-cachingserver/servers.json", "r"))
    for server in servers:
        if ip == servers[server]["ip"]:
            if servers[server]["secret"] == secret:
                return servers[server]
    return False

def getServerActions():
    return json.load(open("/var/lib/linuxmuster-cachingserver/actions.json", "r"))

def main():
    host = "0.0.0.0"
    port = 4455

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    logging.info(f"Server is running on {host}:{port}")

    while True:
        client_socket, client_address = server.accept()
        logging.info(f"New connection from {client_address[0]}:{client_address[1]}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_handler.start()

if __name__ == "__main__":
    logging.info("======= STARTED =======")
    try:
        main()
    except OSError:
        logging.error("Server address is already in use. Weit for 10 seconds...")
        time.sleep(10)
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        logging.info("======= STOPPED =======")