
from neox.commons.dialogs import HelpDialog


class Help(HelpDialog):

    def __init__(self, parent):
        super(Help, self).__init__(parent)
        shortcuts = [
            (self.tr('AYUDA'), 'F1'),
            (self.tr('BUSCAR PRODUCTO'), 'F2'),
            (self.tr('FACTURAR'), 'F3'),
            (self.tr('BUSCAR CLIENTE'), 'F4'),
            (self.tr('CAJA NUEVA'), 'F5'),
            (self.tr('AGREGAR CLIENTE'), 'F6'),
            (self.tr('IMPRIMIR FACTURA'), 'F7'),
            (self.tr('METODO DE ENTREGA'), 'F8'),
            (self.tr('BUSCAR VENTA'), 'F9'),
            (self.tr('CERRAR CAJA'), 'F10'),
            (self.tr('NUEVA VENTA'), 'F11'),
            (self.tr('CANCELAR VENTA'), 'F12'),
            (self.tr('AGREGAR PRODUCTO'), 'ENTER'),
            (self.tr('AGREGAR AGENTE'), '+'),
            (self.tr('AGREGAR DESCUENTO'), '-'),
            (self.tr('AGREGAR CLIENTE'), '/'),
            (self.tr('MODIFICAR CANTIDAD'), '*'),
            #(self.tr('SALESMAN'), 'Home'),
            #(self.tr('POSITION'), 'Insert'),
            #(self.tr('CASH'), 'End'),
            #(self.tr('COMMENT'), 'Page Down'),
        ]

        self.set_shortcuts(shortcuts)
