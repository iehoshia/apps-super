import json
import neox.commons.common as common
import neox.commons.rpc as rpc

from decimal import Decimal
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from neox.commons.timeout import timeout


__all__ = ['Modules', 'TrytonTableModel', 'TrytonModel']


class Modules(object):
    'Load/Set target modules on context of mainwindow'

    def __init__(self, parent=None, connection=None):
        self.parent = parent
        self.conn = connection

    def set_models(self, mdict):
        for val in mdict:
            if val:
                fields = val['fields']
                model = TrytonModel(self.conn, val['model'],
                    val['fields'], val.get('methods'))
                setattr(self.parent, val['name'], model)

    def set_model(self, mdict):
        model = TrytonModel(self.conn, mdict['model'],
            mdict['fields'], mdict.get('methods'))
        return model

    def permission_delete(self, target, ctx_groups):
        """ Check if the user has permissions for delete records """
        #FIXME
        return True
        model_data = TrytonModel(self.conn, 'ir.model',
            ('values', 'fs_id'), [])
        groups_ids = model_data.setDomain([
            ('fs_id', '=', target),
        ])
        if groups_ids:
            group_id = eval(groups_ids[0]['values'])[0][1]
            if group_id in ctx_groups:
                return True
        return False

class TrytonTableModel(QAbstractTableModel):

    def __init__(self, connection, model, fields):
        super(TrytonTableModel, self).__init__()
        self._fields = fields
        self._proxy = connection.get_proxy(model)
        self._context = connection.context #with xmlrpc
        self._data = []

    def setDomain(self, domain, order=None):
        self.beginResetModel()
        if domain:
            if order is not None:
                self._data = self._search_read(domain,
                    fields_names=[x['name'] for x in self._fields],
                    order=order)
            else:
                self._data = self._search_read(domain,
                    fields_names=[x['name'] for x in self._fields],
                    order=[('id', 'ASC')])
        else:
            self._data = []
        self.endResetModel()

    def _search_read(self, domain, offset=0, limit=None, order=None,
            fields_names=None):
        if order:
            ids = self._proxy.search(domain, offset, limit, order, self._context)
            records = self._proxy.read(ids, fields_names, self._context)
            rec_dict = {}
            for rec in records:
                rec_dict[rec['id']] = rec
            res = []
            for id_ in ids:
                res.append(rec_dict[id_])
        else:
            res = self._proxy.search_read(domain, offset, limit, order,
                    fields_names, self._context)
        return res

    def appendId(self, idx):
        fields_names = []
        if not idx:
            return
        for f in self._fields:
            name = f['name']
            fields_names.append(name)
        rec, = self._search_read([('id', '=', idx)], fields_names=fields_names)
        length = len(self._data)
        self.beginInsertRows(QModelIndex(), length, length)
        self._data.append(rec)
        self.endInsertRows()
        return rec

    def removeId(self, row, mdl_idx):
        self.beginRemoveRows(mdl_idx, row, row)
        id_ = self._data[row].get('id')
        self._data.pop(row)
        self.endRemoveRows()
        return id_

    def deleteRecords(self, ids):
        self._proxy.delete(ids, self._context)

    def _search(self, domain, offset=0, limit=None, order=None):
        pass

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._fields)

    def get_data(self, index):
        raw_value = self._data[index.row()]
        return raw_value

    def data(self, index, role, field_name='name'):
        field = self._fields[index.column()]

        if role == Qt.DisplayRole:
            def flatten_dict(dd, separator ='', prefix =''):
                return { prefix + separator + k if prefix else k : v
                         for kk, vv in dd.items()
                         for k, v in flatten_dict(vv, separator, kk).items()
                         } if isinstance(dd, dict) else { prefix : dd }

            def safeget(dct, *keys):
                for key in keys:
                    try:
                        dct = dct[key]
                    except (KeyError, TypeError):
                        return None
                return dct

            default_dict = self._data[index.row()]

            searched_field = field['name']
            if searched_field.find('.') != -1:
                keys = searched_field.split('.')
                keys[0] = keys[0] + '.'
                if len(keys) == 3:
                    keys[1] = keys[1] + '.'
                raw_value = safeget(default_dict, *keys)
            else:
                raw_value = default_dict.get(searched_field)
            #FIX ME
            #keys = str(searched_field).split('.')
            #raw_value = safeget(default_dict, *keys)

            #flat_dict = flatten_dict(default_dict)
            #raw_value = flat_dict[field[field_name]]

            #raw_value = self._data[index.row()][field[field_name]]
            digits = None
            if field.get('digits'):
                rowx = self._data[index.row()]
                target_field = field.get('digits')[0]
                if rowx.get(target_field):
                    target = rowx[target_field]
                    group_digits = field.get('digits')[1]
                    if group_digits.get(target):
                        digits = group_digits.get(target)
                    else:
                        digits = 2

            if not raw_value:
                return None

            if field.get('format'):
                field_format = field['format']
                if digits:
                    field_format = field['format'] % str(digits)
                fmt_value = field_format.format(float(raw_value))
                #fmt_value = raw_value
            else:
                fmt_value = raw_value
            return fmt_value

        elif role == Qt.TextAlignmentRole:
            align = Qt.AlignmentFlag(Qt.AlignVCenter | field['align'])
            return align
        else:
            return None

    def update(self, id, pos=None):
        rec, = self._search_read([('id', '=', id)],
                fields_names=[x['name'] for x in self._fields])

        if pos is None:
            pos = 0
            for d in self._data:
                if d['id'] == id:
                    break
                pos += 1

        self._data.pop(pos)
        self._data.insert(pos, rec)
        self.dataChanged.emit(self.index(pos, 0),
            self.index(pos, len(self._fields) - 1))
        return rec

    def headerData(self, section, orientation, role):
        """ Set the headers to be displayed. """
        if role != Qt.DisplayRole:
            return None
        elements =[ f['description'] for f in self._fields]
        if orientation == Qt.Horizontal:
            for i in range(len(elements)):
                if section == i:
                    return elements[i]
        return None

