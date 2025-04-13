import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import serial.tools.list_ports

import ble_uart

mainloop = GLib.MainLoop()


def register_app_cb():
    print("GATT application registered")


def register_app_error_cb(error):
    print("Failed to register application: " + str(error))
    mainloop.quit()


def register_ad_cb():
    print("Advertisement registered")


def register_ad_error_cb(error):
    print("Failed to register advertisement: " + str(error))
    mainloop.quit()


def setup_ble(serial_device, hamlib_device):
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = ble_uart.find_adapter(bus)
    if not adapter:
        print("BLE adapter not found")
        return

    service_manager = dbus.Interface(
        bus.get_object(ble_uart.BLUEZ_SERVICE_NAME, adapter),
        ble_uart.GATT_MANAGER_IFACE)
    advertising_manager = dbus.Interface(
        bus.get_object(ble_uart.BLUEZ_SERVICE_NAME, adapter),
        ble_uart.LE_ADVERTISING_MANAGER_IFACE)
    app = ble_uart.UartApplication(bus, serial_device, hamlib_device)
    adv = ble_uart.UartAdvertisement(bus, 0)
    service_manager.RegisterApplication(
        app.get_path(), {}, reply_handler=register_app_cb,
        error_handler=register_app_error_cb)
    advertising_manager.RegisterAdvertisement(
        adv.get_path(), {}, reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb)
    return adv


# TODO(K6PLI): Not too clear what's best to use here. VID/PID could be good.
# For now just use description.
SERIAL_TO_HAMLIB_DEVICE_MAP = {
        'QDX Transceiver': 2052,
}


def main():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports detected.")
        return
    print("Serial ports:")
    for port in ports:
        print(port.device, port.description)
    if len(ports) > 1:
        print("Handling multiple serial ports not yet supported.")
        return

    port = ports[0]
    if port.description not in SERIAL_TO_HAMLIB_DEVICE_MAP:
        print("Unknown device:", port.description)
        return
    hamlib_device = SERIAL_TO_HAMLIB_DEVICE_MAP[port.description]
    print("Matching hamlib device:", hamlib_device)

    adv = setup_ble(port.device, hamlib_device)
    try:
        mainloop.run()
    except KeyboardInterrupt:
        adv.Release()


if __name__ == "__main__":
    main()
