# генерация отчетов
import os
import tempfile
from qgis.PyQt.QtWidgets import QMessageBox

class ReportGenerator:
    def generate_simple_report(self, layer, field_name):
        # cобираем статистику
        values = []
        for feature in layer.getFeatures():
            try:
                values.append(float(feature[field_name]))
            except:
                pass
        
        if not values:
            return "Нет данных для отчета"
        
        # рассчитываем показатели
        avg = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        
        # формируем отчет
        report = f"Отчет экологического мониторинга\n\n"
        report += f"Анализируемый слой: {layer.name()}\n"
        report += f"Анализируемое поле: {field_name}\n\n"
        report += f"Среднее значение: {avg:.2f}\n"
        report += f"Максимальное значение: {max_val:.2f}\n"
        report += f"Минимальное значение: {min_val:.2f}\n"
        report += f"Количество объектов: {len(values)}\n"
        
        # сохраняем во временный файл
        report_file = os.path.join(tempfile.gettempdir(), "eco_report.txt")
        with open(report_file, 'w') as f:
            f.write(report)
        
        return report_file