# -*- coding: utf-8 -*-
"""Handles ANT devices

There should only evern be one instance of the AntDevices class, since
it talks to a hardware device.

- Strives to keep a device connected
- Runs the Node object
- Caches channels or ANT+ objects for specific devices
"""

import random
import sys
import time

from gevent.queue import Queue, Full
from gevent import Greenlet, joinall, sleep

from ant.core import driver, node, log
from ant.core.exceptions import DriverError, NodeError, ChannelError
from ant.plus.heartrate import *

class HrmCallback(HeartRateCallback):

    def __init__(self, queue):
        self.queue = queue

    def device_found(self, device_number, transmission_type):
        pass

    def heartrate_data(self, computed_heartrate, event_time_s, rr_interval_ms):
        try:
            self.queue.put_nowait((computed_heartrate, event_time_s, rr_interval_ms))
        except Full:
            print("warning: consumer not reading hr messages from queue")

class AntDevices(object):
    def __init__(self, usb_product_id):
        self.usb_product_id = usb_product_id

        self.usb_device = None
        self.node = None
        self.devices = {}

    def start(self): # todo USB device configuration input
        if self.usb_product_id == 'fake':
            print("Faking HR device with randomness")
            return

        try:
            print("Opening USB...")
            self.usb_device = driver.USB2Driver(debug=True, idProduct=0x1009)
            print("Got USB: {0}".format(self.usb_device))
        except DriverError as e:
            print("Unable to open USB device.")
            return
        except Exception as e:
            print("Unexpected exception: {0}".format(e))
            return

        try:
            print("Creating node...")
            self.node = node.Node(self.usb_device)
            print("Starting node {0}".format(self.node))
            self.node.start()
            print("Node started.")
        except NodeError as e:
            self.node = None
            print("Unable to start node: {0}".format(e))
        except ChannelError as e:
            self.node = None
            print("Unable to open channel: {0}".format(e))
        except Exception as e:
            self.node = None
            print("Unexpected exception...: {0}".format(e))



    def stop(self):
        if self.node and self.node.running:
            self.node.stop()


    def open_heartrate_device(self, device_number, transmission_type):
        if self.usb_product_id == 'fake':
            def random_heart_data(q):
                event_time_s = 0
                while True:
                    sleep(1)

                    hr = random.randint(60, 180)
                    rr_interval = random.randint(800, 1100)
                    event_time_s += 1.0

                    try:
                        q.put_nowait((hr, event_time_s, rr_interval))
                    except Full:
                        pass

            device = {}
            device['queue'] = Queue(maxsize=1)
            device['callback'] = Greenlet.spawn(random_heart_data, device['queue'])
            return device

        if not (self.usb_device and self.node):
            print("Unable to open hr device, no usb device or node.")
            return None

        if not self.node.running:
            print("Unable to open hr device, node not running.")
            return None

        key = (device_number, transmission_type)
        if key in self.devices:
            print("Found existing hr device.")
            return self.devices[key]

        try:
            # TODO make this a class
            device = {}
            device['queue'] = Queue(maxsize=1)
            device['callback'] = HrmCallback(device['queue'])
            device['object'] = HeartRate(self.node, callback = device['callback'])

            self.devices[key] = device
        except:
            print("Unable to open heart rate device.")
            device = None

        return device
