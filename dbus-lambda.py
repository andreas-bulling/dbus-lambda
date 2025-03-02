#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#  Please note that any incorrect or careless usage of this module as
#  well as errors in the implementation can damage your hardware!
#  Therefore, the author does not provide any guarantee or warranty
#  concerning to correctness, functionality or performance and does not
#  accept any liability for damage caused by this module, examples or
#  mentioned information.
#
#  Thus, use it at your own risk!

# import normal packages
import logging
import platform
import logging
import sys
import os
import time
import configparser # for config/ini file
from enum import Enum
from math import log10
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject

sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.exceptions import ModbusException

class DbusLAMBDAService:
    def __init__(self, servicename, paths, productname='lambda', connection='LAMBDA Modbus Service'):
        config = self._getConfig()
        deviceinstance = int(config['DEFAULT']['Deviceinstance'])
        self.host = str(config['DEFAULT']['Host'])
        self.port = int(config['DEFAULT']['Port'])
        self.acposition = int(config['DEFAULT']['Position'])
        self.model = str(config['DEFAULT']['Model'])
        self.timeout = int(config['DEFAULT']['Timeout'])

        self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0xFFFF)
        self._dbusservice.add_path('/ProductName', "LAMBDA " + self.model)
        self._dbusservice.add_path('/CustomName', "LAMBDA " + self.model)
        self._dbusservice.add_path('/FirmwareVersion', "0")
        self._dbusservice.add_path('/Serial', "0")
        self._dbusservice.add_path('/HardwareVersion', self.model)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/UpdateIndex', 0)
        self._dbusservice.add_path('/Position', self.acposition) # 0: ac out, 1: ac in

        # add path values to dbus
        for path, settings in self._paths.items():
            self._dbusservice.add_path(path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

        # last update
        self._lastUpdate = 0

        # add _update function 'timer'
        gobject.timeout_add(self.timeout, self._update) # pause before the next request

        # add _signOfLife 'timer' to get feedback in log every x minutes
        gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)

        # open Modbus connection to heatpump
        self._client = ModbusTcpClient(self.host, port=self.port)
        self._client.connect()
        logging.info("Modbus connected")

    def __del__(self):
        # close Modbus connection
        self._client.close()

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        return config
    
    def _getSignOfLifeInterval(self):
        config = self._getConfig()
        value = config['DEFAULT']['SignOfLifeLog']

        if not value:
            value = 0

        return int(value)
    
    def _handlechangedvalue(self, path, value):
        logging.critical("Someone else updated %s to %s" % (path, value))
        # TODO: handle changes

    def getLAMBDAData(self, register):
        if register == "state": # UINT16, works
            addr = 1003
            format = "H"
            count = 1
            factor = 1
            comment = "Operating State"
            unit = ""
        elif register == "temp": # INT16, works
            addr = 1004
            format = "h"
            count = 1
            factor = 0.01
            comment = "Flow Temperature"
            unit = "°C"
        elif register == "ttemp": # INT16, doesn't work
            addr = 1016
            format = "h"
            count = 1
            factor = 0.1
            comment = "Request Flow Temperature"
            unit = "°C"
        elif register == "power": # INT16, works
            addr = 103
            format = "h"
            count = 1
            factor = 1
            comment = "Power Consumption"
            unit = "W"
        elif register == "energy": # INT32, works
            addr = 1020
            format = "i"
            count = 2
            factor = 0.001
            comment = "Total Energy"
            unit = "kWh"
        
        try:
            rr = self._client.read_holding_registers(address=addr, count=count, slave=1)
        except ModbusException as exc:
            logging.error(f"Modbus exception: {exc!s}")

        payload = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.Big, wordorder=Endian.Big)
        if register == "state": # UINT16, works
            value = payload.decode_16bit_uint()
        elif register == "temp": # INT16, works
            value = payload.decode_16bit_int()
        elif register == "ttemp": # INT16, doesn't work
            value = payload.decode_16bit_int()
        elif register == "power": # INT16, works
            value = payload.decode_16bit_int()
        elif register == "energy": # INT32, works
            value = payload.decode_32bit_int()
      
        value = value * factor
        if factor < 1:
            value = round(value, int(log10(factor) * -1))
        logging.debug(f"{comment} = {value} {unit}")

        return value
   
    def _signOfLife(self):
        logging.info("--- Start: sign of life ---")
        logging.info("Last _update() call: %s" % (self._lastUpdate))
        logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
        logging.info("--- End: sign of life ---")
        return True

    def _update(self):
        try:
            self._dbusservice['/State'] = self.getLAMBDAData("state")
            self._dbusservice['/Temperature'] = self.getLAMBDAData("temp")
            self._dbusservice['/TargetTemperature'] = self.getLAMBDAData("ttemp")
            self._dbusservice['/Ac/Power'] = self.getLAMBDAData("power")
            self._dbusservice['/Ac/Energy/Forward'] = self.getLAMBDAData("energy")

            # logging
            logging.debug("Operating State (/State): %s" % (self._dbusservice['/State']))
            logging.debug("Flow Temperature (/Temperature): %s" % (self._dbusservice['/Temperature']))
            logging.debug("Request Flow Temperature (/TargetTemperature): %s" % (self._dbusservice['/TargetTemperature']))
            logging.debug("Power Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            logging.debug("Total Energy (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            logging.debug("---")

            # increment UpdateIndex - to show that new data is available
            index = self._dbusservice['/UpdateIndex'] + 1  # increment index
            if index > 255:   # maximum value of the index
                index = 0       # overflow from 255 to 0
            self._dbusservice['/UpdateIndex'] = index

            # update lastupdate vars
            self._lastUpdate = time.time()

        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)
            logging.critical(e)

        # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
        return True


def main():
    # configure logging
    logging.basicConfig(  format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                          datefmt='%Y-%m-%d %H:%M:%S',
                          level=logging.INFO,
                          handlers=[
                              logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                              logging.StreamHandler()
                          ]
                        )

    try:
        logging.info("Start")

        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # formatting
        _kWh = lambda p, v: (str(round(v, 2)) + 'kWh')
        _a = lambda p, v: (str(round(v, 1)) + 'A')
        _w = lambda p, v: (str(round(v, 1)) + 'W')
        _v = lambda p, v: (str(round(v, 1)) + 'V')
        _degC = lambda p, v: (str(v) + '°C')
        _s = lambda p, v: (str(v) + 's')
        _n = lambda p, v: (str(v))

        # start our main-service
        hp_output = DbusLAMBDAService(
          servicename='com.victronenergy.heatpump',
          paths={
            '/State': {'initial': 0, 'textformat': _n},
            '/Temperature': {'initial': 0, 'textformat': _degC},
            '/TargetTemperature': {'initial': 0, 'textformat': _degC},
            '/Ac/Power': {'initial': 0, 'textformat': _w},
            '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kWh},
          }
        )

        logging.info('Connected to dbus and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)

if __name__ == "__main__":
    main()

