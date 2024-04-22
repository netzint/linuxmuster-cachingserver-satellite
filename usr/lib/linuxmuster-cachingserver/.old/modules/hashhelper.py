#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import hashlib
import logging
import os
import time
import threading
import json

class HashHelper:

    def __init__(self, filename, save=True) -> None:
        self.filename = filename
        self.save = save

    def __saveHash(self, hash) -> None:
        if not self.save:
            return
        
        with open("/var/lib/linuxmuster-cachingserver/cached_filehashes.json", "r") as f:
            cached_hashes = json.load(f)

        if self.filename in cached_hashes:
            cached_hashes[self.filename]["hash"] = hash
        else:
            cached_hashes[self.filename] = {
                "filename": self.filename.split("/")[len(self.filename.split("/")) - 1],
                "hash": hash,
                "action": "n/a"
            }
        
        with open("/var/lib/linuxmuster-cachingserver/cached_filehashes.json", "w") as f:
            json.dump(cached_hashes, f)

    def getMD5(self) -> str:
        def printStatus():
            while True:
                time.sleep(5)
                if counter >= filesize:
                    break
                logging.info(f"[{os.path.basename(self.filename)}] Generating MD5-Hash ({counter} / {filesize}) => {percent}%")
        
        if not os.path.exists(self.filename):
            return "0"

        md5_hash = hashlib.md5()
        filesize = os.stat(self.filename).st_size
        counter = 0
        if filesize > 61440:
            threading.Thread(target=printStatus).start()
        with open(self.filename,"rb") as f:
            for byte_block in iter(lambda: f.read(4096),b""):
                md5_hash.update(byte_block)
                counter += 4096
                percent = round((counter / filesize) * 100, 2)
        hash = md5_hash.hexdigest()
        self.__saveHash(hash)
        return hash