class TrytonModel(object):
    'Model interface for Tryton'

    def __init__(self, connection, model, fields, methods=None):
        self._fields = fields
        self._methods = methods
        self._proxy = connection.get_proxy(model)
        self._context = connection.context # to work with xmlrpc and jsonrpc
        self._data = []
        if self._methods:
            self.setMethods()

    def setFields(self, fields):
        self._fields = fields

    def setMethods(self):
        for name in self._methods:
            if not hasattr(self._proxy, name):
                continue
            setattr(self, name, getattr(self._proxy, name))

    def find(self, domain, limit=None, order=None, context=None):
        if context:
            self._context.update(context)
        return self._setDomain(domain, limit, order)

    def _setDomain(self, domain, limit=None, order=None):
        if domain and isinstance(domain[0], int):
            operator = 'in'
            operand = domain
            if len(domain) == 1:
                operator = '='
                operand = domain[0]
            domain = [('id', operator, operand)]
        if not order:
            order = [('id', 'ASC')]
        self._data = self._search_read(domain,
            fields_names=self._fields, limit=limit, order=order)
        return self._data

    def _search_read(self, domain, offset=0, limit=None, order=None,
        fields_names=None):
        if order:
            ids = self._proxy.search(domain, offset, limit, order, self._context)
            records = self._proxy.read(ids, fields_names, self._context)
            rec_dict = {}
            for rec in records:
                rec_dict[rec['id']] = rec
            res = []
            for id_ in ids:
                res.append(rec_dict[id_])
        else:
            res = self._proxy.search_read(domain, offset, limit, order,
                    fields_names, self._context)
        return res

    def read(self, ids, fields_names=None):
        records = self._proxy.read(ids, fields_names, self._context)
        return records

    def _search(self, domain, offset=0, limit=None, order=None):
        pass

    def deleteRecords(self, ids):
        self._proxy.delete(ids, self._context)

    def getRecord(self, id_):
        records = self.setDomain([('id', '=', id_)])
        if records:
            return records[0]

    def update(self, id, pos=False):
        rec, = self._search_read([('id', '=', id)],
            fields_names=[x['name'] for x in self._fields])
        return rec

    def create(self, values):
        records = self._proxy.create([values], self._context)
        return records[0]

    def write(self, ids, values):
        self._proxy.write(ids, values, self._context)

    def method(self, name):
        # TODO Add reuse self context (*values, self._context)
        return getattr(self._proxy, name)