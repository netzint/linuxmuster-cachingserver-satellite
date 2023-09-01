#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import logging
import json
import os
import subprocess

from subprocess import PIPE, CompletedProcess
from modules.filesyncer import FileSyncer

class ClientHelper:

    def __init__(self, socket, address, secret, server=None) -> None:
        self.socket = socket
        self.address = address
        self.secret = secret
        self.server = server

        actionfile = "/var/lib/linuxmuster-cachingserver/actions.json"
        actionoveridefile = "/var/lib/linuxmuster-cachingserver/actions.overide.json"

        with open(actionfile, "r") as f:
            self.actions = json.load(f)

        if os.path.exists(actionoveridefile):
            with open(actionoveridefile, "r") as f:
                self.actions = json.load(f)
    
    def __execute(self, command) -> CompletedProcess:
        return subprocess.run(command, stdout=PIPE, stderr=PIPE)

    def send(self, message) -> None:
        logging.debug(f"[{self.socket.getpeername()[0]}] Sending message '{message}'")
        self.socket.send(message.encode())
    
    def receive(self) -> str:
        message = self.socket.recv(1024).decode()
        logging.debug(f"[{self.socket.getpeername()[0]}] Receiving message '{message}'")
        return message
    
    def receiveAuth(self) -> bool:
        message = self.receive()
        message = message.split(" ")
        if message[0] == "auth" and message[1] == self.secret:
            logging.info(f"[{self.socket.getpeername()[0]}] Authentification for client was successful!")
            self.send("auth successful")
            return True
        logging.info(f"[{self.socket.getpeername()[0]}] Authentification for client failed!")
        self.send("auth failed")
        return False
    
    def sendAuth(self) -> bool:
        self.send(f"auth {self.secret}")
        message = self.receive()
        if message == "auth successful":
            logging.info(f"[{self.socket.getpeername()[0]}] Authentification for client was successful!")
            return True
        logging.info(f"[{self.socket.getpeername()[0]}] Authentification for client failed!")
        return False
    
    def close(self) -> None:
        logging.info(f"[{self.socket.getpeername()[0]}] Connection with client closed!")
        self.socket.close()

    def handle(self) -> None:
        ## Say hello
        self.send("hello")

        ## Authentification
        if not self.receiveAuth():
            return

        ## Get action from client
        message = self.receive()
        message = message.split(" ")

        ## handle sync
        if message[0] == "sync":
            action = message[1]
            logging.info(f"[{self.socket.getpeername()[0]}] Sync command received. Now syncing {action}")
            if action not in self.actions:
                self.send("invalid")
                return
            
            ## check if action is images and filter required images
            if action == "images":
                pattern = ""
                for image in self.server["images"]:
                    pattern += "/srv/linbo/images/" + image.split(".")[0] + "/*;"
                if pattern != "":
                    pattern = pattern[:-1]
            else:
                pattern = self.actions[action]["pattern"]
            syncer = FileSyncer(self, pattern)
            syncer.sync()

            ## handle posthook
            message = self.receive()
            if message == "posthook?":
                if "posthook" in self.actions[action]:
                    self.send(self.actions[action]["posthook"])
                else:
                    self.send("no")

                message = self.receive()
                if message != "done":
                    return
        
        ## handle download
        elif message[0] == "download":
            logging.info(f"[{self.socket.getpeername()[0]}] Download command received. Try to download {message[1]}")
            syncer = FileSyncer(self, message[1])
            syncer.send()

            message = self.receive()
            if message != "ok":
                return

        ## handle receive
        elif message[0] == "upload":
            logging.info(f"[{self.socket.getpeername()[0]}] Receive command upload. Starting receiving files...")
            syncer = FileSyncer(self)
            syncer.receive()

            message = self.receive()
            if message != "ok":
                return
            
        ## say goodbye
        logging.info(f"[{self.socket.getpeername()[0]}] Sync with client finished. Closing connection!")
        self.send("bye")
        self.close()

    #
    # Sync files from server to client
    # Client ask for files an server send them to him
    #
    def sync(self, item) -> None:
        ## Receive hello
        message = self.receive()
        if message != "hello":
            return

        ## Authentification
        if not self.sendAuth():
            return
        
        ## send command an item to sync
        logging.info(f"[{self.socket.getpeername()[0]}] Sending sync command to server. Try to sync {item}")
        self.send(f"sync {item}")

        ## receive file
        syncer = FileSyncer(self)
        syncer.receive()

        ## handle posthook
        self.send("posthook?")
        message = self.receive()
        if message != "no":
            logging.info(f"[{self.socket.getpeername()[0]}] Try to run posthook '{message}'")
            result = self.__execute(message.split(" "))
            logging.info(f"[{self.socket.getpeername()[0]}] Posthook finished. Result: {result}")
        self.send("done")

        ## receive goodbye and close client
        if self.receive() == "bye":
            logging.info(f"[{self.socket.getpeername()[0]}] Server said bye. Close connection!")
            self.close()

    #
    # Download files from server
    # Same as sync but you can set the file / path to download
    # Your can use semicolon in pattern to download multiple files / paths
    #
    def download(self, pattern):
        ## Receive hello
        message = self.receive()
        if message != "hello":
            return

        ## Authentification
        if not self.sendAuth():
            return
        
        ## send command an item to sync
        logging.info(f"[{self.socket.getpeername()[0]}] Sending download command to server. Try to download {pattern}")
        self.send(f"download {pattern}")

        ## receive file
        syncer = FileSyncer(self)
        syncer.receive()
        self.send("ok")

        ## receive goodbye and close client
        if self.receive() == "bye":
            logging.info(f"[{self.socket.getpeername()[0]}] Server said bye. Close connection!")
            self.close()
    
    #
    # Upload file to server
    # Server is going in receiving mode and receive all files sending from client
    # Your can use semicolon in pattern to download multiple files / paths
    #
    def upload(self, pattern):
        ## Receive hello
        message = self.receive()
        if message != "hello":
            return

        ## Authentification
        if not self.sendAuth():
            return
        
        ## send command an item to sync
        logging.info(f"[{self.socket.getpeername()[0]}] Sending upload command to server. Try to upload {pattern}")
        self.send(f"upload {pattern}")

        ## receive file
        syncer = FileSyncer(self, pattern)
        syncer.send()
        self.send("ok")

        ## receive goodbye and close client
        if self.receive() == "bye":
            logging.info(f"[{self.socket.getpeername()[0]}] Server said bye. Close connection!")
            self.close()