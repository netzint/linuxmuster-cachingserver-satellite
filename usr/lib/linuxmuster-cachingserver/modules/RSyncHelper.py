#!/usr/bin/env python3
#
# by lukas.spitznagel@netzint.de
#

import subprocess
import jc
import json
import logging
import threading
import time
import os
import socket
import netifaces as ni

class RSyncHelper:

    def __init__(self, name:str, server:str) -> None:
        self.name = name
        self.server = server

        self.pid = "/var/lib/linuxmuster-cachingserver/" + self.name + "_sync.pid"

    def __create_task_pid(self) -> bool:
        if not os.path.exists(self.pid):
            with open(self.pid, "w") as f:
                f.write(str(time.time()))
            return True
        return False

    def __remove_task_pid(self) -> None:
        os.remove(self.pid)

    def __status_task_pid(self) -> tuple:
        if os.path.exists(self.pid):
            return (True, float(open(self.pid).read()))
        return (False, None)

    def __execute_rsync_command(self, command:list) -> list:
        output = subprocess.check_output(command, text=True)
        result = jc.parse('rsync', output)
        return result

    def __get_ip_address(self, interface='ens18'):
        try:
            ip_address = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
        except (ValueError, KeyError):
            ip_address = None
        return ip_address

    def check_file_status(self, share:str, pattern:str, destination:str, include:str=None, exclude:str=None) -> bool:
        """
        Check if the files are up-to-date or need to be updated.
        Return TRUE if all files are up-to-date
        Return FALSE if update is needed
        """

        command = [
            "rsync",
            "-Piavcn",
            "--ignore-missing-args",
            "--password-file",
            "/var/lib/linuxmuster-cachingserver/cachingserver_rsync.secret",
        ]

        if include != None:
            command.append("--include")
            command.append(include)

        if exclude != None:
            command.append("--exclude")
            command.append(exclude)

        command.append(f"rsync://{self.name}@{self.server}/{share}/{pattern}")
        command.append(destination)

        result = self.__execute_rsync_command(command)

        for f in result[0]["files"]:
            logging.debug(f" -> File '{f['filename']}' is not up-to-date!")

        return len(result[0]["files"]) == 0

    def update_file(self, share:str, pattern:str, destination:str) -> bool:
        """
        Check if one file is up-to-date or need to be updated.
        """

        logging.info(f"Starting download for {self.name} on {self.server}...")

        command = [
            "rsync",
            "-Piavc",
            "--ignore-missing-args",
            "--password-file",
            "/var/lib/linuxmuster-cachingserver/cachingserver_rsync.secret",
        ]

        command.append(f"rsync://{self.name}@{self.server}/{share}/{pattern}")
        command.append(destination)

        result = self.__execute_rsync_command(command)

        for f in result[0]["files"]:
            logging.debug(f" -> Receiving new file '{f['filename']}' and save to '{destination}'")

        logging.info(f"Download finished!")

        return True

    def update_files(self, share:str, pattern:str, destination:str, include:str=None, exclude:str=None) -> bool:
        """
        Download / update files
        Always return true
        """

        command = [
            "rsync",
            "-iavc",
            "--ignore-missing-args",
            "--mkpath",
            "--password-file",
            "/var/lib/linuxmuster-cachingserver/cachingserver_rsync.secret"
        ]

        if include != None:
            command.append("--include")
            command.append(include)

        if exclude != None:
            command.append("--exclude")
            command.append(exclude)

        command.append(f"rsync://{self.name}@{self.server}/{share}/{pattern}")
        command.append(destination)

        rsync_process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        jc_process = subprocess.Popen(['jc', '--rsync-s'], stdin=rsync_process.stdout, stdout=subprocess.PIPE, text=True)

        def run(c):
            t1 = time.time()
            logging.info(f"[{c}] New thread started...")
            try:
                while True:
                    line = jc_process.stdout.readline()
                    if line:
                        parsed_data = json.loads(line.strip())
                        if parsed_data["type"] == "summary":
                            logging.debug(f"[{c}] Summary: Sent: {parsed_data['sent']} byte, Received: {parsed_data['received']} byte, Speed: {parsed_data['bytes_sec']} byte/s")
                        else:
                            logging.debug(f"[{c}] -> Receiving new file '{parsed_data['filename']}' and save to '{destination}'")
                    else:
                        break
            finally:
                jc_process.stdout.close()
                jc_process.terminate()
                jc_process.wait()
                rsync_process.terminate()
                rsync_process.wait()
            
            t2 = time.time()
            logging.info(f"[{c}] Thread finished after {(t2 - t1)} seconds!")
            

        x = threading.Thread(target=run, args=(share + ":" + pattern,))
        x.start()

        return x
    
    def check(self, configuration_files:list) -> bool:
        t1 = time.time()
        logging.info(f"Starting file check for {self.name} on {self.server}...")

        status = True
        for configuration_file in configuration_files:
            result = self.check_file_status(configuration_file["share"],
                                            configuration_file["pattern"], 
                                            configuration_file["destination"],
                                            configuration_file.get("include", None),
                                            configuration_file.get("exclude", None))
            if not result:
                status = result

        t2 = time.time()
        logging.info("File check finished after %s seconds!" % (t2 - t1))

        return status
    
    def sync(self, configuration_files:list) -> None:
        while(self.__status_task_pid()[0]):
            logging.info(f"Sync task already running since {(time.time() - self.__status_task_pid()[1])} seconds. Waiting for it to finish!")
            time.sleep(2)
        
        self.__create_task_pid()

        t1 = time.time()

        logging.info(f"Starting new download process for {self.name} on {self.server}...")

        threads = []

        for configuration_file in configuration_files:
            threads.append(self.update_files(configuration_file["share"], 
                                configuration_file["pattern"], 
                                configuration_file["destination"],
                                configuration_file.get("include", None),
                                configuration_file.get("exclude", None)))
        
        logging.info(f"All threads are started. Now waiting for them to finish!")

        for thread in threads:
            thread.join()
            
        logging.info(f"All threads are finished!")

        logging.info(f"Checking hostname in /etc/hosts...")
        
        ip = self.__get_ip_address()
        hostname = socket.gethostname()
        if "." in hostname:
            shortname = hostname.split(".")[0]
        else:
            shortname = hostname

        new_hosts_file = []
        with open("/etc/hosts") as f:
            entry_found = False
            for line in f.readlines():
                if hostname in line:
                    if socket.gethostbyname(socket.gethostname()) not in line:
                        new_hosts_file.append(ip + " " + shortname)
                        entry_found = True
                        logging.info(f"No entry found. Add '{ip} {shortname}' to /etc/hosts")
                    else:
                        logging.info("IP and hostname in /etc/hosts are correct!")
                else:
                    new_hosts_file.append(line)
            if not entry_found:
                new_hosts_file.append(ip + " " + shortname)
                logging.info(f"No entry found. Add '{ip} {shortname}' to /etc/hosts")

        with open("/etc/hosts", "w") as f:
          for line in new_hosts_file:
            f.write(line)

        for service in [ "isc-dhcp-server", "linbo-torrent", "linbo-multicast" ]:
            logging.info(f"Restart service '{service}'")
            subprocess.Popen(["/usr/bin/systemctl", "restart", service])
        
        t2 = time.time()
        logging.info("Download process finished after %s seconds!" % (t2 - t1))

        self.__remove_task_pid()

    def syncStatus(self) -> tuple:
        return self.__status_task_pid()
        
