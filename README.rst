========================
JSON-RPC 2.0 Over ZeroMQ
========================

Written by `Dan Brown <mailto:dan@danwb.net>`_. See the the LICENSE file for licensing information.

This is a library in Python enabling `JSON-RPC 2.0 <http://www.jsonrpc.org/spec.html>`_ over `ZeroMQ <http://zeromq.org/>`_. It includes support for both clients and servers.

This is packaged as a standard Python project, so just install using ``python setup.py install``, or with `pip <http://www.pip-installer.org/>`_.

Servers
-------

::

    from jsonrpc2_zeromq import RPCServer

    class EchoServer(RPCServer):
        
        def handle_echo_method(self, msg):
            return msg

    s = EchoServer("tcp://127.0.0.1:57570")
    s.run()

This creates a server listening on a ZeroMQ REP socket – so only methods are allowed, not notifications. See the ``RPCNotificationServer`` as well, which will listen on a ROUTER socket and allow notifications.

Each server is a Python ``Thread``, so the call to ``run()`` can be replaced by ``start()`` to have it running in a background thread.

Clients
-------

::

    from jsonrpc2_zeromq import RPCClient

    c = RPCClient("tcp://127.0.0.1:57570")
    print c.echo("Echo?")

    # Assuming the above compliant server, should print "Echo?"

There are various classes, assuming different JSON-RPC 2.0 and ZeroMQ characteristics. The above, for example, will connect a REQ socket to the given endpoint.

Notifications
-------------

Given a server that accepts notifications::

    from jsonrpc2_zeromq import RPCNotificationServer

    class EventReceiver(RPCNotificationServer):
        
        def handle_event_method(self, event_type, event_data):
            print "Got event!\nType: {0}\nData: {1}\n".format(event_type, event_data)

    s = EventReceiver("tcp://127.0.0.1:60666")
    s.run()

You can then send notifications thus::

    from jsonrpc2_zeromq import RPCNotifierClient

    c = RPCNotifierClient("tcp://127.0.0.1:60666")
    c.notify.event('birthday!', 'yours!')

Also included are ``NotificationOnlyPullServer`` and ``NotifierOnlyPushClient`` which are designed for sending only notifications one-way over PUSH and PULL sockets.

Logging
-------

The `standard Python logging module <http://docs.python.org/library/logging.html>`_ is used for logging. It doesn't output anything by default. Either retrieve the built-in library logger with ``logging.getLogger('jsonrpc2_zeromq')`` or pass your own ``Logger`` instance into a client or server's ``__init__`` with the ``logger`` keyword argument.

Currently there are some helpful messages outputted at the ``DEBUG`` level, server exceptions on ``ERROR``, and a server start message on ``INFO``.

Testing
-------

Tests are included. Install `nose <http://readthedocs.org/docs/nose/>`_ and just run ``nosetests`` in the project root.
