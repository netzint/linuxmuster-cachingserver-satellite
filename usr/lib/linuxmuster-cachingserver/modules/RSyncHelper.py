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

class RSyncHelper:

    def __init__(self, name:str, server:str) -> None:
        self.name = name
        self.server = server

    def __execute_rsync_command(self, command:list) -> list:
        output = subprocess.check_output(command, text=True)
        result = jc.parse('rsync', output)
        return result

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
            
        logging.info(f"All threads are finished! Now running post-hooks!")

        for service in [ "isc-dhcp-server", "linbo-torrent", "linbo-multicast" ]:
            logging.info(f"Restart service '{service}'")
            subprocess.Popen(["/usr/bin/systemctl", "restart", service])

        logging.info("Download process finished!")
        
