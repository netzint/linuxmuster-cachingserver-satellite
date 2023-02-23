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

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver-satellite.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

def error(msg):
    logging.error(msg)
    exit(1)

def sendMessage(conn, msg):
    conn.send(msg.encode("utf-8"))

def receiveMessage(conn):
    message = conn.recv(1024).decode()
    if len(message) > 40:
        logging.debug("Receive message '" + message[:40].replace('\n', '') + "...'")
    else:
        logging.debug(f"Receive message '{message}'")
    return message

def getConfig():
    return json.load(open("/etc/linuxmuster-cachingserver/config.json", "r"))

def connect(ip, port):
    logging.info(f"Starting new connection to {ip} on port {port}...")
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip, port))
        logging.info("Connection successful!")
        return client
    except Exception as e:
        error(f"Connection to {ip} on port {port} not possible! Message: " + str(e))

def authenticate(client, config):
    sendMessage(client, "auth %s" % config["key"])
    result = receiveMessage(client).split(" ", 1)

    if result[0] != "hello":
        error(f"Authentification failed! Connection to {client.getpeername()[0]} is not possible!")

    logging.info("Authentification successful!")
    
def get(client, actions):
    sendMessage(client, "get " + actions)
    if receiveMessage(client) != "ok":
        error("Server said action is invalid!")
    sendMessage(client, "start")
    invalidtaskcount = 0
    while True:
        task = receiveMessage(client)
        logging.debug(f"Receive task {task}")
        if task == "end":
            break
        elif task == "file":
            invalidtaskcount = 0
            sendMessage(client, "ok")
            headers = receiveMessage(client)
            filename = headers.split(";")[0]
            size = int(headers.split(";")[1])
            logging.info(f"Receive file {filename}")
            sendMessage(client, "ok")
            data = ""
            for i in range(0, (int(size / 1024) + 1)):
                data += receiveMessage(client)
            sendMessage(client, "ok")
            path = "/".join(filename.split('/')[0:-1])
            if not os.path.exists(path):
                os.makedirs(path)
            with open(filename, "w") as file:
                file.write(data)
            logging.info(f"File {filename} received successfully!")
        else:
            invalidtaskcount += 1
        
        if(invalidtaskcount > 10):
            error("To many invalid messages. Maybe server is not responding anymore...?")


def main():
    config = getConfig()
    server = config["server_name"] + "." + config["server_domain"]
    port = config["server_port"]
    client = connect(server, port)
    authenticate(client, config)

    parser = argparse.ArgumentParser()
    parser.add_argument("--items", nargs="+", required=True, help="List items to sync")

    args = parser.parse_args()
    for item in args.items:
        get(client, item)

    logging.info("Finished!")
    client.close()
    

if __name__ == "__main__":
    main()

