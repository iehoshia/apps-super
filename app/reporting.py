# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os
from io import StringIO
import logging
from datetime import datetime
from decimal import Decimal

pyudev = None

try:
    import pyudev
except:
    pass
    #logging.warning("Pyudev module not found!")

try:
    from escpos import printer
except:
    pass
    #logging.warning("Escpos module not found!")

try:
    import cups
except:
    pass
    #logging.warning("Cups module not found!")

__all__ = ['Receipt']

_ROW_CHARACTERS = 48

_DIGITS = 9
_PRINT_TAX_ID = False
_DIGITS_CODE_RECEIPT = 4

# ------------------- Type Font Escpos -----------------
_FONT_A = 'a'  # Normal Font
_FONT_B = 'b'  # Condensed Font
# ------------------------------------------------------

if os.name == 'posix':
    homex = 'HOME'
    dirconfig = '.tryton/temp'
elif os.name == 'nt':
    homex = 'USERPROFILE'
    dirconfig = 'AppData/Local/tryton/temp'

HOME_DIR = os.getenv(homex)
directory = os.path.join(HOME_DIR, dirconfig)


if not os.path.exists(directory):
    os.makedirs(directory)

TEMP_INVOICE_FILE = os.path.join(directory, 'invoice.txt')
SSH_PORT = 23


def money(value):
    if type(value) != int:
        value = int(value)
    return '{:,}'.format(value)


dev_printers = {}
if pyudev:
    context = pyudev.Context()
#     for device in context.list_devices():
#         if device.subsystem == 'usbmisc':
#            print(device.subsystem, device.sys_path.split('2-1/')[1][0:5], device.device_node)
#            dev_printers[str(device.sys_path.split('2-1/')[1][0:5])] = device.device_node


