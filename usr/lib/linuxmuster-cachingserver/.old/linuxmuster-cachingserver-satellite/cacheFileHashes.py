#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import json
import hashlib
import os
import glob

def getMD5Hash(filename):
    md5_hash = hashlib.md5()
    with open(filename,"rb") as f:
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def getServerActions():
    return json.load(open("/var/lib/linuxmuster-cachingserver/actions.json", "r"))

def main():
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
                    result[filename] = {
                        "filename": filename.split("/")[len(filename.split("/")) - 1],
                        "hash": getMD5Hash(filename),
                        "action": action
                    }
    
    print(result)

    with open("/var/lib/linuxmuster-cachingserver/cached_filehashes.json", "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()