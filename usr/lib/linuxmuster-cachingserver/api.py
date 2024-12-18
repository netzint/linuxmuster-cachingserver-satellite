#!/usr/bin/env python3

#########################################################
# 
# by Netzint GmbH 2024
# Lukas Spitznagel (lukas.spitznagel@netzint.de)
# 
#########################################################

import json
import subprocess
import logging
import uvicorn

from fastapi import FastAPI, BackgroundTasks
from modules.RSyncHelper import RSyncHelper

logging.basicConfig(filename='/var/log/linuxmuster/cachingserver/api.log',format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

with open("/var/lib/linuxmuster-cachingserver/server.json") as f:
    config = json.load(f)

configuration_files = [
    {"share": "cachingserver-dhcp", "pattern": "subnets.conf", "destination": "/etc/dhcp/"},
    {"share": "cachingserver-dhcp", "pattern": "devices/*.conf", "destination": "/etc/dhcp/devices/"},
    {"share": "cachingserver-dhcp", "pattern": "devices.conf", "destination": "/etc/dhcp/"},
    {"share": "cachingserver-ssh", "pattern": "id_rsa*", "destination": "/root/.ssh/"},
    {"share": "cachingserver-linuxmuster", "pattern": "setup.ini", "destination": "/var/lib/linuxmuster/"},
    {"share": "cachingserver-linbo", "pattern": "start.conf.*", "destination": "/srv/linbo/"},
    {"share": "cachingserver-linbo", "pattern": "boot/grub/*.cfg", "destination": "/srv/linbo/boot/grub/"},
    {"share": "cachingserver-linbo", "pattern": "linbocmd/*", "destination": "/srv/linbo/linbocmd/"},
    {"share": "cachingserver-school", "pattern": "default-school/devices.csv", "destination": "/etc/linuxmuster/sophomorix/default-school/"},
    {"share": "cachingserver-school", "pattern": "*", "destination": "/etc/linuxmuster/sophomorix/", "include": "*.devices.csv", "exclude": "*"},
]

app = FastAPI()

@app.get("/v1/status")
def get_status_of_cachingserver():
    return { "status": True, "data": "Cachingserver is reachable!" }

#########################################
# CONFIGURATION
#########################################

@app.get("/v1/configuration/check")
def check_configuration_files_on_server():
    helper = RSyncHelper(config["name"], config["server_ip"])
    result = helper.check(configuration_files)
    return { "status": result, "data": "" }

@app.get("/v1/configuration/sync")
def sync_configuration_files_with_server(background_tasks: BackgroundTasks):
    def initSync():
        helper = RSyncHelper(config["name"], config["server_ip"])
        helper.sync(configuration_files)

    background_tasks.add_task(initSync)
    return { "status": True, "data": "Successful initiated!" }

#########################################
# IMAGES
#########################################

@app.get("/v1/images/check")
def check_image_files_on_server():
    logging.info("Refreshing image database file...")
    helper = RSyncHelper(config["name"], config["server_ip"])
    helper.update_file("cachingserver-linuxmuster-cachingserver", config["name"] + "_images.json", "/var/lib/linuxmuster-cachingserver/")

    image_files = []
    try:
        with open("/var/lib/linuxmuster-cachingserver/" + config["name"] + "_images.json") as f:
            for image in json.load(f):
                image_files.append({"share": "cachingserver-images", "pattern": image + "/*", "destination": "/srv/linbo/images/" + image, "exclude": "backups*"})

        if len(image_files) != 0:
            logging.info(f"Found {len(image_files)} images to sync localy!")
            result = helper.check(image_files)
            return { "status": result, "data": "" }
        else:
            logging.info("No images configured!")
            return { "status": True, "data": "" }
    except Exception as e:
        logging.error(e)
        logging.info("No images configured!")
        return { "status": True, "data": "" }


@app.get("/v1/images/sync")
def sync_image_files_with_server(background_tasks: BackgroundTasks):
    logging.info("Refreshing image database file...")
    helper = RSyncHelper(config["name"], config["server_ip"])
    helper.update_file("cachingserver-linuxmuster-cachingserver", config["name"] + "_images.json", "/var/lib/linuxmuster-cachingserver/")

    image_files = []
    try:
        with open("/var/lib/linuxmuster-cachingserver/" + config["name"] + "_images.json") as f:
            for image in json.load(f):
                image_files.append({"share": "cachingserver-images", "pattern": image + "/*", "destination": "/srv/linbo/images/" + image, "exclude": "backups*"})

        if len(image_files) != 0:
            logging.info(f"Found {len(image_files)} images to sync localy!")

            def initSync():
                helper = RSyncHelper(config["name"], config["server_ip"])
                helper.sync(image_files)

            background_tasks.add_task(initSync)

            return { "status": True, "data": "" }
        else:
            logging.info("No images configured!")
            return { "status": True, "data": "" }
    except:
        logging.info("No images configured!")
        return { "status": True, "data": "" }

@app.get("/v1/images/sync/status")
def check_image_status_of_image_sync():
    helper = RSyncHelper(config["name"], config["server_ip"])
    return { "status": True, "data": helper.syncStatus() }

#########################################
# SERVICES
#########################################

@app.get("/v1/services/status/{service}")
def get_status_of_service(service):
    stat = subprocess.call(["systemctl", "is-active", "--quiet", service])
    if(stat == 0):
        return { "status": True, "data": "Service is active" }
    return { "status": False, "data": "Service is unknown or inactive" }

@app.get("/v1/services/start/{service}")
def start_given_service(service, background_tasks: BackgroundTasks):
    def start():
        subprocess.Popen(["/usr/bin/systemctl", "start", service])
    background_tasks.add_task(start)
    return { "status": True, "data": "Initiate start successfully!" }

@app.get("/v1/services/stop/{service}")
def stop_given_service(service, background_tasks: BackgroundTasks):
    def stop():
        subprocess.Popen(["/usr/bin/systemctl", "stop", service])
    background_tasks.add_task(stop)
    return { "status": True, "data": "Initiate stop successfully!" }

@app.get("/v1/services/restart/{service}")
def restart_given_service(service, background_tasks: BackgroundTasks):
    def restart():
        subprocess.Popen(["/usr/bin/systemctl", "restart", service])
    background_tasks.add_task(restart)
    return { "status": True, "data": "Initiate restart successfully!" }

#########################################
# LOGS
#########################################

@app.get("/v1/logs")
def get_logs():
    with open("/var/log/linuxmuster/cachingserver/api.log") as f:
        return { "status": True, "data": "".join(f.readlines()[-100:]) }

#########################################

def main():
    logging.info("Starting Linuxmuster-Cachingserver-API on port 4457!")
    uvicorn.run(app, host="0.0.0.0", port=4457)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(e)
