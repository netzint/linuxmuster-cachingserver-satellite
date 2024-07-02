#!/usr/bin/env python3
#
# by lukas.spitznagel@netzint.de
#

import json
import os

print("# Migrating server to rsync file...")

with open("/var/lib/linuxmuster-cachingserver/server.json") as f:
    server = json.load(f)
    if "name" in server:
        print(f"# Add secret for {server['name']} to rsync file...", end="")
        with open("/var/lib/linuxmuster-cachingserver/cachingserver_rsync.secret", "w") as f2:
            f2.write(server["secret"])
        os.chmod("/var/lib/linuxmuster-cachingserver/cachingserver_rsync.secret", 600)
        print(" ok")