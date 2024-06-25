#!/bin/bash

# Get it from "aplay -L" list
adev="default:CARD=CODEC"

file=$1

./ptt.sh 1
sleep 0.5
aplay --device ${adev} "tone1750.wav" "$file"
./ptt.sh 0
