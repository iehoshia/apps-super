# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext
import os
import subprocess
import tempfile
import re
import logging
import unicodedata
import colorsys
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus
from functools import wraps
from neox.commons.config import CONFIG
import sys
import webbrowser
import traceback
import neox.commons.rpc as rpc
import socket
import _thread
from string import Template
from functools import partial
import shlex
try:
    import ssl
except ImportError:
    ssl = None
from threading import Lock
from neox import __version__
from neox.commons.exceptions import EfficaServerError, EfficaError

from PyQt5.QtWidgets import (QDialogButtonBox, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFrame, QLabel, QVBoxLayout)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

__all__ = ["JsonrpcProxy", "Login", "Logout", "RPCException",
    "RPCProgress", "RPCExecute", "RPCContextReload",
    "ErrorDialog"]

_ = gettext.gettext
logger = logging.getLogger(__name__)
_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')

current_dir = os.path.dirname(__file__)
current_dir = os.path.dirname(current_dir)

def get_icon(name):
    file_icon = name if name else 'fork'
    path_icon = os.path.join(current_dir, 'share', file_icon + '.svg')
    _icon = QIcon(path_icon)
    return _icon


def test_server_version(host, port):
    version = rpc.server_version(host, port)
    if not version:
        return False
    return version.split('.')[:2] == __version__.split('.')[:2]


def slugify(value):
    if not isinstance(value, str):
        value = value.decode('utf-8')
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = value.decode('utf-8')
    value = _slugify_strip_re.sub('', value).strip().lower()
    return _slugify_hyphenate_re.sub('-', value)


def file_open(filename, type, direct_print=False):
    def save():
        pass

    name = filename.split('.')

    if 'odt' in name:
        direct_print = False

    if os.name == 'nt':
        operation = 'open'
        if direct_print:
            operation = 'print'
        try:
            os.startfile(os.path.normpath(filename), operation)
        except WindowsError:
            save()
    elif sys.platform == 'darwin':
        try:
            subprocess.Popen(['/usr/bin/open', filename])
        except OSError:
            save()
    else:
        if direct_print:
            try:
                subprocess.Popen(['lp', filename])
            except:
                direct_print = False

        if not direct_print:
            try:
                subprocess.Popen(['xdg-open', filename])
            except OSError:
                pass

def to_xml(string):
    return string.replace('&', '&amp;'
        ).replace('<', '&lt;').replace('>', '&gt;')


PLOCK = Lock()


def process_exception(exception, *args, **kwargs):
    #from .domain_parser import DomainParser

    rpc_execute = kwargs.get('rpc_execute', rpc.execute)

    if isinstance(exception, EfficaServerError):
        if exception.faultCode == 'UserWarning':
            name, msg, description = exception.args
            print("name, msg, description", name, msg, description)
            res = userwarning(description, msg)
            if res in ('always', 'ok'):
                RPCExecute('model', 'res.user.warning', 'create', [{
                            'user': rpc._USER,
                            'name': name,
                            'always': (res == 'always'),
                            }],
                    process_exception=False)
                return rpc_execute(*args)
        elif exception.faultCode == 'UserError':
            msg, description, domain = exception.args
            #if domain:
            #    domain, fields = domain
            #    domain_parser = DomainParser(fields)
            #    if domain_parser.stringable(domain):
            #        description += '\n' + domain_parser.string(domain)
            print("description in isinstance", description, msg, domain)
            warning(description, msg)
        elif exception.faultCode == str(int(HTTPStatus.UNAUTHORIZED)):
            from neox.commons.frontwindow import FrontWindow
            if PLOCK.acquire(False):
                try:
                    Login()
                except EfficaError as exception:
                    if exception.faultCode == 'QueryCanceled':
                        FrontWindow().on_quit()
                    raise
                finally:
                    PLOCK.release()
                if args:
                    return rpc_execute(*args)
        else:
            error(exception, exception.faultString)
            print("exception in process_exception",
                exception,
                exception.faultString,
                traceback.format_exc()
                )
    else:
        print("exception in isinstance", exception, traceback.format_exc())
        #error(exception, traceback.format_exc())
    print("exception in RPCException",exception,
        traceback.format_exc())
    #raise RPCException(exception)

