# Part of the jsonrpc2-zeromq-python project.
# (c) 2012 Wireless Innovation Ltd, All Rights Reserved.
# Please see the LICENSE file in the root of this project for license
# information.

import unittest
import logging
from time import sleep

import zmq

import jsonrpc2_zeromq


class RPCTestServer(jsonrpc2_zeromq.RPCServer):

    def handle_echo_method(self, msg):
        return msg

    def handle_dict_args_method(self, an_int=None, a_bool=None, a_float=None,
                                a_str=None):
        return dict(an_int=an_int, a_bool=a_bool, a_float=a_float, a_str=a_str)

    def handle_return_null_method(self):
        return None


class RPCNotificationTestServer(jsonrpc2_zeromq.RPCNotificationServer):

    def handle_echo_method(self, msg):
        return msg


class NotificationOnlyPullTestServer(jsonrpc2_zeromq.NotificationOnlyPullServer):

    def handle_event_method(self, event_type, event_value):
        # Do things!
        pass


test_debug_logger = logging.getLogger('jsonrpc2_zeromq_test')
test_debug_logger.setLevel(logging.DEBUG)
logger_console_handler = logging.StreamHandler()
logger_console_handler.setLevel(logging.DEBUG)
test_debug_logger.addHandler(logger_console_handler)


class BaseServerTestCase(unittest.TestCase):

    endpoint = "inproc://jsonrpc2-zeromq-tests"
    logger = None

    def tearDown(self):
        self.server.stop()
        self.server.join()
        self.server.close()
        sleep(0.1) # Wait for socket to actually close


class RPCServerTestCase(BaseServerTestCase):

    def setUp(self):
        self.server = RPCTestServer(endpoint=self.endpoint,
                                    logger=self.logger)
        self.server.daemon = True
        self.server.start()
        self.client = jsonrpc2_zeromq.RPCClient(endpoint=self.endpoint,
                                                logger=self.logger)

    def test_echo(self):
        msg = "Test message"
        result = self.client.echo(msg)
        self.assertEqual(msg, result)

    def test_many(self):
        msgs = ["test lots", "and another", "me too"]
        for i, msg in enumerate(msgs):
            result = self.client.echo(msg)
            self.assertEqual(msgs[i], result)

    def test_dict_args(self):
        dict_out = dict(an_int=1, a_bool=True, a_float=1.5556, a_str="hello!")
        result = self.client.dict_args(**dict_out)
        self.assertEqual(dict_out, result)

    def test_method_not_found(self):
        try:
            self.client.non_existent_method()
        except jsonrpc2_zeromq.MethodNotFound:
            pass
        else:
            self.fail("Non-existent method allowed")

    def test_return_null(self):
        result = self.client.return_null()
        self.assertEqual(None, result)


class RPCNotificationServerTestCase(BaseServerTestCase):

    def setUp(self):
        self.server = RPCNotificationTestServer(endpoint=self.endpoint,
                                                logger=self.logger)
        self.server.daemon = True
        self.server.start()
        self.client = jsonrpc2_zeromq.RPCNotifierClient(endpoint=self.endpoint,
                                                        logger=self.logger)

    def test_rpc(self, msg="clowns and monkeys"):
        result = self.client.echo(msg)
        self.assertEqual(msg, result)

    def test_notify(self):
        self.client.notify.echo("a message into the void")

    def test_notify_then_rpc(self):
        self.test_notify()
        self.test_rpc()
        self.test_rpc("and lions and tigers")


class NotificationOnlyPullServerTestCase(BaseServerTestCase):

    def setUp(self):
        self.server = NotificationOnlyPullTestServer(endpoint=self.endpoint,
                                                     logger=self.logger)
        self.server.daemon = True
        self.server.start()
        self.client = jsonrpc2_zeromq.NotifierOnlyPushClient(
                            endpoint=self.endpoint, logger=self.logger)

    def test_event(self):
        self.client.notify.event("fell over", "quickly")

    def test_many_events(self):
        for i in xrange(100):
            self.client.notify.event("balloon launched", "number {0}".format(i))

