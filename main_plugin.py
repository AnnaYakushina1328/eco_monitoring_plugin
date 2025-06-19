import os
import tempfile
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QComboBox, QMessageBox, QAction,
    QTextEdit, QFileDialog, QProgressBar, QFrame
)
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QVariant
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, 
    QgsField, QgsFields, QgsSymbol, 
    QgsRendererCategory, QgsCategorizedSymbolRenderer
)
import fitz  # PyMuPDF
from qgis.PyQt.QtWidgets import QInputDialog
import cv2
import numpy as np
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY
import json


class PDFConverterThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    ask_filename = pyqtSignal()  # новый сигнал для запроса имени файла

    def __init__(self, pdf_path, output_dir, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.file_name = "converted_map"  # значение по умолчанию
        self.ask_filename.connect(self.request_filename, Qt.QueuedConnection)

    def request_filename(self):
        """Вызывается в основном потоке через сигнал"""
        file_name, ok = QInputDialog.getText(
            None,  # используем None вместо self.parent
            "Имя файла",
            "Введите имя для сохраняемого файла (без расширения):",
            text="converted_map"
        )
        if ok and file_name:
            self.file_name = file_name
        self.start_conversion()

    def start_conversion(self):
        """Запускает конвертацию после получения имени файла"""
        try:
            doc = fitz.open(self.pdf_path)
            output_path = os.path.join(self.output_dir, f"{self.file_name}.png")
            
            # проверка существования файла
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(self.output_dir, f"{self.file_name}_{counter}.png")
                counter += 1

            # конвертация
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=300)
                pix.save(output_path)
                self.progress.emit(int((i + 1) / len(doc) * 100))
            
            self.finished.emit(output_path)
            
        except Exception as e:
            self.error.emit(f"Ошибка конвертации: {str(e)}")

    def run(self):
        """Точка входа в поток"""
        self.ask_filename.emit()  # запрашиваем имя файла через сигнал

class EcoMonitoringPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dialog = None
        self.pdf_thread = None

    def initGui(self):
        """Инициализация интерфейса"""
        try:
            icon = QIcon(os.path.join(self.plugin_dir, 'icons', 'icon.png'))
        except:
            icon = QIcon.fromTheme("applications-science")
            
        self.action = QAction(
            icon,
            "Эко Мониторинг",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.show_dialog)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Эко Мониторинг", self.action)

    def unload(self):
        """Удаление плагина"""
        self.iface.removePluginMenu("Эко Мониторинг", self.action)
        self.iface.removeToolBarIcon(self.action)

    def show_dialog(self):
        """Создание диалогового окна"""
        self.dialog = QDialog()
        self.dialog.setWindowTitle("Экологический мониторинг")
        self.dialog.setMinimumSize(450, 350)
        
        layout = QVBoxLayout()

        # Заголовок
        title = QLabel("<h2>Экологический мониторинг</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Извлечение набора данных границ с карты
        btn_extract_contours = QPushButton("Извлечь контуры")
        btn_extract_contours.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px;")
        btn_extract_contours.clicked.connect(self.extract_contours)
        layout.addWidget(btn_extract_contours)

        # Выбор слоя
        layout.addWidget(QLabel("Выберите слой для анализа:"))
        self.layer_combo = QComboBox()
        self.update_layer_list()
        layout.addWidget(self.layer_combo)
        
        # Выбор поля
        layout.addWidget(QLabel("Выберите поле с данными:"))
        self.field_combo = QComboBox()
        layout.addWidget(self.field_combo)
        self.layer_combo.currentIndexChanged.connect(self.update_field_list)
        
        # Кнопки анализа
        btn_frame = QFrame()
        btn_layout = QHBoxLayout()
        
        btn_classify = QPushButton("Классифицировать загрязнение")
        btn_classify.clicked.connect(self.classify_pollution)
        btn_layout.addWidget(btn_classify)
        
        btn_report = QPushButton("Создать отчет")
        btn_report.clicked.connect(self.generate_report)
        btn_layout.addWidget(btn_report)
        
        btn_frame.setLayout(btn_layout)
        layout.addWidget(btn_frame)
        
        # Кнопка конвертации PDF
        btn_pdf = QPushButton("Конвертировать PDF в PNG")
        btn_pdf.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px;")
        btn_pdf.clicked.connect(self.convert_pdf)
        layout.addWidget(btn_pdf)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.dialog.setLayout(layout)
        self.dialog.show()

    def extract_contours(self):
        """Извлечение контуров из растровой карты"""
        # Выбор файла карты
        image_path, _ = QFileDialog.getOpenFileName(
            self.dialog, "Выберите файл карты", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not image_path:
            return

        # Выбор папки для сохранения результатов
        output_dir = QFileDialog.getExistingDirectory(
            self.dialog, "Выберите папку для сохранения"
        )
        if not output_dir:
            return

        # Имя выходного файла
        output_file = os.path.join(output_dir, "contours.geojson")

        # Запуск потока для извлечения контуров
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.contour_thread = ContourExtractorThread(image_path, output_file)
        self.contour_thread.progress.connect(self.progress_bar.setValue)
        self.contour_thread.finished.connect(self.on_contours_extracted)
        self.contour_thread.error.connect(self.show_error)
        self.contour_thread.start()

    def convert_pdf(self):
        """Конвертация PDF в PNG с прогресс-баром"""
        pdf_path, _ = QFileDialog.getOpenFileName(
            self.dialog, "Выберите PDF файл", "", "PDF Files (*.pdf)"
        )
        if not pdf_path:
            return
            
        output_dir = QFileDialog.getExistingDirectory(
            self.dialog, "Выберите папку для сохранения"
        )
        if not output_dir:
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.pdf_thread = PDFConverterThread(pdf_path, output_dir)
        self.pdf_thread.progress.connect(self.progress_bar.setValue)
        self.pdf_thread.finished.connect(self.on_pdf_converted)
        self.pdf_thread.error.connect(self.show_error)
        self.pdf_thread.start()

    def on_pdf_converted(self, output_dir):
        """Действия после конвертации"""
        self.progress_bar.setVisible(False)
        QMessageBox.information(
            self.dialog,
            "Готово",
            f"PDF успешно конвертирован!\nСохранено в:\n{output_dir}"
        )

    def show_error(self, message):
        """Показать ошибку"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self.dialog, "Ошибка", message)

    def update_layer_list(self):
        """Обновление списка слоев"""
        self.layer_combo.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            self.layer_combo.addItem(layer.name(), layer)

    def update_field_list(self):
        """Обновление списка полей"""
        self.field_combo.clear()
        layer = self.layer_combo.currentData()
        if layer and isinstance(layer, QgsVectorLayer):
            for field in layer.fields():
                self.field_combo.addItem(field.name())

    def classify_pollution(self):
        """Классификация загрязнения"""
        layer = self.layer_combo.currentData()
        field_name = self.field_combo.currentText()
        
        if not layer or not field_name:
            self.show_message("Ошибка", "Выберите слой и поле!")
            return
            
        try:
            # Создаем новый слой для результатов
            crs = layer.crs().authid()
            result_layer = QgsVectorLayer(f"Polygon?crs={crs}", "Классификация загрязнения", "memory")
            provider = result_layer.dataProvider()
            
            # Копируем поля из исходного слоя
            provider.addAttributes(layer.fields())
            provider.addAttributes([QgsField("class", QVariant.String)])
            result_layer.updateFields()
            
            # Пороги классификации
            thresholds = {
                (0, 1000)
            }
            
            # Обрабатываем объекты
            for feature in layer.getFeatures():
                try:
                    value = float(feature[field_name])
                    # Определяем класс
                    pollution_class = "Неизвестно"
                    for cls, (min_val, max_val) in thresholds.items():
                        if min_val <= value <= max_val:
                            pollution_class = cls
                            break
                    
                    # Создаем новую фичу
                    new_feature = QgsFeature(result_layer.fields())
                    new_feature.setGeometry(feature.geometry())
                    new_feature.setAttributes(feature.attributes() + [pollution_class])
                    provider.addFeature(new_feature)
                except:
                    continue
            
            # Применяем стиль
            self.apply_style(result_layer)
            
            # Добавляем слой в проект
            QgsProject.instance().addMapLayer(result_layer)
            self.show_message("Успех", "Классификация завершена!")
            
        except Exception as e:
            self.show_message("Ошибка", f"Ошибка классификации: {str(e)}")

    def apply_style(self, layer):
        """Применение стиля к слою"""
        # Цвета для классов
        colors = {
            'Низкий': '#00FF00',    # Зеленый
            'Умеренный': '#FFFF00',  # Желтый
            'Высокий': '#FFA500',    # Оранжевый
            'Очень высокий': '#FF0000' # Красный
        }
        
        # Создаем категории
        categories = []
        for name, color in colors.items():
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(color))
            category = QgsRendererCategory(name, symbol, name)
            categories.append(category)
        
        # Применяем рендерер
        renderer = QgsCategorizedSymbolRenderer("class", categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def generate_report(self):
        """Генерация отчета"""
        layer = self.layer_combo.currentData()
        field_name = self.field_combo.currentText()
        
        if not layer or not field_name:
            self.show_message("Ошибка", "Выберите слой и поле!")
            return
            
        try:
            # Собираем статистику
            values = []
            for feature in layer.getFeatures():
                try:
                    values.append(float(feature[field_name]))
                except:
                    continue
            
            if not values:
                self.show_message("Ошибка", "Нет данных для анализа!")
                return
                
            # Формируем отчет
            report = QTextEdit()
            report.setReadOnly(True)
            report.setText(
                f"Отчет экологического мониторинга\n\n"
                f"Слой: {layer.name()}\n"
                f"Поле: {field_name}\n\n"
                f"Объектов: {len(values)}\n"
                f"Среднее: {sum(values)/len(values):.2f}\n"
                f"Минимум: {min(values):.2f}\n"
                f"Максимум: {max(values):.2f}\n"
            )
            
            # Показываем отчет в диалоге
            report_dialog = QDialog()
            report_dialog.setWindowTitle("Отчет")
            layout = QVBoxLayout()
            layout.addWidget(report)
            report_dialog.setLayout(layout)
            report_dialog.exec_()
            
        except Exception as e:
            self.show_message("Ошибка", f"Ошибка генерации отчета: {str(e)}")

    def show_message(self, title, message):
        """Показать сообщение"""
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()

    def on_contours_extracted(self, output_file):
        """Действия после извлечения контуров"""
        self.progress_bar.setVisible(False)
        QMessageBox.information(
            self.dialog,
            "Готово",
            f"Контуры успешно извлечены и сохранены!\nФайл: {output_file}"
        )

        # Загружаем GeoJSON как слой в QGIS
        layer_name = os.path.splitext(os.path.basename(output_file))[0]
        layer = QgsVectorLayer(output_file, layer_name, "ogr")
        if not layer.isValid():
            self.show_message("Ошибка", "Не удалось загрузить слой!")
            return

        QgsProject.instance().addMapLayer(layer)
        self.generate_contour_report_with_csv(output_file)
    
    def generate_contour_report(self, geojson_path):
        """Генерация отчета с координатами полигонов"""
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            report_text = "📊 Отчет по извлеченным контурам:\n\n"
            for feature in data.get("features", []):
                poly_id = feature["properties"]["id"]
                coords = feature["geometry"]["coordinates"][0]  # Только внешний контур
                coord_str = "\n".join([f"{x:.2f}, {y:.2f}" for x, y in coords])
                report_text += f"🔹 Полигон #{poly_id} ({len(coords)} точек):\n{coord_str}\n\n"

            # Показываем отчет
            dialog = QDialog()
            dialog.setWindowTitle("Отчет по контурам")
            layout = QVBoxLayout()
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setText(report_text)
            layout.addWidget(text_edit)
            dialog.setLayout(layout)
            dialog.resize(600, 400)
            dialog.exec_()
    
        except Exception as e:
            self.show_message("Ошибка", f"Ошибка генерации отчета: {str(e)}")

    def generate_contour_report_with_csv(self, geojson_path):
        """Генерация отчета с возможностью сохранения в CSV"""
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            dialog = QDialog()
            dialog.setWindowTitle("Отчет по контурам")
            layout = QVBoxLayout()

            # Текстовое поле
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)

            # Кнопки
            btn_layout = QHBoxLayout()
            save_btn = QPushButton("Сохранить в CSV")

            # Сбор текста
            report_text = "📊 Отчет по извлеченным контурам:\n\n"
            csv_data = []

            for feature in data.get("features", []):
                poly_id = feature["properties"]["id"]
                coords = feature["geometry"]["coordinates"][0]  # Только внешний контур
                coord_str = "\n".join([f"{x:.2f}, {y:.2f}" for x, y in coords])
                report_text += f"🔹 Полигон #{poly_id} ({len(coords)} точек):\n{coord_str}\n\n"

                # Для CSV
                for x, y in coords:
                    csv_data.append([poly_id, x, y])

            text_edit.setText(report_text)
            layout.addWidget(text_edit)

            # Обработчик нажатия на кнопку
            def save_to_csv():
                path, _ = QFileDialog.getSaveFileName(dialog, "Сохранить CSV", "", "CSV Files (*.csv)")
                if path:
                    import csv
                    with open(path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(["Polygon ID", "X", "Y"])
                        writer.writerows(csv_data)
                    QMessageBox.information(dialog, "Сохранено", f"Данные сохранены в файл:\n{path}")

            save_btn.clicked.connect(save_to_csv)
            btn_layout.addWidget(save_btn)
            layout.addLayout(btn_layout)

            dialog.setLayout(layout)
            dialog.resize(600, 400)
            dialog.exec_()

        except Exception as e:
            self.show_message("Ошибка", f"Ошибка генерации отчета: {str(e)}")

class ContourExtractorThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, image_path, output_file, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.output_file = output_file

    def run(self):
        try:
            # Чтение изображения
            image = cv2.imread(self.image_path)
            if image is None:
                raise ValueError("Не удалось загрузить изображение")

            # Переводим в оттенки серого
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Удаление шумов
            gray = cv2.GaussianBlur(gray, (5, 5), 0)

            # Адаптивная бинаризация
            thresh = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                11,  # Размер блока
                2    # Константа C
            )

            # Морфологическая операция: закрытие (заполнение дырок)
            kernel = np.ones((5, 5), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            # Поиск контуров
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Фильтрация внешнего контура
            if not contours:
                raise ValueError("Контур не найден")

            # Сортировка контуров по площади (от большего к меньшему)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            # Игнорируем самый большой контур (внешняя рамка)
            contours = contours[1:]  # Пропускаем первый элемент (самый большой контур)

            # Формируем GeoJSON FeatureCollection
            features = []
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if area < 500:  # фильтруем слишком маленькие объекты
                    continue

                # Преобразуем контур в список координат
                coords = [list(map(float, pt[0])) for pt in contour]
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords]
                    },
                    "properties": {
                        "id": i + 1,
                        "area_px": area
                    }
                }
                features.append(feature)

            geojson_data = {
                "type": "FeatureCollection",
                "features": features
            }

            # Сохраняем GeoJSON
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, indent=2)

            self.finished.emit(self.output_file)

        except Exception as e:
            self.error.emit(f"Ошибка при извлечении контуров: {str(e)}")