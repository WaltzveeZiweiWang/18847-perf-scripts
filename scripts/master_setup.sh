#!/usr/bin/env bash

cd ~/DeathStarBench/$1/wrk2 && make

curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
      sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
      echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
      sudo tee /etc/apt/sources.list.d/ngrok.list && \
      sudo apt update && sudo apt install ngrok

sudo apt update
sudo apt install jq -y
sudo apt install dos2unix -y