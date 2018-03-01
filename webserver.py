from pydispatch import dispatcher
from wsgiref import handlers

import SocketServer
import eventlet
import logging
import thread
import time
import json
import os

from flask import Flask, render_template, url_for, request, jsonify, g, redirect
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
app.config['SECRET_KEY'] = 'H4114'
socketio = SocketIO(app, async_mode='threading', ping_timeout=30, logger=True, engineio_logger=True)

class WebServer:
    # Start the web server on port 80
    def __init__(self):
        thread.start_new_thread(lambda: socketio.run(app,host='0.0.0.0',port=80,debug=False), ())
        self.socket = socketio

    # Broadcast an event over the socket
    def broadcast(self,id,data):
        with app.app_context():
            try:
                socketio.emit(id,data,broadcast=True)
            except:
                pass

    # Define the routes for our web app's URLs.
    @app.route("/")
    def index():
        return app.send_static_file('index.html')

    # Guess the correct MIME type for static files
    @app.route('/<path:path>')
    def static_proxy(path):
        return app.send_static_file(path)

    # Socket event when a user connects to the web server
    @socketio.on('on_connect')
    def connectEvent(msg):
        dispatcher.send(signal='on_html_connection',data=msg)

    @socketio.on('on disconnect')
    def disconnectEvent():
        print('disconnected')

    @socketio.on('on_call_function')
    def callFunction(data):
        dispatcher.send(signal='call_function',functionName=data['functionName'],arg1=data['arg1'],arg2=data['arg2'])
        
    def shutdown(self):
        global socketio
        socketio.stop()
        socketio.shutdown(socketio.SHUT_RDWR)