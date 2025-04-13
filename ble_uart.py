import subprocess
import sys
import dbus
from ble_advertisement import Advertisement
from ble_server import Application, Service, Characteristic

BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
LOCAL_NAME = "usb-ble-bridge"

class TxCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UART_TX_CHARACTERISTIC_UUID, ["notify"], service)
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
    def __init__(self, bus, index, service, serial_device, hamlib_device, send_tx):
        super().__init__(
                bus, index, UART_RX_CHARACTERISTIC_UUID, ["write"], service)
        self.serial_device = serial_device
        self.hamlib_device = hamlib_device
        self.send_tx = send_tx

    def WriteValue(self, value, options):
        cmd_str = bytearray(value).decode()
        print(f"remote: {cmd_str}")

        cmd = ['/usr/bin/rigctl']
        cmd += ['-r', self.serial_device]
        cmd += ['-m', str(self.hamlib_device)]
        cmd += cmd_str.split()
        cp = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        reply = cp.stdout.strip()
        error = cp.stderr.strip() 
        print("rigctl stdout:", reply)
        print("rigctl stderr:", error)

        if error:
            self.send_tx(error)
        elif reply:
            self.send_tx(reply)


class UartService(Service):
    def __init__(self, bus, index, serial_device, hamlib_device):
        super().__init__(bus, index, UART_SERVICE_UUID, True)
        tx_characteristic = TxCharacteristic(bus, 0, self)
        rx_characteristic = RxCharacteristic(
                bus, 1, self, serial_device, hamlib_device,
                tx_characteristic.send_tx)
        self.add_characteristic(tx_characteristic)
        self.add_characteristic(rx_characteristic)


class UartApplication(Application):
    def __init__(self, bus, serial_device, hamlib_device):
        super().__init__(bus)
        self.add_service(UartService(bus, 0, serial_device, hamlib_device))


class UartAdvertisement(Advertisement):
    def __init__(self, bus, index):
        super().__init__(bus, index, "peripheral")
        self.add_service_uuid(UART_SERVICE_UUID)
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
