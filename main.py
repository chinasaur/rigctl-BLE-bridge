import argparse
import json
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import serial.tools.list_ports
import serial.tools.list_ports_common
import ble_bridge

MAINLOOP = GLib.MainLoop()


def register_app_cb():
    print("GATT application registered")


def register_app_error_cb(error):
    print("Failed to register application: " + str(error))
    MAINLOOP.quit()


def register_ad_cb():
    print("Advertisement registered")


def register_ad_error_cb(error):
    print("Failed to register advertisement: " + str(error))
    MAINLOOP.quit()


def setup_ble(mock_ports):
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = ble_bridge.find_adapter(bus)
    if not adapter:
        print("BLE adapter not found")
        return

    service_manager = dbus.Interface(
        bus.get_object(ble_bridge.BLUEZ_SERVICE_NAME, adapter),
        ble_bridge.GATT_MANAGER_IFACE,
    )
    advertising_manager = dbus.Interface(
        bus.get_object(ble_bridge.BLUEZ_SERVICE_NAME, adapter),
        ble_bridge.LE_ADVERTISING_MANAGER_IFACE,
    )
    app = ble_bridge.BridgeApplication(bus, mock_ports)
    advertisement = ble_bridge.BridgeAdvertisement(bus, 0)
    service_manager.RegisterApplication(
        app.path, {}, reply_handler=register_app_cb, error_handler=register_app_error_cb
    )
    advertising_manager.RegisterAdvertisement(
        advertisement.get_path(),
        {},
        reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb,
    )
    return advertisement


def main():
    parser = argparse.ArgumentParser(
        prog="rigctl-ble-bridge",
        description="Bridge to control rigctl devices (radios, etc.) via BLE",
    )
    parser.add_argument("-d", "--add_dummy_port", action="store_true")
    args = parser.parse_args()

    mock_ports = []
    if args.add_dummy_port:
        info = serial.tools.list_ports_common.ListPortInfo("/dev/null")
        info.description = "Hamlib Dummy"
        mock_ports.append(info)

    advertisement = setup_ble(mock_ports)

    try:
        MAINLOOP.run()
    except KeyboardInterrupt:
        advertisement.Release()


if __name__ == "__main__":
    main()
