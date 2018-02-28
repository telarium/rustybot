import os
import socket
import sys
import thread
import eventlet
import logging
import SocketServer
from wsgiref import handlers
from pydispatch import dispatcher
from multiprocessing import Process
from flask import Flask, render_template, url_for, request, g, redirect, session, flash, Response
from flask_socketio import SocketIO, emit

# Patch system modules to be greenthread-friendly
eventlet.monkey_patch()

# Another monkey patch to avoid annoying (and useless?) socket pipe warnings when users disconnect
SocketServer.BaseServer.handle_error = lambda *args, **kwargs: None
handlers.BaseHandler.log_exception = lambda *args, **kwargs: None

# Turn off more annoying log messages that aren't helpful.
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, static_folder='webpage')
app.config['SECRET_KEY'] = os.urandom(12)
socketio = SocketIO(app, async_mode='threading', ping_timeout=30, logger=False, engineio_logger=False)

class WebServer:
    def __init__(self):
        app.adminMode = False

    def start(self,bAdminMode=None):
        app.adminMode = bAdminMode
        thread.start_new_thread(lambda: socketio.run(app,host='0.0.0.0',port=80), ())
        self.socket = socketio

    def shutdown(self):
        global socketio
        socketio.stop()
        socketio.shutdown(socketio.SHUT_RDWR)
        self.socketio = None
        self.server.terminate()
        self.server.join()

    @app.route("/")
    def index():
        return app.send_static_file('index.html'), 200

    @app.errorhandler(404)
    def page_not_found(error):
        return app.send_static_file('index.html'), 200

    @app.route('/', methods=['POST'])
    def do_admin_settings():
        print "GOT IT!"
        print request.method
        if request.method=='POST':
            return ('', 204)

    # Broadcast an event over the socket
    def broadcast(self,id,data):
        with app.app_context():
            try:
                socketio.emit(id,data,broadcast=True)
            except:
                pass

    @app.route('/<path:path>')
    def static_proxy(path):
        # send_static_file will guess the correct MIME typen
        return app.send_static_file(path)

    @socketio.on('onConnect')
    def connectEvent(msg):
        dispatcher.send(signal='connectEvent')