#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2023
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import json
import subprocess
import logging
import uvicorn

from fastapi import FastAPI
from modules.sockethelper import SocketHepler

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/api.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

with open("/var/lib/linuxmuster-cachingserver/server.json") as f:
    config = json.load(f)

app = FastAPI()

@app.get("/status")
def get_status_of_cachingserver():
    return { "status": True, "data": None }

@app.get("/files/hashes/get")
def get_filehashes_from_cachingserver():
    with open("/var/lib/linuxmuster-cachingserver/cached_filehashes.json") as f:
        return { "status": True, "data": json.load(f) }
    
@app.get("/files/hashes/regenerate")
def regenerate_filehashes_on_cachingserver():
    subprocess.Popen(["/usr/lib/linuxmuster-cachingserver/cacheFileHashes.py"])
    return { "status": True, "data": None }

@app.get("/files/sync/{item}")
def sync_files_from_server_to_cachingserver(item):
    try:
        client = SocketHepler(config["server_ip"], config["server_port"]).connect(config["secret"])
        client.sync(item)
        return { "status": True, "data": None }
    except Exception as e:
        return { "status": False, "data": str(e) }

def main():
    uvicorn.run(app, host="0.0.0.0", port=4457)

if __name__ == "__main__":
    main()