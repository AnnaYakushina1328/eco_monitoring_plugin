# стилизация карты
from qgis.core import QgsSymbol, QgsRendererRange, QgsGraduatedSymbolRenderer
from qgis.PyQt.QtGui import QColor

class EcoVisualizer:
    @staticmethod
    def apply_pollution_style(layer):
        # цвета для классов загрязнения
        classes = {
            'Низкий': (0, 50, QColor(0, 255, 0)),      # зеленый
            'Умеренный': (51, 100, QColor(255, 255, 0)), # жёлтый
            'Высокий': (101, 200, QColor(255, 165, 0)),  # оранжевый
            'Очень высокий': (201, 1000, QColor(255, 0, 0)) # красный
        }
        
        ranges = []
        for class_name, (min_val, max_val, color) in classes.items():
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(color)
            range = QgsRendererRange(min_val, max_val, symbol, class_name)
            ranges.append(range)
        
        renderer = QgsGraduatedSymbolRenderer("", ranges)
        renderer.setClassAttribute("class")
        layer.setRenderer(renderer)
        layer.triggerRepaint()