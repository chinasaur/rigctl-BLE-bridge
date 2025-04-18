# rigctl-BLE-bridge
A rigctl <-> BLE serial communication bridge for controlling radio transceivers,
written in Python for Linux SBCs like the RasPi zero W.

The BLE code is derived with significant modification from:
* https://github.com/RadiusNetworks/bluez/blob/master/test/example-gatt-server
* https://github.com/RadiusNetworks/bluez/blob/master/test/example-advertisement
* https://github.com/mengguang/pi-ble-uart-server/blob/main/uart_peripheral.py

# Requirements
python3-serial, python3-dbus, libhamlib-utils

If your user doesn't have permission to start the BLE service / advertisement
try adding your user to the `bluetooth` group and restarting the Pi.

# Usage
`python3 main.py`

And then use an app like nRF Connect to connect to the BLE server and send
rigctl ASCII format commands. For example send `F 14060000 f` to QSY to 14.060
MHz and ask for the new frequency setting as a reply.

The program will attempt to autodetect usable serial ports and corresponding
Hamlib device IDs. These can also be set manually using the extra read/write
Characteristic config endpoints. You can also pass flag -d to add a dummy device
for testing purposes.

TODO(K6PLI): The extra config endpoints need descriptors added to make it more
clear what they're for.
