#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import os
import logging
import qcrash.api as qcrash
import threading

from decimal import Decimal
import time
from datetime import datetime, timedelta, date
import calendar
from collections import OrderedDict
from PyQt5.QtCore import Qt, QThread, pyqtSignal, \
    QModelIndex, pyqtSlot, QObject, QTimer, QSettings, \
    QDate, QRegExp
from PyQt5.QtGui import QTouchEvent, QMouseEvent, QRegExpValidator
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import (QLabel, QTextEdit, QHBoxLayout, QVBoxLayout,
    QWidget, QGridLayout, QLineEdit, QDoubleSpinBox, QTreeView,
    QListView, QAbstractItemView, QCalendarWidget, QApplication,
    QDateEdit)

from neox.commons.action import Action
from neox.commons.buttons import ActionButton
from neox.commons.forms import GridForm, FieldMoney, ComboBox
from neox.commons.messages import MessageBar
from neox.commons.image import Image
from neox.commons.dialogs import QuickDialog, ProductDialog, \
    AgentDialog, TableDialog, CategoryDialog, DeliveryDialog
from neox.commons.table import TableView
from neox.commons.jsonrpc import Fault, ProtocolError, ResponseError
from neox.commons.model import TrytonTableModel, Modules
from neox.commons.search_window import SearchWindow
from neox.commons.frontwindow import FrontWindow
from neox.commons.menu_buttons import MenuDash
from neox.commons.signal_event import SignalEvent
from neox.commons.widget import CustomQLineEdit

import neox.commons.dblogin as dblogin

from PyQt5.QtGui import QIcon

from xmlrpc import client

from email_validator import validate_email, EmailNotValidError

from .common import create_icon_file

from .reporting import Receipt
from .buttonpad import Buttonpad, Productpad, \
    Agentpad, Categorypad, Deliverypad
from .manage_tables import ManageTables
from .states import STATES, RE_SIGN
from .common import get_svg_icon
from .constants import (PATH_PRINTERS, DELTA_LOCALE, STRETCH, alignRight,
    alignLeft, alignCenter, alignHCenter, alignVCenter, DIALOG_REPLY_NO,
    DIALOG_REPLY_YES, ZERO, FRACTIONS, RATE_CREDIT_LIMIT, SCREENS, FILE_BANNER,
    EMAIL, _YEAR, _MONTH, MONTHS)


