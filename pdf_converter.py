import os
import tempfile
import fitz  
import cv2
import numpy as np
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, 
    QFileDialog, QLabel, QProgressBar
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal

class PDFConverter(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF to Image Converter")
        self.setMinimumSize(400, 200)
        
        self.layout = QVBoxLayout()
        
        # элементы интерфейса
        self.label = QLabel("Выберите PDF-файл для конвертации")
        self.btn_select = QPushButton("Выбрать PDF")
        self.btn_convert = QPushButton("Конвертировать в PNG")
        self.btn_convert.setEnabled(False)
        self.progress = QProgressBar()
        
        # настройка машинного зрения
        self.use_opencv = True  # включить обработку OpenCV по умолчанию
        
        # добавляем элементы в layout
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.btn_select)
        self.layout.addWidget(self.btn_convert)
        self.layout.addWidget(self.progress)
        self.setLayout(self.layout)
        
        # подключаем сигналы
        self.btn_select.clicked.connect(self.select_pdf)
        self.btn_convert.clicked.connect(self.start_conversion)

    def select_pdf(self):
        """Выбор PDF-файла"""
        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите PDF", "", "PDF Files (*.pdf)"
        )
        if pdf_path:
            self.pdf_path = pdf_path
            self.label.setText(f"Выбран: {os.path.basename(pdf_path)}")
            self.btn_convert.setEnabled(True)

    def start_conversion(self):
        """Запуск конвертации в отдельном потоке"""
        self.thread = ConversionThread(self.pdf_path, self.use_opencv)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def update_progress(self, value):
        """Обновление прогресс-бара"""
        self.progress.setValue(value)

    def on_finished(self, output_dir):
        """Завершение конвертации"""
        self.label.setText(f"Готово! Изображения сохранены в:\n{output_dir}")
        self.progress.setValue(100)

class ConversionThread(QThread):
    """Поток для конвертации PDF с прогрессом"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, pdf_path, use_opencv=True):
        super().__init__()
        self.pdf_path = pdf_path
        self.use_opencv = use_opencv

    def run(self):
        """Основная логика конвертации"""
        try:
            # создаем временную папку
            output_dir = tempfile.mkdtemp(prefix="pdf_export_")
            
            # открываем PDF
            doc = fitz.open(self.pdf_path)
            total_pages = len(doc)
            
            for i, page in enumerate(doc):
                # конвертируем страницу в изображение (300 DPI)
                pix = page.get_pixmap(dpi=300)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )
                
                # обработка OpenCV (если включена)
                if self.use_opencv:
                    img = self.process_with_opencv(img)
                
                # сохраняем как PNG
                output_path = os.path.join(output_dir, f"page_{i+1}.png")
                cv2.imwrite(output_path, img)
                
                # обновляем прогресс
                self.progress.emit(int((i + 1) / total_pages * 100))
            
            self.finished.emit(output_dir)
        except Exception as e:
            print(f"Ошибка: {e}")

    def process_with_opencv(self, img):
        """Обработка изображения через OpenCV"""
        # конвертируем в grayscale (если нужно)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # улучшаем контраст (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # детекция краев (Canny)
        edges = cv2.Canny(enhanced, 50, 150)
        
        return edges