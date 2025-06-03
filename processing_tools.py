#обработка данных
from qgis.core import QgsVectorLayer, QgsFeature, QgsField, QgsFields, QgsGeometry
from qgis.PyQt.QtCore import QVariant

class EcoDataProcessor:
    def __init__(self, layer):
        self.layer = layer
        
    def classify_pollution(self, field_name, thresholds):
        # создаем новый слой для результатов
        crs = self.layer.crs().authid()
        classified_layer = QgsVectorLayer(f"Polygon?crs={crs}", "Classified Pollution", "memory")
        
        # настраиваем поля
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("class", QVariant.String))
        classified_layer.dataProvider().addAttributes(fields)
        classified_layer.updateFields()
        
        # обрабатываем каждый объект
        for i, feature in enumerate(self.layer.getFeatures()):
            value = feature[field_name]
            pollution_class = self._get_class(value, thresholds)
            
            new_feature = QgsFeature()
            new_feature.setGeometry(feature.geometry())
            new_feature.setAttributes([i, pollution_class])
            classified_layer.dataProvider().addFeature(new_feature)
            
        classified_layer.updateExtents()
        return classified_layer
    
    def _get_class(self, value, thresholds):
        try:
            value = float(value)
        except:
            return "Invalid data"
            
        for class_name, (min_val, max_val) in thresholds.items():
            if min_val <= value <= max_val:
                return class_name
        return "Unknown"