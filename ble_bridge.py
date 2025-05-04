import subprocess
import dbus
import serial.tools.list_ports
from ble_advertisement import Advertisement
from ble_server import Application, Service, Characteristic

BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LOCAL_NAME = "rigctl-BLE-bridge"


class TxCharacteristic(Characteristic):
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


class RxCharacteristic(Characteristic):
    UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self, bus, path, service):
        super().__init__(bus, path, self.UUID, ["write"], service)

    def WriteValue(self, value, options):
        cmd_str = bytearray(value).decode()
        print(f"remote: {cmd_str}")
        self.service.bridge_command(cmd_str)


class PortListCharacteristic(Characteristic):
    UUID = "d144ae91-eb03-426d-9c59-6659aa3bc324"

    def __init__(self, bus, path, service, extra_ports):
        self.extra_ports = extra_ports
        super().__init__(bus, path, self.UUID, ["read"], service)

    def read_ports(self) -> list[serial.tools.list_ports_common.ListPortInfo]:
        return serial.tools.list_ports.comports() + self.extra_ports

    def ReadValue(self, options):
        ports = self.read_ports()
        value = ";".join(f"{p.device}:{p.description}" for p in ports)
        return [dbus.Byte(c.encode()) for c in value]


class PortSelectCharacteristic(Characteristic):
    UUID = "d144ae92-eb03-426d-9c59-6659aa3bc324"

    def __init__(self, bus, path, service):
        super().__init__(bus, path, self.UUID, ["write"], service)
        self.value = None

    def WriteValue(self, value, options):
        value = "".join(chr(byte) for byte in value)
        print("Ports value: ", value)
        self.value = value


class HamlibDeviceCharacteristic(Characteristic):
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
        port_info = self.service.get_selected_port()
        if port_info is None:
            return self.UNKNOWN_DEVICE
        return self.SERIAL_PORT_DESCRIPTION_TO_HAMLIB_DEVICE_MAP.get(
            port_info.description, self.UNKNOWN_DEVICE)

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


class BridgeService(Service):
    UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"  # Nordic UART

    def __init__(self, bus, extra_ports):
        path = "/org/bluez/rigctl_bridge"
        self.tx = TxCharacteristic(bus, path + "/tx", self)
        self.rx = RxCharacteristic(bus, path + "/rx", self)
        self.portlist = PortListCharacteristic(bus, path + "/portlist", self, extra_ports)
        self.portselect = PortSelectCharacteristic(bus, path + "portselect", self)
        self.hamlib = HamlibDeviceCharacteristic(bus, path + "/hamlib", self)
        characteristics = [self.tx, self.rx, self.portlist, self.portselect, self.hamlib]
        super().__init__(bus, path, self.UUID, True, characteristics)

    def get_selected_port(self):
        ports = self.portlist.read_ports()

        if not self.portselect.value:
            if len(ports) == 1:
                return ports[0]
            return None

        for port in ports:
            if port.device == self.portselect.value:
                return port
        return None  # Selected port is no longer present.

    def bridge_command(self, cmd_str):
        port = self.get_selected_port()
        if port is None:
            self.tx.send_tx("No serial port found for command.")
            return

        hamlib_device = self.hamlib.get_device()
        if not hamlib_device:
            self.tx.send_tx("No recognized Hamlib device.")
            return

        cmd = ["/usr/bin/rigctl"]
        cmd += ["-r", port.device]
        cmd += ["-m", str(hamlib_device)]
        cmd += cmd_str.split()
        print(cmd)
        cp = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        reply = cp.stdout.strip()
        error = cp.stderr.strip()
        print("rigctl stdout:", reply)
        print("rigctl stderr:", error)

        if error:
            self.tx.send_tx(error)
        elif reply:
            self.tx.send_tx(reply)


class BridgeApplication(Application):
    def __init__(self, bus, extra_ports):
        uart_service = BridgeService(bus, extra_ports)
        super().__init__(bus, services=[uart_service])


class BridgeAdvertisement(Advertisement):
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
