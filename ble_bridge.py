import subprocess
import dbus
import serial.tools.list_ports
import ble_advertisement
import ble_server
import rigctl

BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LOCAL_NAME = "rigctl-BLE-bridge"


class TxCharacteristic(ble_server.Characteristic):
    UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Nordic UART.

    def __init__(self, bus, path, service):
        super().__init__(bus, path, self.UUID, ["notify"], service)
        self.notifying = False

    def send_tx(self, s):
        if not self.notifying:
            return
        value = [dbus.Byte(c.encode()) for c in s]
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])

    def StartNotify(self):
        self.notifying = True

    def StopNotify(self):
        self.notifying = False


class RxCharacteristic(ble_server.Characteristic):
    UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self, bus, path, service):
        super().__init__(bus, path, self.UUID, ["write"], service)

    def WriteValue(self, value, options):
        cmd_str = bytearray(value).decode()
        print(f"remote: {cmd_str}")
        self.service.bridge_command(cmd_str)


class PortListCharacteristic(ble_server.Characteristic):
    UUID = "d144ae91-eb03-426d-9c59-6659aa3bc324"

    def __init__(self, bus, path, service, extra_serial_ports):
        self.extra_serial_ports = extra_serial_ports
        super().__init__(bus, path, self.UUID, ["read"], service)

    def read_serial_ports(self) -> list[serial.tools.list_ports_common.ListPortInfo]:
        return serial.tools.list_ports.comports() + self.extra_serial_ports

    def ReadValue(self, options):
        serial_ports = self.read_serial_ports()
        value = ";".join(f"{p.device}:{p.description}" for p in serial_ports)
        return [dbus.Byte(c.encode()) for c in value]


class PortSelectCharacteristic(ble_server.Characteristic):
    UUID = "d144ae92-eb03-426d-9c59-6659aa3bc324"

    def __init__(self, bus, path, service):
        super().__init__(bus, path, self.UUID, ["write"], service)
        self.value = None

    def WriteValue(self, value, options):
        value = "".join(chr(byte) for byte in value)
        print("Ports value: ", value)
        self.value = value


class HamlibDeviceCharacteristic(ble_server.Characteristic):
    UUID = "1a274176-8531-49c2-b127-a1b4138501fa"
    UNKNOWN_DEVICE = 0

    # TODO(K6PLI): Not too clear what's best to use here. VID/PID could be good.
    # For now just use description.
    SERIAL_PORT_DESCRIPTION_TO_HAMLIB_DEVICE_MAP = {
        "Hamlib Dummy": 1,
        "QDX Transceiver": 2052,
    }

    def __init__(self, bus, path, service):
        super().__init__(bus, path, self.UUID, ["read", "write"], service)
        self.value = None

    def map_device(self):
        serial_port_info = self.service.get_selected_serial_port()
        if serial_port_info is None:
            return self.UNKNOWN_DEVICE
        return self.SERIAL_PORT_DESCRIPTION_TO_HAMLIB_DEVICE_MAP.get(
            serial_port_info.description, self.UNKNOWN_DEVICE)

    def get_device(self):
        if self.value is None:
            self.value = self.map_device()
        return self.value

    def ReadValue(self, options):
        self.value = self.map_device()
        return [dbus.Byte(c.encode()) for c in str(self.value)]

    def WriteValue(self, value, options):
        value = int("".join(chr(byte) for byte in value))
        print("Hamlib device value: ", value)
        self.value = value


class BridgeService(ble_server.Service):
    UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"  # Nordic UART

    def __init__(self, bus, extra_serial_ports):
        path = "/org/bluez/rigctl_bridge"
        self.tx = TxCharacteristic(bus, path + "/tx", self)
        self.rx = RxCharacteristic(bus, path + "/rx", self)
        self.serialportlist = PortListCharacteristic(bus, path + "/serialportlist", self, extra_serial_ports)
        self.serialportselect = PortSelectCharacteristic(bus, path + "serialportselect", self)
        self.hamlib = HamlibDeviceCharacteristic(bus, path + "/hamlib", self)
        characteristics = [self.tx, self.rx, self.serialportlist, self.serialportselect, self.hamlib]
        super().__init__(bus, path, self.UUID, True, characteristics)

        self.rigctl_manager = rigctl.RigctlManager()

    def cull_invalid_connections(self, valid_serial_ports):
        valid_serial_device_paths = frozenset(p.device for p in valid_serial_ports)
        self.rigctl_manager.cleanup(valid_serial_device_paths)

    def get_selected_serial_port(self):
        serial_ports = self.serialportlist.read_serial_ports()
        self.cull_invalid_connections(serial_ports)  # Opportunistic since we have serial ports in hand.

        if not self.serialportselect.value:
            if len(serial_ports) == 1:
                return serial_ports[0]
            return None

        for serial_port in serial_ports:
            if serial_port.device == self.serialportselect.value:
                return serial_port
        return None  # Selected serial port is no longer present.

    def bridge_command(self, cmd_str):
        serial_port = self.get_selected_serial_port()
        if serial_port is None:
            self.tx.send_tx("No serial port found for command.")
            return

        hamlib_device = self.hamlib.get_device()
        if not hamlib_device:
            self.tx.send_tx("No recognized Hamlib device.")
            return

        rigctl = self.rigctl_manager.get_rigctl(serial_port.device, hamlib_device)
        written = rigctl.write(cmd_str)
        if not written:
            self.tx.send_tx("Bridging to rigctl failed to write any bytes.")
            return

        reply, error = rigctl.waitread(timeout_secs=2.0)
        if error:
            self.tx.send_tx(error)
        elif reply:
            self.tx.send_tx(reply)
        elif reply is not None:
            self.tx.send_tx("Command accepted.")
        else:
            self.tx.send_tx("No reply from rigctl.")


class BridgeApplication(ble_server.Application):
    def __init__(self, bus, extra_serial_ports):
        uart_service = BridgeService(bus, extra_serial_ports)
        super().__init__(bus, services=[uart_service])


class BridgeAdvertisement(ble_advertisement.Advertisement):
    def __init__(self, bus, index):
        super().__init__(bus, index, "peripheral")
        self.add_service_uuid(BridgeService.UUID)
        self.add_local_name(LOCAL_NAME)
        self.include_tx_power = True


def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, "/"), DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for o, props in objects.items():
        if LE_ADVERTISING_MANAGER_IFACE in props and GATT_MANAGER_IFACE in props:
            print("Using adapter:", o)
            return o
        print("Skipping adapter:", o)
    return None