class MainWindow(FrontWindow):

    def __init__(self, connection, params):
        title = "EFFICA  |  SMART POS"
        self.conn = connection

        super(MainWindow, self).__init__(connection, params, title,
            icon=get_svg_icon('pos-icon'))
        self.set_style(SCREENS[self.screen_size])

        self._product_mode = False
        self.is_clear_right_panel = True
        self.payment_ctx = {}
        self.set_keys()
        self.stock_context = None

        response = self.load_modules()
        if response is not True:
            d = self.dialog(response)
            d.exec_()
            super(MainWindow, self).close()
            return
        self.setupSaleLineModel()
        self.setupPaymentModel()
        self.set_domains()

        self.create_gui()
        self.installEventFilter(self)
        self.message_bar.load_stack(self.stack_msg)

        if not hasattr(self, 'auto_print_commission'):
            self.auto_print_commission = False

        self.active_usb_printers = []

        if os.name == 'posix' and os.path.exists(PATH_PRINTERS):
            self.set_printers_usb(PATH_PRINTERS)

        self.create_statusbar()

        self.window().showMaximized()

        if not self.tablet_mode:
            self.grabKeyboard()
        self.reader_thread = None
        self._current_line_id = None
        self._is_valid_email = False
        self._is_valid_phone = False
        self._current_product = None
        self._current_quantity = None
        self._current_pdf_document = None
        self._difference = -1
        self._invalid_voucher = False
        self._amount_text = ''
        self._sign = None
        self._last_event = None
        self._add_combo = False
        self._disable_state = False
        self.selected_category = []
        self.selected_products = []
        self.create_dialogs()
        self.except_hook()
        self.createNewSale()
        if not hasattr(self, 'active_weighing'):
            self.active_weighing = False
        elif self.active_weighing is True:
            from .electronic_scale import ScaleReader
            self.reader_thread = ScaleReader()
            self.reader_thread.sigSetWeight.connect(self.set_weight_readed)

        self.do_invoice = DoInvoice(self, self._context)
        self.do_invoice.sigDoInvoice.connect(self.__do_invoice_thread)

        my_settings = QSettings()
        qcrash.set_qsettings(my_settings)
        qcrash.install_backend(qcrash.backends.EmailBackend(EMAIL, 'Effica POS'))

        # setup our own function to collect system info and application log
        qcrash.get_application_log = self.get_application_log()
        qcrash.get_system_information = self.get_system_info()

        qcrash.install_except_hook(except_hook=self.except_hook)
        self.createNewStatement()

    def set_domains(self):
        self.domain_search_product = [
            ('code', '!=', None),
            ('active', '=', True),
            ('template.salable', '=', True),
            ('template.account_category', '!=', None),
        ]


    def event(self, events):
        event_type = super(MainWindow, self).event(events)
        touch = QTouchEvent(event_type)
        return event_type

    def set_printers_usb(self, PATH_PRINTERS):
        for usb_dev in os.listdir(PATH_PRINTERS):
            if 'lp' not in usb_dev:
                continue
            path_device = os.path.join(PATH_PRINTERS, usb_dev)
            self.active_usb_printers.append(['usb', path_device])

    def get_current_sale(self):
        if hasattr(self, '_sale') and self._sale['id']:
            sales = self._PosSale.find([
                ('id', '=', self._sale['id']),
            ])
            if not sales:
                return
            return sales[0]

    def get_return_sale(self, return_sale_id):
        sales = self._PosSale.find([
            ('id', '=', return_sale_id),
        ])
        if not sales:
            return
        return sales[0]

    def check_empty_sale(self):
        sale = self.get_current_sale()
        if sale and self._model_sale_lines.rowCount() == 0 \
                and sale['state'] == 'draft':
            self.delete_current_sale()

    def close_statement(self):

        two_hundred = float(str(self.field_statement_two_hundred.value()))
        one_hundred = float(str(self.field_statement_one_hundred.value()))
        fifty = float(str(self.field_statement_fifty.value()))
        twenty = float(str(self.field_statement_twenty.value()))
        ten = float(str(self.field_statement_ten.value()))
        fifth = float(str(self.field_statement_fifth.value()))
        one = float(str(self.field_statement_one.value()))
        currency = float(str(self.field_statement_currency.value()))
        surplus = float(str(self.field_statement_surplus.value()))
        surplus_potato = float(str(self.field_statement_surplus_potato.value()))
        surplus_gizzard = float(str(self.field_statement_surplus_gizzard.value()))

        start_balance = float(self.field_statement_start_balance.value())
        end_balance = float(self.field_statement_end_balance.value())

        cash_amount = two_hundred * 200 + one_hundred * 100 + \
            fifty * 50 + twenty * 20 + ten * 10 + fifth * 5 + \
            one + currency

        difference = start_balance + end_balance - cash_amount # - surplus 

        #if difference > Decimal('0.00'):
        #    self.dialog('difference_must_zero').exec_()
        #    return

        result = self._Statement.check_open_statement([], self._context)
        if result.get('error'):
            self.dialog('more_than_one_statement_open')
            return
        if result['is_open'] == True:
            result = self._Statement.check_statement_before_close([],
                self._shop['id'],
                surplus,
                self._context)
            if result['to_close'] == False:
                return self.dialog('sales_processing').exec_()
            self.action_print_statement()
            self._Statement.close_statement([],
                self._shop['id'],
                cash_amount,
                surplus,
                surplus_potato,
                surplus_gizzard,
                self._context)
            self.dialog('statement_closed')
            self.message_bar.set('statement_closed')
            self.set_state('cancel')
            self._model_payment_lines.setDomain([('statement.state','=','draft')], \
                order=[('id','DESC')])
        return

    def close(self, from_close=False):
        if self.conn is None:
            if self.active_weighing and self.reader_thread:
                self.reader_thread.onClose()
            super(MainWindow, self).close()
            return
        if from_close == True:
            self._PosSale.clear_empty_sales([], self._shop['id'], self._context)
            if self.active_weighing and self.reader_thread:
                self.reader_thread.onClose()
            super(MainWindow, self).close()
        else:
            dialog = self.dialog('confirm_exit', response=True)
            response = dialog.exec_()
            if response == DIALOG_REPLY_YES:
                self._PosSale.clear_empty_sales([], self._shop['id'], self._context)
                if self.active_weighing and self.reader_thread:
                    self.reader_thread.onClose()
                super(MainWindow, self).close()

    def delete_current_sale(self):
        if self._sale['id']:
            self._PosSale.cancel_sale([], self._sale['id'], self._context)

    def resize_window_tablet_dev(self):
        self.resize(690, self.get_geometry()[1])

    def set_stack_messages(self):
        super(MainWindow, self).set_stack_messages()
        self.stack_msg.update({
            'system_ready': ('info', self.tr('SYSTEM READY...')),
            'invoice_posted': ('info', self.tr('INVOICE POSTED...')),
            'sale_credited': ('info', self.tr('SALE CREDITED...')),
            'purchase_approved': ('info', self.tr('PURCHASE APPROVED...')),
            'confirm_exit': ('warning', self.tr('DO YOU WANT TO EXIT?')),
            'no_return_sale': ('warning', self.tr('NO RETURN SALE CREATED')),
            'confirm_sale': ('warning', self.tr('DO YOU WANT TO CONFIRM?')),
            'print_invoice': ('warning', self.tr('DO YOU WANT PRINT THE INVOICE?')),
            'product_not_available': ('info', self.tr('PRODUCT NOT AVAILABLE, PLEASE CHECK STOCK!')),
            'confirm_credit': ('question', self.tr('PLEASE CONFIRM YOUR PAYMENT TERM AS CREDIT?')),
            'sale_number_not_found': ('warning', self.tr('SALE ORDER / INVOICE NUMBER NOT FOUND!')),
            'sale_closed': ('error', self.tr('THIS SALE IS CLOSED, YOU CAN NOT TO MODIFY!')),
            'sales_processing': ('error', self.tr('SALES OPENED, PLEASE VERIFY BEFORE CONTINUE!')),
            'something_wrong': ('error', self.tr('SOMETHING WRONG, PLEASE VERIFY WITH ADMINISTRATOR!')),
            'production_error': ('error', self.tr('ERROR EN PRODUCCIÓN. CONSULTE AL ADMINISTRADOR.')),
            'discount_not_valid': ('warning', self.tr('DISCOUNT VALUE IS NOT VALID!')),
            'add_payment_sale_draft': ('info', self.tr('YOU CAN NOT ADD PAYMENTS TO SALE ON DRAFT STATE!')),
            'enter_quantity': ('question', self.tr('ENTER QUANTITY...')),
            'enter_discount': ('question', self.tr('ENTER DISCOUNT...')),
            'enter_payment': ('question', self.tr('ENTER PAYMENT AMOUNT BY:')),
            'payment_valid': ('question', self.tr('VALID PAYMENT')),
            'enter_new_price': ('question', self.tr('ENTER NEW PRICE...')),
            'order_successfully': ('info', self.tr('ORDER SUCCESUFULLY SENT.')),
            'production_successfully':('info', self.tr('PRODUCCIÓN LISTA')),
            'statement_open': ('info', self.tr('STATEMENT ALREADY OPEN. SYSTEM READY.')),
            'statement_opened': ('info', self.tr('NOT STATEMENT OPEN. A NEW ONE WAS CREATED.')),
            'order_failed': ('warning', self.tr('FAILED SEND ORDER!')),
            'missing_agent': ('warning', self.tr('MISSING AGENT!')),
            'sale_is_from_credit_note': ('error', self.tr('SALE IS GENERATED FROM CREDIT NOTE!')),
            'sale_has_credit_note': ('error', self.tr('SALE HAS ALREADY A CREDIT NOTE!')),
            'sale_cancel_credit_note': ('error', self.tr('SALE HAS BEEN CANCELED, CAN NOT BE CREDITED!')),
            'more_than_one_statement_open': ('error', \
                self.tr('MORE THAN ONE STATEMENT OPEN, PLEASE CONTACT YOUR ADMINISTRATOR!')),
            'missing_salesman': ('warning',
                self.tr('THERE IS NOT SALESMAN FOR THE SALE!')),
            'sale_without_products': ('warning', self.tr('YOU CAN NOT CONFIRM A SALE WITHOUT PRODUCTS!')),
            'user_without_permission': ('error', self.tr('USER WITHOUT PERMISSION FOR SALE POS!')),
            'quantity_not_valid': ('error', self.tr('THE QUANTITY IS NOT VALID...!')),
            'user_not_permissions_device': ('error', self.tr('THE USER HAVE NOT PERMISSIONS FOR ACCESS' \
                ' TO DEVICE!')),
            'missing_party_configuration': ('warning',
                self.tr('MISSING THE DEFAULT PARTY ON SHOP CONFIGURATION!')),
            'missing_journal_device': ('error', self.tr('MISSING SET THE JOURNAL ON DEVICE!')),
            'statement_closed': ('error', self.tr('THERE IS NOT A STATEMENT OPEN FOR THIS DEVICE!')),
            'product_not_found': ('warning', self.tr('PRODUCT NOT FOUND!')),
            'party_not_found': ('question', self.tr('ADDING NEW PARTY!')),
            'must_load_or_create_sale': ('warning', self.tr('FIRST YOU MUST CREATE/LOAD A SALE!')),
            'new_sale': ('warning', self.tr('DO YOU WANT CREATE NEW SALE?')),
            'cancel_sale': ('question', self.tr('DO YOU WANT TO CANCEL SALE?')),
            'credit_sale': ('question', self.tr('DO YOU WANT TO CREDIT SALE?')),
            'not_permission_delete_sale': ('info', self.tr('YOU HAVE NOT PERMISSIONS FOR DELETE THIS SALE!')),
            'not_permission_for_cancel': ('info', self.tr('YOU HAVE NOT PERMISSIONS FOR CANCEL THIS SALE!')),
            'not_permission_for_credit': ('info', self.tr('YOU HAVE NOT PERMISSIONS FOR CREDIT THIS SALE!')),
            'not_permission_for_credit_draft': ('info', self.tr('YOU HAVE NOT PERMISSIONS FOR CREDIT SALE IN DRAFT!')),
            'customer_not_credit': ('info', self.tr('THE CUSTOMER HAS NOT CREDIT!')),
            'agent_not_found': ('warning', self.tr('AGENT NOT FOUND!')),
            'invalid_commission': ('warning', self.tr('COMMISSION NOT VALID!')),
            'invalid_payment_amount': ('question', self.tr('INVALID PAYMENT AMOUNTS, PLEASE VERIFY!')),
            'invalid_payment_voucher': ('question', self.tr('INVALID PAYMENT VOUCHER, PLEASE VERIFY!')),
            'unhandled_exception': ('warning', self.tr('UNHANDLED EXCEPTION!')),
            'cancel_sale_success': ('info', self.tr('SALE CANCEL WITH SUCCESS!')),
            'in_invoices_to_print': ('info', self.tr('NO INVOICE TO PRINT!')),
            'invalid_email': ('warning', self.tr('INVALID EMAIL!')),
            'not_can_force_assign': ('warning', self.tr('YOU CAN NOT FORCE ASSIGN!')),
            'no_statement_lines': ('info', self.tr('CIERRE DE CAJA VACÍO!')),
            'expense_successfully': ('info', self.tr('GASTO REGISTRADO EXITÓSAMENTE')),
        })

    def load_modules(self):
        modules = Modules(self, self.conn)

        self._sale_pos_restaurant = None

        _Configuration = {
            'model': 'sale.configuration',
            'fields': (
                'show_description_pos',
                'show_stock_pos',
                'show_agent_pos',
                'show_location_pos',
                'decimals_digits_quantity',
                'allow_zero_quantity_sale',
                'sale_price_list',
                'self_pick_up',
            ),
        }

        _Module = {
            'model': 'ir.module',
            'fields': ('name', 'state'),
        }

        self._config = modules.set_model(_Configuration)
        self._config, = self._config.find([('id', '=', 1)])

        self._Module = modules.set_model(_Module)
        self._commission_activated = self._Module.find([
            ('name', '=', 'commission'),
            ('state', '=', 'activated'),
        ])

        _Device = {
            'name': '_Device',
            'model': 'sale.device',
            'fields': ('name', 'shop', 'shop.company', )
        }
        _Journal = {
            'name': '_Journal',
            'model': 'account.statement.journal',
            'fields': ('name',),
        }
        _Statement = {
            'name':'_Statement',
            'model':'account.statement',
            'fields': ('id','name','state','date','journal','end_balance',
                'start_balance','surplus','leftout',
                'calculated_end_balance'),
            'methods': ('new_statement','close_statement',
                'check_open_statement',
                'check_statement_before_close',
                'previous_leftout'),
        }
        _StatementLine = {
            'name':'_StatementLine',
            'model':'account.statement.line',
            'fields': ('statement',
                'invoice.invoice_with_serie','number','amount','party.name','description'),
        }
        _Party = {
            'name': '_Party',
            'model': 'party.party',
            'fields': ('id', 'name', 'tax_identifier.code', 'addresses',
                'city', 'contact_mechanisms', 'email', 'phone'),
            'methods': ('new_party', 'search_party'),
        }

        _PartyAddress = {
            'name': '_PartyAddress',
            'model': 'party.address',
            'fields': ('party', 'city'),
            'methods': ('new_address',)
        }

        _PartyContact = {
            'name': '_PartyContact',
            'model': 'party.contact_mechanism',
            'fields': ('party', 'type', 'value'),
            'methods': ('new_mechanism',)
        }

        _Employee = {
            'name': '_Employee',
            'model': 'company.employee',
            'fields': ('party','party.name',),
        }

        _User = {
            'name': '_User',
            'model': 'res.user',
            'fields': ('id', 'name', 'company', 'shop'),
        }

        _Product = {
            'name': '_Product',
            'model': 'product.product',
            'fields': ('template', 'template.name', 'code', 'description',
                'template.brand','template.barcode', 'template.code',
                'template.account_category', 'quantity',
                'template.list_price', 'template.producible', 'template.name',
                'active',
                'photo',
                'template.expense', 
            ),
            'methods':('get_stock_by_locations',)
        }

        _Template = {
            'name': '_Template',
            'model': 'product.template',
            'fields': ('id','name', 'list_price', 'account_category',
                'producible','active', 'pos_producible',
                'photo',
            ),
        }

        _ProductCategory = {
            'name': '_ProductCategory',
            'model': 'product.category',
            'fields': ('id','name','templates', 
            'image',
            'next_category'),
        }

        _TemplateCategory = {
            'name': '_TemplateCategory',
            'model': 'product.template-product.category',
            'fields': ('id','template', 'template.name', 'category')
        }

        _Shop = {
            'name': '_Shop',
            'model': 'web.shop',
            'fields': ('id', 'name', 'categories',
                'guest_party', 'products', 'warehouses',
                'company')
        }


        _PosPurchase = {
            'name': '_PosPurchase',
            'model': 'purchase.purchase',
            'fields': ('company', 'number', 'reference', 'description',
            'state', 'purchase_date', 'party', 'party.name','warehouse',
            'warehouse.name', 'lines', 'custom_state',
            'invoices', 'moves',),
            'methods': (
                'approve_purchase', 'cancel',
            )
        }

        _PosPurchaseLine = {
            'name': '_PosPurchaseLine',
            'model': 'purchase.line',
            'fields': ('product', 'product.name','quantity', 'type',
                'quantity', 'unit', 'unit_price', 'amount',
                'description', 'delivery_date',),
        }

        _PosStockMove = {
            'name': '_PosStockMove',
            'model': 'stock.move',
            'fields': ('product', 'uom', 'quantity', 'from_location',
            'to_location', 'shipment', 'planned_date', 'effective_date',
            'state', ),
            'methods': (
                'do',
            )
        }

        _PosSale = {
            'name': '_PosSale',
            'model': 'sale.sale',
            'fields': ('id','number', 'party', 'party.name',  'lines',
                'party.city', 'party.tax_identifier.code', 'position',
                'invoices', 'untaxed_amount', 'state', 'invoice_state',
                'total_amount','total_amount', 'sale_date', 'is_credit_sale',
                'has_credit_sale', 'invoice_with_serie',
                'total_amount', 'origin', 'has_production_included',
                'short_description','agent', 'agent.party.name',
                'fiscal_invoice_state', 'description','delivery_method' ),
            'methods': (
                'cancel_sale','credit_sale', 'get_amounts',
                'get_discount_total', 'process_sale',
                'post_invoice', 'get_data', 'add_value', 'add_product',
                'add_payment', 'update_description',
                'get_order2print', 'add_expense',
                'new_sale', 'workflow_to_end', 'clear_empty_sales',
                'update_delivery_method', 'create_production',
            )
        }

        _PosWarning = {
            'name': '_PosWarning',
            'model': 'res.user.warning',
            'fields': ('name', 'user','always'),
            'methods': ('new_warning',),
        }

        _PosSaleLine = {
            'name': '_PosSaleLine',
            'model': 'sale.line',
            'fields': ('product', 'product.code', 'product.template.name', 'type',
                'quantity', 'unit_price', 'product.description', 'note',
                'description', 'discount','discount_amount', 'principal',
                'principal.party.name', 'amount'),
            'methods': ('set_discount', 'set_unit_price',
                'set_quantity', 'set_agent')
        }

        _PosInvoice = {
            'name': '_PosInvoice',
            'model': 'account.invoice',
            'fields': ('number', 'total_amount', 'percentage'),
        }

        _Category = {
            'name': '_Category',
            'model': 'product.category',
            'fields': ('name', 'parent', 'childs', 'name_icon'),
        }
        _PaymentTerm = {
            'name': '_PaymentTerm',
            'model': 'account.invoice.payment_term',
            'fields': ('name', 'active'),
        }

        _ActionReport = {
            'name': '_ActionReport',
            'model': 'ir.action.report',
            'fields': ('action', 'report_name'),
        }
        _Agent = {
            'name': '_Agent',
            'model': 'commission.agent',
            'fields': ('id', 'party.name', 'party',
                ),
        }
        _Commission = {
            'name': '_Commission',
            'model': 'commission',
            'fields': ('id', 'origin', 'invoice_line', 'invoice_line.invoice'),
        }
        _Taxes = {
            'name': '_Taxes',
            'model': 'account.tax',
            'fields': ('id', 'name'),
        }

        modules.set_models([_Agent, _Commission])

        models_to_work = [
            _Journal, _Party, _PartyAddress, _Employee, _Product,
            _PosSale, _User, _PosSaleLine, _Category, _PaymentTerm,
            _ActionReport, _Taxes, _Statement, _StatementLine, _PosInvoice,
            _PosPurchase, _PosPurchaseLine, _PosStockMove, _PosWarning, _Shop,
            _Template, _PartyContact, _ProductCategory, _TemplateCategory,
        ]

        modules.set_models(models_to_work)

        self._user, = self._User.find([
            ('login', '=', self.user),
        ])

        self._shop, = self._Shop.find([('id', '=', self._user['shop'])])

        self._default_warehouse = self._shop['warehouses'][0]

        self._default_self_pick_up = self._config['self_pick_up']

        self._journals = self._Journal.find([
            ('company', '=', self._user['company'])
        ])

        self._journals = dict([(j['id'], j) for j in self._journals])
        journal_iterator = iter(self._journals)
        self._default_journal_id = next(journal_iterator)# self._journals[0]
        if not self._default_journal_id:
            return 'missing_journal_device'

        self._employees = self._Employee.find([
            ('company', '=', self._user['company']),
        ])
        self._agents = self._Agent.find([
            ('company', '=', self._user['company']),
        ])
        self._expenses = self._Product.find([
            ('template.expense', '=', True),
        ])

        self._production_products = self._Product.find([
            ('template.pos_producible','=',True)
        ])
        self._payment_terms = self._PaymentTerm.find([()],
            limit=1)

        #self.type_pos_user = self._context.get('type_pos_user')

        #if not self.type_pos_user:
        #    return 'user_without_permission'
        self.user_can_delete = True # self.type_pos_user in ('salesman','frontend_admin', 'cashier')

        #self._default_party_id = 7# self._shop['guest_party'] TODO CHANGE
        self._default_party, = self._Party.find([('tax_identifier','=','CF')],
            limit=1)
        self._default_party_id = self._default_party['id']
        self._default_party_name = self._default_party['name']
        try:
            self._default_tax_identifier = self._default_party['tax_identifier.']['code']
        except:
            self._default_tax_identifier = 'CIN'
        self._default_address, = self._PartyAddress.find([('party','=',
            self._default_party_id)],
            limit=1)
        self._default_party_city = self._default_address['city']
        self._default_agent = self._agents[0]
        if not self._default_party_id:
            return 'missing_party_configuration'

        self._payment_term, = self._payment_terms

        self._default_payment_term_id = self._payment_term['id']
        self._default_payment_term_name = self._payment_term['name']

        self._password_admin = self._config.get('password_admin_pos')

        self._action_report, = self._ActionReport.find([
            ('report_name', '=', 'simplified.account.invoice'),
        ])

        self._action_short_report, = self._ActionReport.find([
            ('report_name', '=', 'simplified.account.invoice'),
        ])

        #self._action_report_command, = self._ActionReport.find([
        #    ('report_name', '=', 'command.sale.sale'),
        #])

        self._action_report_purchase, = self._ActionReport.find([
            ('report_name', '=', 'purchase.purchase'),
        ])

        self._action_report_statement, = self._ActionReport.find([
            ('report_name', '=', 'account.statement'),
        ],limit=1)

        self._action_report_invoice_binnacle, = self._ActionReport.find([
            ('report_name', '=', 'account.invoice.report.print'),
        ],limit=1)

        self._action_report_auth_binnacle, = self._ActionReport.find([
            ('report_name', '=', 'account.invoice.authorization.report.print'),
        ],limit=1)

        self._action_report_product_by_location, = self._ActionReport.find([
            ('report_name', '=', 'product.by_location.report'),
        ],limit=1)

        self._product_categories = self._ProductCategory.find(
            [('accounting','=',False),
            ('menu','=',True)], limit=16, order=[('name','ASC')])

        self._product_combos = self._ProductCategory.find(
            [('accounting','=',False),
            ('combo','=',True)], limit=16, order=[('name','ASC')])

        self._complementary_categories = self._ProductCategory.find(
            [('accounting','=',False),
            ('complementary','=',True)], limit=16, order=[('name','ASC')])

        for i, category in enumerate(self._product_categories):
            create_icon_file(category.get('name'), category.get('image'))
            templates = category.get('templates')
            products = []
            for i, template in enumerate(templates):

                if i > 15:
                    break
                #try:
                product, = self._Product.find([('template','=', template)], limit=1)
                products.append(product)

                #except:
                #    pass
            products = sorted(products, key=lambda d:d['template.']['name'])
            category['products'] = products

        for i, category in enumerate(self._product_combos):
            create_icon_file(category.get('name'), category.get('image'))
            templates = category.get('templates')
            products = []
            for i, template in enumerate(templates):

                if i > 15:
                    break
                #try:
                product, = self._Product.find([('template','=', template)], limit=1)
                products.append(product)

                #except:
                #    pass
            products = sorted(products, key=lambda d:d['template.']['name'])
            category['products'] = products

        for i, category in enumerate(self._complementary_categories):
            create_icon_file(category.get('name'), category.get('image'))
            templates = category.get('templates')
            products = []
            for i, template in enumerate(templates):

                if i > 15:
                    break
                #try:
                product, = self._Product.find([('template','=', template)], limit=1)
                products.append(product)

                #except:
                #    pass
            products = sorted(products, key=lambda d:d['template.']['name'])
            category['products'] = products

        self._action_categories = [
            'action_first_category',
            'action_second_category',
            'action_third_category',
            'action_fourth_category',
            'action_fifth_category',
            'action_sixth_category',
            'action_seventh_category',
            'action_eighth_category',
            'action_nineth_category',
            'action_tenth_category',
            'action_evelenth_category',
            'action_twelveth_category',
            'action_thirteenth_category',
            'action_fourteenth_category',
            'action_fifteenth_category',
            'action_sixteenth_category',
        ]

        self._action_combos = [
            'action_first_combo',
            'action_second_combo',
            'action_third_combo',
            'action_fourth_combo',
            'action_fifth_combo',
            'action_sixth_combo',
            'action_seventh_combo',
            'action_eighth_combo',
            'action_nineth_combo',
            'action_tenth_combo',
            'action_evelenth_combo',
            'action_twelveth_combo',
            'action_thirteenth_combo',
            'action_fourteenth_combo',
            'action_fifteenth_combo',
            'action_sixteenth_combo',
        ]

        self._action_products = [
            'action_first_product',
            'action_second_product',
            'action_third_product',
            'action_fourth_product',
            'action_fifth_product',
            'action_sixth_product',
            'action_seventh_product',
            'action_eighth_product',
            'action_ninth_product',
            'action_tenth_product',
            'action_eleventh_product',
            'action_twelfth_product',
            'action_thirteenth_product',
            'action_fourteenth_product',
            'action_fifteenth_product',
            'action_sixteenth_product',
        ]

        self._category_buttons = [ ( str(e['id']),
                str(e['name']),
                self._action_categories[i] ) for i, e in enumerate(self._product_categories)
            ]

        self._combo_buttons = [ ( str(e['id']),
                str(e['name']),
                self._action_combos[i] ) for i, e in enumerate(self._product_combos)
            ]

        self._actions_agent = [
            'action_first_agent',
            'action_second_agent',
            'action_third_agent',
            'action_fourth_agent',
            'action_fifth_agent',
            'action_sixth_agent',
            'action_seventh_agent',
            'action_eighth_agent',
        ]

        self._agents_buttons = [] #[ ( str(e['id']),
                 #str(e['party']['name']),
                 #self._actions_agent[i] ) for i, e in enumerate(self._agents)
                #]

        #FIXME
        now = date.today() + timedelta(days=1)
        if self._config['show_stock_pos'] in ('value', 'icon'):
            self.stock_context = {
                'stock_date_end': now,
                'locations': [self._default_warehouse],
            }
        return True

    def create_dialogs(self):
        self.create_dialog_agent()
        self.create_dialog_create_party()
        self.create_dialog_cancel_invoice()
        self.create_dialog_credit_invoice()
        self.create_dialog_close_statement()
        self.create_dialog_comment()
        self.create_dialog_force_assign()
        self.create_dialog_force_reconnect()
        self.create_dialog_global_discount()
        self.create_dialog_start_balance()
        self.create_wizard_new_sale()
        #self.create_dialog_order()
        #self.create_dialog_payment()
        #self.create_dialog_payment_term()
        #self.create_dialog_position()
        #self.create_dialog_print_invoice()
        self.create_dialog_purchase()
        self.create_dialog_statement()
        #self.create_dialog_salesman()
        self.create_dialog_sale_line()
        self.create_dialog_sale_line_from_search()
        self.create_dialog_search_party()
        self.create_dialog_search_products()
        self.create_dialog_search_products_by_image()
        self.create_dialog_search_categories_by_image()
        self.create_dialog_search_combos_by_image()
        self.create_dialog_search_purchases()
        self.create_dialog_search_agent_by_image()
        self.create_dialog_select_delivery_method()
        self.create_dialog_search_sales()
        self.create_dialog_expense()
        self.create_dialog_production()
        self.create_dialog_select_dates()
        self.create_dialog_select_end_date()
        self.create_dialog_stock()
        self.create_dialog_voucher()
        self.create_dialog_confirm_payment()
        if self._commission_activated:
            self.create_dialog_agent()

    def set_default_printer(self, printer=None):
        if self.active_usb_printers:
            self.printer_sale_name = self.active_usb_printers[0]
        if not printer and self.printer_sale_name:
            printer = {
                'interface': self.printer_sale_name[0],
                'device': self.printer_sale_name[1],
            }
        if printer:
            self.receipt_sale.set_printer(printer)

    def button_new_sale_pressed(self):
        self.createNewSale()

    def button_send_to_pay_pressed(self):
        # Return sale to draft state

        self._PosSale.to_quote(self._sale['id'], self._context)
        if self._model_sale_lines.rowCount() > 0:
            self.state_disabled()

    def button_to_draft_pressed(self):
        # Return sale to draft state
        # TODO FIXME
        return
        if hasattr(self, '_sale'):
            self._PosSale.to_draft(self._sale['id'], self._context)
            self.state_disabled()

    def create_gui(self):
        panels = QHBoxLayout()
        panel_left = QVBoxLayout()
        panel_right = QVBoxLayout()
        panel_right.setObjectName('panel_right')

        left_head = QHBoxLayout()
        left_head.setObjectName('left_head')
        left_middle = QHBoxLayout()
        left_table = None

        self.message_bar = MessageBar()
        self.message_bar.setObjectName('message_bar')

        self.label_input = QLabel()
        self.label_input.setFocus()
        self.label_input.setObjectName('label_input')

        if not self.tablet_mode:
            _label_invoice = QLabel(self.tr('INVOICE:'))
            _label_invoice.setObjectName('label_invoice')
            _label_invoice.setAlignment(alignRight | alignVCenter)

        self.field_invoice = QLineEdit()
        self.field_invoice.setReadOnly(True)
        self.field_invoice.setObjectName('field_invoice')
        if self.tablet_mode:
            self.field_invoice.setPlaceholderText(self.tr('INVOICE'))

        self.field_amount = FieldMoney(self, 'amount', {})
        self.field_amount.setObjectName('field_amount')
        self.field_sign = QLabel('   ')
        self.field_sign.setObjectName('field_sign')

        layout_message = QGridLayout()
        layout_message.addLayout(self.message_bar,1,0,1,4)#, 1, 0, 1, 4)
        layout_message.setObjectName('layout_message')

        left_head.addLayout(layout_message, 0)

        info_fields = [
            ('salesman', {
                'name': self.tr('SALESMAN'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'invisible': True,
                'color': 'gray'
            }),
            ('agent', {
                'name': self.tr('AGENT'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'invisible': True,
                'color': 'gray'
            }),
            ('payment_term', {
               'name': self.tr('PAYMENT TERM'),
                'readonly': True,
                #'invisible': self.tablet_mode,
                'invisible': True,
                'placeholder': False,
                'size': self.screen_size,
                'color': 'gray'
            }),
        ]

        if self._commission_activated and not self.tablet_mode \
                and self._config['show_agent_pos']:
            info_fields.append(('agent', {
                'name': self.tr('AGENT'),
                'placeholder': self.tablet_mode,
                'readonly': True,
                'size': self.screen_size,
                'color': 'gray'
            }))

        _cols = 2

        self.grid_info = GridForm(self, OrderedDict(info_fields), col=_cols)

        layout_input = QGridLayout()
        layout_input.addWidget(self.label_input, 1, 0, 1, 4)

        left_middle.addLayout(self.grid_info, 1)
        left_middle.addLayout(layout_input,1)
        left_middle.addWidget(self.field_sign, 0)
        left_middle.addWidget(self.field_amount, 0)

        col_sizes_tlines = [field['width'] for field in self.fields_sale_line]
        left_table = TableView('table_sale_lines', self._model_sale_lines,
            col_sizes_tlines, method_selected_row=self.sale_line_selected,
            method_clicked_row=self.sale_line_clicked)
        self.left_table_lines = left_table

        for i, f in enumerate(self._model_sale_lines._fields, 0):
            if f.get('invisible'):
                self.left_table_lines.hideColumn(i)

        _fields_amounts = [
            ('date', {
                'name': self.tr('DATE'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('delivery_method', {
                'name': self.tr('ENTREGA'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('order_number', {
                'name': self.tr('No ORDER'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('party', {
                'name': self.tr('CUSTOMER'),
                'readonly': True,
                'type': 'char',
                'size': self.screen_size,
                'color': 'gray'

            }),
            ('nit', {
                'name': self.tr('NIT'),
                'readonly': True,
                'type': 'char',
                'size': self.screen_size,
                'color': 'gray',
            }),
            ('address', {
                'name': self.tr('ADDRESS'),
                'readonly': True,
                'type': 'char',
                'size': self.screen_size,
                'color': 'gray'

            }),
            ('invoice', {
                'name': self.tr('INVOICE'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('invoice_state', {
                'name': self.tr('INVOICE STATE'),
                'readonly': True,
                'placeholder': False,
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('untaxed_amount', {
                'name': self.tr('SUBTOTAL'),
                'readonly': True,
                'type': 'money',
                'size': self.screen_size,
                'color': 'gray'

            }),
            ('discount', {
                'name': self.tr('DISCOUNT'),
                'readonly': True,
                'type': 'money',
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('total_amount', {
                'name': self.tr('TOTAL'),
                'readonly': True,
                'type': 'money',
                'size': self.screen_size,
                'color': 'blue'
            }),
            ('paid', {
                'name': self.tr('PAID'),
                'readonly': True,
                'invisible':True,
                'type': 'money',
                'size': self.screen_size,
                'color': 'gray'
            }),
            ('change', {
                'name': self.tr('CHANGE'),
                'readonly': True,
                'invisible':True,
                'type': 'money',
                'size': self.screen_size,
                'color': 'orange'
            })
        ]

        fields_amounts = OrderedDict(_fields_amounts)
        self.grid_amounts = GridForm(self, fields_amounts, col=1)

        self.buttonpad = Buttonpad(self)
        self.pixmap_pos = Image(self, 'pixmap_pos', FILE_BANNER)

        self.table_payment = TableView('table_payment',
            self._model_payment_lines, [200, STRETCH])

        panel_left.addLayout(left_head, 0)
        panel_left.addLayout(left_middle, 0)
        panel_left.addWidget(left_table, 1)

        panel_right.addWidget(self.pixmap_pos, 0)
        panel_right.addLayout(self.buttonpad.functions, 1)
        panel_right.addLayout(self.grid_amounts, 0)
        panel_right.addLayout(self.buttonpad.stacked, 0)
        #panel_right.addWidget(self.table_payment,1)

        panels.addLayout(panel_left, 1)
        panels.addLayout(panel_right, 0)

        widget = QWidget()
        widget.setLayout(panels)
        self.setCentralWidget(widget)

    def create_statusbar(self):
        values = OrderedDict([
            ('stb_shop', {'name': self.tr('SHOP'), 'value': self._shop['name']}),
            #('stb_device', {'name': self.tr('DEVICE'), 'value': self.device_name}),
            ('stb_database', {'name': self.tr('DATABASE'), 'value': self.database}),
            ('stb_user', {'name': self.tr('USER'), 'value': self.user}),
            ('stb_printer', {'name': self.tr('PRINTER'), 'value': self.printer_sale_name})
        ])
        self.set_statusbar(values)

    def button_plus_pressed(self):
        error = False
        if self._input_text == '' and self._amount_text == '0':
            return
        if self._state in ('paid', 'disabled','cash'):
            return
        if self._sign in ('*', '-',):# '/'):
            if hasattr(self, '_sale_line') and self._sale_line \
                and self._sale_line.get('type') and self._state == 'add' \
                and self._model_sale_lines.rowCount() > 0:
                if self._sign == '*':
                    self._process_quantity(self._amount_text)
                else:
                    error = not(self._process_price(self._amount_text))
        elif self._state in ['add', 'cancel', 'accept']:
            self.clear_right_panel()
            #self.on_selected_new_product(code=self._input_text)
            self.add_product(code=self._input_text)
        elif self._state == 'cash':
            is_paid = self._process_pay(self.field_amount.text())
            if not is_paid:
                self.clear_input_text()
                self.clear_amount_text()
                return
        else:
            logging.warning('Unknown command/text')
        self._clear_context(error)

    def button_add_party_pressed(self):
        if self._sale['state'] and self._sale['state'] != 'draft':
            return
        error = False

        if self._state not in ('add', 'cancel','accept'):
            return
        if self._current_line_id is None:
            return
        if self._state in ['add', 'accept','cancel']:
            self.clear_right_panel()
            self.action_create_party()
        else:
            logging.warning('Unknown command/text')
        #self._clear_context(error)

    def button_add_agent_pressed(self):
        error = False
        if self._input_text == '':
            return
        if self._state in ['add', 'accept','cancel']:
            self.clear_right_panel()
            self.add_agent(agent_id=self._input_text)
        else:
            logging.warning('Unknown command/text')
        #self._clear_context(error)

    def action_read_weight(self):
        self.reader_thread.start()

    def set_weight_readed(self):
        if not self.reader_thread or not self.reader_thread.best_weight:
            return

        if self.reader_thread.best_weight:
            self.amount_text_changed(self.reader_thread.best_weight)
            self._process_quantity(self._amount_text)
            self._clear_context(False)
        self.reader_thread.resetZERO()

    def _clear_context(self, error=False):
        self.clear_input_text()
        self.clear_amount_text()
        self.clear_sign()
        self.label_input.setFocus()

        if self._state not in ('warning', 'cash') and not error:
            self.message_bar.set('system_ready')
        else:
            self.set_state('add')

    def _process_quantity(self, text):
        eval_value = text.replace(',', '.')
        try:
            quantity = Decimal(eval_value)
            #if self._sale_line['product'].get('quantity'):
            #    if not self._check_stock_quantity(self._sale_line['product'], quantity):
            #        return
            if self._current_line_id:
                self._PosSaleLine.set_quantity(
                    [self._current_line_id], quantity, self._context)
        except:
            return self.message_bar.set('quantity_not_valid')

        self.message_bar.set('system_ready')
        self.label_input.setFocus()
        self.update_subtotal_amount()
        self.set_amounts()
        self.set_discount_amount()
        self._clear_context()

    def _process_price(self, text):
        discount_valid = True
        text = str(text)
        eval_value = text.replace(',', '')

        if self._sign == '-':
            # Do discount
            discount_valid = self.set_discount(eval_value)

        if not discount_valid:
            self.message_bar.set('discount_not_valid')
            return False

        self.message_bar.set('system_ready')
        self._update_amounts()
        self.set_discount_amount()
        return True

    def _update_amounts(self):
        self.update_subtotal_amount()
        self.set_amounts()

    def _process_pay(self, text):
        if not self.validate_done_sale():
            return
        val = Decimal(text.replace(',', ''))

        cash_received = Decimal(val)
        residual_amount = self._sale['total_amount']
        if residual_amount < 0:
            # The sale is paid
            self._done_sale()
            return True

        change = cash_received - residual_amount

        if residual_amount >= cash_received:
            amount_to_add = cash_received
        else:
            amount_to_add = residual_amount

        res = self.add_payment(amount_to_add)

        self.field_journal_id = self._default_journal_id

        if res['result'] != 'ok':
            self.message_bar.set('statement_closed')
            self.dialog('statement_closed')
            return False

        if change < ZERO:
            self.message_bar.set('enter_payment')

        self._sale.update(res)
        residual_amount = self._sale['residual_amount']

        if self._sale['residual_amount'] <= 0:
            # The sale is paid
            self._done_sale()
            return True

    def validate_done_sale(self):
        if self._model_sale_lines.rowCount() == 0:
            self.dialog('sale_without_products')
            self.set_state('add')
            self.message_bar.set('system_ready')
            return
        return True

    def _get_sum_amount_paid(self):
        return sum([data.get('amount')
            for data in self._model_payment_lines._data])

    def _get_total_amount(self):
        return sum([data.get('amount')
            for data in self._model_sale_lines._data])

    def update_subtotal_amount(self):
        res = 0
        if self._current_line_id:
            res = self._model_sale_lines.update(self._current_line_id)['amount']
        self.field_amount.setText(res)

    def update_lines_amount(self, lines_ids):
        for i, line_id in enumerate(lines_ids):
            self._model_sale_lines.update(line_id, i)

    def update_expense_line(self, value, field):
        amount = self.row_field_expense_amount.value()
        description = self.row_field_line_description.text()

        if amount > 0 and len(description)>3:
            self.dialog_expense.ok_button.setEnabled(True)
        else:
            self.dialog_expense.ok_button.setEnabled(False)

    def update_production_line(self, value, field):
        quantity = int(self.row_field_production_quantity.value())

        if quantity > 0:
            self.dialog_production.ok_button.setEnabled(True)
        else:
            self.dialog_production.ok_button.setEnabled(False)

    def set_discount_amount(self):
        res = 0
        if self._sale['id']:
            res = self._PosSale.get_discount_total(self._sale['id'],
                self._context)
            res = str(res)
        self.field_discount.setText(res)

    def amount_text_changed(self, text=None):
        if text:
            self._amount_text += text
        self.field_amount.setText(self._amount_text)

    def input_text_changed(self, text=None):
        if text:
            self._input_text += text
        elif text == '':
            self._input_text = ''
        self.label_input.setText(self._input_text)

    def __do_invoice_thread(self):
        if self.sale_to_post['is_credit']:
            return

    def _done_sale(self, is_credit=False):
        self._sale['is_credit'] = is_credit
        self.sale_to_post = self._sale
        self.do_invoice.start()

        try:
            sale = self.get_current_sale()
            self.print_odt_short_invoice(sale, direct_print=True, reprint=False)

            #FIX ME 
            self.print_odt_short_invoice(sale, direct_print=True, reprint=False)
        except:
            logging.error(sys.exc_info()[0])

        self.dialog('order_successfully').exec_()
        self.createNewSale()

        return True

    def button_accept_pressed(self):
        if not self._sale['id'] or \
                not self._model_sale_lines.rowCount() > 0 or \
                self._sale['state']=='processing' or \
                self._sale['state']=='done':
            return
        self.set_state('accept')
        lines = self._PosSaleLine.find([('sale','=',self._sale['id'])])
        res = self._PosSale.process_sale([], self._sale['id'], \
            self._context)
        if res['res'] != 'ok' or res.get('status') and res.get('status') != 'ok':
            self.message_bar.set(res['msg'])
            return
        self.field_invoice.setText(res['msg'])
        self.field_invoice_state.setText(self.tr('PROCESSING'))
        self._sale['state'] = 'processing'
        self.button_cash_pressed()

    def button_cash_pressed(self):
        if not self._sale.get('fiscal_invoice_state'):

            self._sale, = self._PosSale.find([('id','=',
                self._sale['id'])])

        if self._sale['state'] == 'done' or \
            self._sale['fiscal_invoice_state'] == 'PAGADA' or \
            self._sale['fiscal_invoice_state'] == 'CANCELADA':
            return
        sale = self.get_current_sale()
        if len(sale['lines'])<1:
            return

        if self.field_party.text() == '':
            self.field_party.setText(self._default_party_name)
            self.field_tax_identifier.setText(self._default_tax_identifier)
            self.field_address.setText(self._default_party_city)

        self.field_amount.zero()

        self.message_bar.set('enter_payment')

        self.label_total_amount.setText(str(self._sale['total_amount']))
        self.row_field_difference.setText(str(self._sale['total_amount']))
        self.row_field_voucher_number.setText(str('0'))
        self.row_field_voucher_amount.setText(str('0'))
        self.row_field_cash_amount.setText(str('0'))
        self.row_field_cash_amount.setFocus()
        self.dialog_confirm_payment.exec_()

    def action_reservations(self):
        print('Buscando reservas.....')

    def action_tables(self):
        self.dialog_manage_tables.exec_()

    def action_salesman(self):
        self.dialog_salesman.exec_()

    def action_tax(self):
        self.dialog_tax.exec_()

    def action_payment(self):
        if self._state != 'cash':
            self.dialog('add_payment_sale_draft')
            return
        self.dialog_payment.exec_()

    def action_delivery_method(self):
        self._PosSale.update_delivery_method([], self._sale['id'], 'delivery', self._context)
        self.field_delivery_method.setText('DOMICILIO')
        self.dialog_select_delivery_method.hide()
        return

    def action_local_table(self):
        self._PosSale.update_delivery_method([], self._sale['id'], 'table', self._context)
        self.field_delivery_method.setText('MESAS')
        self.dialog_select_delivery_method.hide()
        return

    def action_take_away(self):
        self._PosSale.update_delivery_method([], self._sale['id'], 'take_away', self._context)
        self.field_delivery_method.setText('PARA LLEVAR')
        self.dialog_select_delivery_method.hide()
        return

    def action_payment_term_selection_changed(self):
        is_credit = self._payment_terms[str(self.field_payment_term_id)]['is_credit']
        self._PosSale.write([self._sale['id']], {'payment_term': self.field_payment_term_id})
        if is_credit:
            self._done_sale(is_credit=True)

    def action_journal_selection_changed(self):
        self.message_bar.set('enter_payment')

    def action_salesman_selection_changed(self):
        self._PosSale.write([self._sale['id']], {'salesman': self.field_salesman_id})

    def action_agent_selection_changed(self):
        self._PosSale.write([self._sale['id']], {'agent': self.field_agent_id})

    def action_re_print_invoice(self):
        sale = self.get_current_sale()
        if not sale.get('invoices'):
            return self.dialog('in_invoices_to_print').exec_()

        self.print_odt_short_invoice(sale, direct_print=True, reprint=True)
        self.dialog('order_successfully')

    def action_new_statement(self):
        result = self._Statement.check_open_statement([], self._context)
        if result.get('error'):
            self.dialog('more_than_one_statement_open')
            return
        if result['is_open'] == False:
            #leftout = self._Statement.previous_leftout([], self._context)
            #previous_leftout = leftout['previous_leftout']
            #self.field_previous_leftout.setText(str(previous_leftout))
            #self.field_previous_leftout.setEnabled(False)

            res = self.dialog_start_balance.exec_()

            amount = self.field_start_balance.text()

            if amount and float(amount):
                res = self._Statement.new_statement([], amount, self._context)
                if res['result'] == True:
                    self.field_start_balance.setText('')
                    self.dialog('statement_opened')

                    self.set_state('add')
                    self.message_bar.set('system_ready')
                    self.createNewSale()
                else:
                    self.dialog('statement_closed')
                    self.close()
        return

    def action_close_statement(self):
        self.action_print_statement()

    def action_print_statement(self):
        result = self._Statement.check_open_statement([],
                self._context)
        if result==False:
            return
        self.print_odt_statement(result['statement'], direct_print=True)
        return

    def action_create_party(self):
        if self._current_line_id is None:
            return
        self.field_tax_identifier.setText("")
        self.field_name.setText("")
        self.field_city.setText("")
        self.field_tax_identifier.setFocus()
        res = self.dialog_create_party.exec_()

        if res == DIALOG_REPLY_NO:
            return

    def action_select_delivery_method(self):
        self.dialog_select_delivery_method.exec_()

    def action_category_selected(self):
        self._current_product_code = 347
        self.dialog_search_products_by_image.hide()
        self.action_agent_by_image()

    def action_product_selected(self):
        current_agent = 1
        #FIX ME EDIT AGENT TO CHANGE
        product, agent = self.search_product_agent(self._current_product_code,
            current_agent)
        if not product or not agent:
            return
        self.add_product_from_agent(
            product=product,
            quantity=1,
            discount=0,
            agent=agent)

    def action_first_category(self):
        try:
            self.selected_category = self._product_categories[0]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            pass

    def action_second_category(self):
        try:
            self.selected_category = self._product_categories[1]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            pass

    def action_third_category(self):
        try:
            self.selected_category = self._product_categories[2]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_fourth_category(self):
        try:
            self.selected_category = self._product_categories[3]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_fifth_category(self):
        try:
            self.selected_category = self._product_categories[4]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_sixth_category(self):
        try:
            self.selected_category = self._product_categories[5]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_seventh_category(self):
        try:
            self.selected_category = self._product_categories[6]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_eighth_category(self):
        try:
            self.selected_category = self._product_categories[7]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_nineth_category(self):
        try:
            self.selected_category = self._product_categories[8]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_tenth_category(self):
        try:
            self.selected_category = self._product_categories[9]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_evelenth_category(self):
        try:
            self.selected_category = self._product_categories[10]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_twelveth_category(self):
        try:
            self.selected_category = self._product_categories[11]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_thirteenth_category(self):
        try:
            self.selected_category = self._product_categories[12]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_fourteenth_category(self):
        try:
            self.selected_category = self._product_categories[13]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_fifteenth_category(self):
        try:
            self.selected_category = self._product_categories[14]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_sixteenth_category(self):
        try:
            self.selected_category = self._product_categories[15]

            self.selected_products = self.selected_category['products']

            self.dialog_search_categories_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_first_combo(self):
        try:
            self.selected_combo = self._product_combos[0]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
            
            
        except:
            pass

    def action_second_combo(self):
        try:
            self.selected_combo = self._product_combos[1]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True
            
            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            pass

    def action_third_combo(self):
        try:
            self.selected_combo = self._product_combos[2]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
            
        except:
            return

    def action_fourth_combo(self):
        try:
            self.selected_combo = self._product_combos[3]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()

        except:
            return

    def action_fifth_combo(self):
        try:
            self.selected_combo = self._product_combos[4]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_sixth_combo(self):
        try:
            self.selected_combo = self._product_combos[5]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_seventh_combo(self):
        try:
            self.selected_combo = self._product_combos[6]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_eighth_combo(self):
        try:
            self.selected_combo = self._product_combos[7]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_nineth_combo(self):
        try:
            self.selected_combo = self._product_combos[8]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_tenth_combo(self):
        try:
            self.selected_combo = self._product_combos[9]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_evelenth_combo(self):
        try:
            self.selected_combo = self._product_combos[10]

            self.selected_products = self.selected_combo['products']

            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
            next_category = self.selected_combo.get('next_category')
        except:
            return

    def action_twelveth_combo(self):
        try:
            self.selected_combo = self._product_combos[11]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_thirteenth_combo(self):
        try:
            self.selected_combo = self._product_combos[12]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_fourteenth_combo(self):
        try:
            self.selected_combo = self._product_combos[13]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_fifteenth_combo(self):
        try:
            self.selected_combo = self._product_combos[14]

            self.selected_products = self.selected_combo['products']

            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_sixteenth_combo(self):
        try:
            self.selected_combo = self._product_combos[15]

            self.selected_products = self.selected_combo['products']
            
            next_category = self.selected_combo.get('next_category')
            if next_category is not None:
                self.next_category = next_category
                self._add_combo = True

            self.dialog_search_combos_by_image.hide()
            self.create_dialog_search_products_by_image()
            self.dialog_search_products_by_image.exec_()
        except:
            return

    def action_first_product(self):
        try:
            product = self.selected_products[0]

            product_id = product.get('id')

            self.dialog_search_products_by_image.hide()

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_second_product(self):
        try:
            product = self.selected_products[1]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_third_product(self):
        try:
            product = self.selected_products[2]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_fourth_product(self):
        try:
            product = self.selected_products[3]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_fifth_product(self):
        try:
            product = self.selected_products[4]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_sixth_product(self):
        try:
            product = self.selected_products[5]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_seventh_product(self):
        try:
            product = self.selected_products[6]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_eighth_product(self):
        try:
            product = self.selected_products[7]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_eighth_product(self):
        try:
            product = self.selected_products[7]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_ninth_product(self):
        try:
            product = self.selected_products[8]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_tenth_product(self):
        try:
            product = self.selected_products[9]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_eleventh_product(self):
        try:
            product = self.selected_products[10]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_twelfth_product(self):
        try:
            product = self.selected_products[11]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_thirteenth_product(self):
        try:
            product = self.selected_products[12]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_fourteenth_product(self):
        try:
            product = self.selected_products[13]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_fifteenth_product(self):
        try:
            product = self.selected_products[14]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def action_sixteenth_product(self):
        try:
            product = self.selected_products[15]


            product_id = product.get('id')
            self.dialog_search_products_by_image.hide()

            product, = self._Product.find([('id','=',product_id)], limit=1)

            self.add_product(product=product, quantity=1)
        except:
            return

    def print_odt_invoice(self, sale, direct_print=False,
            reprint=False):

        if not sale.get('invoices'):
            return
        invoice_id = sale['invoices'][0]
        model = u'account.invoice'

        data = {
            'model': model,
            'reprint':reprint,
            'sale_origin':sale['origin'],
            'action_id': self._action_report['id'],
            'id': invoice_id,
            'ids': [invoice_id],
        }
        ctx = {'date_format': u'%d/%m/%Y'}
        ctx.update(self._context)
        Action.exec_report(self.conn, u'simplified.account.invoice',
            data, direct_print=direct_print, printer=self.printer_sale_name[1],
            context=ctx)

    def print_odt_short_invoice(self, sale, direct_print=False,
            reprint=False):

        if not sale.get('invoices'):
            return
        invoice_id = sale['invoices'][0]
        model = u'account.invoice'

        data = {
            'model': model,
            'reprint':reprint,
            'sale_origin':sale['origin'],
            'action_id': self._action_short_report['id'],
            'id': invoice_id,
            'ids': [invoice_id],
        }
        ctx = {'date_format': u'%d/%m/%Y'}
        ctx.update(self._context)
        Action.exec_report(self.conn, u'simplified.account.invoice',
            data, direct_print=direct_print, printer=self.printer_sale_name[1],
            context=ctx)

    def print_odt_command(self, sale, direct_print=False,
            reprint=False):

        if not sale:
            return

        sale_id = sale['id']
        model = u'sale.sale'

        data = {
            'model': model,
            'reprint':reprint,
            'action_id': self._action_report_command['id'],
            'id': sale_id,
            'ids': [sale_id],
        }

        ctx = {'date_format': u'%d/%m/%Y'}
        ctx.update(self._context)

        Action.exec_report(self.conn, u'command.sale.sale',
            data, direct_print=True, printer=self.printer_sale_name[1],
            context=ctx)

    def print_odt_statement(self, statement_id=None, direct_print=False):
        if not statement_id:
            return
        model = u'account.statement'
        data = {
            'model': model,
            'action_id': self._action_report_statement['id'],
            'id': statement_id,
            'ids': [statement_id],
        }
        ctx = {'date_format': u'%d/%m/%Y'}
        ctx.update(self._context)
        Action.exec_report(self.conn, u'account.statement',
            data, direct_print=direct_print, context=ctx)

    def print_purchase_report(self, purchase_id=None, direct_print=True):
        if not purchase_id:
            return
        model = u'purchase.purchase'
        data = {
            'model': model,
            'action_id': self._action_report_purchase['id'],
            'id': purchase_id,
            'ids': [purchase_id],
        }
        ctx = {'date_format': u'%d/%m/%Y'}
        ctx.update(self._context)
        Action.exec_report(self.conn, u'purchase.purchase',
            data, direct_print=direct_print, context=ctx)

    def print_invoice_binnacle(self, start_date=None, end_date=None,
            direct_print=False):
        model = u'account.invoice.report.print'
        data = {
            'model': model,
            'action_id': self._action_report_invoice_binnacle['id'],
            'ids': [],
            'from_date':start_date,
            'to_date':end_date,
        }
        ctx = {'date_format': u'%d/%m/%Y',
            'company':self._user['company'], }
        ctx.update(self._context)
        Action.exec_report(self.conn, u'account.invoice.report.print',
            data, direct_print=direct_print, context=ctx)

    def print_product_by_location(self, end_date=None,
            direct_print=False):
        model = u'product.by_location.report'
        data = {
            'model': model,
            'action_id': self._action_report_product_by_location['id'],
            'ids': [],
            'stock_date_end':end_date,
            'warehouse':self._default_warehouse,
        }
        ctx = {'date_format': u'%d/%m/%Y',
            'company': self._user['company'], }
        ctx.update(self._context)
        Action.exec_report(self.conn, u'product.by_location.report',
            data, direct_print=direct_print, context=ctx)

    def print_auth_report(self, direct_print=False):
        model = u'account.invoice.authorization.report.print'
        data = {
            'model': model,
            'action_id': self._action_report_auth_binnacle['id'],
            'ids': [],
        }
        ctx = {'date_format': u'%d/%m/%Y',
            'company':self._user['company'], }
        ctx.update(self._context)
        Action.exec_report(self.conn, u'account.invoice.authorization.report.print',
            data, direct_print=direct_print, context=ctx)

    def action_comment(self):
        self.dialog_comment.exec_()
        comment = self.field_comment_ask.text()
        if comment:
            self._PosSale.write([self._sale['id']], {'comment': comment})

    def action_position(self):
        self.dialog_position.exec_()
        position = self.field_position_ask.text()
        if hasattr(self, 'field_position') and position:
            self.field_position.setText(position)
            self._PosSale.write([self._sale['id']], {'position': position})

    def action_agent(self):
        self.dialog_agent.exec_()

    def _set_commission_amount(self, untaxed_amount, commission):
        untaxed_amount = int(untaxed_amount)
        commission = int(commission)
        total = ((untaxed_amount * commission) / 100)
        self.field_commission_amount.setText(str(total))

    def action_party(self):
        self.dialog_search_parties.clear_rows()
        domain = [
            #('tax_identifier', '!=', None),
        ]
        parties = self._Party.find(domain, order=[('id','DESC')],
            limit=100)
        self.dialog_search_parties.set_from_values(parties)
        self.dialog_search_parties.execute()

    def action_global_discount(self, sale_id=None):
        self.dialog_global_discount.exec_()
        discount = self.field_global_discount_ask.text()
        if discount and discount.isdigit():
            if self._model_sale_lines.rowCount() > 0:
                lines = [line['id'] for line in self._model_sale_lines._data]
                self.set_discount(int(discount), lines)

    def _print_order(self, sale_id, kind, order_number, repeat=False, reversion=False):
        result = False
        try:
            if int(order_number) > 1:
                repeat = True
            orders = self._PosSale.get_order2print(sale_id, reversion, repeat, self._context)
            result = self.receipt_order.print_orders(orders, reversion, kind)
        except:
            logging.error('Printing order fail!')
        return result

    def action_new_sale(self):
        if not self._sale['id']:
            return
        if self._ask_new_sale():
            self.createNewSale()

    def action_invoice_report(self):
        self.dialog_select_dates.exec_()

    def action_print_product_by_location(self):
        self.dialog_select_end_date.exec_()

    def action_delivery_note(self):
        self.dialog_search_delivery_note.exec_()

    def action_auth_report(self):
        self.print_auth_report()

    def wizard_new_sale(self):
        self.action_position()
        self.action_salesman()

    def numpad_price_clicked(self):
        code = self.label_input.text()
        product = self._search_product(code)
        if not product:
            return

    def _ask_new_sale(self):
        dialog = self.dialog('new_sale', response=True)
        res = dialog.exec_()
        if res == DIALOG_REPLY_NO:
            return False
        return True

    def action_cancel(self):

        if not self._sale['id']:
            return
        if self._sale['state'] == 'draft':
            return
        if self._sale['state'] == 'cancel':
            return
        if self._state == 'cash' and not self.user_can_delete:
            return self.dialog('not_permission_delete_sale')
        dialog = self.dialog('cancel_sale', response=True)
        response = dialog.exec_()
        if response == DIALOG_REPLY_NO:
            return
        self._PosSale.cancel_sale([], self._sale['id'], self._context)
        dialog = self.dialog('cancel_sale_success')
        dialog.exec_()
        self.field_password_for_cancel_ask.setText('')
        self.set_state('cancel')
        self.clear_right_panel()
        self.createNewSale()

    def action_credit_sale(self):
        if not self._sale['id']:
            return self.dialog('not_permission_for_credit').exec_()
        if self._sale['state'] == 'draft':
            return self.dialog('not_permission_for_credit_draft').exec_()
        if self._sale['is_credit_sale'] == True:
            return self.dialog('sale_is_from_credit_note').exec_()
        if self._sale['has_credit_sale'] == True:
            return self.dialog('sale_has_credit_note').exec_()
        if self._sale['state'] in ['cancel']:
            return self.dialog('sale_cancel_credit_note').exec_()
        elif self._sale['state'] not in ['confirmed', 'processing', 'done']:
            return self.dialog('not_permission_for_credit').exec_()
        if self._state == 'cash' and not self.user_can_delete:
            return self.dialog('not_permission_for_credit').exec_()

        dialog = self.dialog('credit_sale', response=True)
        response = dialog.exec_()
        if response == DIALOG_REPLY_NO:
            return
        res = self._PosSale.credit_sale([], self.field_journal_id,
            self._sale['id'], self._context)
        dialog = self.dialog('sale_credited')
        dialog.exec_()
        if res['res'] == 'error':
            return self.dialog(res['msg']).exec_()
        if res['return_sale']:
            return_sale = self.get_return_sale(res['return_sale'])
            self.print_odt_short_invoice(return_sale, direct_print=True, reprint=False)
            self.dialog('order_successfully').exec_()

        self.field_invoice.setText(res['msg'])
        self.field_invoice_state.setText(self.tr('PROCESSING'))
        self._sale['state'] = 'processing'
        self.addPaymentLine(res['line_id'])
        self.field_password_for_cancel_ask.setText('')
        self.clear_right_panel()
        self.createNewSale()

    def action_search_product(self):
        if self._state == 'cash':
            return
        self.dialog_search_products.clear_rows()

        dom = [
                ('active', '=', True),
                ('salable','=',True),
                ('consumable','=',False),
            ]

        products = self._Product.find(dom, 
            order=[('template.code', 'ASC')],
            limit=20,
            context=self.stock_context
        )
        self.dialog_search_products.set_from_values(products)
        response = self.dialog_search_products.execute()
        if response == DIALOG_REPLY_NO:
            return

    def action_search_category(self):
        if self._state == 'cash':
            return
        response = self.dialog_search_categories_by_image.exec_()
        if response == DIALOG_REPLY_NO:
            return

    def action_search_combo(self):
        if self._state == 'cash':
            return
        response = self.dialog_search_combos_by_image.exec_()
        if response == DIALOG_REPLY_NO:
            return

    def action_search_purchase(self):
        self.dialog_search_purchases.clear_rows()
        dom = [
                ('state', 'in', ['quotation', 'confirmed',
                    'processing', 'done']),
            ]

        purchases = self._PosPurchase.find(dom, order=[('id', 'DESC')],
            limit=100)
        self.dialog_search_purchases.set_from_values(purchases)
        response = self.dialog_search_purchases.execute()
        if response == DIALOG_REPLY_NO:
            return

    def action_search_product_by_image(self):
        if self._state == 'cash':
            return
        self.dialog_search_products_by_image.exec_()

    def action_search_category_by_image(self):
        if self._state == 'cash':
            return
        self.dialog_search_categories_by_image.exec_()

    def action_agent_by_image(self):
        if self._state == 'cash':
            return
        self.dialog_search_agent_by_image.exec_()

    def action_search_sale(self):

        two_weeks_ago_date = date.today() - timedelta(100)
        dom = [
                #('web_shop', '=', self._user['shop']),
                ('sale_date', '>=', two_weeks_ago_date),
            ]

        sales = self._PosSale.find(dom, order=[('id', 'DESC')],
            limit=300)
        self.dialog_search_sales.set_from_values(sales)

        response = self.dialog_search_sales.execute()
        if response == DIALOG_REPLY_NO:
            return

    def on_selected_sale(self):
        sale_id = self.dialog_search_sales.get_id()
        if not sale_id:
            return
        self.load_sale(sale_id)
        self.setFocus()
        self.label_input.setFocus()
        self.grabKeyboard()

    def on_selected_party(self):
        party_id = self.dialog_search_parties.get_id()
        if not party_id:
            return

        party, = self._Party.find([
            ('id', '=', party_id)
        ])

        values = {
            'party': party_id,
            'invoice_party': party_id,
            'invoice_address': party['addresses'][0],
            'shipment_address': party['addresses'][0],
        }

        values['payment_term'] = self._default_payment_term_id
        self.field_payment_term_id = self._default_payment_term_id
        self.field_payment_term.setText(self._default_payment_term_name)

        self._PosSale.write([self._sale['id']], values)

        self.party_id = party_id
        self.field_party.setText(party['name'])
        if party.get('tax_identifier'):
            if party.get('tax_identifier.',{}).get('code',{}):
                self.field_tax_identifier.setText(party['tax_identifier.']['code'])
        else:
            self.field_tax_identifier.setText('|N')
        self.field_address.setText(party['city'] or '')

        self.message_bar.set('system_ready')
        self.label_input.setFocus()
        self.grabKeyboard()

    def on_selected_purchase(self):
        purchase_id = self.dialog_search_purchases.get_id()
        if not purchase_id:
            return

        purchase, = self._PosPurchase.find([
            ('id', '=', purchase_id)
        ])

        if not purchase:
            return
        else:
            self.purchase = purchase

            self._model_purchase_lines.setDomain(domain=None)

            for line_id in purchase['lines']:
                self._model_purchase_lines.appendId(line_id)

            self.field_purchase_party.setText(purchase['party.']['name'])
            self.field_purchase_number.setText(purchase['number'])
            self.field_purchase_description.setText(purchase['description'])
            self.field_purchase_date.setDate(purchase['purchase_date'])
            self.field_purchase_warehouse.setText(purchase['warehouse.']['name'])
            self.field_purchase_state.setText(purchase['state'])
            self.dialog_purchase.exec_()

    def action_load_statement(self):

        result = self._Statement.check_open_statement([], self._context)
        if result.get('error'):
            self.dialog('more_than_one_statement_open')
            return
        if result['is_open'] == True:
            statement_id = result['statement']

        if not statement_id:
            return

        try:
            statement, = self._Statement.find([
                ('id','=',statement_id),
            ], limit=1)
        except:
            self.dialog('more_than_one_statement_open')
            return

        statement_lines = self._StatementLine.find([
            ('statement', '=', statement_id)
        ])

        start_balance = statement['start_balance']
        end_balance = statement['calculated_end_balance']

        
        leftout = Decimal('0')
        try:
            if statement['leftout']:
                leftout = statement['leftout']
        except:
            pass

        difference = start_balance + end_balance + leftout

        self.field_statement_date.setDate(statement['date'])

        self.field_statement_start_balance.setValue(start_balance)
        self.field_statement_end_balance.setValue(end_balance)
        self.field_statement_previous_leftout.setValue(leftout)

        self.field_statement_two_hundred.setValue(0)
        self.field_statement_one_hundred.setValue(0)
        self.field_statement_fifty.setValue(0)
        self.field_statement_twenty.setValue(0)
        self.field_statement_ten.setValue(0)
        self.field_statement_fifth.setValue(0)
        self.field_statement_one.setValue(0)
        self.field_statement_currency.setValue(0)
        self.field_statement_voucher.setValue(0)
        self.field_statement_surplus.setValue(0)
        self.field_statement_surplus_potato.setValue(0)
        self.field_statement_surplus_gizzard.setValue(0)
        self.field_statement_count.setValue(0)

        self.field_statement_difference.setValue(difference)
        self._model_statement_lines.setDomain([])
        if len(statement_lines) > 0:

            self._model_statement_lines.setDomain(domain=None)

            for line in statement_lines:
                line_id = line['id']
                self._model_statement_lines.appendId(line_id)

            self.dialog_statement.ok_button.setEnabled(False)
            self.dialog_statement.exec_()
        else:
            self.dialog_statement.ok_button.setEnabled(False)
            self.dialog_statement.exec_()
            #self.dialog('no_statement_lines')
            return

    def load_sale(self, sale_id):
        # loads only draft sales
        self.is_clear_right_panel = True
        self.clear_data()
        self.clear_left_panel()
        self.clear_right_panel()
        sale, = self._PosSale.find([
            ('id', '=', sale_id),
        ])
        if not sale:
            return
        def flatten_dict(dd, separator ='', prefix =''):
            return { prefix + separator + k if prefix else k : v
                for kk, vv in dd.items()
                for k, v in flatten_dict(vv, separator, kk).items()
                } if isinstance(dd, dict) else { prefix : dd }
        flat_sale = flatten_dict(sale)
        self._sale.update(flat_sale)
        #self._model_payment_lines.setDomain([('statement.state','=','draft')], \
        #    order=[('id','DESC')])
        self.field_order_number.setText(flat_sale['number'] or '')
        self.field_delivery_method.setText(flat_sale['delivery_method'] or '')
        self._set_sale_date()
        if hasattr(self, 'field_position'):
            self.field_position.setText(flat_sale['position'] or '')
        if flat_sale.get('agent'):
            self.field_agent.setText(flat_sale['agent.party.name'] or '')
            self.field_agent_id = flat_sale['agent']
        if flat_sale.get('party.tax_identifier.code'):
            self.field_nit.setText(str(flat_sale['party.tax_identifier.code']) or '')
        if flat_sale.get('party.city'):
            self.field_address.setText(str(flat_sale['party.city']) or '')
        if flat_sale.get('fiscal_invoice_state'):
            self.field_invoice_state.setText(flat_sale['fiscal_invoice_state'])
        if flat_sale.get('invoice_with_serie'):
            self.field_invoice.setText(flat_sale['invoice_with_serie'])

        self.field_change.zero()

        for line_id in flat_sale['lines']:
            self.addSaleLineModel(line_id)

        self.set_state('add')
        self.party_id = flat_sale['party']
        self.field_party.setText(flat_sale['party.name'])
        self.set_amounts()
        self.set_amount_received()
        self.set_discount_amount()
        self._clear_context()
        self.field_amount.zero()

        if sale['state'] == 'draft':
            self.left_table_lines.setEnabled(True)

    def set_change_amount(self):
        res = self._get_sum_amount_paid() - self._get_total_amount()
        self.field_change.setText(res)

    def set_amount_received(self, cash_received=ZERO):
        if cash_received:
            amount = cash_received
        else:
            amount = self._sale['paid_amount']
        self.field_paid.setText(amount)

    def set_amounts(self, res=None):
        if not res:
            res = self._PosSale.get_amounts([self._sale['id']], self._context)
            self._sale.update(res)

        self.field_discount.setText(self._sale['total_discount'])
        self.field_untaxed_amount.setText(self._sale['untaxed_amount'])
        self.field_total_amount.setText(self._sale['total_amount'])

    def _get_products_by_category(self, cat_id):
        records = self._Product.find([
            ('template.salable', '=', True),
            ('template.categories', '=', cat_id),
        ], context=self.stock_context)
        return [[r['id'], r['code'], r['template.name'], r['template.list_price'],
                r['description'], #r['template']
            ]
            for r in records]

    def get_product_by_categories(self):
        domain = [
            ('parent', '=', None),
            ('accounting', '=', False),
            ('id', 'in', self._shop['categories'])
        ]
        self.allow_categories = self._Category.find(domain)

        for cat in self.allow_categories:
            cat['icon'] = get_svg_icon(cat['name_icon'])
            cat['items'] = self._get_products_by_category(cat['id'])
        return self.allow_categories

    def _get_childs(self, parent_cat):
        res = {}
        for cat_id in parent_cat['childs']:
            sub_categories = self._Category.find([
                ('parent', '=', parent_cat['id'])
            ])

            for sub_cat in sub_categories:
                res.update(self._get_childs(sub_cat))
        res = {
            'id': parent_cat['id'],
            'name': parent_cat['name'],
            'childs': parent_cat['childs'],
            'records': [],
            'obj': parent_cat,
        }
        return res

    def get_category_items(self, records):
        records_by_category = {}

        def _get_tree_categories(cat):
            sub_categories = {}
            if not cat['childs']:
                sub_categories[cat['name']] = records_by_category.get(cat['id']) or []
            else:
                for child in cat['childs']:
                    sub_categories.update(_get_tree_categories(
                        self.target_categories[child]['obj']))
            return sub_categories

        for record in records:
            cat_id = record.get('template.account_category')
            if cat_id not in records_by_category.keys():
                records_by_category[cat_id] = []

            records_by_category[cat_id].append(record)

        res = {}
        for ac in self.allow_categories:
            res[ac['name']] = _get_tree_categories(ac)
        return res

    def on_selected_product(self):
        if self.dialog_search_products.current_row:
            self.clear_right_panel()
            self.add_product(product=self.dialog_search_products.current_row)
            #self.on_selected_new_product(
            #    code=self.dialog_search_products.current_row['code'])

    def on_selected_product_from_dialog(self):
        if self.dialog_search_products.current_row:
            self.clear_right_panel()
            #self.add_product(product=self.dialog_search_products.current_row)
            self.on_selected_new_product(
                code=self.dialog_search_products.current_row['code'])

    def on_selected_product_by_image(self):
        if self.dialog_search_products.current_row:
            self.clear_right_panel()
            self.on_selected_new_product(
                code=self.dialog_search_products.current_row['code'])

    def on_selected_category_by_image(self):

        if self.dialog_search_products.current_row:
            self.clear_right_panel()
            self.on_selected_new_product(
                code=self.dialog_search_products.current_row['code'])

    def on_selected_combo_by_image(self):

        if self.dialog_search_products.current_row:
            self.clear_right_panel()
            self.on_selected_new_product(
                code=self.dialog_search_products.current_row['code'])


    def on_selected_delivery_method(self):
        return

    def on_selected_product_quantity(self):
        if self.dialog_search_products.current_row:
            self.clear_right_panel()
            self.add_product(product=self.dialog_search_products.current_row)

    def on_selected_icon_product(self):
        if self.dialog_search_products.current_row:
            code = self.dialog_search_products.current_row['code']
            products = self._Product.find([
                ('code', '=', code)
            ])
            if not products:
                return
            product = products[0]
            image = Image(name='product_icon')
            image.set_image(product['image'])
            image.activate()

    def on_selected_stock_product(self):
        if self.dialog_search_products.current_row:
            code = self.dialog_search_products.current_row['code']
            res = self._Product.get_stock_by_locations([str(code)], self._context)
            self.dialog_product_stock.update_values(res)
            self.dialog_product_stock.show()

    def on_selected_item(self, product_id):
        if product_id:
            self.clear_right_panel()
            self.add_product(id=product_id)


    def create_dialog_purchase(self):
        title = self.tr('COMPRAS')
        vbox_product = QVBoxLayout()
        grid = QGridLayout()

        label_purchase_party = QLabel(self.tr('PARTY:'))
        label_purchase_party.setObjectName('label_purchase_party')
        grid.addWidget(label_purchase_party, 1, 1)
        self.field_purchase_party = QLineEdit()
        self.field_purchase_party.setObjectName('field_purchase_party')
        self.field_purchase_party.setEnabled(False)
        grid.addWidget(self.field_purchase_party, 1, 2)

        label_purchase_number = QLabel(self.tr('NUMBER:'))
        label_purchase_number.setObjectName('label_purchase_number')
        grid.addWidget(label_purchase_number, 2, 1)
        self.field_purchase_number = QLineEdit()
        self.field_purchase_number.setObjectName('field_purchase_party')
        self.field_purchase_number.setEnabled(False)
        grid.addWidget(self.field_purchase_number, 2, 2)

        label_purchase_description = QLabel(self.tr('DESCRIPTION:'))
        label_purchase_description.setObjectName('label_purchase_description')
        grid.addWidget(label_purchase_description, 3, 1)
        self.field_purchase_description = QLineEdit()
        self.field_purchase_description.setObjectName('field_purchase_party')
        self.field_purchase_description.setEnabled(False)
        grid.addWidget(self.field_purchase_description, 3, 2)

        label_purchase_date = QLabel(self.tr('PURCHASE DATE:'))
        label_purchase_date.setObjectName('label_purchase_date')
        grid.addWidget(label_purchase_date, 4, 1)
        self.field_purchase_date = QDateEdit()
        self.field_purchase_date.setDisplayFormat("dd/MM/yyyy")
        self.field_purchase_date.setObjectName('field_purchase_date')
        self.field_purchase_date.setEnabled(False)
        grid.addWidget(self.field_purchase_date, 4, 2)

        label_purchase_warehouse = QLabel(self.tr('WAREHOUSE:'))
        label_purchase_warehouse.setObjectName('label_purchase_warehouse')
        grid.addWidget(label_purchase_warehouse, 5, 1)
        self.field_purchase_warehouse = QLineEdit()
        self.field_purchase_warehouse.setObjectName('field_purchase_warehouse')
        self.field_purchase_warehouse.setEnabled(False)
        grid.addWidget(self.field_purchase_warehouse, 5, 2)

        label_purchase_state = QLabel(self.tr('STATE:'))
        label_purchase_state.setObjectName('label_purchase_state')
        grid.addWidget(label_purchase_state, 6, 1)
        self.field_purchase_state = QLineEdit()
        self.field_purchase_state.setObjectName('field_purchase_state')
        self.field_purchase_state.setEnabled(False)
        grid.addWidget(self.field_purchase_state, 6, 2)

        vbox_product.addLayout(grid)

        col_sizes_tlines = [field['width'] for field in self.fields_purchase_line]
        table = TableView('table_purchase_lines', self._model_purchase_lines,
            col_sizes_tlines)
        methods = {
            'on_accepted_method': 'on_accept_purchase',
        }
        self.dialog_purchase = TableDialog(self, methods=methods,
            widgets=vbox_product, table=table, title=title,
            cols_width=col_sizes_tlines)

    def create_dialog_statement(self):
        title = self.tr('CIERRE DE CAJA')
        vbox_statement = QVBoxLayout()
        grid = QGridLayout()

        label_statement_date = QLabel(self.tr('FECHA:'))
        label_statement_date.setObjectName('label_statement_date')
        grid.addWidget(label_statement_date, 1, 1)
        self.field_statement_date = QDateEdit()
        self.field_statement_date.setDisplayFormat("dd/MM/yyyy")
        self.field_statement_date.setObjectName('field_statement_date')
        self.field_statement_date.setEnabled(False)
        grid.addWidget(self.field_statement_date, 1, 2)

        label_statement_start_balance = QLabel(self.tr('SALDO INICIAL:'))
        label_statement_start_balance.setObjectName('label_statement_start_balance')
        #grid.addWidget(label_statement_start_balance, 2, 1)
        self.field_statement_start_balance = QDoubleSpinBox()
        self.field_statement_start_balance.setObjectName('field_statement_start_balance')
        self.field_statement_start_balance.setMinimum(0)
        self.field_statement_start_balance.setMaximum(100000)
        self.field_statement_start_balance.setDecimals(2)
        self.field_statement_start_balance.setAlignment(alignRight)
        self.field_statement_start_balance.setEnabled(False)
        #grid.addWidget(self.field_statement_start_balance, 2, 2)

        label_statement_previous_leftout = QLabel(self.tr('SALDO PIEZAS ANTERIOR:'))
        label_statement_previous_leftout.setObjectName('label_statement_previous_leftout')
        #grid.addWidget(label_statement_previous_leftout, 2, 3)
        self.field_statement_previous_leftout = QDoubleSpinBox()
        self.field_statement_previous_leftout.setObjectName('field_statement_previous_leftout')
        self.field_statement_previous_leftout.setMinimum(0)
        self.field_statement_previous_leftout.setMaximum(100000)
        self.field_statement_previous_leftout.setDecimals(2)
        self.field_statement_previous_leftout.setAlignment(alignRight)
        self.field_statement_previous_leftout.setEnabled(False)
        #grid.addWidget(self.field_statement_previous_leftout, 2, 4)

        label_statement_end_balance = QLabel(self.tr('VENTAS - GASTOS:'))
        label_statement_end_balance.setObjectName('label_statement_end_balance')
        #grid.addWidget(label_statement_end_balance, 3, 1)
        self.field_statement_end_balance = QDoubleSpinBox()
        self.field_statement_end_balance.setObjectName('field_statement_end_balance')
        self.field_statement_end_balance.setMinimum(0)
        self.field_statement_end_balance.setMaximum(100000)
        self.field_statement_end_balance.setDecimals(2)
        self.field_statement_end_balance.setAlignment(alignRight)
        self.field_statement_end_balance.setEnabled(False)
        #grid.addWidget(self.field_statement_end_balance, 3, 2)

        label_statement_difference = QLabel(self.tr('DIFERENCIA:'))
        label_statement_difference.setObjectName('label_statement_difference')
        #grid.addWidget(label_statement_difference, 4, 1)
        self.field_statement_difference = QDoubleSpinBox()
        self.field_statement_difference.setObjectName('field_statement_difference')
        self.field_statement_difference.setMinimum(-100000)
        self.field_statement_difference.setMaximum(100000)
        self.field_statement_difference.setDecimals(2)
        self.field_statement_difference.setAlignment(alignRight)
        self.field_statement_difference.setEnabled(False)
        #grid.addWidget(self.field_statement_difference, 4, 2)

        label_statement_two_hundred = QLabel(self.tr('BILLETES DE 200:'))
        label_statement_two_hundred.setObjectName('label_statement_two_hundred')
        grid.addWidget(label_statement_two_hundred, 1, 3)
        self.field_statement_two_hundred = QDoubleSpinBox()
        self.field_statement_two_hundred.setObjectName('field_statement_two_hundred')
        self.field_statement_two_hundred.setMinimum(0)
        self.field_statement_two_hundred.setMaximum(100000)
        self.field_statement_two_hundred.setDecimals(0)
        self.field_statement_two_hundred.setAlignment(alignRight)
        self.field_statement_two_hundred.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_two_hundred, 1, 4)

        label_statement_one_hundred = QLabel(self.tr('BILLETES DE 100:'))
        label_statement_one_hundred.setObjectName('label_statement_one_hundred')
        grid.addWidget(label_statement_one_hundred, 2, 1)
        self.field_statement_one_hundred = QDoubleSpinBox()
        self.field_statement_one_hundred.setObjectName('field_statement_one_hundred')
        self.field_statement_one_hundred.setMinimum(0)
        self.field_statement_one_hundred.setMaximum(100000)
        self.field_statement_one_hundred.setDecimals(0)
        self.field_statement_one_hundred.setAlignment(alignRight)
        self.field_statement_one_hundred.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_one_hundred, 2, 2)

        label_statement_fifty = QLabel(self.tr('BILLETES DE 50:'))
        label_statement_fifty.setObjectName('label_statement_fifty')
        grid.addWidget(label_statement_fifty, 2, 3)
        self.field_statement_fifty = QDoubleSpinBox()
        self.field_statement_fifty.setObjectName('field_statement_fifty')
        self.field_statement_fifty.setMinimum(0)
        self.field_statement_fifty.setMaximum(100000)
        self.field_statement_fifty.setDecimals(0)
        self.field_statement_fifty.setAlignment(alignRight)
        self.field_statement_fifty.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_fifty, 2, 4)

        label_statement_twenty = QLabel(self.tr('BILLETES DE 20:'))
        label_statement_twenty.setObjectName('label_statement_twenty')
        grid.addWidget(label_statement_twenty, 3, 1)
        self.field_statement_twenty = QDoubleSpinBox()
        self.field_statement_twenty.setObjectName('field_statement_twenty')
        self.field_statement_twenty.setMinimum(0)
        self.field_statement_twenty.setMaximum(100000)
        self.field_statement_twenty.setDecimals(0)
        self.field_statement_twenty.setAlignment(alignRight)
        self.field_statement_twenty.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_twenty, 3, 2)

        label_statement_ten = QLabel(self.tr('BILLETES DE 10:'))
        label_statement_ten.setObjectName('label_statement_ten')
        grid.addWidget(label_statement_ten, 3, 3)
        self.field_statement_ten = QDoubleSpinBox()
        self.field_statement_ten.setObjectName('field_statement_ten')
        self.field_statement_ten.setMinimum(0)
        self.field_statement_ten.setMaximum(100000)
        self.field_statement_ten.setDecimals(0)
        self.field_statement_ten.setAlignment(alignRight)
        self.field_statement_ten.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_ten, 3, 4)

        label_statement_fifth = QLabel(self.tr('BILLETES DE 5:'))
        label_statement_fifth.setObjectName('label_statement_fifth')
        grid.addWidget(label_statement_fifth, 4, 1)
        self.field_statement_fifth = QDoubleSpinBox()
        self.field_statement_fifth.setObjectName('field_statement_fifth')
        self.field_statement_fifth.setMinimum(0)
        self.field_statement_fifth.setMaximum(100000)
        self.field_statement_fifth.setDecimals(0)
        self.field_statement_fifth.setAlignment(alignRight)
        self.field_statement_fifth.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_fifth, 4, 2)

        label_statement_one = QLabel(self.tr('BILLETES DE 1:'))
        label_statement_one.setObjectName('label_statement_one')
        grid.addWidget(label_statement_one, 4, 3)
        self.field_statement_one = QDoubleSpinBox()
        self.field_statement_one.setObjectName('field_statement_one')
        self.field_statement_one.setMinimum(0)
        self.field_statement_one.setMaximum(100000)
        self.field_statement_one.setDecimals(0)
        self.field_statement_one.setAlignment(alignRight)
        self.field_statement_one.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_one, 4, 4)

        label_statement_currency = QLabel(self.tr('MONEDAS:'))
        label_statement_currency.setObjectName('label_statement_currency')
        grid.addWidget(label_statement_currency, 5, 1)
        self.field_statement_currency = QDoubleSpinBox()
        self.field_statement_currency.setObjectName('field_statement_currency')
        self.field_statement_currency.setMinimum(0)
        self.field_statement_currency.setMaximum(100000)
        #self.field_statement_currency.setDecimals(0)
        self.field_statement_currency.setAlignment(alignRight)
        self.field_statement_currency.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_currency, 5, 2)

        label_statement_voucher = QLabel(self.tr('VOUCHER:'))
        label_statement_voucher.setObjectName('label_statement_voucher')
        grid.addWidget(label_statement_voucher, 5, 3)
        self.field_statement_voucher = QDoubleSpinBox()
        self.field_statement_voucher.setObjectName('field_statement_voucher')
        self.field_statement_voucher.setMinimum(0)
        self.field_statement_voucher.setMaximum(100000)
        #self.field_statement_voucher.setDecimals(0)
        self.field_statement_voucher.setAlignment(alignRight)
        self.field_statement_voucher.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_voucher, 5, 4)

        label_statement_surplus = QLabel(self.tr('SOBRANTE TORTILLA:'))
        label_statement_surplus.setObjectName('label_statement_surplus')
        grid.addWidget(label_statement_surplus, 6, 1)
        self.field_statement_surplus = QDoubleSpinBox()
        self.field_statement_surplus.setObjectName('field_statement_surplus')
        self.field_statement_surplus.setMinimum(0)
        self.field_statement_surplus.setMaximum(100000)
        self.field_statement_surplus.setDecimals(0)
        self.field_statement_surplus.setAlignment(alignRight)
        self.field_statement_surplus.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_surplus, 6, 2)

        label_statement_surplus_potato = QLabel(self.tr('SOBRANTE PAPA FRITA:'))
        label_statement_surplus_potato.setObjectName('label_statement_surplus_potato')
        grid.addWidget(label_statement_surplus_potato, 6, 3)
        self.field_statement_surplus_potato = QDoubleSpinBox()
        self.field_statement_surplus_potato.setObjectName('field_statement_surplus_potato')
        self.field_statement_surplus_potato.setMinimum(0)
        self.field_statement_surplus_potato.setMaximum(100000)
        self.field_statement_surplus_potato.setDecimals(0)
        self.field_statement_surplus_potato.setAlignment(alignRight)
        self.field_statement_surplus_potato.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_surplus_potato, 6, 4)

        label_statement_surplus_gizzard = QLabel(self.tr('SOBRANTE MOLLEJA:'))
        label_statement_surplus_gizzard.setObjectName('label_statement_surplus_gizzard')
        grid.addWidget(label_statement_surplus_gizzard, 7, 1)
        self.field_statement_surplus_gizzard = QDoubleSpinBox()
        self.field_statement_surplus_gizzard.setObjectName('field_statement_surplus_gizzard')
        self.field_statement_surplus_gizzard.setMinimum(0)
        self.field_statement_surplus_gizzard.setMaximum(100000)
        self.field_statement_surplus_gizzard.setDecimals(0)
        self.field_statement_surplus_gizzard.setAlignment(alignRight)
        self.field_statement_surplus_gizzard.valueChanged.connect(
            lambda value: self.update_end_amount(value, 'name')
        )
        grid.addWidget(self.field_statement_surplus_gizzard, 7, 2)

        label_statement_count = QLabel(self.tr('EFECTIVO DISPONIBLE:'))
        label_statement_count.setObjectName('label_statement_count')
        grid.addWidget(label_statement_count, 7, 3)
        self.field_statement_count = QDoubleSpinBox()
        self.field_statement_count.setObjectName('field_statement_count')
        self.field_statement_count.setMinimum(-100000)
        self.field_statement_count.setMaximum(100000)
        self.field_statement_count.setDecimals(2)
        self.field_statement_count.setAlignment(alignRight)
        self.field_statement_count.setEnabled(False)
        grid.addWidget(self.field_statement_count, 7, 4)


        vbox_statement.addLayout(grid)

        col_sizes_tlines = [field['width'] for field in self.fields_statement_line]
        table = TableView('table_statement_lines', self._model_statement_lines,
            col_sizes_tlines)
        methods = {
            'on_accepted_method': 'close_statement',
        }
        self.dialog_statement = TableDialog(self, methods=methods,
            widgets=vbox_statement, table=table, title=title,
            cols_width=col_sizes_tlines)
        #self.dialog_statement.accepted.connect(self.dialog_statement_accepted)
        self.dialog_statement.ok_button.setEnabled(False)

    # install our own except hook.
    def except_hook(self, exc=None, tb=None):
        if not exc or not tb:
            return
        if isinstance(exc,client.ProtocolError):
            url = exc.url
            headers = exc.headers
            error_code = exc.errcode
            error_msg = exc.errmsg
            complete_error = "Error de Protocolo " + " \n " + \
                str(url) + " \n " + \
                str(headers) +  " \n " +\
                str(error_code) + " \n " + str(error_msg)
            error_dialog = QuickDialog(self, 'error', string=complete_error)
            error_dialog.exec_()
            return
        if isinstance(exc, client.Fault):
            if str(exc.faultCode)=="UserError":
                stringFault = exc.faultString[0]
                info_dialog = QuickDialog(self, 'info', string=stringFault)
                info_dialog.exec_()
                return
            if str(exc.faultCode)=="UserWarning":
                stringFault = exc.faultString[0]
                info_dialog = QuickDialog(self, 'info', string=stringFault)
                info_dialog.exec_()
                return
            if exc.faultCode==1:
                stringFault = exc.faultString
                tupleFault = eval(stringFault)
                if tupleFault[0] == 'UserError' or tupleFault[0] == 'UserWarning':
                    info_dialog = QuickDialog(self, 'info', string=tupleFault[1][0])
                    info_dialog.exec_()
                    return
            if exc.faultCode==2:
                stringFault = exc.faultString
                tupleFault = eval(stringFault)
                if tupleFault[0] == 'UserWarning':
                    info_dialog = QuickDialog(self, 'info', string=tupleFault[1][0])
                    info_dialog.exec_()
                    return
            #if exc.faultCode==255:
            #    stringFault = exc[0]
            #    info_dialog = QuickDialog(self, 'info', string=stringFault)
            #    info_dialog.exec_()
            #    return
        dialog = self.dialog('unhandled_exception', response=True)
        response = dialog.exec_()
        if response == DIALOG_REPLY_YES:
            qcrash.show_report_dialog(
                window_title=self.tr('UNHANDLED EXCEPTION'),
                issue_title=str(exc),
                traceback=tb)

    def create_dialog_search_sales(self):
        headers = [
            ('id', self.tr('ID')),
            ('number', self.tr('NUMBER')),
            ('party.name', self.tr('PARTY')),
            ('party.tax_identifier.code', self.tr('TAX ID')),
            #('description', self.tr('DESCRIPTION')),
            ('sale_date', self.tr('DATE')),
            ('invoice_with_serie', self.tr('INVOICE')),
            ('total_amount', self.tr('TOTAL AMOUNT')),
            ('fiscal_invoice_state', self.tr('STATE')),
            #('position', self.tr('POSITION')),
        ]
        widths = [20, 
            85, 
            260, 
            90, 
            #300, 
            100, 
            200, 
            100,
            100
            ]
        title = self.tr('BUSCAR VENTAS...')
        methods = {
            'on_selected_method': 'on_selected_sale',
            'on_return_method': 'on_search_sale'
        }
        self.dialog_search_sales = SearchWindow(self, headers, None, methods,
            filter_column=[1, 2, 3, 4], cols_width=widths, title=title, fill=True)

        self.dialog_search_sales.activate_counter()

    def create_dialog_search_products(self):
        _cols_width = [10, 90, 350, 90, 90, 150, 90]
        headers = [
            ('id', self.tr('ID')),
            ('code', self.tr('CODE')),
            ('template.name', self.tr('NAME')),
            ('template.list_price', self.tr('PRICE')),
            ('quantity', self.tr('QUANTITY')),
            #('template.brand', self.tr('MARCA')),
            #('barcode', self.tr('BARRAS'),),
        ]

        title = self.tr('SEARCH PRODUCTS...')

        methods = {
            'on_selected_method': 'on_selected_product_from_dialog',
            'on_return_method': 'on_search_product',
            #'quantity': self.on_selected_stock_product
        }

        self.dialog_search_products = SearchWindow(self, headers, None,
            methods, title=title, cols_width=_cols_width,
            filter_column=[1,2,5,6], #code, template.name, template.brand, barcode
            fill=True)
        self.dialog_search_products.activate_counter()

    def create_dialog_search_purchases(self):
        headers = [
            ('id', self.tr('ID')),
            ('number', self.tr('NUMBER')),
            ('description', self.tr('DESCRIPTION')),
            ('party.name', self.tr('SUPPLIER')),
            ('custom_state', self.tr('ESTADO')),
            ('purchase_date', self.tr('DATE')),
            ('warehouse.name', self.tr('WAREHOUSE')),
        ]
        title = self.tr('SEARCH PURCHASE')
        methods = {
            'on_selected_method': 'on_selected_purchase',
        }
        self.dialog_search_purchases = SearchWindow(self, headers, None,
            methods, cols_width=[40, 60, 200, 200, 90, 80, 100],
            title=title, fill=True, filter_column=[1, 2, 3, 4])
        self.dialog_search_purchases.activate_counter()

    def create_dialog_search_categories_by_image(self):
        methods = {
            'on_selected_category_by_image': self.on_selected_category_by_image,
        }

        self.categorypad = Categorypad(self, self._category_buttons)

        widget = self.categorypad

        self.dialog_search_categories_by_image = CategoryDialog(self,
            methods, widget=widget,
            title=self.tr('MENU'),
            )

    def create_dialog_search_combos_by_image(self):
        methods = {
            'on_selected_combo_by_image': self.on_selected_combo_by_image,
        }

        self.combopad = Categorypad(self, self._combo_buttons)

        widget = self.combopad

        self.dialog_search_combos_by_image = CategoryDialog(self,
            methods,
            widget=widget,
            title=self.tr('COMBOS'),
            )

    def create_dialog_search_products_by_image(self):
        methods = {
            'on_selected_product_by_image': self.on_selected_product_by_image,
        }
        for product in self.selected_products:
            name = product.get('template.').get('name')
            create_icon_file(name, product.get('photo'))

        data = []
        #try:
        data = [ ( str(e['id']),
            #str('Q. ' + str(e['template.']['list_price']) + ' - ' + e['template.']['name']),
            str(e['template.']['name']),
            self._action_products[i],
            str(e['template.']['list_price'])) for i, e in enumerate(self.selected_products)
        ]
        #except:
        #    pass

        self.productpad = Productpad(self, data)
        widget = self.productpad

        self.dialog_search_products_by_image = ProductDialog(self,
            methods, widget=widget,
            title=self.tr('SELECCIONE PRODUCTO'),
            )

    def create_dialog_search_agent_by_image(self):
        methods = {
            'on_selected_product_by_image': self.on_selected_product_by_image,
        }
        self.agentpad = Agentpad(self, self._agents_buttons)
        widget = self.agentpad

        self.dialog_search_agent_by_image = AgentDialog(self,
            methods, widget=widget,
            title=self.tr('AGENT BY IMAGE'),
            )

    def create_dialog_select_delivery_method(self):
        methods = {
            'on_selected_delivery_method': self.on_selected_delivery_method,
        }

        self.deliverypad = Deliverypad(self)

        widget = self.deliverypad

        self.dialog_select_delivery_method = DeliveryDialog(self,
            methods, widget=widget,
            title=self.tr('ENTREGA'),
            )

    def create_dialog_search_party(self):
        headers = [
            ('id', self.tr('ID')),
            ('tax_identifier.code', self.tr('ID NUMBER')),
            ('name', self.tr('NAME')),
            ('city', self.tr('ADDRESS')),
            ('phone', self.tr('PHONE')),
        ]
        title = self.tr('SEARCH CUSTOMER')
        methods = {
            'on_selected_method': 'on_selected_party',
            'on_return_method': 'on_search_party',
        }
        self.dialog_search_parties = SearchWindow(self, headers, None,
            methods, cols_width=[60, 120, 270, 190, 90],
            title=title, fill=True, filter_column=[1, 2, 3, 4])
        self.dialog_search_parties.activate_counter()

    def create_dialog_payment(self):
        data = {
            'name': 'journal',
            'values': sorted([(str(j), self._journals[j]['name'])
                for j in self._journals]),
            'heads': [self.tr('ID'), self.tr('PAYMENT MODE:')],
        }
        string = self.tr('SELECT PAYMENT MODE:')
        self.dialog_payment = QuickDialog(self, 'selection', string, data)

    def create_dialog_stock(self):
        data = {
            'name': 'stock',
            'values': [],
            'heads': [self.tr('WAREHOUSE'), self.tr('QUANTITY')],
        }
        label = self.tr('STOCK BY PRODUCT:')
        self.dialog_product_stock = QuickDialog(self.dialog_search_products,
            'selection', label, data, readonly=True)

    def create_dialog_salesman(self):
        data = {
            'name': 'salesman',
            'values': [(str(e['id']), e['party.name'])
                for e in self._employees],
            'heads': [self.tr('Id'), self.tr('Salesman')],
        }
        string = self.tr('CHOOSE SALESMAN')
        self.dialog_salesman = QuickDialog(self, 'selection', string, data)

    def create_dialog_agent(self):
        data = {
            'name': 'agent',
            'values': [(str(e['id']), e['party'])
                for e in self._agents],
            'heads': [self.tr('Id'), self.tr('Agent')],
        }
        string = self.tr('CHOOSE AGENT')
        self.dialog_agent = QuickDialog(self, 'selection', string, data)

    def create_dialog_payment_term(self):
        data = {
            'name': 'payment_term',
            'values': [(p_id, self._payment_terms[p_id]['name'])
            for p_id in self._payment_terms],
            'heads': [self.tr('ID'), self.tr('PAYMENT TERM')],
        }
        string = self.tr('SELECT PAYMENT TERM')
        self.dialog_payment_term = QuickDialog(self, 'selection', string, data)

    def on_search_product(self):
        target = self.dialog_search_products.filter_field.text()
        if not target:
            return
        target_words = target.split(' ')
        domain = [('active','=',True),
            ('salable','=',True),
            ('consumable','=',False),]

        for tw in target_words:
            if len(tw) <= 2:
                continue
            clause = ['OR',
                ('template.name', 'ilike', '%' + tw + '%'),
                #('description', 'ilike', '%' + tw + '%'),
                ('template.brand', 'ilike', '%' + tw + '%'),
                ('code', 'ilike', '%' + tw + '%'),
                ('barcode', 'ilike', '%' + tw + '%'),
            ]
            domain.append(clause)

        #domain.append(self.domain_search_product)
        order=[('id','ASC')]
        products = self._Product.find(domain,
            context=self.stock_context
            )
        self.dialog_search_products.set_from_values(products)

    def on_search_sale(self):
        target = self.dialog_search_sales.filter_field.text()
        if not target:
            return
        target_words = target.split(' ')
        #domain = [('active','=',True)]
        domain = []

        for tw in target_words:
            if len(tw) <= 2:
                continue
            clause = ['OR',
                ('reference', 'ilike', '%' + tw + '%'),
                ('description', 'ilike', '%' + tw + '%'),
                ('party.name', 'ilike', '%' + tw + '%'),
                ('number', 'ilike', '%' + tw + '%'),
                #('code', 'ilike', '%' + tw + '%'),
                #('barcode', 'ilike', '%' + tw + '%'),
            ]
            domain.append(clause)

        order=[('id','DESC')]
        sales = self._PosSale.find(domain,
            context=self._context,
            )
        self.dialog_search_sales.set_from_values(sales)

    def on_search_party(self):
        target = self.dialog_search_parties.filter_field.text()
        if not target:
            return
        target_words = target.split(' ')
        domain = [
            ('tax_identifier', '!=', None),]
        for tw in target_words:
            if len(tw) <= 2:
                continue
            or_clause = ['OR',
                ('name', 'ilike', '%' + tw + '%'),
                ('contact_mechanisms.value', 'like', tw + '%'),
                ('tax_identifier', 'like', tw + '%'),
                ('name', 'like', tw + '%'),
            ]
            domain.append(or_clause)

        parties = self._Party.find(domain)
        self.dialog_search_parties.set_from_values(parties)

    def create_dialog_print_invoice(self):
        view = [
            ('invoice_number_ask', {'name': self.tr('INVOICE NUMBER')}),
            ('printer_ask', {
                'name': self.tr('PRINTER'),
                'type': 'selection',
                'values': [
                    (1, 'LASER'),
                    (2, 'POS'),
                ],
            }),
            ('type_ask', {
                'name': self.tr('TYPE'),
                'type': 'selection',
                'values': [
                    ('invoice', self.tr('INVOICE')),
                    ('order', self.tr('ORDER'))
                ],
            }),
        ]
        self.dialog_print_invoice = QuickDialog(self, 'action', data=view)

    def create_dialog_close_statement(self):
        view = [
            ('amount_to_close', {'name': self.tr('TOTAL AMOUNT'),'readonly': True,}),
            #('total_voucher_amount', {'name': self.tr('TOTAL VOUCHER AMOUNT')}, 'readonly': True,),
        ]
        self.dialog_close_statement = QuickDialog(self, 'action', data=view)

    def create_dialog_cancel_invoice(self):
        view = [
            ('password_for_cancel_ask', {
                'name': self.tr('INSERT PASSWORD FOR CANCEL'),
                'password': True
            }),
        ]
        self.dialog_cancel_invoice = QuickDialog(self, 'action', data=view)

    def create_dialog_credit_invoice(self):
        view = [
            ('password_for_credit_ask', {
                'name': self.tr('INSERT PASSWORD FOR CREDIT'),
                'password': True,
            }),
        ]
        self.dialog_credit_invoice = QuickDialog(self, 'action', data=view)

    def create_dialog_global_discount(self):
        field = 'global_discount_ask'
        data = {'name': self.tr('GLOBAL DISCOUNT')}
        self.dialog_global_discount = QuickDialog(self, 'action', data=[(field, data)])

    def create_dialog_start_balance(self):        
        view = [
            ('start_balance', {'name': self.tr('SALDO INICIAL')}),
            #('previous_leftout', {'name': self.tr('PIEZAS SOBRANTES')}),
        ]
        self.dialog_start_balance = QuickDialog(self, 'action', data=view)

    def create_dialog_force_assign(self):
        field = 'password_force_assign_ask'
        data = {'name': self.tr('PASSWORD FORCE ASSIGN')}
        self.dialog_force_assign = QuickDialog(self, 'action', data=[(field, data)])
        self.field_password_force_assign_ask.setEchoMode(QLineEdit.Password)

    def create_dialog_force_reconnect(self):
        field = 'password_force_reconnect'
        data = {'name': self.tr('PASSWORD FORCE RECONNECT')}
        self.dialog_force_reconnect = QuickDialog(self, 'action', data=[(field, data)])
        self.field_password_force_reconnect.setEchoMode(QLineEdit.Password)
        self.dialog_force_reconnect.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.dialog_force_reconnect.cancel_button.clicked.connect(self.dialog_confirm_payment_rejected)

    def create_dialog_voucher(self):
        field = 'voucher_ask'
        data = {'name': self.tr('VOUCHER NUMBER')}
        self.dialog_voucher = QuickDialog(self, 'action', data=[(field, data)])

    def create_dialog_order(self):
        field = 'order_ask'
        data = {'name': self.tr('COPY NUMBER')}
        self.dialog_order = QuickDialog(self, 'action', data=[(field, data)])

    def create_dialog_position(self):
        field = 'position_ask'
        data = {'name': self.tr('POSITION')}
        self.dialog_position = QuickDialog(self, 'action', data=[(field, data)])

    def create_wizard_new_sale(self):
        pass

    def create_dialog_comment(self):
        field = 'comment_ask'
        data = {'name': self.tr('COMMENTS'), 'widget': 'text'}
        self.dialog_comment = QuickDialog(self, 'action', data=[(field, data)])

    def clear_data(self):
        self._sale = {}
        self.party_name = None
        self.party_id = None
        self._tax_identifier = None
        self._sale_line = {'id': None}
        self._total_amount = {}
        self._sale_lines_taxes = {}
        self.field_journal_id = self._default_journal_id

    def clear_left_panel(self):
        self.message_bar.set('system_ready')
        self.field_party.setText('')
        self.field_salesman.setText('')
        self.field_salesman_id = None
        self.field_agent.setText('')
        self.field_party_id = None
        self.field_agent_id = None
        self.field_tax_identifier.setText('')
        self.field_address.setText('')
        self.field_invoice.setText('')
        self.field_invoice_state.setText(self.tr('DRAFT'))
        self.field_payment_term_id = self._default_payment_term_id
        self.field_payment_term.setText(self._default_payment_term_name)
        self.field_date.setText('')
        self.field_global_discount_ask.setText('')
        self.field_amount.zero()
        self.field_order_number.setText('')
        self.field_delivery_method.setText('')
        self.current_comment = ''
        self._model_sale_lines.setDomain([])
        self.clear_input_text()
        self.clear_amount_text()

    def clear_right_panel(self):
        if self.is_clear_right_panel:
            return
        self.field_invoice.setText('')
        self.field_invoice_state.setText(self.tr('DRAFT'))
        self.field_nit.setText('')
        self.field_untaxed_amount.zero()
        self.field_discount.zero()
        #self.field_taxes_amount.zero()
        self.field_total_amount.zero()
        self.field_change.zero()
        self.field_paid.zero()
        self._model_payment_lines.setDomain([('statement.state','=','draft')], \
            order=[('id','DESC')])
        self.is_clear_right_panel = True

    def state_enabled(self):
        pass

    def state_disabled(self):
        self.payment_ctx = {}
        self.clear_left_panel()
        self.left_table_lines.setDisabled(True)
        self.set_state('disabled')

    def createNewStatement(self):
        result = self._Statement.check_open_statement([], self._context)
        if result.get('error'):
            self.dialog('more_than_one_statement_open')
            return
        if result['is_open'] == False:
            #leftout = self._Statement.previous_leftout([], self._context)
            #previous_leftout = leftout['previous_leftout']
            #self.field_previous_leftout.setText(str(previous_leftout))
            #self.field_previous_leftout.setEnabled(False)

            res = self.dialog_start_balance.exec_()
            if res:
                amount = self.field_start_balance.text()

                if amount and float(amount):
                    res = self._Statement.new_statement([], amount, self._context)
                    if res['result'] == True:
                        self.field_start_balance.setText('')
                        self.dialog('statement_opened')
                    else:
                        self.dialog('statement_closed')
                        self.message_bar.set('statement_closed')
                        self.set_state('cancel')

            else:
                self.dialog('statement_closed')
                self.message_bar.set('statement_closed')
        return

    def createNewSale(self):
        self.check_empty_sale()
        self.set_state('add')
        self.input_text_changed('')
        self.amount_text_changed('0')
        self.clear_sign()
        self._global_timer = 0
        self.payment_ctx = {}
        self.is_clear_right_panel = False
        self.left_table_lines.setEnabled(True)
        self._current_line_id = None
        self.clear_data()
        self.clear_left_panel()
        self.clear_right_panel()
        self._clear_context()
        self._sale = self._PosSale.new_sale([], {
            'party': self._default_party_id,
            'invoice_party': self._default_party_id,
            'shipment_address':self._default_address['id'],
            'invoice_address':self._default_address['id'],
            'web_shop': self._shop['id'],
            'payment_term': self._default_payment_term_id,
            'self_pick_up': self._default_self_pick_up,
        }, self._context)
        self.party_id = self._default_party_id
        self._party = None
        if self._sale.get('id'):
            self._model_sale_lines.setDomain([('sale', '=', self._sale['id'])])
            self._set_sale_date()
            self.field_order_number.setText(self._sale['number'])
            self.field_delivery_method.setText('MESAS')
        self.field_party.setText('CONSUMIDOR FINAL')
        self.field_address.setText('CIUDAD')
        self.field_nit.setText('CF')
        #self.action_select_delivery_method()
        self.label_input.setFocus()

    def _set_sale_date(self):
        if self._sale.get('sale_date'):
            local_datetime = self._sale['sale_date']
            self.field_date.setText(local_datetime.strftime('%d/%m/%Y'))

    def _search_product(self, code):
        domain = []
        #domain.append(
            #['OR',
            #[('barcode', '=', code),
            #('active', '=', True),],
            #[('code', '=', code),
            #('active', '=', True),],
        #])
        domain.append([('template.code','=',code),
            ('active','=',True),
        ])
        products = self._Product.find(domain,
            context=self.stock_context)

        if not products or len(products) > 1:
            self.message_bar.set('product_not_found')
            return False
        else:
            product = products[0]
        return product

    def _search_party(self, tax_identifier):
        party = self._Party.search_party([], tax_identifier, self._context)
        return party
        
    def _search_party_by_name(self, name):
        domain = [('name','=',name)]
        parties = self._Party.find(domain)

        party = None
        if len(parties) != 1:
            self.message_bar.set('party_not_found')
        else:
            party = parties[0]
        return party

    def _search_agent(self, agent_id):
        domain = []
        domain.append(['OR',
            ('code', '=', agent_id)
        ])
        agents = self._Agent.find(domain)

        agent = None
        if not agents or len(agents) > 1:
            self.message_bar.set('agent_not_found')
        else:
            agent = agents[0]
        return agent

    def add_product(self, id=None, code=None, product=None,
        quantity=None, discount=None, agent=None, description=None):

        if self._state == 'disabled':
            self.message_bar.set('must_load_or_create_sale')
            return
        if self._sale['state'] != 'draft':
            return

        if quantity == None:
            quantity = 1
        
        if discount == None:
            discount = Decimal(self.row_field_discount_from_search.value())
            discount_amount = Decimal(self.row_field_discount_from_search.value())
        else:
            discount_amount = discount
            discount = discount

        product_id = None

        if not product and code:
            product = self._search_product(code)

        if not product and product_id:
            products = self._Product.find([('id','=',product_id)],
                limit=1)
            if len(products) == 1:
                product = products[0]

        if product:
            product_id = product['id']
        
        if not product_id:
            self._state = 'warning'
            return

        #FIXME PRICE_LIST

        res = self._PosSale.add_product(
            self._sale['id'],
            product_id,
            quantity,
            discount,
            agent,
            description,
            self._context,
        )

        if res['new_line'] == True:
            self._sale_line = res['sale_line']
            self._current_line_id = self._sale_line['id']

            self.addSaleLineModel(self._current_line_id)
            self._sale.update(res)
            self.update_subtotal_amount()
            self.set_discount_amount()

            self.set_amounts()
            self._clear_context()
            self.set_state('add')

            if self._add_combo:
                self.load_next_category()

            #if self._model_sale_lines.rowCount() == 1 and \
            #        self.party_id == self._default_party['id'] :
                # TODO
                # FIX ME
                #self.action_create_party()
                #self.action_select_delivery_method()

        else:
            self._sale_line = res['sale_line']
            self._current_line_id = self._sale_line['id']
            self.update_subtotal_amount()
            self.set_discount_amount()
            self.set_amounts()
            self._clear_context()
            self.set_state('add')

            if self._add_combo:
                self.load_next_category()


    def load_next_category(self):

        for item in  self._complementary_categories:
            if item['id'] == self.next_category:
                current_category = item
                break
        #current_category = self._product_categories[self.next_category]
        #next_category = next(item for item in self._product_categories \
        #        if item["id"] == self.next_category)

        self.selected_products = current_category['products']

        next_category = current_category.get('next_category')
        if next_category is not None:
            self.next_category = next_category
        else:
            self._add_combo = False

        self.dialog_search_combos_by_image.hide()
        self.create_dialog_search_products_by_image()
        self.dialog_search_products_by_image.exec_()

    def add_product_from_agent(self, id=None, code=None, product=None,
        quantity=None, discount=None, agent=None):

        if self._state == 'disabled':
            self.message_bar.set('must_load_or_create_sale')
            return
        if self._sale['state'] != 'draft':
            return

        product_id = None
        if id:
            product_id = id
        elif product:
            product_id = product

        if not product_id:
            self._state = 'warning'
            return

        allow_zero_quantity_sale = self._config['allow_zero_quantity_sale']
        if not allow_zero_quantity_sale:
            products = self._Product.find([('id','=',product_id)],
                context=self.stock_context)
            if len(products) == 1:
                product, = products
                product_stock = product['quantity']
                if product_stock < 1:
                    dialog = self.dialog('product_not_available')
                    return dialog.exec_()
            else:
                self.message_bar.set('product_not_found')
                return False

        if quantity == None:
            quantity = 1

        if discount == None:
            discount = 0
        else:
            discount_amount = discount
            discount = 0

        res = self._PosSale.add_product(
            self._sale['id'],
            product_id,
            quantity,
            discount,
            agent,
            context=self._context,
        )
        self._sale_line = res['sale_line']
        self._current_line_id = self._sale_line['id']

        self.addSaleLineModel(self._current_line_id)
        self._sale_line['product'] = product
        self._sale.update(res)
        self.set_discount(discount_amount)
        self.set_amounts()
        self.set_state('add')

        if self._model_sale_lines.rowCount() == 1:
            self.action_create_party()

    def add_party(self, tax_identifier=None):
        if self._state == 'disabled':
            self.message_bar.set('must_load_or_create_sale')
            return
        if not tax_identifier:
            return

        self.party = self._search_party(tax_identifier)
        if self.party:
            self.party_id = party['id']
            self.address_id = party['addresses'][0]
            self.field_party.setText(party['name'])
            self.field_tax_identifier.setText(party['tax_identifier'])
            self.field_address.setText(addresses['city'])
            self._PosSale.write(
                [self._sale['id']],
                {
                    'party': party['id'],
                    'invoice_address':party['addresses'][0],
                    'shipment_address':party['addresses'][0],
                }
            )
            self.set_amounts()
            self.set_state('add')
        else:
            self.action_create_party()

        self._clear_context()

    def add_agent(self, agent_id=None):
        if self._state == 'disabled':
            self.message_bar.set('must_load_or_create_sale')
            return
        if not agent_id:
            return
        agent = self._search_agent(agent_id)
        if agent:
            agent_id = agent['id']
            self._PosSaleLine.set_agent(
                [self._current_line_id], agent_id,
                self._context
            )

        self.set_state('add')
        self.message_bar.set('system_ready')
        self.label_input.setFocus()
        self.update_subtotal_amount()
        self.set_amounts()
        self.set_discount_amount()
        self._clear_context()

    def _check_stock_quantity(self, product, request_qty):
        if self._password_admin and product['quantity'] < request_qty:
            self.dialog_force_assign.exec_()
            password = self.field_password_force_assign_ask.text()
            self.field_password_force_assign_ask.setText('')
            if password != self._password_admin:
                self.message_bar.set('not_can_force_assign')
                return False
        return True

    def addSaleLineModel(self, line_id):
        rec = self._model_sale_lines.appendId(line_id)
        total = rec['amount']
        self.field_amount.setText(total)

    def sale_line_selected(self, product=None):
        if self._state == 'cash':
            return

        if product:
            # FIX ME DISCOUNT AMOUNT
            try:
                discount = product['discount_amount']
                if discount> Decimal('0.0000'):
                    self.row_field_discount_amount.setValue(float(discount))
            except:
                pass

            self._current_line_id = product['id']
            #self.label_product.setText(product['description'])
            self.row_field_qty.setValue(float(product['quantity']))
            self.row_field_price.setValue(float(product['unit_price']))
            #index = self.field_agent_ask.findText(product['principal.party.name'], Qt.MatchFixedString)
            #if index >= 0:
            #     self.field_agent_ask.setCurrentIndex(index)
            self.row_field_qty.setFocus()
            self.dialog_product_edit.exec_()
        elif self._current_line_id:
            current_line_id = int(self._current_line_id)
            current_line, = self._PosSaleLine.find([
                ('id','=',current_line_id)
                ])
            index = self.field_agent_ask.findText(current_line['principal.party.name'], Qt.MatchFixedString)
            if index >= 0:
                 self.field_agent_ask.setCurrentIndex(index)
            self.label_product.setText(current_line['description'])
            self.row_field_qty.setValue(float(current_line['quantity']))
            if current_line.get('discount_amount'):
                self.row_field_discount_amount.setValue(float(current_line['discount_amount']))
            self.row_field_price.setValue(float(current_line['unit_price']))
            self.row_field_qty.setFocus()
            self.dialog_product_edit.exec_()
        else:
            return

    def sale_line_clicked(self):
        if self._state == 'cash':
            return

        current_index = self.left_table_lines.currentIndex()
        current_line = self.left_table_lines.model.get_data(current_index)
        if current_line and current_line['id']:
            self._current_line_id = current_line['id']
        self.label_input.setFocus()

    def on_accept_purchase(self):
        if not self.purchase:
            return

        res = self._PosPurchase.approve_purchase([], self.purchase['id'], \
                self._context)
        if res['res'] == 'ok':
            self.message_bar.set('purchase_approved')
            self.print_purchase_report(self.purchase['id'])
        elif res['res'] == 'error':
            self.message_bar.set('something_wrong')

    def on_selected_new_product(self, product=None, code=None):
        if self._state == 'cash':
            return

        if product is None and code is not None:
            products =self._Product.find([('code', '=', code),
                ('active', '=', True),],
                context=self.stock_context)
            if len(products)==1:
                product = products[0]
            else:
                return

        #if product is not None:
        #    templates = self._Template.find([('id', '=', product['template'])])

        #if len(templates) == 1:
        #    template, = templates
        #else:
        #    return

        self._current_product = product
        self._current_line_id = product['id']
        template = product.get('template.')

        name = template.get('name')
        list_price = template.get('list_price')

        self.label_product_from_search.setText(name)
        self.row_field_qty_from_search.setValue(float(1))
        self.row_field_price_from_search.setValue(float(list_price))
        self.row_field_discount_from_search.setValue(float(0))
        self.row_field_qty_from_search.setFocus()

        self.dialog_product_edit_from_search.exec_()

    def create_dialog_create_party(self):
        self.party_line = {}

        vbox_party = QVBoxLayout()
        grid = QGridLayout()
        qty = 0

        label_tax_identifier = QLabel(self.tr('NIT:'))
        label_tax_identifier.setObjectName('label_tax_identifier')
        grid.addWidget(label_tax_identifier, 1, 1)
        self.field_tax_identifier = QLineEdit()
        self.field_tax_identifier.setObjectName('field_tax_identifier')
        self.field_tax_identifier.editingFinished.connect(self.update_nit)
        grid.addWidget(self.field_tax_identifier, 1, 2)

        label_name = QLabel(self.tr('NAME:'))
        label_name.setObjectName('label_name')
        grid.addWidget(label_name, 2, 1)
        self.field_name = QLineEdit()
        self.field_name.setObjectName('field_name')
        grid.addWidget(self.field_name, 2, 2)

        label_city = QLabel(self.tr('CITY:'))
        label_city.setObjectName('label_city')
        grid.addWidget(label_city, 3, 1)
        self.field_city = QLineEdit()
        self.field_city.setObjectName('field_city')
        grid.addWidget(self.field_city, 3, 2)

        vbox_party.addLayout(grid)
        self.dialog_create_party = QuickDialog(self, 'action', widgets=[vbox_party], disable_cancel=True)
        self.dialog_create_party.accepted.connect(self.dialog_create_party_accepted)
        self.dialog_create_party.ok_button.setEnabled(False)
        self.dialog_create_party.cancel_button.setEnabled(False)
        self.dialog_create_party.setWindowFlag(Qt.WindowCloseButtonHint, False)

    def create_dialog_sale_line(self):
        self.state_line = {}

        vbox_product = QVBoxLayout()
        grid = QGridLayout()
        qty = 0
        if self._config.get('decimals_digits_quantity'):
            qty = self._config['decimals_digits_quantity']

        self.label_product = QLabel()
        self.label_product.setAlignment(alignCenter)
        self.label_product.setObjectName('label_product')
        vbox_product.addWidget(self.label_product)

        label_price = QLabel(self.tr('UNIT PRICE:'))
        label_price.setObjectName('label_price')
        grid.addWidget(label_price, 1, 1)
        self.row_field_price = QDoubleSpinBox()
        self.row_field_price.setObjectName('row_field_price')
        self.row_field_price.setMinimum(0)
        self.row_field_price.setMaximum(100000)
        self.row_field_price.setDecimals(4)
        self.row_field_price.setAlignment(alignRight)
        self.row_field_price.setReadOnly(True)
        grid.addWidget(self.row_field_price, 1, 2)
        self.row_field_price.valueChanged.connect(
            lambda value: self.update_sale_line(value, 'unit_price')
        )

        label_qty = QLabel(self.tr('QUANTITY:'))
        label_qty.setObjectName('label_qty')
        grid.addWidget(label_qty, 2, 1)
        self.row_field_qty = QDoubleSpinBox()
        self.row_field_qty.setObjectName('row_field_qty')
        self.row_field_qty.setMinimum(0)
        self.row_field_qty.setMaximum(100000)
        self.row_field_qty.setDecimals(0)
        self.row_field_qty.setAlignment(alignLeft)
        grid.addWidget(self.row_field_qty, 2, 2)
        self.row_field_qty.valueChanged.connect(
            lambda value: self.update_sale_line(value, 'quantity')
        )

        label_agent = QLabel(self.tr('AGENT:'))
        label_agent.setObjectName('label_agent')
        #grid.addWidget(label_agent, 3, 1)
        self.field_agent_ask = ComboBox(self, 'agent_ask',
                {'values': [(str(e['id']), e['party'])
                    for e in self._agents]})
        self.field_agent_ask.currentIndexChanged.connect(
            lambda value: self.update_sale_line(value, 'agent')
        )
        #grid.addWidget(self.field_agent_ask, 3, 2)

        label_discount = QLabel(self.tr('DISCOUNT:'))
        label_discount.setObjectName('label_discount')
        grid.addWidget(label_discount, 3, 1)
        self.row_field_discount_amount = QDoubleSpinBox()
        self.row_field_discount_amount.setObjectName('row_field_discount_amount')
        self.row_field_discount_amount.setMinimum(0)
        self.row_field_discount_amount.setMaximum(100000)
        self.row_field_discount_amount.setDecimals(qty)
        self.row_field_discount_amount.setAlignment(alignRight)
        self.row_field_discount_amount.setDecimals(qty)
        self.row_field_discount_amount.setEnabled(True)
        grid.addWidget(self.row_field_discount_amount, 3, 2)
        self.row_field_discount_amount.valueChanged.connect(
            lambda value: self.update_sale_line(value, 'discount_amount')
        )

        agent_data = data = {
            'name': 'salesman',
            'values': [(str(e['id']), e['party.name'])
                for e in self._employees],
            'heads': [self.tr('Id'), self.tr('Salesman')],
        }

        vbox_product.addLayout(grid)
        self.dialog_product_edit = QuickDialog(self, 'action', widgets=[vbox_product])
        self.dialog_product_edit.accepted.connect(self.dialog_product_edit_accepted)

    def create_dialog_sale_line_from_search(self):
        self.state_line = {}

        vbox_product = QVBoxLayout()
        grid = QGridLayout()
        qty = 0

        self.label_product_from_search = QLabel()
        self.label_product_from_search.setAlignment(alignCenter)
        self.label_product_from_search.setObjectName('label_product_from_search')
        vbox_product.addWidget(self.label_product_from_search)

        label_price = QLabel(self.tr('UNIT PRICE:'))
        label_price.setObjectName('label_price')
        grid.addWidget(label_price, 1, 1)
        self.row_field_price_from_search = QDoubleSpinBox()
        self.row_field_price_from_search.setObjectName('row_field_price_from_search')
        self.row_field_price_from_search.setMinimum(0)
        self.row_field_price_from_search.setMaximum(1000)
        self.row_field_price_from_search.setReadOnly(True)
        if self._config.get('decimals_digits_quantity'):
            qty = self._config['decimals_digits_quantity']
        #self.row_field_price_from_search.setDecimals(qty)
        self.row_field_price_from_search.setDecimals(4)
        self.row_field_price_from_search.setAlignment(alignRight)
        grid.addWidget(self.row_field_price_from_search, 1, 2)
        self.row_field_price_from_search.valueChanged.connect(
            lambda value: self.update_sale_line_from_search(value, 'unit_price')
        )

        label_qty = QLabel(self.tr('QUANTITY:'))
        label_qty.setObjectName('label_qty')
        grid.addWidget(label_qty, 2, 1)
        self.row_field_qty_from_search = QDoubleSpinBox()
        self.row_field_qty_from_search.setObjectName('row_field_qty_from_search')
        self.row_field_qty_from_search.setMinimum(0)
        self.row_field_qty_from_search.setMaximum(1000)
        self.row_field_qty_from_search.setDecimals(0)
        self.row_field_qty_from_search.setAlignment(alignRight)
        grid.addWidget(self.row_field_qty_from_search, 2, 2)
        self.row_field_qty_from_search.valueChanged.connect(
            lambda value: self.update_sale_line_from_search(value, 'quantity')
        )

        label_agent = QLabel(self.tr('AGENT:'))
        label_agent.setObjectName('label_agent')
        #grid.addWidget(label_agent, 3, 1)
        self.field_agent_ask_from_search = ComboBox(self, 'agent_ask_from_search',
                {'values': [(str(e['id']), e['party'])
                    for e in self._agents]})
        #grid.addWidget(self.field_agent_ask_from_search, 3, 2)

        label_line_description = QLabel('DESCRIPCIÓN:')
        label_line_description.setObjectName('label_line_description')
        grid.addWidget(label_line_description, 3, 1)
        self.row_field_line_description = QLineEdit()
        self.row_field_line_description.setObjectName('row_field_line_description')
        self.row_field_line_description.setAlignment(alignLeft)
        grid.addWidget(self.row_field_line_description, 3, 2)
        self.row_field_line_description.textChanged.connect(
            lambda value: self.update_sale_line(value, 'description')
        )

        label_discount = QLabel(self.tr('DISCOUNT:'))
        label_discount.setObjectName('label_discount')
        grid.addWidget(label_discount, 4, 1)
        self.row_field_discount_from_search = QDoubleSpinBox()
        self.row_field_discount_from_search.setObjectName('row_field_discount_from_search')
        self.row_field_discount_from_search.setMinimum(0)
        self.row_field_discount_from_search.setMaximum(1000)
        self.row_field_discount_from_search.setEnabled(True)
        if self._config.get('decimals_digits_quantity'):
            qty = self._config['decimals_digits_quantity']
        self.row_field_discount_from_search.setDecimals(qty)
        self.row_field_discount_from_search.setAlignment(alignRight)
        grid.addWidget(self.row_field_discount_from_search, 4, 2)
        self.row_field_discount_from_search.valueChanged.connect(
            lambda value: self.update_sale_line_from_search(value, 'discount_amount')
        )

        self.row_field_qty_from_search.setFocus()
        vbox_product.addLayout(grid)
        self.dialog_product_edit_from_search = QuickDialog(self, 'action', widgets=[vbox_product])
        self.dialog_product_edit_from_search.accepted.connect(
            self.dialog_product_edit_from_search_accepted)

    def create_dialog_expense(self):
        
        vbox_product = QVBoxLayout()
        grid = QGridLayout()

        label_expense = QLabel(self.tr('GASTO:'))
        label_expense.setObjectName('label_expense')
        grid.addWidget(label_expense, 1, 1)
        self.field_expense_product = ComboBox(self, 'expense_product',
                {'values': [(str(e['id']), str(e['template.']['name']))
                    for e in self._expenses]})
        grid.addWidget(self.field_expense_product, 1, 2)

        label_expense_amount = QLabel(self.tr('MONTO:'))
        label_expense_amount.setObjectName('label_expense_amount')
        grid.addWidget(label_expense_amount, 2, 1)
        self.row_field_expense_amount = QDoubleSpinBox()
        self.row_field_expense_amount.setObjectName('row_field_expense_amount')
        self.row_field_expense_amount.setMinimum(0)
        self.row_field_expense_amount.setMaximum(100000)
        self.row_field_expense_amount.setDecimals(2)
        self.row_field_expense_amount.setAlignment(alignRight)
        grid.addWidget(self.row_field_expense_amount, 2, 2)
        self.row_field_expense_amount.valueChanged.connect(
            lambda value: self.update_expense_line(value, 'expense')
        )

        label_line_description = QLabel('DESCRIPCIÓN:')
        label_line_description.setObjectName('label_line_description')
        grid.addWidget(label_line_description, 3, 1)
        self.row_field_line_description = QLineEdit()
        self.row_field_line_description.setObjectName('row_field_line_description')
        self.row_field_line_description.setAlignment(alignLeft)
        grid.addWidget(self.row_field_line_description, 3, 2)
        self.row_field_line_description.textChanged.connect(
            lambda value: self.update_expense_line(value, 'description')
        )

        self.field_expense_product.setFocus()
        vbox_product.addLayout(grid)
        self.dialog_expense = QuickDialog(self, 'action', widgets=[vbox_product])
        self.dialog_expense.accepted.connect(self.dialog_expense_accepted)
        self.dialog_expense.ok_button.setEnabled(False)

    def create_dialog_production(self):
        
        vbox_product = QVBoxLayout()
        grid = QGridLayout()

        label_product_production = QLabel(self.tr('PRODUCTO:'))
        label_product_production.setObjectName('label_product_production')
        grid.addWidget(label_product_production, 1, 1)
        self.field_product_production = ComboBox(self, 'product_production',
                {'values': [(str(e['id']), str(e['template.']['name']))
                    for e in self._production_products]})
        grid.addWidget(self.field_product_production, 1, 2)

        label_production_quantity = QLabel(self.tr('CANTIDAD:'))
        label_production_quantity.setObjectName('label_production_quantity')
        grid.addWidget(label_production_quantity, 2, 1)
        self.row_field_production_quantity = QDoubleSpinBox()
        self.row_field_production_quantity.setObjectName('row_field_expense_amount')
        self.row_field_production_quantity.setMinimum(0)
        self.row_field_production_quantity.setMaximum(1000)
        self.row_field_production_quantity.setDecimals(0)
        self.row_field_production_quantity.setAlignment(alignRight)
        grid.addWidget(self.row_field_production_quantity, 2, 2)
        self.row_field_production_quantity.valueChanged.connect(
            lambda value: self.update_production_line(value, 'quantity')
        )

        self.field_product_production.setFocus()
        vbox_product.addLayout(grid)

        self.dialog_production = QuickDialog(self, 'action', widgets=[vbox_product])
        self.dialog_production.accepted.connect(self.dialog_production_accepted)
        self.dialog_production.ok_button.setEnabled(False)

    def month_number_spanish(self, number):
        switcher = {
            0: "Enero",
            1: "Febrero",
            2: "Marzo",
            3: "Abril",
            4: "Mayo",
            5: "Junio",
            6: "Julio",
            7: "Agosto",
            8: "Septiembre",
            9: "Octubre",
            10: "Noviembre",
            11: "Diciembre",
        }
        return switcher.get(number, "None")

    def month_name(self, number):
        Date = Pool().get('ir.date')
        today = Date.today()
        month = date.month
        return month

    def allmonth(self, year):
        list = []
        for i in range(0,12):
            label = self.month_number_spanish(i) + ' - ' +str(year)
            list.append( (i,label) )
        return list

    def first_day_month(self, date):
        first_day =  date.replace(day=1)
        return first_day

    def last_day_month(self, date):
        last_day = date.replace(day = calendar.monthrange(date.year, date.month)[1])
        return last_day

    def create_dialog_select_dates(self):
        self.selected_dates = {}

        today = datetime.today()
        current_date = date(today.year, today.month, 1)
        from_date = self.first_day_month(current_date)
        to_date =  self.last_day_month(current_date)
        #QDate(y,m,d)
        start_date = QDate(from_date.year, from_date.month,from_date.day)
        end_date = QDate(to_date.year, to_date.month, to_date.day)

        vbox_dates = QVBoxLayout()
        grid = QGridLayout()

        label_month = QLabel(self.tr('MONTH:'))
        label_month.setObjectName('label_month')
        grid.addWidget(label_month, 1, 1)
        self.field_month_ask = ComboBox(self, 'month_ask',
            {'values': [(str(e['id']), e['name'])
                    for e in MONTHS]})
        self.field_month_ask.setCurrentIndex(_MONTH-1)
        self.field_month_ask.currentIndexChanged.connect(
            lambda value: self.update_selected_month(value, 'month')
        )
        grid.addWidget(self.field_month_ask, 1, 2)

        label_start_date = QLabel(self.tr('START DATE:'))
        label_start_date.setObjectName('label_start_date')
        grid.addWidget(label_start_date, 2, 1)
        self.field_start_date = QCalendarWidget()
        self.field_start_date.setSelectedDate(start_date)
        grid.addWidget(self.field_start_date,2,2)

        label_end_date = QLabel(self.tr('END DATE:'))
        label_end_date.setObjectName('label_end_date')
        grid.addWidget(label_end_date, 3, 1)
        self.field_end_date = QCalendarWidget()
        self.field_end_date.showToday()
        grid.addWidget(self.field_end_date, 3,2)


        vbox_dates.addLayout(grid)
        self.dialog_select_dates = QuickDialog(self, 'action', widgets=[vbox_dates])
        self.dialog_select_dates.accepted.connect(self.dialog_select_dates_accepted)

    def create_dialog_select_end_date(self):

        vbox_dates = QVBoxLayout()
        grid = QGridLayout()

        label_end_date = QLabel(self.tr('END DATE:'))
        label_end_date.setObjectName('label_end_date')
        grid.addWidget(label_end_date, 1, 1)
        self.field_location_end_date = QCalendarWidget()
        self.field_location_end_date.showToday()
        grid.addWidget(self.field_location_end_date, 1,2)


        vbox_dates.addLayout(grid)
        self.dialog_select_end_date = QuickDialog(self, 'action', widgets=[vbox_dates])
        self.dialog_select_end_date.accepted.connect(self.dialog_select_end_date_accepted)

    def create_dialog_confirm_payment(self):
        self.state_payment = {}

        vbox_payment = QVBoxLayout()
        grid = QGridLayout()
        qty = 2

        label_total_amount = QLabel(self.tr('TOTAL:'))
        grid.addWidget(label_total_amount, 1, 1)
        self.label_total_amount = QLabel()
        self.label_total_amount.setObjectName('label_total_amount')
        grid.addWidget(self.label_total_amount, 1, 2)

        label_cash_amount = QLabel(self.tr('CASH:'))
        label_cash_amount.setObjectName('label_cash_amount')
        grid.addWidget(label_cash_amount, 2, 1)

        self.row_field_cash_amount = FieldMoney(self, 'row_field_cash_amount', {}, readonly=False)

        reg_ex = QRegExp("[0-9]+.?[0-9]{,2}")
        cash_amount_validator = QRegExpValidator(reg_ex, self.row_field_cash_amount)

        self.row_field_cash_amount.setObjectName('row_field_cash_amount')
        self.row_field_cash_amount.setValidator(cash_amount_validator)
        grid.addWidget(self.row_field_cash_amount, 2, 2)
        self.row_field_cash_amount.textChanged.connect(
            lambda value: self.update_state_payment(value,'row_field_cash_amount')
        )

        #label_voucher_amount = QLabel(self.tr('VOUCHER AMOUNT:'))
        label_voucher_amount = QLabel(self.tr('VOUCHER:'))
        label_voucher_amount.setObjectName('label_voucher_amount')
        grid.addWidget(label_voucher_amount, 3, 1)

        self.row_field_voucher_amount = FieldMoney(self, 'row_field_voucher_amount', {}, readonly=False)
        self.row_field_voucher_amount.setObjectName('row_field_voucher_amount')

        voucher_amount_validator = QRegExpValidator(reg_ex, self.row_field_voucher_amount)
        self.row_field_voucher_amount.setValidator(voucher_amount_validator)
        self.row_field_voucher_amount.setEnabled(True)

        grid.addWidget(self.row_field_voucher_amount, 3, 2)
        self.row_field_voucher_amount.textChanged.connect(
            lambda value: self.update_state_payment(value,'row_field_voucher_amount')
        )

        #label_voucher_number = QLabel(self.tr('VOUCHER NUMBER:'))
        label_voucher_number = QLabel(self.tr('VOUCHER NUMBER:'))
        label_voucher_number.setObjectName('label_voucher_number')
        grid.addWidget(label_voucher_number, 4, 1)

        reg_ex = QRegExp("[0-9]")
        self.row_field_voucher_number = QLineEdit()
        cash_amount_validator = QRegExpValidator(reg_ex, self.row_field_voucher_number)
        self.row_field_voucher_number.setObjectName('row_field_voucher_number')
        self.row_field_voucher_number.setEnabled(True)
        self.row_field_voucher_number.textChanged.connect(
            lambda value: self.update_state_payment(value, 'row_field_voucher_number'),
        )
        grid.addWidget(self.row_field_voucher_number, 4, 2)

        '''
        self.row_field_voucher_number = QDoubleSpinBox()
        self.row_field_voucher_number.setObjectName('row_field_voucher_number')
        self.row_field_voucher_number.setMinimum(0)
        self.row_field_voucher_number.setMaximum(999999)
        self.row_field_voucher_number.setDecimals(0)
        self.row_field_voucher_amount.textChanged.connect(
            lambda value: self.update_state_payment(value,'row_field_voucher_number')
        )
        grid.addWidget(self.row_field_voucher_number, 4, 2)
        '''

        label_difference = QLabel(self.tr('DIFFERENCE:'))
        label_difference.setObjectName('label_difference')
        grid.addWidget(label_difference, 5, 1)

        self.row_field_difference = FieldMoney(self, 'row_field_difference', {}, readonly=True)
        self.row_field_difference.setObjectName('row_field_difference')
        grid.addWidget(self.row_field_difference, 5, 2)

        vbox_payment.addLayout(grid)

        label_difference = QLabel(self.tr('DESCRIPCION CORTA:'))
        label_difference.setObjectName('label_description')
        grid.addWidget(label_difference, 6, 1)

        self.row_field_description = QLineEdit()
        self.row_field_description.setObjectName('row_field_description')
        grid.addWidget(self.row_field_description, 6, 2)

        vbox_payment.addLayout(grid)

        self.dialog_confirm_payment = QuickDialog(self, 'action',
            widgets=[vbox_payment], disable_cancel=False,
            active_widget=self.label_input,
            message_bar=self.message_bar, cancel_message='system_ready')
        self.dialog_confirm_payment.ok_button.setEnabled(False)
        self.dialog_confirm_payment.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.dialog_confirm_payment.cancel_button.clicked.connect(self.dialog_confirm_payment_rejected)
        self.dialog_confirm_payment.accepted.connect(self.dialog_confirm_payment_accepted)


    def update_sale_line(self, value, field):
        if field == 'product_id':
            value = self._current_line_id
        if field == 'quantity':
            value = Decimal(self.row_field_qty.value())
        if field == 'description':
            value = self.row_field_line_description.text()
        if field == 'discount_amount':
            value = Decimal(self.row_field_discount_amount.value())
        if field == 'agent':
            value = self.field_agent_ask.get_id()

        self.state_line[field] = value

    def update_sale_line_from_search(self, value, field):
        if field == 'product_id':
            value = self._current_line_id
        if field == 'quantity':
            value = Decimal(self.row_field_qty_from_search.value())
        if field == 'discount_amount':
            value = Decimal(self.row_field_discount_from_search.value())
        if field == 'description':
            value = self.row_field_line_description.value()
        if field == 'agent':
            value = self.field_agent_ask.get_id()
        self.state_line[field] = value

    def update_selected_month(self, value, field):
        if field == 'month':
            current_month = self.field_month_ask.get_id()
            if current_month=='A':
                month=1
            elif current_month=='B':
                month=2
            elif current_month=='C':
                month=3
            elif current_month=='D':
                month=4
            elif current_month=='E':
                month=5
            elif current_month=='F':
                month=6
            elif current_month=='G':
                month=7
            elif current_month=='H':
                month=8
            elif current_month=='I':
                month=9
            elif current_month=='J':
                month=10
            elif current_month=='K':
                month=11
            else:
                month=12
            today = datetime.today()
            current_date = date(today.year, int(month),1)
            from_date = self.first_day_month(current_date)
            to_date =  self.last_day_month(current_date)
            #QDate(y,m,d)
            start_date = QDate(from_date.year, from_date.month,from_date.day)
            end_date = QDate(to_date.year, to_date.month, to_date.day)
            self.field_start_date.setSelectedDate(start_date)
            self.field_end_date.setSelectedDate(end_date)

    def update_state_payment(self, value, field):
        valid_voucher = True
        difference = -1
        total_amount = round(Decimal(str(self.label_total_amount.text())),6)
        self.message_bar.set('enter_payment')
        if len(self.row_field_cash_amount.text()) > 0:
            cash_amount = round(Decimal(str(self.row_field_cash_amount.text())),6)
        else:
            cash_amount = 0
        if len(self.row_field_voucher_amount.text())>0:
            voucher_amount = round(Decimal(str(self.row_field_voucher_amount.text())),6)
        else:
            voucher_amount = 0
        voucher_number = self.row_field_voucher_number.text()
        total_received = cash_amount + voucher_amount
        difference = total_amount - total_received
        self.row_field_difference.setText(str(difference))

        if difference > 0:
            self.message_bar.set('invalid_payment_amount')
            valid_voucher = False

        if voucher_amount>0 and len(voucher_number)<4:
            valid_voucher = False
            self.message_bar.set('invalid_payment_voucher')
        elif voucher_amount>0 and len(voucher_number)>=4:
            valid_voucher = True
            self.message_bar.set('enter_payment')

        # TODO NEVER PASS TO STATE DRAFT
        if difference == 0 and valid_voucher and self._sale['state'] == 'draft':
            self.message_bar.set('payment_valid')
            self.dialog_confirm_payment.ok_button.setEnabled(True)
            dialog = self.dialog('invoice_posted')
            dialog.exec_()

        if self._sale['state'] == 'processing' and \
                difference <= 0 and valid_voucher:
            self.message_bar.set('payment_valid')
            self.dialog_confirm_payment.ok_button.setEnabled(True)

        else:
            self.dialog_confirm_payment.ok_button.setEnabled(False)

    def update_nit(self):
        tax_identifier = str(self.field_tax_identifier.text())
        name = str(self.field_name.text())
        city = str(self.field_city.text())
        is_valid_phone = is_valid_email = False

        if tax_identifier == 'CF' or tax_identifier == 'cf' or tax_identifier == '00':
            party = self._search_party("CF")
            if not party:
                return self.dialog('missing_party_configuration').exec_()
            self.party_id = party['id']
            self.field_name.setText(party['name'])
            self.field_city.setText(party['city'])
            self.party = party
            self.address_id = party['address']            
        elif len(tax_identifier)>5:
            party = self._search_party(tax_identifier)
            if party:
                self.party_id = party['id']
                self.address_id = party['address']
                self.field_name.setText(party['name'])
                self.field_city.setText('CIUDAD')
                self.party = party
        elif len(tax_identifier)==0:
            self.field_name.setText('')
            self.field_city.setText('')
        
        if len(tax_identifier)>5 and \
                len(self.field_name.text()) >3 \
                and len(self.field_city.text())>3 :
            self.dialog_create_party.ok_button.setEnabled(True)
        elif tax_identifier in ['CF', 'cf', '00', 'VAR'] and \
                len(self.field_name.text()) > 3 \
                and len(self.field_city.text())>3:
            self.dialog_create_party.ok_button.setEnabled(True)
        else:
            self.dialog_create_party.ok_button.setEnabled(False)

    def update_end_amount(self, value, field):

        two_hundred = float(str(self.field_statement_two_hundred.value()))
        one_hundred = float(str(self.field_statement_one_hundred.value()))
        fifty = float(str(self.field_statement_fifty.value()))
        twenty = float(str(self.field_statement_twenty.value()))
        ten = float(str(self.field_statement_ten.value()))
        fifth = float(str(self.field_statement_fifth.value()))
        one = float(str(self.field_statement_one.value()))
        currency = float(str(self.field_statement_currency.value()))
        voucher = float(str(self.field_statement_voucher.value()))
    
        end_balance = float(str(self.field_statement_end_balance.value()))


        cash_amount = two_hundred * 200 + one_hundred * 100 + \
            fifty * 50 + twenty * 20 + ten * 10 + fifth * 5 + \
            one + currency + voucher

        difference = end_balance - cash_amount

        self.field_statement_count.setValue(float(cash_amount))
        self.field_statement_difference.setValue(float(difference))
        
        if difference <= float(0):
            self.dialog_statement.ok_button.setEnabled(True)
        else:
            self.dialog_statement.ok_button.setEnabled(False)

    def dialog_product_edit_accepted(self):
        if not self.state_line or not self._current_line_id:
            return

        if self.state_line.get('description'):
            description = self.state_line.get('description')
            self._PosSaleLine.write([self._current_line_id], 
                {'description':description})

        if self.state_line.get('quantity'):
            quantity = self.state_line.pop('quantity')
            self._PosSaleLine.set_quantity(
                [self._current_line_id], quantity, self._context)

        if self.state_line.get('unit_price'):
            unit_price = self.state_line.pop('unit_price')
            self._sign = '/'
            self._process_price(unit_price)
            self._sign = None

        if 'agent' in self.state_line:
            agent = self.state_line.pop('agent')
            self._PosSaleLine.write([self._current_line_id],
                {'principal':agent})

        #self._PosSaleLine.write([self._current_line_id], self.state_line)
        if self.state_line.get('discount_amount'):
            discount = self.state_line.get('discount_amount')
            self.set_discount(discount)
        self.update_subtotal_amount()
        self.set_amounts()
        self.set_discount_amount()
        self._model_sale_lines.update(self._current_line_id)
        self.state_line = {}

    def dialog_create_party_accepted(self):

        tax_identifier = str(self.field_tax_identifier.text())
        name = str(self.field_name.text())
        city = str(self.field_city.text())

        self.field_party.setText(name)
        self.field_nit.setText(str(tax_identifier))
        self.field_address.setText(city)

        self._PosSale.write([self._sale['id']], {
                'party': self.party['id'],
                'invoice_party': self.party['id'],
                'shipment_party': self.party['id'],
                'invoice_address': self.party['address'],
                'shipment_address': self.party['address'],
            }
        )

        self.field_tax_identifier.setFocus()
        self.field_name.setText('')
        self.field_city.setText('')
        self.dialog_create_party.ok_button.setEnabled(False)


        self.set_state('add')
        self._clear_context()

    def dialog_confirm_payment_rejected(self):
        self.set_state('add')
        self.message_bar.set('system_ready')
        self.label_input.setFocus()

    def dialog_select_dates_accepted(self):
        start_date = self.field_start_date.selectedDate().toPyDate()
        end_date = self.field_end_date.selectedDate().toPyDate()
        self.print_invoice_binnacle(start_date=start_date, end_date=end_date, \
                direct_print=False)

    def dialog_select_end_date_accepted(self):
        end_date = self.field_location_end_date.selectedDate().toPyDate()
        self.print_product_by_location(end_date=end_date,
                direct_print=False)

    def dialog_product_edit_from_search_accepted(self):
        _current_product = self._current_product
        _current_quantity = Decimal(self.row_field_qty_from_search.value())
        _current_discount = Decimal(self.row_field_discount_from_search.value())
        description = ''
        try:
            description = self.row_field_line_description.text()
        except:
            pass
        self.row_field_line_description.setText('')
        agent_count = self.field_agent_ask_from_search.count()
        _current_agent = None
        if agent_count > 0:
            _current_agent = self.field_agent_ask_from_search.get_id()
        self.add_product(
            product=_current_product,
            quantity=_current_quantity,
            discount=_current_discount,
            agent=_current_agent,
            description=description)

    def dialog_confirm_payment_accepted(self):
        total_amount = round(Decimal(str(self.label_total_amount.text())),6)
        cash_amount = round(Decimal(str(self.row_field_cash_amount.text())),6)
        voucher_amount = round(Decimal(str(self.row_field_voucher_amount.text())),6)
        voucher_number = self.row_field_voucher_number.text()
        current_discount = round(Decimal(str(self.row_field_discount_amount.value())),6)
        short_description = self.row_field_description.text()
        self._difference = total_amount - cash_amount - voucher_amount
        if self._difference > 0:
            self.row_field_cash_amount.setText(str(cash_amount))
            self.row_field_voucher_amount.setText(str(voucher_amount))
            self.row_field_voucher_number.setValue(voucher_number)
            return
        else:
            self.field_journal_id = self._default_journal_id

            if len(short_description) > 0:
                res = self._PosSale.update_description([],
                    self._sale['id'],
                    True,
                    short_description,
                    self._context
                )
                if res['result'] == 'ok':
                    self.row_field_description.setText('')

            if voucher_amount > 0:
                res = self._PosSale.add_payment(self.field_journal_id,
                    voucher_amount, self._sale['id'],
                    str(voucher_number), self._context)
                if res['result'] == 'statement_closed':
                    self.dialog('statement_closed')
                    self.message_bar.set('statement_closed')
                    return res
                self.addPaymentLine(res['line_id'])

            if cash_amount > 0:
                res = self.add_payment(cash_amount)

                if res['result'] != 'ok':
                    self.message_bar.set('statement_closed')
                    self.dialog('statement_closed')
                    return False

                self._sale.update(res)

            #self._PosSale.workflow_to_end([], self._sale['id'], self._context)
            self._done_sale()

    def setupSaleLineModel(self):

        product_code = {
            'name': 'product.code',
            'align': alignRight,
            'width': 110,
            'description': self.tr('COD'),
        }

        product = {
            'name': 'product.template.name',
            'align': alignLeft,
            'description': self.tr('PRODUCTO'),
            'width': STRETCH
        }

        product_name = {
            'name': 'product.template.name',
            'align': alignRight,
            'description': self.tr('NAME'),
            'width': 350,
        }

        brand = {
            'name': 'product.template.brand',
            'align': alignLeft,
            'description': self.tr('MARCA'),
            'width': 110,
        }
        unit_price = {
            'name': 'unit_price',
            'format': '{:5,.4f}',
            'align': alignLeft,
            'description': self.tr('UNIT PRICE'),
            'invisible': False,
            'width': 90
        }
        uom = {
            'name': 'unit.symbol',
            'align': alignHCenter,
            'description': self.tr('UNIT'),
            'width': 20
        }
        qty = {
            'name': 'quantity',
            'format': '{:3,.0f}',
            'align': alignRight,
            'description': self.tr('QTY'),
            'digits': ('unit.symbol', {'gal': '4', 'u': '0'}),
            'width': 90
        }
        discount_amount = {
            'name': 'discount_amount',
            'format': '{:6,.4f}',
            'align': alignRight,
            'description': self.tr('DESC'),
            'width': 90
        }
        amount = {
            'name': 'amount',
            'format': '{:5,.2f}',
            'align': alignRight,
            'description': self.tr('SUBTOTAL'),
            'width': 100
        }
        note = {
            'name': 'note',
            'align': alignLeft,
            'description': self.tr('NOTE'),
            'invisible': True,
            'width': 100
        }
        principal = {
            'name': 'principal.party.name',
            'align': alignRight,
            'description': self.tr('AGENT'),
            'width': 100
        }

        invoice = {
            'name': 'invoice.number',
            'align': alignLeft,
            'description': self.tr('FACTURA'),
            'width': 90,
        }

        number = {
            'name': 'number',
            'align': alignLeft,
            'description': self.tr('VOUCHER'),
            'width': 90,
        }

        party = {
            'name': 'party.name',
            'align': alignLeft,
            'description': self.tr('CLIENTE'),
            'width': 200,
        }

        description = {
            'name': 'description',
            'align': alignLeft,
            'description': self.tr('DESCRIPCIÓN'),
            'width': 200,
        }

        statement_line_amount = {
            'name': 'amount',
            'align': alignRight,
            'format': '{:5,.2f}',
            'description': self.tr('MONTO'),
            'width': 90,
        }

        self.fields_sale_line = [
            #product_code,
            product,
            #brand,
            #discount_amount, 
            qty,
            unit_price,
            #uom,
            amount,
            #note, 
            #principal
            ]

        self.fields_purchase_line = [product_code, product_name,
            qty, uom]

        self.fields_statement_line = [invoice, number, statement_line_amount, #party, 
            description,
        ]

        #if self._config.get('show_description_pos'):
        #    self.fields_sale_line.insert(2, description)


        self._model_sale_lines = TrytonTableModel(self.conn, 'sale.line',
            self.fields_sale_line)

        self._model_purchase_lines = TrytonTableModel(self.conn, 'purchase.line',
            self.fields_purchase_line)

        self._model_statement_lines = TrytonTableModel(self.conn, 'account.statement.line',
            self.fields_statement_line)

    def setupPaymentModel(self):
        self._model_payment_lines = TrytonTableModel(self.conn,
            'account.statement.line', [
                #{
                #    'name': 'party.name',
                #    'align': alignLeft,
                #    'description': self.tr('PARTY'),
                #},
                {
                    'name': 'description',
                    'align': alignLeft,
                    'description': self.tr('INVOICE'),
                },
                {
                    'name': 'amount',
                    'align': alignRight,
                    'format': '{:5,.1f}',
                    'description': self.tr('AMOUNT'),
                },
            ]
        )

    def action_table(self):
        self.left_table_lines.setFocus()

    def action_top_sales(self):
        
        self.dialog_search_products_by_image.exec_()

    def action_expense(self):
        self.row_field_expense_amount.setValue(0)
        self.row_field_description.setText('')
        self.dialog_expense.exec_()

    def action_production(self):
        self.row_field_production_quantity.setValue(0)
        self.dialog_production.exec_()

    def action_delete_line(self, key):
        sale = self.get_current_sale()
        if self._model_sale_lines.rowCount() <= 0 or \
            self._state == 'cash' or sale['state'] != 'draft':
            return
        if key is False:
            key = Qt.Key_Delete
        self.left_table_lines.setFocus()
        removed_item = self.left_table_lines.movedSelection(key)
        if removed_item is None:
            current_index = self.left_table_lines.currentIndex()
            current_line = self.left_table_lines.model.get_data(current_index)
            if current_line and current_line['id']:
                self._current_line_id = current_line['id']

        if key == Qt.Key_Delete or key == 0:
            if self._model_sale_lines.rowCount() > 0:
                self.set_amounts()
            else:
                self.clear_right_panel()
            self._current_line_id = None
            self.setFocus()
            self.label_input.setFocus()

    def set_discount(self, eval_value, lines_ids=[]):
        res = False
        try:
            #value = round(float(str(eval_value)), 6)
            value = round(eval_value,6)
        except ValueError:
            return

        if float(value) < 0:
            return

        if not lines_ids:
            target_lines = [self._current_line_id]
        else:
            target_lines = lines_ids

        for line_id in target_lines:
            res = self._PosSaleLine.set_discount([line_id], value, self._context)
        if lines_ids:
            self.update_lines_amount(lines_ids)
        else:
            # Just update last product
            self._model_sale_lines.update(self._current_line_id)

        if res:
            self.set_amounts()
            self.set_discount_amount()
            self.update_subtotal_amount()
            self._clear_context()
        return res

    def set_unit_price(self, value):
        if float(value) <= 0:
            return
        validate = self._PosSaleLine.set_unit_price(
            [self._current_line_id], value, self._context)

        if validate:
            self._update_amounts()
            return True
        return False

    def add_payment(self, amount):
        voucher_number = None

        res = self._PosSale.add_payment(self.field_journal_id,
            amount, self._sale['id'], voucher_number, self._context)
        if res['result'] == 'statement_closed':
            self.dialog('statement_closed')
            self.message_bar.set('statement_closed')
            return res
        self.addPaymentLine(res['line_id'])
        return res

    def dialog_expense_accepted(self):
        voucher_number = None
        product = self.field_expense_product.get_id()
        amount = float(str(self.row_field_expense_amount.value()))
        description = str(self.row_field_line_description.text())

        res = self._PosSale.add_expense([], amount,
            product, description, self._context)

        if res['result'] == 'statement_closed':
            self.dialog('statement_closed')
            self.message_bar.set('statement_closed')
        else:
            self.dialog('expense_successfully')
        return

    def dialog_production_accepted(self):
        
        product = self.field_product_production.get_id()
        quantity = float(str(self.row_field_production_quantity.value()))

        res = self._PosSale.create_production([], product, quantity, self._context)

        if res['result'] == 'done':
            self.dialog('production_successfully')
        else:
            self.dialog('production_error')            
        return

    def addPaymentLine(self, line_id):
        self._model_payment_lines.appendId(line_id)

    def create_dialog_help(self):
        from .help import Help
        help = Help(self)
        help.show()

    def set_keys(self):
        self.keys_numbers = list(range(Qt.Key_0, Qt.Key_9 + 1))
        self.keys_alpha = list(range(Qt.Key_A, Qt.Key_Z + 1))
        self.keys_period = [Qt.Key_Period]
        self.show_keys = self.keys_numbers + self.keys_alpha + self.keys_period

        self.keys_special = [Qt.Key_Asterisk, #Qt.Key_Comma,
            Qt.Key_Minus, Qt.Key_Shift]
        self.keys_input = [Qt.Key_Backspace]
        self.keys_input.extend(self.keys_special)
        self.keys_input.extend(self.show_keys)
        self.keys_input.extend(self.keys_numbers)
        self.keys_input.extend([Qt.Key_Return, Qt.Key_Plus, \
            Qt.Key_Comma, Qt.Key_Slash, Qt.Key_Enter,Qt.Key_F6])

    def set_state(self, state='add'):
        self._state = state
        state = STATES[state]
        self._re = state['re']
        #if not self.type_pos_user == 'order':
        #    if not self.buttonpad.stacked.stacked.currentWidget():
        #        return
        #self.buttonpad.stacked.stacked.currentWidget().setVisible(True)
        if not self.buttonpad.stacked.stacked.currentWidget():
            return
        if state['button']:
            self.buttonpad.stacked.stacked.setCurrentWidget(
                getattr(self.buttonpad.stacked, state['button'])
            )
            if not self.tablet_mode:
                self.buttonpad.stacked.stacked.currentWidget().setVisible(True)
        else:
            self.buttonpad.stacked.stacked.currentWidget().setVisible(False)

    def key_pressed(self, text):
        if not self._sign and self._state != 'cash':
            if self._re.match(self._input_text + text):
                self.input_text_changed(text)
        else:
            if RE_SIGN['quantity'].match(self._amount_text + text):
                self.amount_text_changed(text)

    def clear_sign(self):
        self._sign = None
        self.field_sign.setText(' {0} '.format(' '))

    def sign_text_changed(self, sign):
        self._sign = sign
        self.field_sign.setText(' {0} '.format(sign))
        if hasattr(self, '_sale_line') and self._sale_line:
            if sign == '-':
                self.message_bar.set('enter_discount')
            #elif sign == '/':
            #    self.message_bar.set('enter_new_price')
            elif sign == '*':
                self.message_bar.set('enter_quantity')
                if self.active_weighing and self._sale_line['unit_symbol'] != 'u':
                    self.action_read_weight()

    def key_special_pressed(self, value):
        self.clear_amount_text()
        self.clear_input_text()
        #if value not in ['-', '/', '*']:
        if value not in ['-', '*']:
            return
        self.sign_text_changed(value)

    def key_backspace_pressed(self):
        if self._sign or self._state == 'cash':
            self._amount_text = self._amount_text[:-1]
            self.amount_text_changed()
        else:
            self._input_text = self._input_text[:-1]
            self.input_text_changed()

    def set_text(self, text):
        if not self._state == 'cash':
            self.input_text_changed(text)
        else:
            self.amount_text_changed(text)

    def clear_input_text(self):
        self.input_text_changed('')

    def clear_amount_text(self):
        self._amount_text = '0'
        self.amount_text_changed()

    def eventFilter(self, source, event):
        self._global_timer = 0
        return super(MainWindow, self).eventFilter(source, event)

    def keyPressEvent(self, event):
        self._keyStates[event.key()] = True
        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        #if self._state == 'add' and key in [Qt.Key_Enter]:
        #    self.button_accept_pressed()
        if self._state == 'add' and key not in self.keys_input and \
                key not in (Qt.Key_Enter, Qt.Key_End, \
                    Qt.Key_Comma,
                    Qt.Key_Return,
                    Qt.Key_Escape):
            # Clear ui context when keys function are pressed
            self.label_input.setFocus()
            self._clear_context()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.button_plus_pressed()
        elif key in self.show_keys:
            # No allow change quantity o discount in state == cash
            if self._state == 'cash' and key not in self.keys_numbers:
                return
            self.key_pressed(event.text())
        elif key in self.keys_special:
            if self._state == 'cash' or not self._current_line_id:
                return
            self.key_special_pressed(event.text())
        elif key == Qt.Key_Backspace:
            self.key_backspace_pressed()
        elif key == Qt.Key_Escape:
            self.close()
        elif key == Qt.Key_F1:
            self.create_dialog_help()
        elif self._state == 'disabled':
            self.message_bar.set('must_load_or_create_sale')
            return
        elif key == Qt.Key_End: #(Qt.Key_Enter, Qt.Key_End):
            if self._state == 'add':
                self.button_accept_pressed()
            elif self._state in ['accept', 'cash']:
                self.button_cash_pressed()
        elif key == Qt.Key_F2:
            self._current_line_id = None
            self.action_search_product()
        elif key == Qt.Key_F3:
            self.button_accept_pressed()
            self.button_cash_pressed()
        elif key == Qt.Key_F4:
            self.action_party()
        elif key == Qt.Key_F5:
            self.action_new_statement()
        elif key == Qt.Key_F6:
            self.button_add_party_pressed()
        elif key == Qt.Key_F7:
            self.action_re_print_invoice()
        elif key == Qt.Key_F8:
            #self.action_print_statement()
            self.action_select_delivery_method()
        elif key == Qt.Key_F9:
            self.action_search_sale()
        elif key == Qt.Key_F10:
            #self.close_statement()
            self.action_top_sales()
        elif key == Qt.Key_F11:
            self.action_new_sale()
        elif key == Qt.Key_F12:
            self.action_cancel()
        elif key == Qt.Key_Home:
            self.sale_line_selected()
        elif key == Qt.Key_Down or key == Qt.Key_Up or key == Qt.Key_Delete:
            self.action_delete_line(key)
        elif key == Qt.Key_Insert:
            self.action_position()
        elif key == Qt.Key_Slash:
            self.button_add_party_pressed()
        elif key == Qt.Key_Plus:
            self.button_add_agent_pressed()
        elif key == Qt.Key_QuoteDbl:
            self.action_comment()
        elif key == Qt.Key_Question:
            self.action_tax()
        else:
            pass

    @property
    def state(self):
        return self._state

    def get_system_info(self):
        return 'OS: %s\nPython: %r' % (sys.platform, sys.version_info)

    def get_application_log(self):
        return "Crash Report: "

class DoInvoice(QThread):
    """
    Process invoices using a thread
    """
    sigDoInvoice = pyqtSignal()

    def __init__(self, main, context):
        QThread.__init__(self)

    def run(self):
        self.sigDoInvoice.emit()
