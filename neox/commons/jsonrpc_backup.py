
import sys
import ssl
from decimal import Decimal
import datetime
import socket
import gzip
import hashlib
import base64
import threading
import errno
from functools import partial
from contextlib import contextmanager
import string
import ssl

from xmlrpc import client

try:
    import simplejson as json
except ImportError:
    import json

try:
    import http.client as httplib
except:
    import httplib

# import xmlrpc.client as xmlrpclib
# import simplejson as json
# import http.client as httplib
#import StringIO
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

__all__ = ["ResponseError", "Fault", "ProtocolError", "Transport",
    "ServerProxy", "ServerPool", ]

PYTHON_VERSION = str(sys.version_info[0])
CONNECT_TIMEOUT = 5
DEFAULT_TIMEOUT = 0


class Fault(client.Fault):

    def __init__(self, faultCode, faultString='', **extra):
        super(Fault, self).__init__(faultCode, faultString, **extra)
        self.args = faultString

    def __str__(self):
        return str(self.faultCode)


class ProtocolError(client.ProtocolError):
    pass

class ResponseError(client.ResponseError):
    pass

def object_hook(dct):
    if '__class__' in dct:
        if dct['__class__'] == 'datetime':
            return datetime.datetime(dct['year'], dct['month'], dct['day'],
                dct['hour'], dct['minute'], dct['second'], dct['microsecond'])
        elif dct['__class__'] == 'date':
            return datetime.date(dct['year'], dct['month'], dct['day'])
        elif dct['__class__'] == 'time':
            return datetime.time(dct['hour'], dct['minute'], dct['second'],
                dct['microsecond'])
        elif dct['__class__'] == 'timedelta':
            return datetime.timedelta(seconds=dct['seconds'])
        elif dct['__class__'] == 'bytes':
            cast = bytearray if bytes == str else bytes
            return cast(base64.decodestring(dct['base64']))
        elif dct['__class__'] == 'Decimal':
            return Decimal(dct['decimal'])
    return dct


class JSONEncoder(json.JSONEncoder):

    def __init__(self, *args, **kwargs):
        super(JSONEncoder, self).__init__(*args, **kwargs)
        # Force to use our custom decimal with simplejson
        self.use_decimal = False

    def default(self, obj):
        if isinstance(obj, datetime.date):
            if isinstance(obj, datetime.datetime):
                return {'__class__': 'datetime',
                        'year': obj.year,
                        'month': obj.month,
                        'day': obj.day,
                        'hour': obj.hour,
                        'minute': obj.minute,
                        'second': obj.second,
                        'microsecond': obj.microsecond,
                        }
            return {'__class__': 'date',
                    'year': obj.year,
                    'month': obj.month,
                    'day': obj.day,
                    }
        elif isinstance(obj, datetime.time):
            return {'__class__': 'time',
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond,
                }
        elif isinstance(obj, datetime.timedelta):
            return {'__class__': 'timedelta',
                'seconds': obj.total_seconds(),
                }
        elif isinstance(obj, memoryview):
            return {'__class__': 'buffer',
                'base64': base64.encodestring(obj),
                }
        elif isinstance(obj, Decimal):
            return {'__class__': 'Decimal',
                'decimal': str(obj),
                }
        return super(JSONEncoder, self).default(obj)


class JSONParser(object):

    def __init__(self, target):
        self.__targer = target

    def feed(self, data):
        self.__targer.feed(data)

    def close(self):
        pass


class JSONUnmarshaller(object):
    def __init__(self):
        self.data = []

    def feed(self, data):
        self.data.append(data)

    def close(self):
        # Convert data bytes to string
        data = self.data[0].decode('utf-8')
        return json.loads(data, object_hook=object_hook)


