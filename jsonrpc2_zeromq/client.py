# Part of the jsonrpc2-zeromq-python project.
# (c) 2012 Wireless Innovation Ltd, All Rights Reserved.
# Please see the LICENSE file in the root of this project for license
# information.

import threading
import pprint

import zmq

from . import common


class TimeoutError(Exception): pass


class RPCClient(common.Endpoint):

    default_socket_type = zmq.REQ
    error_code_exceptions = None
    request_method_class = common.RequestMethod

    socket = None

    def __init__(self, endpoint, context=None, timeout=5000,
                 socket_type=None, logger=None):
        super(RPCClient, self).__init__(endpoint, socket_type, timeout, context,
                                        logger)
        self.notify = NotifierProxy(self)
        self.request_poller = zmq.Poller()
        self._reconnect_socket()

    def _reconnect_socket(self):
        if self.socket:
            if self.socket in self.request_poller.sockets:
                self.request_poller.unregister(self.socket)
            self.socket.close()
        self.socket = self.context.socket(self.socket_type)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect(self.endpoint)
        self.request_sock = self.socket

    def request(self, request):
        self.logger.debug(">_> Client calling \"{method}\" on {endpoint} "
                       "with params:\n  {params}".format(method=request.method,
                           endpoint=self.endpoint,
                           params=pprint.pformat(request.params)))

        self.request_poller.register(self.request_sock, zmq.POLLOUT)
        if not self.request_poller.poll(self.timeout):
            self._reconnect_socket()
            raise TimeoutError("Timed out while waiting to call {method} on "
                    "{endpoint}".format(method=request.method,
                        endpoint=self.endpoint))

        self.request_poller.unregister(self.request_sock)
        self.request_sock.send(common.json_rpc_dumps(request))

        if request.id is None: return # We don't get a response for notifications

        self.logger.debug("-.- Client waiting for response from {method} "
                       "on {endpoint}".format(method=request.method,
                           endpoint=self.endpoint,
                           params=pprint.pformat(request.params)))
        self.request_poller.register(self.request_sock, zmq.POLLIN)
        if not self.request_poller.poll(self.timeout):
            self._reconnect_socket() # Drop outgoing message
            raise TimeoutError("Timed out while getting response to {method} on "
                    "{endpoint}".format(method=request.method,
                        endpoint=self.endpoint))

        self.request_poller.unregister(self.request_sock)
        response = common.json_rpc_loads(self.request_sock.recv())

        if request.id != response.id:
            raise ValueError("Received out-of-order response")
        if not isinstance(response, common.Response):
            raise ValueError("Received a non-response")
        if response.is_error:
            raise response.error_exception(self.error_code_exceptions)

        self.logger.debug("<_< Client received from call of \"{method}\""
                          " on {endpoint}:\n  {result}".format(
                              method=request.method,
                              endpoint=self.endpoint,
                              result=pprint.pformat(response.result)))
        return response.result

    def get_request_method(self, method, notify=False):
        return self.request_method_class(method, client=self, notify=notify)

    def __getattr__(self, method):
        return self.get_request_method(method)


class NotifierProxy(object):

    def __init__(self, client):
        self.client = client

    def __getattr__(self, method):
        return self.client.get_request_method(method, notify=True)


class RPCNotifierClient(RPCClient):

    default_socket_type = zmq.DEALER


class NotifierOnlyPushClient(RPCClient):

    default_socket_type = zmq.PUSH


class SubscriptionClient(RPCNotifierClient, threading.Thread):

    on_notification = None
    should_stop = False
    poll_timeout = 1000 # milliseconds

    def __init__(self, *args, **kwargs):
        super(SubscriptionClient, self).__init__(*args, **kwargs)
        self.request_sock = self.context.socket(zmq.PAIR)
        self.request_sock_endpoint = \
                "inproc://jsonrpc2-subscription-client-%x" % id(self)
        self.request_sock.bind(self.request_sock_endpoint)

    def run(self):
        poller = zmq.Poller()
        thread_pair_sock = self.context.socket(zmq.PAIR)
        thread_pair_sock.connect(self.request_sock_endpoint)
        poller.register(thread_pair_sock, zmq.POLLIN)
        poller.register(self.socket, zmq.POLLIN)
        request_id = None

        while not self.should_stop:
            socks = dict(poller.poll(self.poll_timeout))
            if thread_pair_sock in socks and \
                    socks[thread_pair_sock] == zmq.POLLIN:
                msg = common.json_rpc_loads(thread_pair_sock.recv())
                request_id = msg.id
                self.socket.send(json_rpc_dumps(msg))

            if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                msg = common.json_rpc_loads(self.socket.recv())
                if msg.id and msg.id == request_id:
                    thread_pair_sock.send(json_rpc_dumps(msg))
                    request_id = None
                elif not msg.id and self.on_notification:
                    self.on_notification(msg)

    def stop(self):
        self.should_stop = True

