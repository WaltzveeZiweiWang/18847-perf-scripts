#!/usr/bin/env bash

# make sure two arguments are specified
if [ $# -ne 2 ]; then
    echo "Usage: $0 <name of output file> <duration>"
    exit 1
fi

# remove existing data file
rm -f $1

# call power measurement command for duration time
sleep 1
timeout --signal=SIGINT $2 cpu-energy-meter -r > $1
