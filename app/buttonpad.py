import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QGridLayout, QHBoxLayout, QStackedWidget

from neox.commons.custom_button import CustomButton, CustomProductButton
from .common import get_svg_icon, get_png_icon, get_local_png_icon

DIR_SHARE = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', 'share')))

__all__ = ['ButtonsFunction', 'ButtonsStacked', 'ButtonsNumber',
    'Productpad','ProductButtons']

def factoryIcons():
    pass

factoryIcons()

class ButtonsFunction(QGridLayout):
    # Function Numpad

    def __init__(self, parent, tablet_mode=False):
        super(ButtonsFunction, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)

        columns = 3
        rows = 3

        self.values = []

        self.values.extend([

            #['button_search_product', self.tr('PRODUCTO'), 'action_search_product'], #SERVICIOS
            ['button_search_category', self.tr('MENU'), 'action_search_category'], #CATEGORIES
            #['button_search_combo', self.tr('COMBO'), 'action_search_combo'], #CATEGORIES
            ['button_new_sale', self.tr('NEW SALE'), 'action_new_sale'],
        ])

        self.values.extend([
            ['button_search_sale', self.tr('S. SALE'), 'action_search_sale'],
            ['button_cancel', self.tr('CANCEL'), 'action_cancel'],
            ['button_credit_sale', self.tr('CREDIT SALE'), 'action_credit_sale'],
            ['button_invoice_reprint', self.tr('REPRINT'), 'action_re_print_invoice'],
            #['button_product_by_location', self.tr('P. BY LOCATION'), \
            #    'action_print_product_by_location'],
            ['button_expense', self.tr('GASTOS'), 'action_expense'],
            ['button_purchase', self.tr('COMPRAS'), \
                'action_search_purchase'],
            ['button_statement', self.tr('CIERRE'), \
                'action_load_statement'],
        ])

        positions = [(i, j) for i in range(rows) for j in range(columns)]
        for position, value in zip(positions, self.values):
            name_icon = value[0][7:]
            button = CustomButton(
                parent,
                id=value[0],
                icon=get_svg_icon(name_icon),
                desc=value[1],
                method=value[2],
                name_style='toolbar_button'
            )
            self.addWidget(button, *position)

class Buttonpad(QWidget):

    def __init__(self, parent):
        super(Buttonpad, self).__init__()
        self._text = ''
        self._keyStates = {}
        self.functions = ButtonsFunction(parent)
        self.numbers = ButtonsNumber(parent)

        self.stacked = ButtonsStacked(parent)
        self.set_keys()

    def set_keys(self):
        q = Qt
        self.keys_numbers = list(range(q.Key_0, q.Key_9 + 1))
        self.keys_alpha = list(range(q.Key_A, q.Key_Z + 1))
        self.keys_special = [
            q.Key_Asterisk, q.Key_Comma, q.Key_Period,
            q.Key_Minus, q.Key_Slash]
        self.show_keys = self.keys_numbers + self.keys_alpha + self.keys_special

class ButtonsStacked(QHBoxLayout):

    def __init__(self, parent):
        super(ButtonsStacked, self).__init__()
        self.stacked = QStackedWidget()

        self.button_accept = CustomButton(
            id='button_accept',
            parent=parent,
            icon=get_svg_icon('accept'),
            name_style='toolbar',
            method='button_accept_pressed'
        )
        self.button_cash = CustomButton(
            id='button_cash',
            parent=parent,
            icon=get_svg_icon('cash'),
            name_style='toolbar',
            method='button_cash_pressed'
        )

        #if parent.type_pos_user != 'order' and not parent.tablet_mode:
        self.stacked.addWidget(self.button_accept)
        self.stacked.addWidget(self.button_cash)
        self.addWidget(self.stacked, 0)

class ButtonsNumber(QGridLayout):

    def __init__(self, parent):
        # Numpad for Numbers
        super(ButtonsNumber, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)

class ProductButtons(QGridLayout):
    # Product by Images

    def __init__(self, parent, tablet_mode=False, data=[]):
        super(ProductButtons, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)

        columns = 4
        rows = 4

        self.values = data

        positions = [(i, j) for i in range(rows) for j in range(columns)]
        for position, value in zip(positions, self.values):
            name_icon = value[1]
            button = CustomProductButton(
                parent,
                id=value[0],
                icon=get_png_icon(name_icon),
                desc=value[1],
                method=value[2],
                name_style='category_button'
            )

            self.addWidget(button, *position)

