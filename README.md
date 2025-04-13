# USB-BLE-bridge-pithon
A USB-BLE serial communication bridge for controlling radio transceivers via
Linux SBCs like the RasPi zero W.

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
