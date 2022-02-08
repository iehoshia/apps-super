
from PyQt5.QtGui import QColor

color_white           = QColor(255, 255, 255)
color_white_hide      = QColor(255, 255, 255, 0)

color_gray_soft       = QColor(242, 242, 242, 255)
color_gray_light      = QColor(102, 102, 102, 255)
color_gray_dark       = QColor(170, 170, 170, 255)
color_gray_hover      = QColor(225, 225, 225, 250)

color_blue_soft       = QColor(15, 160, 210, 255)
color_blue_light      = QColor(220, 240, 250, 255)
color_blue_press      = QColor(190, 230, 245, 255)
color_blue_hover      = QColor(80, 170, 210, 120)

color_green_soft      = QColor(140, 225, 210, 235)
color_green_light     = QColor(170, 215, 110, 250)
color_green_dark      = QColor(105, 180, 55)
color_green_hover     = QColor(180, 215, 100)

color_yellow_font     = QColor(185, 110, 5, 255)
color_yellow_bg       = QColor(251, 215, 110, 230)
color_yellow_hover    = QColor(251, 215, 50, 255)
color_yellow_press    = QColor(251, 215, 70, 110)

color_red             = QColor(20, 150, 230)

themes = {
    'default': {
        'font_color': color_gray_light,
        'bg_color': color_blue_light,
        'hover_color': color_blue_hover,
        'press_color': color_gray_hover,
        'pen': color_white_hide,
    },
    'blue': {
        'font_color': color_gray_dark,
        'bg_color': color_white,
        'hover_color': color_blue_light,
        'press_color': color_blue_press,
        'pen': color_white_hide,
    },
    'green': {
        'font_color': color_white,
        'bg_color': color_green_soft,
        'hover_color': color_green_light,
        'press_color': color_green_dark,
        'pen': color_white_hide,
    },
    'yellow': {
        'font_color': color_yellow_font,
        'bg_color': color_yellow_bg,
        'hover_color': color_yellow_hover,
        'press_color': color_yellow_press,
        'pen': color_white_hide,
    }
}
