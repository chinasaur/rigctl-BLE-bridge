import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import ble_uart

mainloop = None


def register_app_cb():
  print('GATT application registered')


def register_app_error_cb(error):
  print('Failed to register application: ' + str(error))
  mainloop.quit()


def register_ad_cb():
    print('Advertisement registered')


def register_ad_error_cb(error):
    print('Failed to register advertisement: ' + str(error))
    mainloop.quit()


def main():
  dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
  bus = dbus.SystemBus()
  adapter = ble_uart.find_adapter(bus)
  if not adapter:
    print('BLE adapter not found')
    return

  service_manager = dbus.Interface(bus.get_object(
      ble_uart.BLUEZ_SERVICE_NAME, adapter), ble_uart.GATT_MANAGER_IFACE)
  advertising_manager = dbus.Interface(bus.get_object(
      ble_uart.BLUEZ_SERVICE_NAME, adapter),
      ble_uart.LE_ADVERTISING_MANAGER_IFACE)

  app = ble_uart.UartApplication(bus)
  adv = ble_uart.UartAdvertisement(bus, 0)

  global mainloop
  mainloop = GLib.MainLoop()
  service_manager.RegisterApplication(
      app.get_path(), {}, reply_handler=register_app_cb,
      error_handler=register_app_error_cb)
  advertising_manager.RegisterAdvertisement(
      adv.get_path(), {}, reply_handler=register_ad_cb,
      error_handler=register_ad_error_cb)

  try:
    mainloop.run()
  except KeyboardInterrupt:
    adv.Release()


if __name__ == '__main__':
    main()