class JsonrpcProxy(object):
    'Proxy for function call for JSON-RPC'

    def __init__(self, name, config, type='model'):
        super(JsonrpcProxy, self).__init__()
        self._config = config
        print("config in JsonrpcProxy",config)
        self._object = getattr(config.connection, '%s.%s' % (type, name))
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return partial(
            getattr(self._object, name),
            self._config.user_id, self._config.session
        )

    def ping(self):
        return True

class Login(object):
    def __init__(self, url=None,):# func=rpc.login):

        self.connection = None
        self.CONNECTION = None
        self.session = None
        self.user_id = None

        parameters = {"password":"ADMIN123"}
        while True:

            try:
                self.connection, self.CONNECTION, \
                    self.session, self._USER = rpc.login(parameters)

            except EfficaServerError as exception:
                if exception.faultCode == str(int(HTTPStatus.UNAUTHORIZED)):
                    parameters.clear()
                    continue
                if exception.faultCode != 'LoginException':
                    raise
                name, message, _type = exception.args
                value = getattr(self, 'get_%s' % _type)(message)
                if value is None:
                    raise EfficaError('QueryCanceled')
                parameters[name] = value
                continue
            else:
                return

    @classmethod
    def get_char(cls, message):
        pass
        #return ask(message)

    @classmethod
    def get_password(cls, message):
        pass
        #return ask(message, visibility=False)

    def get_proxy(self, name, type='model'):
        'Return Proxy class'
        return JsonrpcProxy(name, self, type=type)

    def get_proxy_methods(self, name, type='model'):
        'Return list of methods'
        object_ = '%s.%s' % (type, name)
        return [x[len(object_) + 1:]
                for x in self.server.system.listMethods(None, None)
                if x.startswith(object_)
                and '.' not in x[len(object_) + 1:]]

class Logout:
    def __init__(self):
        try:
            rpc.logout()
        except EfficaServerError:
            pass

class RPCException(Exception):

    def __init__(self, exception):
        super(RPCException, self).__init__(exception)
        self.exception = exception


class RPCProgress(object):

    def __init__(self, method, args):
        self.method = method
        self.args = args
        self.parent = None
        self.res = None
        self.error = False
        self.exception = None

    def start(self):
        try:
            self.res = getattr(rpc, self.method)(*self.args)
        except Exception as exception:
            self.error = True
            self.res = False
            self.exception = exception
        else:
            if not self.res:
                self.error = True
        if self.callback:
            # Post to GTK queue to be run by the main thread
            #GLib.idle_add(self.process)
            pass
        return True

    def run(self, process_exception_p=True, callback=None):
        self.process_exception_p = process_exception_p
        self.callback = callback

        if callback:
            # Parent is only useful if it is asynchronous
            # otherwise the cursor is not updated.
            #self.parent = get_toplevel_window()
            #window = self.parent.get_window()
            #if window:
                #display = window.get_display()
                #watch = Gdk.Cursor.new_for_display(
                #    display, Gdk.CursorType.WATCH)
                #window.set_cursor(watch)
            _thread.start_new_thread(self.start, ())
            return
        else:
            self.start()
            return self.process()

    def process(self):
        #if self.parent and self.parent.get_window():
        #    self.parent.get_window().set_cursor(None)

        if self.exception and self.process_exception_p:
            def rpc_execute(*args):
                return RPCProgress('execute', args).run(
                    self.process_exception_p, self.callback)
            try:
                return process_exception(
                    self.exception, *self.args, rpc_execute=rpc_execute)
            except RPCException as exception:
                self.exception = exception

        def return_():
            if self.exception:
                raise self.exception
            else:
                return self.res

        if self.callback:
            self.callback(return_)
        else:
            return return_()

