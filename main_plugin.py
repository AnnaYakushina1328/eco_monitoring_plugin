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
                'Низкий': (0, 50),
                'Умеренный': (51, 100),
                'Высокий': (101, 200),
                'Очень высокий': (201, 1000)
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