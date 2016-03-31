#!/usr/bin/env python

import sys
import struct
import socket
import serial
import modbus_tk
import modbus_tk.modbus_tcp as modbus_tcp
import modbus_tk.modbus_rtu as modbus_rtu
from modbus_tk.simulator import *
import mbmap
from optparse import OptionParser

class ModSimError(Exception):
    pass

class ModSimDatabank(modbus_tk.modbus.Databank):

    def handle_request(self, query, request):
        """
        when a request is received, handle it and returns the response pdu
        """
        request_pdu = ""
        try:
            #extract the pdu and the slave id
            (slave_id, request_pdu) = query.parse_request(request)

            #get the slave and let him executes the action
            if slave_id == 0:
                #broadcast
                for key in self._slaves:
                    self._slaves[key].handle_request(request_pdu, broadcast=True)
                return
            else:
                slave = self.get_slave(slave_id)
                response_pdu = slave.handle_request(request_pdu)
                #make the full response
                response = query.build_response(response_pdu)
                return response
        except Exception, excpt:
            modbus_tk.hooks.call_hooks("modbus.Databank.on_error", (self, excpt, request_pdu))
            LOGGER.error("handle request failed: " + str(excpt))
        except:
            LOGGER.error("handle request failed: unknown error")

        #If the request was not handled correctly, return a server error response
        ''' ### don't send response on error
        func_code = 1
        if len(request_pdu) > 0:
            (func_code, ) = struct.unpack(">B", request_pdu[0])
        return struct.pack(">BB", func_code+0x80, defines.SLAVE_DEVICE_FAILURE)
        '''


class ModSimRtuServer(modbus_rtu.RtuServer):

    def __init__(self, serial, databank=None):
        """Constructor: initializes the server settings"""
        modbus_tk.modbus.Server.__init__(self, databank if databank else ModSimDatabank())
        self._serial = serial
        LOGGER.info("RtuServer alt %s is %s" % (self._serial.portstr, "opened" if self._serial.isOpen() else "closed"))
        self._t0 = modbus_tk.modbus.utils.calculate_rtu_inter_char(self._serial.baudrate)
        self._serial.interCharTimeout = 1.5 * self._t0
        self._serial.timeout = 10 * self._t0
        # self._serial.interCharTimeout = .5
        # self._serial.timeout = .5
        print 'to =', self._serial.interCharTimeout, self._serial.timeout

    def _handle(self, request):
        """handle a received sentence"""

        if self._verbose:
            LOGGER.debug(self.get_log_buffer("-->", request))

        #gets a query for analyzing the request
        query = self._make_query()

        retval = modbus_tk.hooks.call_hooks("modbus.Server.before_handle_request", (self, request))
        if retval:
            request = retval

        response = self._databank.handle_request(query, request)
        retval = modbus_tk.hooks.call_hooks("modbus.Server.after_handle_request", (self, response))
        if retval:
            response = retval

        if response and self._verbose:
            LOGGER.debug(self.get_log_buffer("<--", response))
        return response

    def get_log_buffer(self, prefix, buff):
        """Format binary data into a string for debug purpose"""
        log = prefix
        for i in buff:
            log += str(hex(ord(i))) + " "
        return log[:-1]

class ModSim(Simulator):
    def __init__(self, options):
        self.rtu = None
        self.mode = options.mode

        if options.mode == 'rtu':
            self.rtu = serial.Serial(port=options.serial, baudrate=options.baud)
            # Simulator.__init__(self, modbus_rtu.RtuServer(self.rtu))
            Simulator.__init__(self, ModSimRtuServer(self.rtu))
            # timeout is too fast for 19200
            self.server._serial.timeout = self.server._serial.timeout * 1.5
        elif options.mode == 'tcp':
            Simulator.__init__(self, modbus_tcp.TcpServer(address = '', port = options.port))
        else:
            raise ModSimError('Unknown mode: %s' % (options.mode))

        self.server.set_verbose(options.verbose)


if __name__ == "__main__":

    usage = 'usage: %prog [options] map_file'
    parser = OptionParser(usage=usage)
    parser.add_option('-s', '--serial',
                      default='COM1',
                      help='Serial port [default: COM1]')
    parser.add_option('-b', '--baud',
                      default=9600,
                      help='Baud Rate [default: 9600]')
    parser.add_option('-m', '--mode',
                      default='tcp',
                      help='mode: rtu, tcp [default: tcp]')
    parser.add_option('-p', '--port', type='int',
                      default=502,
                      help='IP port [default: 502]')
    parser.add_option('-i', '--id', type='int',
                      default=1,
                      help='slave id [default: 1]')
    parser.add_option('-v', '--verbose', type='int',
                      default=0,
                      help='verbose: 0 or 1 [default: 0]')

    options, args = parser.parse_args()

    if len(args) != 1:
        print parser.print_help()
        sys.exit(1)

    print 'asdf'

    modbus_map = mbmap.ModbusMap(options.id)
    try:
        map_name = args[0]
        ext = os.path.splitext(map_name)[1]
        modbus_map.from_xml(map_name)
    except IOError, e:
        print 'Error loading modbus map file - %s' % (str(e))
        sys.exit(1)

    # create simulator
    try:
        sim = ModSim(options)
    except ModSimError, e:
        print 'Error initializing the simulator - %s' % (str(e))
        sys.exit(1)

    if sim.mode == 'rtu':
        # extend serial timeouts, they seems to cause frequent crc errors
        sim.server._serial.interCharTimeout *= 2
        sim.server._serial.timeout *= 2
        print 'Initialized modbus %s simulator: baud = %d  parity = %s  slave id = %s  base address = %s' % (options.mode,
            sim.rtu.baudrate, sim.rtu.parity, str(options.id), str(modbus_map.base_addr))
    elif sim.mode == 'tcp':
        print 'Initialized modbus %s simulator: addr = %s  port = %s  slave id = %s  base address = %s' % (options.mode,
            socket.gethostbyname(socket.gethostname()), options.port, str(options.id), str(modbus_map.base_addr))
    else:
        print 'Initialized modbus simulator to unknown mode: %s' % (sim.mode)
    
    # add modbus map to simulator slave device
    print 'Modbus map loaded from %s' % args[0]
    slave = sim.server.add_slave(options.id)
    for regs in modbus_map.regs:
        slave.add_block('regs_' + str(regs.offset), modbus_map.func, (modbus_map.base_addr + regs.offset), regs.count)
    for regs in modbus_map.regs:
        values = []
        for i in xrange(0, regs.count):
            index = i * 2
            v = struct.unpack('>H', regs.data[index:(index + 2)])
            values.append(v[0])
        # print values
        slave.set_values('regs_' + str(regs.offset), (modbus_map.base_addr + regs.offset), values)
        print 'Added modbus map block:  address = %d  count = %d' % ((modbus_map.base_addr + regs.offset), regs.count)

    try:
        LOGGER.info("'quit' for closing the simulator")
        sim.start()
        
    except Exception, e:
        print e
            
    finally:
        sim.close()

