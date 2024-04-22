#!/usr/bin/env python3
#
# by lukas.spitznagel@netzint.de
#

import json

print("# Migrating server to rsync file...")

with open("/var/lib/linuxmuster-cachingserver/server.json") as f:
    server = json.load(f)
    print(f"# Add secret for {server['name']} to rsync file...", end="")
    with open("/var/lib/linuxmuster-cachingserver/cachingserver_rsync.secret", "w") as f2:
        f2.write(server["secret"])
    print(" ok")