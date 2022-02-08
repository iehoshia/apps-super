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
import urllib.request
import urllib.error
import urllib.parse as urlparse
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
from neox.commons import bus
from neox.commons.jsonrpc import ServerProxy, ServerPool
from neox.commons.dialogs import QuickDialog
from neox.commons.forms import GridForm
from PyQt5.QtWidgets import (QDialogButtonBox, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFrame, QLabel, QVBoxLayout)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt

CONNECTION = None
_USER = None
_USERNAME = ''
_HOST = ''
_PORT = None
_DATABASE = ''
CONTEXT = {}
DIALOG_REPLY_NO = 0

def context_reset():
    CONTEXT.clear()
    CONTEXT['client'] = bus.ID

__all__ = ["JsonrpcProxy", "RPCException",
    "RPCProgress", "RPCExecute", "RPCContextReload",]

def get_active_window():
    from app.mainwindow import MainWindow
    return Main().get_active_window()

context_reset()

def server_version(host, port):
    try:
        connection = ServerProxy(host, port)
        logging.getLogger(__name__).info(
            'common.server.version(None, None)')
        result = connection.common.server.version()
        logging.getLogger(__name__).debug(repr(result))
        return result
    except (EfficaServerError, socket.error) as e:
        logging.getLogger(__name__).error(e)
        return None

def login(url=None):
    global CONNECTION, _USER

    if url==None:
        return
        hostname = "capybara.effica.io" #common.get_hostname(host)
        port = 8000 #common.get_port(host)
        database = "capybaradb"  #CONFIG['login.db']
        username = "admin" #CONFIG['login.login']
        language = "es" #CONFIG['client.lang']
        parameters = {"password":"crispa7"}
    else:
        url = urlparse.urlparse(url)
        hostname = url.hostname
        port =  url.port
        database = url.path[1:]
        username = url.username
        password = url.password
        language = "es" # CONFIG['client.lang']
        parameters = {"password":password}
    connection = ServerProxy(hostname, port, database)
    result = connection.common.db.login(username, parameters, language)
    _USER = result[0]
    session = ':'.join(map(str, [username] + result))
    if CONNECTION is not None:
        CONNECTION.close()
    CONNECTION = ServerPool(
        hostname, port, database,
        session=session, ) #cache=not CONFIG['dev'])
    bus.listen(CONNECTION)
    return CONNECTION, session

def logout():
    global CONNECTION, _USER
    if CONNECTION is not None:
        try:
            with CONNECTION() as conn:
                conn.common.db.logout()
        except (Fault, socket.error, http.client.CannotSendRequest):
            pass
        CONNECTION.close()
        CONNECTION = None
    _USER = None

def _execute(blocking, *args):
    global CONNECTION, _USER
    if CONNECTION is None:
        raise EfficaServerError('403')
    try:
        name = '.'.join(args[:3])
        args = args[3:]
        #logging.getLogger(__name__).info('%s%s' % (name, args))
        with CONNECTION() as conn:
            result = getattr(conn, name)(*args)
    except (http.client.CannotSendRequest, socket.error) as exception:
        raise EfficaServerUnavailable(*exception.args)
    logging.getLogger(__name__).debug(repr(result))
    return result

def execute(*args):
    return _execute(True, *args)

def execute_nonblocking(*args):
    return _execute(False, *args)

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
            msg_label = QLabel()
            field_password.setText(msg)
            description_label = QLabel
            description_label.setText(description)
            main = get_active_window()
            res = QuickDialog(main, 'action',
                string=name,
                widgets=[msg_label, description_label],
            )._exec_()
            if res != DIALOG_REPLY_NO:
                RPCExecute('model', 'res.user.warning', 'create', [{
                            'user': rpc._USER,
                            'name': name,
                            'always': (res == 'always'),
                            }],
                    process_exception=False)
                return rpc_execute(*args)
        elif exception.faultCode == 'UserError':
            msg, description, domain = exception.args
            if domain:
                domain, fields = domain
                domain_parser = DomainParser(fields)
                if domain_parser.stringable(domain):
                    description += '\n' + domain_parser.string(domain)
            msg_label = QLabel()
            field_password.setText(msg)
            description_label = QLabel
            description_label.setText(description)
            main = get_active_window()
            res = QuickDialog(main, 'action',
                string=main.tr('User Error'),
                widgets=[msg_label, description_label],
            )._exec_()
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
            msg_label = QLabel()
            field_password.setText(msg)
            description_label = QLabel
            description_label.setText(description)
            main = get_active_window()
            res = QuickDialog(main, 'action',
                string=main.tr('Unhandled exception'),
                widgets=[msg_label, description_label],
            )._exec_()
            #error(exception, exception.faultString)
    else:
        #error(exception, traceback.format_exc())
        print("exception", exception, traceback.format_exc())
    raise RPCException(exception)

def clear_cache(prefix=None):
    if CONNECTION:
        CONNECTION.clear_cache(prefix)



class RPCException(Exception):

    def __init__(self, exception):
        super(RPCException, self).__init__(exception)
        self.exception = exception

class RPCProgress(object):

    def __init__(self, conn, method, args):
        self.method = method
        self.args = args
        self.conn = conn
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
            self.parent = get_active_window()
            #window = self.parent.get_window()
            if self.parent:
                self.parent._clear_context()
            _thread.start_new_thread(self.start, ())
            return
        else:
            self.start()
            return self.process()

    def process(self):
        if self.exception and self.process_exception_p:
            def rpc_execute(*args):
                return RPCProgress('execute', args).run(
                    self.process_exception_p)
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

class RPCException(Exception):

    def __init__(self, exception):
        super(RPCException, self).__init__(exception)
        self.exception = exception

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


#error = QuickDialog()

class UserWarningDialog(QuickDialog):

    def build_dialog(self, *args, **kwargs):
        dialog = super().build_dialog(*args, **kwargs)
        self.always = Gtk.CheckButton(label=_('Always ignore this warning.'))
        alignment = Gtk.Alignment(xalign=0, yalign=0.5)
        alignment.add(self.always)
        dialog.vbox.pack_start(alignment, expand=True, fill=False, padding=0)
        label = Gtk.Label(
            label=_('Do you want to proceed?'), halign=Gtk.Align.END)
        dialog.vbox.pack_start(label, expand=True, fill=True, padding=0)
        return dialog

    def process_response(self, response):
        if response == Gtk.ResponseType.YES:
            if self.always.get_active():
                return 'always'
            return 'ok'
        return 'cancel'

    def __call__(self, message, title):
        return super().__call__(message, title, gtk.BUTTONS_YES_NO)

#def idle_add(func):
#    @wraps(func)
#    def wrapper(*args, **kwargs):
#        GLib.idle_add(func, *args, **kwargs)
#        QTimer().singleShot(0, self.my_method)
#    return wrapper

#userwarning = UserWarningDialog()