class Productpad(QWidget):

    def __init__(self, parent, data=[]):
        super(Productpad, self).__init__()
        self._text = ''
        self._keyStates = {}
        self.products = ProductButtons(parent, data=data)
        self.set_keys()

    def set_keys(self):
        q = Qt
        self.keys_numbers = list(range(q.Key_0, q.Key_9 + 1))
        self.keys_alpha = list(range(q.Key_A, q.Key_Z + 1))
        self.keys_special = [
            q.Key_Asterisk, q.Key_Comma, q.Key_Period,
            q.Key_Minus, q.Key_Slash]
        self.show_keys = self.keys_numbers + self.keys_alpha + self.keys_special

class CategoryButtons(QGridLayout):
    # Product by Images

    def __init__(self, parent, tablet_mode=False, data=[]):
        super(CategoryButtons, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)

        columns = 4
        rows = 4

        self.values = data

        positions = [(i, j) for i in range(rows) for j in range(columns)]
        for position, value in zip(positions, self.values):
            name_icon = value[1]
            button = CustomProductButton(
                parent,
                id=value[0],
                icon=get_png_icon(name_icon),
                desc=value[1],
                method=value[2],
                name_style='category_button',
            )
            self.addWidget(button, *position)

class Categorypad(QWidget):

    def __init__(self, parent, data=[]):
        super(Categorypad, self).__init__()
        self._text = ''
        self._keyStates = {}
        self.categories = CategoryButtons(parent, data=data)
        self.set_keys()

    def set_keys(self):
        q = Qt
        self.keys_numbers = list(range(q.Key_0, q.Key_9 + 1))
        self.keys_alpha = list(range(q.Key_A, q.Key_Z + 1))
        self.keys_special = [
            q.Key_Asterisk, q.Key_Comma, q.Key_Period,
            q.Key_Minus, q.Key_Slash]
        self.show_keys = self.keys_numbers + self.keys_alpha + self.keys_special

class AgentButtons(QGridLayout):
    # Product by Images

    def __init__(self, parent, tablet_mode=False, data=[]):
        super(AgentButtons, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)

        columns = 5
        rows = 1

        self.values = data

        positions = [(i, j) for i in range(rows) for j in range(columns)]
        for position, value in zip(positions, self.values):
            name_icon = 'first_agent'#value[0][7:]
            button = CustomButton(
                parent,
                id=value[0],
                icon=get_svg_icon(name_icon),
                desc=value[1],
                method=value[2],
                name_style='product_button'
            )
            self.addWidget(button, *position)

class Agentpad(QWidget):

    def __init__(self, parent, data=[]):
        super(Agentpad, self).__init__()
        self._text = ''
        self._keyStates = {}

        self.agents = AgentButtons(parent, data=data)
        self.set_keys()

    def set_keys(self):
        q = Qt
        self.keys_numbers = list(range(q.Key_0, q.Key_9 + 1))
        self.keys_alpha = list(range(q.Key_A, q.Key_Z + 1))
        self.keys_special = [
            q.Key_Asterisk, q.Key_Comma, q.Key_Period,
            q.Key_Minus, q.Key_Slash]
        self.show_keys = self.keys_numbers + self.keys_alpha + self.keys_special

class DeliveryFunction(QGridLayout):
    # Delivery Numpad

    def __init__(self, parent, tablet_mode=False):
        super(DeliveryFunction, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)

        columns = 3
        rows = 2

        self.values = []

        self.values.extend([
            ['button_delivery', self.tr('DOMICILIO'), 'action_delivery_method'], #DOMICILIO
            ['button_local_table', self.tr('MESAS'), 'action_local_table'], #MESAS
            ['button_take_away', self.tr('LLEVAR'), 'action_take_away'], #LLEVAR
        ])

        positions = [(i, j) for i in range(rows) for j in range(columns)]
        for position, value in zip(positions, self.values):
            name_icon = value[0][7:]
            button = CustomProductButton(
                parent,
                id=value[0],
                icon=get_svg_icon(name_icon),
                desc=value[1],
                method=value[2],
                name_style='category_button'
            )

            self.addWidget(button, *position)

class Deliverypad(QWidget):

    def __init__(self, parent, data=[]):
        super(Deliverypad, self).__init__()
        self._text = ''
        self._keyStates = {}

        self.functions = DeliveryFunction(parent)

        self.set_keys()

    def set_keys(self):
        q = Qt
        self.keys_numbers = list(range(q.Key_0, q.Key_9 + 1))
        self.keys_alpha = list(range(q.Key_A, q.Key_Z + 1))
        self.keys_special = [
            q.Key_Asterisk, q.Key_Comma, q.Key_Period,
            q.Key_Minus, q.Key_Slash]
        self.show_keys = self.keys_numbers + self.keys_alpha + self.keys_special