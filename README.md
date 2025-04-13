# rigctl-BLE-bridge
A rigctl <-> BLE serial communication bridge for controlling radio transceivers,
written in Python for Linux SBCs like the RasPi zero W.

The BLE code is derived with modifications from:
* https://github.com/RadiusNetworks/bluez/blob/master/test/example-gatt-server
* https://github.com/RadiusNetworks/bluez/blob/master/test/example-advertisement
* https://github.com/mengguang/pi-ble-uart-server/blob/main/uart_peripheral.py

Currently the connection to rigctl for the radio only works if:
1) The radio is plugged in before starting the program.
2) There is only one serial device detected.
3) The radio identifies as a QDX Transceiver.

Clearly we will need to extend capabilities to make this more flexible :).

# Requirements
python3-serial, python3-dbus, libhamlib-utils

# Usage
`python3 bridge.py`

And then use an app like nRF Connect to connect to the BLE server and send
rigctl ASCII format commands. For example send `F 14060000 f` to QSY to 14.060
MHz and ask for the new frequency setting as a reply.
