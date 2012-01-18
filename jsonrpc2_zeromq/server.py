# Part of the jsonrpc2-zeromq-python project.
# (c) 2012 Wireless Innovation Ltd, All Rights Reserved.
# Please see the LICENSE file in the root of this project for license
# information.

import threading

import zmq

from . import common


def response_from_exception(e, id_=None):
    if not hasattr(e, 'to_response'):
        e = common.ServerError(str(e))
    return e.to_response(id_)


class RPCServer(common.Endpoint, threading.Thread):

    default_socket_type = zmq.REP
    allow_methods = True
    allow_notifications = False

    should_stop = False

    def __init__(self, endpoint, context=None, timeout=1000, socket_type=None,
                 logger=None):
        super(RPCServer, self).__init__(endpoint, socket_type, timeout, context,
                                        logger=logger)
        self.socket = self.context.socket(self.socket_type)
        self.socket.bind(self.endpoint)
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    def stop(self):
        self.should_stop = True

    def run(self):
        self.logger.info("^_^ Server now listening on %s", self.endpoint)
        while not self.should_stop:
            self._handle_one_message()

    def _handle_one_message(self):
        req = client_id = None

        if not self.poller.poll(self.timeout):
            return

        req_parts = self.socket.recv_multipart()
        try:
            if len(req_parts) > 1:
                client_id, req = req_parts[0], req_parts[1:]
                req = ''.join(req)
            else:
                req = req_parts[0]

            try:
                req = common.json_rpc_loads(req)
            except ValueError:
                raise common.ParseError()

            if not isinstance(req, common.Request):
                raise common.InvalidRequest()

            self.logger.debug("<_< Server received {req_type} \"{method}\""
                              " on {endpoint} with params:\n{params}".format(
                                  req_type=("method call" if req.id
                                            else "notification"),
                                  method=req.method, endpoint=self.endpoint,
                                  params=common.debug_log_object_dump(
                                      req.params)))

            if (req.is_method and self.allow_methods) or \
                    (req.is_notification and self.allow_notifications):
                self._handle_method_and_response(client_id, req)

            elif req.is_method and not self.allow_methods and \
                    self.socket.socket_type in (zmq.REP, zmq.ROUTER):
                raise common.InvalidRequest(
                    "Methods not accepted by this server")

            # Cannot return an error for invalid notifications, as the spec
            # forbids it.

        except Exception as e:
            req_id = req.id if req else None
            self._send_response(client_id, req,
                                response_from_exception(e, req_id))
            if not isinstance(e, common.RPCError):
                self.logger.exception("Exception handling message in %s",
                                      self.__class__.__name__)

    def _handle_method_and_response(self, client_id, req):
        result = common.handle_request(self, 'handle_{method}_method', req)
        self._send_response(client_id, req, common.Response(result, None,
                                                            req.id))

    def _send_response(self, client_id, req, resp):
        # Notifications must not return anything
        if req and req.is_notification: return

        debug_msg_parts = [">_> Server sending"]
        debug_msg_parts.append("error" if resp.is_error else "return")
        if req:
            debug_msg_parts.append("from \"{0}\"".format(req.method))
        debug_msg_parts.append("on {0}:\n".format(self.endpoint))
        debug_msg_result = ("{indent}{0} {1}".format(
                resp.error['code'], resp.error['message'],
                        indent=common.debug_log_object_indent)
            if resp.is_error
            else common.debug_log_object_dump(resp.result))

        self.logger.debug(' '.join(debug_msg_parts) + debug_msg_result)

        self.socket.send_multipart(filter(None,
                                          [client_id,
                                           common.json_rpc_dumps(resp)]))


class RPCNotificationServer(RPCServer):

    default_socket_type = zmq.ROUTER
    allow_notifications = True


class NotificationOnlyPullServer(RPCNotificationServer):

    default_socket_type = zmq.PULL
    allow_methods = False

