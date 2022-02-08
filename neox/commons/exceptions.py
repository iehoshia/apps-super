# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from neox.commons.jsonrpc import Fault

EfficaServerError = Fault

class EfficaServerUnavailable(Exception):
    pass


class EfficaError(Exception):

    def __init__(self, faultCode):
        self.faultCode = faultCode