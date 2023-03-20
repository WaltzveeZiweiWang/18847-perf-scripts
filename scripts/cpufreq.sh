#!/usr/bin/env bash

# make sure two arguments are specified
if [ $# -ne 2 ]; then
    echo "Usage: $0 <name of output file> <duration>"
    exit 1
fi

# remove existing data file
rm -f $1

# loop over duration number of times
for i in $(seq 1 $2); do
    sleep 1
    # output frequencies of all cpu to file
    grep 'MHz' /proc/cpuinfo | awk '{print $4}' >> $1
    # add a new line to separate the data
    echo "" >> $1
done