class Receipt(object):
    __name__ = 'frontend_pos.ticket'

    def __init__(self, context, row_characters=None, logo=None, environment='retail'):
        self.logger = logging.getLogger('reporting')
        self._company = context.get('company')
        self._sale_device = context.get('sale_device')
        self._shop = context.get('shop')
        self._street = context.get('street')
        self._city = context.get('city')
        self._phone = context.get('phone')
        self._id_number = context.get('id_number')
        self._regime_tax = context.get('regime_tax')
        self._gta_info = context.get('gta_info')
        self._user = context.get('user')
        self._footer = context.get('footer')
        self._header = context.get('header')
        self._printing_taxes = context.get('printing_taxes')
        self._delta_locale = context.get('delta_locale')
        self._environment = environment

        self._row_characters = _ROW_CHARACTERS
        if context.get('row_characters'):
            self._row_characters = int(context.get('row_characters'))

        self.taxes_col_width = int(self._row_characters / 3)

        order_col_width = int(self._row_characters / 3)
        self.order_col_1 = order_col_width - 6
        self.order_col_2 = order_col_width + 11
        self.order_col_3 = order_col_width - 5

        self._show_position = context.get('show_position')
        self._show_discount = context.get('show_discount')
        self._img_logo = None

        if logo:
            self._img_logo = StringIO(logo)

    def printer_found(self):
        return self._printer

    def printing(f):
        def p(self, *p, **kw):
            self._open_device()
            try:
                res = f(self, *p, **kw)
            finally:
                pass
            return res
        return p

    def test_printer(self):
        if self._interface == 'usb':
            if os.name == 'posix':
                self._printer = printer.File(self._device)
            elif os.name == 'nt':
                self._printer = printer.UsbWin(self._device)
                self._printer.open()
        elif self._interface == 'network':
            self._printer = printer.Network(self._device)
        elif self._interface == 'ssh':
            self._printer = printer.FileSSH(*self._device.split('@'))
            self._printer.open()
        if not self._printer:
            return
        if self._img_logo:
            self.print_logo()
        self.print_enter()
        self.print_enter()
        self.print_header()
        self.print_enter()
        self.print_enter()
        self._printer.cut()
        self._printer.cashdraw(2)
        self._printer.close()

    def set_printer(self, printer):
        if dev_printers.get(printer['device']):
            device = dev_printers[printer['device']]
        else:
            device = printer['device']

        self._interface = printer['interface']
        self._device = device

    def print_sale(self, sale):
        #print("PRINT SALE",str(sale))
        try:
            #print("INTERFACE",str(self._interface))
            #print("OS",str(os.name))
            #print("PRINTER",str(printer))
            if self._interface == 'usb':
                if os.name == 'posix':
                    self._printer = printer.File(self._device)
                elif os.name == 'nt':
                    self._printer = printer.UsbWin(self._device)
                    self._printer.open()
            elif self._interface == 'network':
                self._printer = printer.Network(self._device)
            elif self._interface == 'ssh':
                self._printer = printer.FileSSH(*self._device.split('@'))
                self._printer.open()
            elif self._interface == 'cups':
                self.conn = cups.Connection()
                self._file = open(TEMP_INVOICE_FILE, 'w')
                self._printer = CupsPrinter(self._file, self._row_characters)
            if not self._printer:
                self.logger.info("Warning: Can not found Printer!")
                return
            self.logger.info("Info: Printer is OK!")
            self._print_sale(sale)
        except:
            self.logger.info("Warning: Printer error or device not found!")

    def _print_sale(self, sale):
        self.print_header()
        self.print_body(sale)
        self.print_footer()
        # self.print_extra_info(sale)
        if self._interface in ['usb', 'ssh', 'network']:
            self._printer.close()
        elif self._interface == 'cups':
            self._file.close()
            self.conn.printFile(self._printer_name, TEMP_INVOICE_FILE,
                'POS Invoice', {})

    def print_logo(self):
        self._printer.set(align='center')
        self._printer.image(self._img_logo)
        self.print_enter()

    def print_header(self):
        if self._img_logo:
            self.print_logo()
        self._printer.set(align='center')
        if self._header != '' and self._header is not None:
            self._printer.text(self._header)
            self.print_enter()
        self._printer.text(self._company)
        self.print_enter()
        self._printer.text(self._shop)
        self.print_enter()
        if self._id_number:
            self._printer.text('NIT:' + self._id_number)
        if self._regime_tax:
            self._printer.text(' ' + self._regime_tax)
        self.print_enter()
        if self._street:
            self._printer.text(self._street)
            self.print_enter()
        if self._city:
            self._printer.text(self._city)
        if self._phone:
            if self._city:
                self._printer.text(' ')
            self._printer.text('Telefono:' + self._phone)
        if self._city or self._phone:
            self.print_enter()
        self.print_enter()
        self.print_enter()

    def print_horinzontal_line(self):
        self._printer.text('-' * self._row_characters)

    def print_horinzontal_double_line(self):
        self._printer.text('=' * self._row_characters)

    def print_enter(self):
        self._printer.text('\n')

    def print_split(self, left, right):
        len_left = self._row_characters - len(right) - 1
        left = left[:len_left]
        if type(left) == bytes:
            left = left.decode("utf-8")
        if type(right) == bytes:
            right = right.decode("utf-8")
        left += (len_left - len(left) + 1) * ' '
        self._printer.text(left)
        self._printer.text(right + '\n')

    def print_body(self, sale):
        self._cashdraw = True
        self._printer.set(font=_FONT_B)
        self._printer.set(align='left')
        if sale['number'] or sale['state'] in ['processing', 'done', 'cancel']:
            if sale['total_amount'] >= 0:
                self._printer.text('FACTURA DE VENTA No. ' + sale['number'])
            else:
                self._printer.text('NOTA CREDITO No. ' + sale['number'])
        else:
            self._cashdraw = False
            self._printer.text('Pedido: ' + sale['order'])
        self.print_enter()
        #mod_hours = sale["create_date"] + timedelta(hours=self._delta_locale)
        #time_ = mod_hours.strftime('%I:%M %p')
        self._printer.text('Fecha:%s' % sale['date'])
        if sale.get('turn') and sale['turn'] != 0:
            self._printer.text('Turno: %s - ' % str(sale['turn']))
        self.print_enter()
        self.print_horinzontal_line()
        party_name = 'Cliente: %s ' % sale['party']
        party_id_number = 'Id: %s' % sale.get('party_id_number', '')
        if len(party_name + party_id_number) > self._row_characters:
            self._printer.text(party_name)
            self.print_enter()
            self._printer.text(party_id_number)
        else:
            self._printer.text(party_name + party_id_number)
        if sale.get('party_address'):
            self.print_enter()
            self._printer.text('Direccion: %s' % sale['party_address'])
        if sale.get('party_phone'):
            self.print_enter()
            self._printer.text('Telefono: %s' % sale['party_phone'])

        self.print_enter()
        self.print_horinzontal_line()
        self.print_split(' Articulo ', 'Subtotal ')
        self.print_horinzontal_line()

        len_row = self._row_characters - (_DIGITS_CODE_RECEIPT + 1) - (_DIGITS + 1)
        for line in sale['lines']:
            if line['taxes'] and _PRINT_TAX_ID:
                tax_id = ' ' + str(line['taxes'][0].id)
            else:
                tax_id = ''
            line_total = money(line['amount_w_tax']) + tax_id

            if line['quantity'] != 1:
                length_name = self._row_characters - 11
                first_line = line['code'] + ' ' + line['name'][:length_name]

                if type(first_line) == bytes:
                    first_line = first_line.decode('utf-8')

                self._printer.text(first_line + '\n')
                second_line = '  %s x %s' % (
                    line['quantity'], money(line['unit_price_w_tax'])
                )
                second_line = second_line.encode('utf-8')
                self.print_split(second_line, line_total)
            else:
                if self._environment == 'retail':
                    line_pt = line['code'] + ' ' + line['name'][:len_row]
                else:
                    line_pt = line['name'][:len_row]

                self.print_split(line_pt, line_total)

        untaxed_amount = sale['untaxed_amount']
        total_amount = sale['total_amount']
        total_string = 'Total:'

        tip = None
        if sale.get('tip') and sale['tip'] > 0:
            untaxed_amount = untaxed_amount - sale['tip']
            total_amount = untaxed_amount + sale['tax_amount']
            tip = sale['tip']
            total_string = 'Total Sin Propina:'

        self.print_split('', '----------------')
        self.print_split('Subtotal Base:', money(untaxed_amount))
        self.print_split('Impuesto:', money(sale['tax_amount']))
        self.print_split('', '----------------')
        self.print_split(total_string, money(total_amount))
        self.print_enter()

        if tip:
            self.print_split('Propina:', money(tip))
            self.print_split('Total con Propina:', money(sale['total_amount']))

        if self._show_discount:
            self.print_split('Ahorro:', money(sale['discount']))
        self.print_enter()
        self.print_split('Recibido:', money(sale['cash_received']))
        self.print_split('Cambio:', money(sale['change']))
        self.print_horinzontal_line()
        self.print_enter()
        if self._printing_taxes:
            self.print_col('Tipo', self.taxes_col_width + 2)
            self.print_col('Base', self.taxes_col_width)
            self.print_col('Imp.', self.taxes_col_width)
            taxes = sale['taxes']
            for tax in taxes:
                self.print_col(str(taxes[tax]['name']) + ' ', self.taxes_col_width)
                self.print_col(str(int(taxes[tax]['base'])), self.taxes_col_width)
                self.print_col(str(int(taxes[tax]['tax'])), self.taxes_col_width)
                self.print_enter()

        self.print_horinzontal_line()
        self.print_enter()
        no_products = 'No Items: %s' % str(sale['num_products'])
        self._printer.text(no_products)
        self.print_enter()

        if self._gta_info and sale['state'] not in ['draft']:
            self._printer.text(self._gta_info)
            self.print_enter()
        if sale['state'] in ['processing', 'done']:
            self._printer.text('Pedido: ' + sale['order'])
            self.print_enter()

        register = 'Caja No. %s' % self._sale_device
        self._printer.text(register)
        self.print_enter()

        self._printer.text('Cajero: %s' % self._user)
        self.print_enter()
        if sale.get('salesman'):
            self._printer.text('Vendedor: %s' % sale['salesman'])
            self.print_enter()
        if sale.get('comment'):
            self._printer.text('Notas: %s' % sale['comment'])
            self.print_enter()

        if self._show_position:
            self._printer.text('Posicion: %s' % str(sale['position']))
            self.print_enter()
        self._printer.set(align='center')
        #self.print_split('Puntos Acumulados:', sale['points'])
        #self.print_enter()
        #printer.barcode(sale.receipt_code, 'CODE128B', 3, 50,'','')
        self.print_enter()
        self.print_enter()

    def print_extra_info(self, sale):
        if sale.get('pos_notes'):
            self.print_enter()
            self.print_header()
            self.print_horinzontal_line()
            self.print_enter()
            party_name = 'Cliente: %s ' % sale['party']
            self._printer.text(party_name)
            self.print_enter()
            if self._show_position:
                self._printer.text('Posicion: %s' % str(sale['position']))
                self.print_enter()

            if sale['state'] in ['draft']:
                self._printer.text('Cotizacion: ', sale['order'])
            else:
                self._printer.text('Factura No. ' + sale['number'])
            self.print_enter()
            self._printer.text(str(sale.get('pos_notes')))
            self.print_enter()
            self.print_horinzontal_line()
            self.print_enter()
            self._printer.cut()

    def print_col(self, x, l):
        self._printer.text(x[:l] + (l - len(x)) * ' ')

    def print_footer(self, ):
        if self._footer:
            self._printer.text(self._footer)
        self.print_enter()
        self._printer.text('SOFTWARE POS TRYTON - www.presik.com')
        self.print_enter()
        self._printer.cut()
        if self._cashdraw:
            self._printer.cashdraw(2)
        self.print_enter()

    def print_orders(self, orders, reversion=None, kind='command'):
        res = []
        self.order_kind = kind
        for order in orders.values():
            try:
                if dev_printers.get(order['host']):
                    host = dev_printers[order['host']]
                else:
                    host = order['host']
                if order['interface'] == 'usb':
                    self._printer = printer.File(host)
                elif order['interface'] == 'network':
                    self._printer = printer.Network(host)
                elif order['interface'] == 'ssh':
                    self._printer = printer.FileSSH(*host.split('@'))
                    if self._printer:
                        self._printer.open()
                elif order['interface'] == 'cups':
                    pass
                if not self._printer:
                    self.logger.info("Warning: Interface not found for printer!")
                    res.append(None)
                    continue

                self.logger.info("Info: Printer is OK!")
                res.append(self._print_order(order, reversion))
            except:
                self.logger.info("Warning: Can not found Printer!")
                res.append(None)
        return all(res)

    def _print_order(self, order, reversion):
        self.print_body_order(order, reversion)
        self._printer.cut()
        self._row_characters = order['row_characters']
        if order['interface'] in ('network', 'usb', 'ssh'):
            self._printer.close()
        return True

    def print_body_order(self, order, reversion):
        self._printer.set(font=_FONT_B)
        self._printer.set(align='center')
        self._printer.text('TURNO: %s' % str(order['turn']))
        self.print_enter()
        self.print_enter()
        kind = 'COMANDA'
        if self.order_kind == 'delivery':
            kind = 'PEDIDO'
        title = '+ + + + + %s + + + + +' % kind
        self._printer.text(title)
        self.print_enter()
        self._printer.set(align='left')
        self.print_enter()
        date_ = datetime.now().strftime("%Y-%m-%d %H:%M %p")
        self._printer.text('FECHA: ' + date_)
        self.print_enter()

        if self.order_kind == 'delivery':
            self._printer.text('FACTURA: ' + order['number'])
            self.print_enter()
            delivery_charge = ' '
            if order['delivery_charge'] == 'customer':
                delivery_charge = 'Cliente'
            elif order['delivery_charge'] == 'company':
                delivery_charge = 'Empresa'
            self._printer.text('CARGO DEL DOMICILIO: ' + delivery_charge)
            self.print_enter()
            if order.get('payment_term'):
                self._printer.text('FORMA DE PAGO: ' + order['payment_term'])
                self.print_enter()

        if order.get('sale_number'):
            self._printer.text('PEDIDO: %s' % str(order['sale_number']))
            self.print_enter()

        self._printer.text('POSICION: %s' % str(order['position']))
        self.print_enter()
        self._printer.text('VENDEDOR: %s' % order['salesman'])
        self.print_enter()
        self._printer.text('AMBIENTE: %s' % order['shop'])
        self.print_enter()
        self._printer.text('CLIENTE: %s' % order['party'])
        self.print_enter()

        if self.order_kind == 'delivery':
            self._printer.text('VALOR: ' + str(order['total_amount']))
            self.print_enter()
        if order.get('pos_notes'):
            self._printer.text(order['pos_notes'])
            self.print_enter()
        self._printer.text('CAJA No: %s' % self._sale_device or '')
        self.print_enter()
        self.print_enter()
        self._printer.set(align='center')
        self.print_horinzontal_line()
        if not reversion and self.order_kind == 'command':
            self._printer.text('-------- PREPARAR Y SERVIR --------')
        elif not reversion and self.order_kind == 'delivery':
            self._printer.text('-------- ENTREGAR --------')
        else:
            self._printer.text('<<<< R E V E R S I O N >>>>')
        self.print_enter()

        if self.order_kind != 'delivery':
            self.print_horinzontal_line()
            self._printer.set(align='left')
            self.print_enter()
            self._printer.set(align='left')

            self.print_enter()
            self.print_horinzontal_line()
            self.print_col('CANT', self.order_col_1)
            self.print_col('PRODUCTO', self.order_col_2)
            self.print_col(' ' + 'PRECIO', self.order_col_3)

            for line in order['lines']:
                qty = str(int(Decimal(line['quantity'])))
                self.print_col(qty, self.order_col_1)
                self.print_col(line['name'], self.order_col_2)
                self.print_col(' ' + str(line['unit_price']), self.order_col_3)
                if line['note']:
                    self.print_enter()
                    self._printer.text('   ----->> NOTA: ' + line['note'])
                    self.print_enter()

        self.print_enter()
        self.print_horinzontal_double_line()

        self.print_enter()
        self._printer.text('NOTA:')
        self.print_enter()
        if order['comment']:
            self._printer.text(str(order['comment']))
            self.print_enter()
            self.print_horinzontal_line()
        self.print_enter()
        self.print_enter()


