#!/bin/bash
cd "$(dirname "$0")"
python3 app.py &
sleep 1
open "http://127.0.0.1:8765"
wait
