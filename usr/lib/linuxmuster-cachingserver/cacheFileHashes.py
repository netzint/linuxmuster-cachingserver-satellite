#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import json
import os
import glob
import logging
import sys

from modules.hashhelper import HashHelper

logging.basicConfig(stream=sys.stdout, format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

def getServerActions():
    return json.load(open("/var/lib/linuxmuster-cachingserver/actions.json", "r"))

def main():
    logging.info("Start creating cachefile for filehashes!")
    result = {}
    actions = getServerActions()
    for action in actions:
        pattern = actions[action]["pattern"]
        if ";" in pattern:
            pattern = pattern.split(";")
        else:
            pattern = [ pattern ]
        
        for p in pattern:
            for filename in glob.glob(p, recursive=True):
                if os.path.isfile(filename):
                    logging.info(f"Generating entry for '{filename}'...")
                    result[filename] = {
                        "filename": filename.split("/")[len(filename.split("/")) - 1],
                        "hash": HashHelper(filename).getMD5(),
                        "action": action
                    }

    logging.info("Hashes generated successfully. Writing to file...")

    with open("/var/lib/linuxmuster-cachingserver/cached_filehashes.json", "w") as f:
        json.dump(result, f)

    logging.info("File written successfully. Finished!")

if __name__ == "__main__":
    main()