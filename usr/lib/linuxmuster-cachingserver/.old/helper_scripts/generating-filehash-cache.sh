#!/bin/bash
# by Netzint GmbH lukas.spitznagel@netzint.de

if [ $(ps -aux | grep "./cacheFileHashes.py" | grep python3 | wc -l) == "0" ]; then
    /usr/bin/python3 /usr/lib/linuxmuster-cachingserver/cacheFileHashes.py
else
    echo "Job is already running"
fi