# Part of the jsonrpc2-zeromq-python project.
# (c) 2012 Wireless Innovation Ltd, All Rights Reserved.
# Please see the LICENSE file in the root of this project for license
# information.

import threading

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
                       "with params:\n{params}".format(method=request.method,
                           endpoint=self.endpoint,
                           params=common.debug_log_object_dump(request.params)))

        self.request_poller.register(self.request_sock, zmq.POLLOUT)
        if not self.request_poller.poll(self.timeout):
            self.on_timeout(request)
            raise TimeoutError("Timed out while waiting to call {method} on "
                    "{endpoint}".format(method=request.method,
                        endpoint=self.endpoint))

        self.request_poller.unregister(self.request_sock)
        self.request_sock.send(common.json_rpc_dumps(request))

        if request.id is None: return # We don't get a response for notifications

        self.logger.debug("-.- Client waiting for response from {method} "
                       "on {endpoint}".format(method=request.method,
                           endpoint=self.endpoint,
                           params=common.debug_log_object_dump(request.params)))
        self.request_poller.register(self.request_sock, zmq.POLLIN)
        if not self.request_poller.poll(self.timeout):
            self.on_timeout(request)
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
                          " on {endpoint}:\n{result}".format(
                              method=request.method,
                              endpoint=self.endpoint,
                              result=common.debug_log_object_dump(response.result)))
        return response.result

    def on_timeout(self, req):
        self._reconnect_socket() # Drop outgoing message

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


class NotificationReceiverClient(RPCNotifierClient, threading.Thread):

    on_notification = None
    should_stop = False
    poll_timeout = 1000 # milliseconds

    def __init__(self, *args, **kwargs):
        super(NotificationReceiverClient, self).__init__(*args, **kwargs)

        # We use a PAIR socket pair to communicate between the calling
        # thread and the thread (this class) receiving subscription events.
        # RPCServer thinks it's talking to the server, but now it's actually
        # talking to this thread.
        self.request_sock = self.context.socket(zmq.PAIR)
        self.request_sock_endpoint = \
                "inproc://jsonrpc2-subscription-client-%x" % id(self)
        self.request_sock.bind(self.request_sock_endpoint)

        # This is run automatically, as RPC-style blocking requests will not
        # get a response otherwise.
        self.start()

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
                self.socket.send(common.json_rpc_dumps(msg))

            if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                msg_parts = self.socket.recv_multipart()
                msg = common.json_rpc_loads(msg_parts[-1])
                if msg.id and msg.id == request_id:
                    thread_pair_sock.send(common.json_rpc_dumps(msg))
                    request_id = None
                elif not msg.id:
                    self.logger.debug("<_< Client received notification "
                                      "\"{method}\" "
                                      "from subscription on {endpoint}:\n"
                                      "{result}".format(
                                          endpoint=self.endpoint,
                                          method=msg.method,
                                          result=common.debug_log_object_dump(
                                              msg.params)
                                      ))

                    try:
                        common.handle_request(self,
                                              'handle_{method}_notification',
                                               msg)
                    except common.MethodNotFound:
                        self.logger.warning("v_v Client has no handler for "
                                            "\"{method}\" notification from "
                                            "subscription on {endpoint}".format(
                                                method=msg.method,
                                                endpoint=self.endpoint
                                            ))

    def on_timeout(self, *args, **kwargs):
        self.stop()
        super(NotificationReceiverClient, self).on_timeout(*args, **kwargs)

    def wait_for_notifications(self):
        while self.is_alive():
            try:
                self.join(self.poll_timeout)
            except KeyboardInterrupt:
                break

    def stop(self):
        self.should_stop = True
        self.join()