class Transport(client.SafeTransport, client.Transport):

    accept_gzip_encoding = True
    encode_threshold = 1400  # common MTU

    def __init__(self, fingerprints=None, ca_certs=None, session=None):
        client.Transport.__init__(self)
        self._connection = (None, None)
        self.__fingerprints = fingerprints
        self.__ca_certs = ca_certs
        self.session = session

    def getparser(self):
        target = JSONUnmarshaller()
        parser = JSONParser(target)
        return parser, target

    def get_host_info(self, host):
        host, extra_headers, x509 = client.Transport.get_host_info(
            self, host)
        if extra_headers is None:
            extra_headers = []
        if self.session:
            auth = base64.encodestring(self.session)
            auth = string.join(string.split(auth), "")  # get rid of whitespace
            extra_headers.append(
                ('Authorization', 'Session ' + auth),
                )
        extra_headers.append(('Connection', 'keep-alive'))
        extra_headers.append(('Content-Type', 'text/json'))
        return host, extra_headers, x509

    def send_content(self, connection, request_body):
        if (self.encode_threshold is not None and
                self.encode_threshold < len(request_body) and
                gzip):
            connection.putheader("Content-Encoding", "gzip")
            request_body = gzip.compress(request_body)
        connection.putheader("Content-Length", str(len(request_body)))
        connection.endheaders()
        if request_body:
            if PYTHON_VERSION == '3':
                request_body = bytes(request_body, 'UTF-8')
            connection.send(request_body)

    def single_request(self, host, handler, request_body, verbose=False):

        # issue XML-RPC request
        try:
            http_conn = self.send_request(host, handler, request_body, verbose)
            resp = http_conn.getresponse()
            if resp.status == 200:
                self.verbose = verbose
                return self.parse_response(resp)

        except Fault:
            raise
        except Exception:
            #All unexpected errors leave connection in
            # a strange state, so we clear it.
            self.close()
            raise

        #We got an error response.
        #Discard any response data and raise exception
        if resp.getheader("content-length", ""):
            resp.read()
        raise ProtocolError(
            host + handler,
            resp.status, resp.reason,
            dict(resp.getheaders())
            )

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        host, self._extra_headers, x509 = self.get_host_info(host)
        ca_certs = self.__ca_certs
        cert_reqs = ssl.CERT_REQUIRED if ca_certs else ssl.CERT_NONE

        class HTTPSConnection(httplib.HTTPSConnection):

            def connect(self):
                sock = socket.create_connection((self.host, self.port),
                    self.timeout)
                if self._tunnel_host:
                    self.sock = sock
                    self._tunnel()
                self.sock = ssl.wrap_socket(sock, self.key_file,
                    self.cert_file, ca_certs=ca_certs, cert_reqs=cert_reqs)

        def http_connection():
            self._connection = host, httplib.HTTPConnection(host,
                timeout=CONNECT_TIMEOUT)
            self._connection[1].connect()
            sock = self._connection[1].sock
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        def https_connection():
            self._connection = host, HTTPSConnection(host,
                timeout=CONNECT_TIMEOUT)
            try:
                self._connection[1].connect()
                sock = self._connection[1].sock
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                try:
                    peercert = sock.getpeercert(True)
                except socket.error:
                    peercert = None

                def format_hash(value):
                    return reduce(lambda x, y: x + y[1].upper() +
                        ((y[0] % 2 and y[0] + 1 < len(value)) and ':' or ''),
                        enumerate(value), '')
                return format_hash(hashlib.sha1(peercert).hexdigest())
            #except ssl.SSLError:
            #    http_connection()
            except (socket.error, ssl.SSLError): #, ssl.CertificateError):
                if allow_http:
                    http_connection()
                else:
                    raise

        fingerprint = ''
        if self.__fingerprints is not None and host in self.__fingerprints:
            if self.__fingerprints[host]:
                fingerprint = https_connection()
            else:
                http_connection()
        else:
            fingerprint = https_connection(allow_http=True)

        if self.__fingerprints is not None:
            self.__fingerprints[host] = fingerprint
            #if host in self.__fingerprints and self.__fingerprints[host]:
            #    if self.__fingerprints[host] != fingerprint:
            #        self.close()
            #        raise ssl.SSLError('BadFingerprint')
            #else:
            #    self.__fingerprints[host] = fingerprint
        self._connection[1].timeout = DEFAULT_TIMEOUT
        self._connection[1].sock.settimeout(DEFAULT_TIMEOUT)
        return self._connection[1]


class ServerProxy(client.ServerProxy):
    __id = 0

    def __init__(self, host, port, database='', verbose=0,
            fingerprints=None, ca_certs=None, session=None):
        self.__host = '%s:%s' % (host, port)
        if database:
            self.__handler = '/%s/' % database
        else:
            self.__handler = '/'
        self.__transport = Transport(fingerprints, ca_certs, session)
        self.__verbose = verbose

    def __request(self, methodname, params):
        self.__id += 1
        id_ = self.__id
        request = json.dumps({
                'id': id_,
                'method': methodname,
                'params': params,
                }, cls=JSONEncoder)
        try:
            response = self.__transport.request(
                self.__host,
                self.__handler,
                request,
                verbose=self.__verbose
                )
        except (socket.error, httplib.HTTPException) as v:
            if (isinstance(v, socket.error)
                    and v.args[0] == errno.EPIPE):
                raise
            # try one more time
            self.__transport.close()
            response = self.__transport.request(
                self.__host,
                self.__handler,
                request,
                verbose=self.__verbose
                )
        except:
            self.__transport.close()
            raise
        if response['id'] != id_:
            raise ResponseError('Invalid response id (%s) excpected %s' %
                (response['id'], id_))
        if response.get('error'):
            raise Fault(*response['error'])
        if self.__cache and response.get('cache'):
            self.__cache.set(
                methodname, dumper(params), response['cache'],
                response['result'])
        return response['result']

    def close(self):
        self.__transport.close()

    @property
    def ssl(self):
        return isinstance(self.__transport.make_connection(self.__host),
            httplib.HTTPSConnection)


class ServerPool(object):

    def __init__(self, *args, **kwargs):
        self.ServerProxy = partial(ServerProxy, *args, **kwargs)
        self._lock = threading.Lock()
        self._pool = []
        self._used = {}
        self.session = None

    def getconn(self):
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
            else:
                conn = self.ServerProxy()
            self._used[id(conn)] = conn
            return conn

    def putconn(self, conn):
        with self._lock:
            self._pool.append(conn)
            del self._used[id(conn)]

    def close(self):
        with self._lock:
            for conn in self._pool + self._used.values():
                conn.close()

    @property
    def ssl(self):
        for conn in self._pool + self._used.values():
            return conn.ssl
        return False

    def __request(self, methodname, params):
        # call a method on the remote server

        request = dumps(params, methodname, encoding=self.__encoding,
                        allow_none=self.__allow_none).encode(self.__encoding, 'xmlcharrefreplace')

        response = self.__transport.request(
            self.__host,
            self.__handler,
            request,
            verbose=self.__verbose
            )

        if len(response) == 1:
            response = response[0]
        return response

    @contextmanager
    def __call__(self):
        conn = self.getconn()
        yield conn
        self.putconn(conn)


if __name__ == "__main__":
    # For testing purposes
    connection = ServerProxy('127.0.0.1', '8000', 'DEMO41')
    result = connection.common.server.version()
    print(result)
    conn = connection()
    res = connection.common.db.login('admin', 'aa')
    print(res)
    tx = connection.common.model.res.user.get_preferences(res[0], res[1], True, {})
