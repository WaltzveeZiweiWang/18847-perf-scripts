#!/usr/bin/env bash

if [[ $# -ne 3 ]]; then
    echo "Illegal number of parameters (need 3): compose, env, service_name" >&2
    exit 2
fi

dos2unix $2
set -a
source $2
sudo docker stack deploy --compose-file=$1 $3
