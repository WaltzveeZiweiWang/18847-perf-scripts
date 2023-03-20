#!/usr/bin/env bash

# make sure one argument is specified
if [ $# -ne 2 ]; then
    echo "Usage: $0 <name of output file> <duration>"
    exit 1
fi

# remove existing data file
rm -f $1

# continue to call docker stats and append
sleep 1
sudo timeout --signal=SIGINT $2 docker stats --format "{{.ID}},{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.NetIO}},{{.BlockIO}},{{.PIDs}},{{.MemPerc}}" >> $1