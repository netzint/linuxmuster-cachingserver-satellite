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

class HashHelper:

    def __init__(self, filename) -> None:
        self.filename = filename

    def getMD5(self):
        def printStatus():
            while True:
                time.sleep(5)
                logging.info(f"[{os.path.basename(self.filename)}] Generating MD5-Hash ({counter} / {filesize}) => {percent}%")
                if counter >= filesize:
                    break

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
        return md5_hash.hexdigest()