class CupsPrinter(object):
    "Cups Printer"
    __name__ = 'sale_pos_frontend.cups_printer'

    def __init__(self, _file, row_characters):
        self._file = _file
        self.align = 'left'
        self._row_characters = row_characters

    def text(self, text):
        self._text(text)

    def set(self, align='left', font=_FONT_A):
        if align:
            self.align = align
        if font:
            self.font = font

    def cut(self):
        pass

    def cashdraw(number):
        pass

    def _text(self, text):
        start_spaces = ''
        if self.align == 'center':
            start_spaces = int((self._row_characters - len(text)) / 2) * ' '
        elif self.align == 'right':
            start_spaces = int(self._row_characters - len(text)) * ' '
        else:
            pass
        text = start_spaces + text
        self._file.write(text)


if __name__ == '__main__':

    # Test for Escpos interface printer Linux

    # Network example
    device = 'network', '192.168.0.32'

    # Unix-like Usb example
    # device = 'usb','/dev/usb/lp1'

    # Windows Usb example for printer nameb SATPOS
    # device = 'usb', 'SATPOS'

    # SSH example
    # device = 'ssh', 'psk@xxxxx@192.168.0.5@23@/dev/usb/lp1'

    example_dev = {
        'interface': device[0],
        'device': device[1],
    }

    ctx_printing = {}
    ctx_printing['company'] = 'OSCORP INC'
    ctx_printing['sale_device'] = 'CAJA-10'
    ctx_printing['shop'] = 'Shop Wall Boulevard'
    ctx_printing['street'] = 'Cll 21 # 172-81. Central Park'
    ctx_printing['user'] = 'Charles Chapplin'
    ctx_printing['city'] = 'Dallas'
    ctx_printing['zip'] = '0876'
    ctx_printing['phone'] = '591 5513 455'
    ctx_printing['id_number'] = '123456789-0'
    ctx_printing['tax_regime'] = 'none'

    receipt = Receipt(ctx_printing)
    receipt.set_printer(example_dev)
    receipt.test_printer()
