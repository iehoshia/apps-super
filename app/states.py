#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from re import compile

# States of mainwindow
STATES = {
    'add': {
        'button': 'button_accept',
        're': compile(r'^(\*[0-9]*|[0-9]+)$|-|/|\*[0-9]*[.]*'),
    },
    'accept': {
        'button': 'button_cash',
        're': compile(r'^[0-9]+$'),
    },
    'cash': {
        'button': None,
        're': compile(r'^[0-9]+(,[0-9]{,2})?$')
    },
    'paid': {
        'button': None,
        're': compile(r'^(\*[0-9]*|[0-9]+)$'),
    },
    'cancel': {
        'button': None,
        're': compile(r'^(\*[0-9]*|[0-9]+)$'),
    },
    'disabled': {
        'button': None,
        're': compile(r'^(\*[0-9]*|[0-9]+)$'),
    },
}

RE_SIGN = {
    'quantity': compile(r'\d+|\.\d+|\d+\.'),
}