def RPCExecute(*args, **kwargs):
    rpc_context = rpc.CONTEXT.copy()
    if kwargs.get('context'):
        rpc_context.update(kwargs['context'])
    args = args + (rpc_context,)
    process_exception = kwargs.get('process_exception', True)
    callback = kwargs.get('callback')
    return RPCProgress('execute', args).run(process_exception, callback)

def RPCContextReload(callback=None):
    def update(context):
        rpc.context_reset()
        try:
            rpc.CONTEXT.update(context())
        except RPCException:
            pass
        if callback:
            callback()
    # Use RPCProgress to not send rpc.CONTEXT
    context = RPCProgress(
        'execute',
        ('model', 'res.user', 'get_preferences', True, {})).run(
            True, update if callback else None)
    if not callback:
        rpc.context_reset()
        rpc.CONTEXT.update(context)

def filter_domain(domain):
    '''
    Return the biggest subset of domain with only AND operator
    '''
    res = []
    for arg in domain:
        if isinstance(arg, str):
            if arg == 'OR':
                res = []
                break
            continue
        if isinstance(arg, tuple):
            res.append(arg)
        elif isinstance(arg, list):
            res.extend(filter_domain(arg))
    return res


def timezoned_date(date, reverse=False):
    try:
        from dateutil.tz.win import tzwinlocal as tzlocal
    except ImportError:
        from dateutil.tz import tzlocal
    from dateutil.tz import tzutc

    lzone = tzlocal()
    szone = tzutc()
    if reverse:
        lzone, szone = szone, lzone
    return date.replace(tzinfo=szone).astimezone(lzone).replace(tzinfo=None)


def untimezoned_date(date):
    return timezoned_date(date, reverse=True)


def humanize(size):
    for x in ('bytes', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if size < 1000:
            return '%3.1f%s' % (size, x)
        size /= 1000.0


def get_hostname(netloc):
    if '[' in netloc and ']' in netloc:
        hostname = netloc.split(']')[0][1:]
    elif ':' in netloc:
        hostname = netloc.split(':')[0]
    else:
        hostname = netloc
    return hostname.strip()


def get_port(netloc):
    netloc = netloc.split(']')[-1]
    if ':' in netloc:
        try:
            return int(netloc.split(':')[1])
        except ValueError:
            pass
    return 8000

def resize_pixbuf(pixbuf, width, height):
    img_height = pixbuf.get_height()
    print("img_height", img_height)
    height = min(img_height, height) if height != -1 else img_height
    img_width = pixbuf.get_width()
    width = min(img_width, width) if width != -1 else img_width

    if img_width / width < img_height / height:
        width = float(img_width) / float(img_height) * float(height)
    else:
        height = float(img_height) / float(img_width) * float(width)

    return pixbuf.scale_simple(
        int(width), int(height), GdkPixbuf.InterpType.BILINEAR)


def _data2pixbuf(data, width=None, height=None):
    loader = GdkPixbuf.PixbufLoader()
    if width and height:
        loader.set_size(width, height)
    loader.write(data)
    loader.close()
    return loader.get_pixbuf()


def data2pixbuf(data, width=None, height=None):
    if data:
        try:
            return _data2pixbuf(data, width, height)
        except GLib.GError:
            pass

def apply_label_attributes(label, readonly, required):
    if not readonly:
        widget_class(label, 'editable', True)
        widget_class(label, 'required', required)
    else:
        widget_class(label, 'editable', False)
        widget_class(label, 'required', False)


def ellipsize(string, length):
    if len(string) <= length:
        return string
    ellipsis = _('...')
    return string[:length - len(ellipsis)] + ellipsis



def date_format(format_=None):
    return format_ or rpc.CONTEXT.get('locale', {}).get('date', '%x')


def idle_add(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        GLib.idle_add(func, *args, **kwargs)
    return wrapper

