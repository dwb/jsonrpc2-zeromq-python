# Part of the jsonrpc2-zeromq-python project.
# (c) 2012 Dan Brown, All Rights Reserved.
# Please see the LICENSE file in the root of this project for license
# information.

from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import *  # NOQA
from past.utils import old_div

import unittest
import logging

import jsonrpc2_zeromq

from .helpers import *  # NOQA FIXME: probably addreess this


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
        sleep(0.1)  # Wait for socket to actually close


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

    def test_timeout(self):
        self.client.timeout = old_div(RPCTestServer.long_time, 10)
        try:
            self.client.take_a_long_time()
        except jsonrpc2_zeromq.client.TimeoutError:
            pass
        else:
            self.fail("Client didn't timeout")


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
        for i in range(100):
            self.client.notify.event("balloon launched", "number {0}".
                                     format(i))


class NotificationReceiverClientTestCase(BaseServerTestCase):

    def setUp(self):
        self.server = NotificationReceiverClientTestServer(
            endpoint=self.endpoint, logger=self.logger)
        self.server.daemon = True
        self.server.start()
        self.client = NotificationReceiverTestClient(endpoint=self.endpoint,
                                                     logger=self.logger)

    def tearDown(self):
        self.client.stop()
        return super(NotificationReceiverClientTestCase, self).tearDown()

    def _test_event_subscription(self, num_notifications, expected_replies,
                                 method):
        getattr(self.client, method)(num_notifications)
        self.client.join(
            NotificationReceiverClientTestServer.notification_reply_sleep_time
            * (num_notifications + 1))

        self.assertEqual(expected_replies,
                         self.client.num_notifications_received)

    def test_subscribe(self):
        self._test_event_subscription(3, 3, "subscribe")

    def test_bad_subscribe(self):
        self._test_event_subscription(1, 0, "subscribe_bad_event")

    def test_timeout(self):
        self.client.timeout = old_div(
            NotificationReceiverClientTestServer.long_time, 10)
        try:
            self.client.take_a_long_time()
        except jsonrpc2_zeromq.client.TimeoutError:
            pass
        else:
            self.fail("Client didn't timeout")
