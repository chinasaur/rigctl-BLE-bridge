import dbus
import dbus.service

DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"


class Characteristic(dbus.service.Object):
    """org.bluez.GattCharacteristic1 interface implementation."""

    def __init__(self, bus, path: str, uuid, flags, service, descriptors=None):
        self.bus = bus
        self.path = dbus.ObjectPath(path)
        self.uuid = uuid
        self.flags = flags
        self.service = service
        if descriptors is None:
            descriptors = []
        self.descriptors = descriptors
        super().__init__(bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "Service": self.service.path,
                "UUID": self.uuid,
                "Flags": self.flags,
                "Descriptors": dbus.Array(self.descriptor_paths, signature="o"),
            }
        }

    @property
    def descriptor_paths(self):
        return [desc.path for desc in self.descriptors]

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise ValueError()
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        raise NotImplemented()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        raise NotImplemented()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        raise NotImplemented()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        raise NotImplemented()

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Service(dbus.service.Object):
    """org.bluez.GattService1 interface implementation."""

    def __init__(
        self, bus, path: str, uuid, primary, characteristics: list[Characteristic]
    ):
        self.path = dbus.ObjectPath(path)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = characteristics
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": self.primary,
                "Characteristics": dbus.Array(self.characteristic_paths, signature="o"),
            }
        }

    @property
    def characteristic_paths(self):
        return [chrc.path for chrc in self.characteristics]

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise ValueError()
        return self.get_properties()[GATT_SERVICE_IFACE]


class Application(dbus.service.Object):
    def __init__(self, bus, services):
        self.path = dbus.ObjectPath("/")
        self.services = services
        dbus.service.Object.__init__(self, bus, self.path)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.path] = service.get_properties()
            for chrc in service.characteristics:
                response[chrc.path] = chrc.get_properties()
        return response
