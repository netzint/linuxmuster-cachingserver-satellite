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
import threading

from fastapi import FastAPI, BackgroundTasks
from modules.RSyncHelper import RSyncHelper

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/api.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

with open("/var/lib/linuxmuster-cachingserver/server.json") as f:
    config = json.load(f)

app = FastAPI()

@app.get("/status")
def get_status_of_cachingserver():
    return { "status": True, "data": "Cachingserver is reachable!" }

#########################################
# FILES
#########################################

@app.get("/files/hashes/get")
def get_filehashes_from_cachingserver():
    with open("/var/lib/linuxmuster-cachingserver/cached_filehashes.json") as f:
        return { "status": True, "data": json.load(f) }
    
@app.get("/files/hashes/regenerate")
def regenerate_filehashes_on_cachingserver(background_tasks: BackgroundTasks):
    def initCache():
        subprocess.Popen(["/usr/lib/linuxmuster-cachingserver/cacheFileHashes.py"])
    background_tasks.add_task(initCache)
    return { "status": True, "data": "Successful initiated!" }

@app.get("/files/sync/{item}")
def sync_files_from_server_to_cachingserver(item, background_tasks: BackgroundTasks):
    def initSync():
        
    background_tasks.add_task(initSync)
    return { "status": True, "data": "Successful initiated!" }

#########################################
# SERVICES
#########################################

@app.get("/services/status/{service}")
def get_status_of_service(service):
    stat = subprocess.call(["systemctl", "is-active", "--quiet", service])
    if(stat == 0):
        return { "status": True, "data": "Service is active" }
    return { "status": False, "data": "Service is unknown or inactive" }

@app.get("/services/start/{service}")
def start_given_service(service, background_tasks: BackgroundTasks):
    def start():
        subprocess.Popen(["/usr/bin/systemctl", "start", service])
    background_tasks.add_task(start)
    return { "status": True, "data": "Initiate start successfully!" }

@app.get("/services/stop/{service}")
def stop_given_service(service, background_tasks: BackgroundTasks):
    def stop():
        subprocess.Popen(["/usr/bin/systemctl", "stop", service])
    background_tasks.add_task(stop)
    return { "status": True, "data": "Initiate stop successfully!" }

@app.get("/services/restart/{service}")
def restart_given_service(service, background_tasks: BackgroundTasks):
    def restart():
        subprocess.Popen(["/usr/bin/systemctl", "sretart", service])
    background_tasks.add_task(restart)
    return { "status": True, "data": "Initiate restart successfully!" }

def main():
    uvicorn.run(app, host="0.0.0.0", port=4457)

if __name__ == "__main__":
    main()
