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

from modules.clienthelper import ClientHelper

class SocketHepler:

    def __init__(self, host, port) -> None:
        self.host = host
        self.port = port
        self.authfile = None

    def start(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
        logging.info(f"Server is running on {self.host}:{self.port}")
        self.socket.listen()

    def setAuthfile(self, authfile) -> None:
        self.authfile = authfile

    def checkAndGetServer(self, address) -> str:
        servers = json.load(open(self.authfile, "r"))
        for server in servers:
            if address == servers[server]["ip"]:
                return servers[server]
        return None

    def waitForClient(self) -> None:
        while True:
            client_socket, client_address = self.socket.accept()
            logging.info(f"New connection from {client_address[0]}:{client_address[1]}")
            server = self.checkAndGetServer(client_address[0])
            if server:
                client = ClientHelper(client_socket, client_address, server["secret"], server)
                logging.info(f"[{client_address[0]}] Client registered. Starting new thread!")
                client_handler = threading.Thread(target=client.handle(), daemon=True)
                client_handler.start()
            else:
                logging.info(f"[{client_address[0]}] Client not registered at this server! Terminate connection!")
                client_socket.close()

    def connect(self, secret) -> ClientHelper:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        return ClientHelper(client_socket, (self.host, self.port), secret)