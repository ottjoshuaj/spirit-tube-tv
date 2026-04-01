#!/usr/bin/env bash
# Wait for PipeWire and Bluetooth speaker to be ready before starting

BT_MAC="5C:FB:7C:B7:B5:AE"

# Give PipeWire time to start
sleep 3

# Attempt to connect the Bluetooth speaker (up to 30 seconds)
for i in $(seq 1 15); do
    if bluetoothctl info "$BT_MAC" 2>/dev/null | grep -q "Connected: yes"; then
        break
    fi
    bluetoothctl connect "$BT_MAC" >/dev/null 2>&1
    sleep 2
done

cd /home/jott/spirit-tube-tv
exec /usr/bin/python3 main.py
