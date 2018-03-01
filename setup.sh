#!/bin/bash

sudo apt-get install git python-dev python-pip flex bison build-essential alsa-utils -y --no-install-recommends

sudo pip install -v --upgrade pip setuptools
sudo pip install -v --no-cache-dir PyDispatcher Flask Flask-SocketIO flask_uploads gevent psutil python-dispatch eventlet greenlet
