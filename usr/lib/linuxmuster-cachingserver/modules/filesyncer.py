#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import glob
import os
import logging
import time
import threading

from modules.hashhelper import HashHelper
from datetime import timedelta

class FileSyncer:

    def __init__(self, client, pattern=None) -> None:
        self.client = client
        if pattern:
            if ";" in pattern:
                self.pattern = pattern.split(";")
            else:
                self.pattern = [ pattern ]

    def sendFile(self, filename) -> None:
        def printStatus():
            while True:
                time.sleep(5)
                logging.info(f"Transfered {percent}% of '{os.path.basename(filename)}' ETA {str(timedelta(seconds=remaining))} / {round(speed / 1000 / 1000, 2)} MB/s ({currentFilesize}/{filesize})")
                if currentFilesize >= filesize:
                    break

        ## wait for ok to check if client is waiting for file
        message = self.client.receive()
        if message != "ok":
            return
        
        ## generate fileinfos and send it to client
        filesize = os.stat(filename).st_size
        filehash = HashHelper(filename).getMD5()
        logging.info(f"[{self.client.socket.getpeername()[0]}] Start sending file '{filename}' to client")
        self.client.send(f"{filename} {filesize} {filehash}")

        # waiting for answer from client -> skip or ok
        message = self.client.receive()
        if message == "skip":
            logging.info(f"[{self.client.socket.getpeername()[0]}] File on client is already the newest version. Skip file!")
            return
        if message != "ok":
            return
        
        # send file
        logging.info(f"[{self.client.socket.getpeername()[0]}] Sending file...")
        lastFilesize = 0
        if filesize > 61440:
            threading.Thread(target=printStatus).start()
        with open(filename, "rb") as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                self.client.socket.send(chunk)
                currentFilesize = os.stat(filename).st_size
                percent = round((currentFilesize / filesize) * 100, 2)
                speed = 1 if (currentFilesize - lastFilesize) == 0 else ((currentFilesize - lastFilesize) / 5)
                remaining = round((filesize - currentFilesize) / speed, 0)
                lastFilesize = currentFilesize

        # waiting for answer from client -> ok
        message = self.client.receive()
        if message != "ok":
            return
        logging.info(f"[{self.client.socket.getpeername()[0]}] File sended!")
        
        # send command to check file on client
        self.client.send("check")
        logging.info(f"[{self.client.socket.getpeername()[0]}] Checking file...")

        # waiting for answer from client -> restart / ok
        message = self.client.receive()
        if message == "restart":
            logging.info(f"[{self.client.socket.getpeername()[0]}] File on client is not valid. Try again!")
            self.sendFile(filename)
        if message != "ok":
            return
        logging.info(f"[{self.client.socket.getpeername()[0]}] File '{filename}' sended successfully!")


    def receiveFiles(self) -> None:
        def printStatus():
            while True:
                time.sleep(5)
                logging.info(f"Transfered {percent}% of '{os.path.basename(filename)}' ETA {str(timedelta(seconds=remaining))} / {round(speed / 1000 / 1000, 2)} MB/s ({currentFilesize}/{filesize})")
                if currentFilesize >= filesize:
                    break
        while True:
            ## check if receiving file or finished
            message = self.client.receive()
            if message == "finished":
                logging.info(f"[{self.client.socket.getpeername()[0]}] All files transfered!")
                break
            if message != "file":
                return
            logging.info(f"[{self.client.socket.getpeername()[0]}] Start receiving file...")
            self.client.send("ok")

            ## receive fileinfos from client
            message = self.client.receive()
            message = message.split(" ")
            filename = message[0]
            filesize = int(message[1])
            filehash = message[2]
            logging.info(f"[{self.client.socket.getpeername()[0]}] Start receiving file '{filename}'")

            ## compare original filehash with received filehash
            logging.info(f"[{self.client.socket.getpeername()[0]}] Generating Hash for '{filename}'")
            if filehash == HashHelper(filename).getMD5():
                logging.info(f"[{self.client.socket.getpeername()[0]}] File is already the newest version. Skip file!")
                self.client.send("skip")
                continue
            self.client.send("ok")

            ## check if filepath exist, if not create it
            if not os.path.exists(os.path.split(filename)[0]):
                logging.info(f"Path '{os.path.split(filename)[0]}' does not exist. Create it...")
                os.makedirs(os.path.split(filename)[0], exist_ok=True)

            ## receive file
            counter = 0
            errorcounter = 0
            logging.info(f"[{self.client.socket.getpeername()[0]}] Receiving file...")
            lastFilesize = 0
            if filesize > 61440:
                threading.Thread(target=printStatus).start()
            f = open(filename, "wb")
            if filesize == 0:
                f.write(b"")
            else:
                while True:
                    data = self.client.socket.recv(1024)
                    f.write(data)
                    counter += len(data)
                    if len(data) == 0:
                        errorcounter += 1
                    if counter == filesize:
                        break
                    if errorcounter > 10:
                        break
                    currentFilesize = os.stat(filename).st_size
                    percent = round((currentFilesize / filesize) * 100, 2)
                    speed = 1 if lastFilesize == 0 else (currentFilesize - lastFilesize) / 5
                    remaining = round((filesize - currentFilesize) / speed, 0)
                    lastFilesize = currentFilesize
            f.close()
            self.client.send("ok")
            logging.info(f"[{self.client.socket.getpeername()[0]}] File received!")

            ## check if file transfered successful
            logging.info(f"[{self.client.socket.getpeername()[0]}] Checking file...")
            if self.client.receive() != "check":
                return
            
            if filehash != HashHelper(filename).getMD5():
                logging.info(f"[{self.client.socket.getpeername()[0]}] File on client is not valid. Try again!")
                self.client.send("restart")
                self.receiveFiles()

            logging.info(f"[{self.client.socket.getpeername()[0]}] File sended successfully!")
            self.client.send("ok")

    def sync(self) -> None:
        for p in self.pattern:
            for filename in glob.glob(p, recursive=True):
                if os.path.isfile(filename):
                    self.client.send("file")
                    self.sendFile(filename)

        self.client.send("finished")

    def send(self) -> None:
        self.sync()

    def receive(self) -> None:
        self.receiveFiles()