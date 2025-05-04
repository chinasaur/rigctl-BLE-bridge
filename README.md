# rigctl-BLE-bridge
A rigctl <-> BLE serial communication bridge for controlling radio transceivers,
written in Python for Linux SBCs like the RasPi zero W.

The BLE code is derived with significant modification from:
* https://github.com/RadiusNetworks/bluez/blob/master/test/example-gatt-server
* https://github.com/RadiusNetworks/bluez/blob/master/test/example-advertisement
* https://github.com/mengguang/pi-ble-uart-server/blob/main/uart_peripheral.py

# Requirements
python3-serial, python3-dbus, python3-gi, libhamlib-utils

If your user doesn't have permission to start the BLE service / advertisement
try adding your user to the `bluetooth` group and restarting the Pi.

# Usage
`python3 main.py`

And then use an app like nRF Connect to connect to the server ("rigctl-BLE-bridge")
and send rigctl ASCII format commands on the UART Rx Characteristic. For example send
`F 14060000 f` to QSY to 14.060 MHz and ask for the new frequency setting as a reply
on the Tx Characteristic (you must enable notifications to receive the reply).

The program will attempt to autodetect usable serial ports and corresponding
Hamlib device IDs. These can also be set manually using the extra read/write
Characteristic config endpoints. You can also pass flag -d to add a dummy device
for testing purposes. To add autodetect for your rig, add it to
`ble_bridge.HamlibDeviceCharacteristic.SERIAL_PORT_DESCRIPTION_TO_HAMLIB_DEVICE_MAP`.

# Config endpoints
Unfortunately adding Descriptors to self-document the config endpoints is not yet
working. The usable config endpoint BLE Characteristics are:
  * PortList UUID d144ae91-eb03-426d-9c59-6659aa3bc324, a read-only Characteristic
    that will query the available serial ports and print their device path (e.g.
    /dev/ttyACM0 or /dev/ttyUSB0) and device description (e.g. QCX Transceiver).
  * PortSelect UUID d144ae92-eb03-426d-9c59-6659aa3bc324, a write-only
    Characteristic for manually setting the serial port device path to use. Only
    needed if there are multiple ports detected; if there is only one port
    detected that one will be used automatically.
  * Hamlib UUID 1a274176-8531-49c2-b127-a1b4138501fa, a read-write Characteristic.
    Write this to set the hamlib device ID to use with the selected port, e.g. 2052
    for QCX. Only needed if the device on the selected port isn't recognized by its
    device description. Reading this Characteristic will give a reply of 0 if the
    current selected port isn't recognized, or will reply with the recognized hamlib
    device ID.
