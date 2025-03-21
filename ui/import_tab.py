"""
Import Tab Module for CSV file import
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, 
                            QLabel, QProgressBar, QTextEdit, QMessageBox, QComboBox, 
                            QLineEdit, QGroupBox, QFormLayout, QCheckBox)
from workers.import_worker import ImportWorker

class ImportTab(QWidget):
    """Tab for importing CSV files"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.init_ui()
        self.import_worker = None
        
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # File selection area
        file_group = QGroupBox("CSV File")
        file_layout = QFormLayout()
        
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_file)
        
        file_button_layout = QHBoxLayout()
        file_button_layout.addWidget(self.file_path)
        file_button_layout.addWidget(browse_button)
        
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["iso-8859-1", "utf-8", "utf-16", "cp1252"])
        
        self.detect_properties_checkbox = QCheckBox("Detect new properties")
        self.detect_properties_checkbox.setChecked(True)
        
        file_layout.addRow("File:", file_button_layout)
        file_layout.addRow("Encoding:", self.encoding_combo)
        file_layout.addRow("", self.detect_properties_checkbox)
        file_group.setLayout(file_layout)
        
        # Import controls
        control_layout = QHBoxLayout()
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.start_import)
        self.import_button.setEnabled(False)
        control_layout.addWidget(self.import_button)
        
        # Progress area
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_log)
        progress_group.setLayout(progress_layout)
        
        # Add all components to main layout
        layout.addWidget(file_group)
        layout.addLayout(control_layout)
        layout.addWidget(progress_group)
        
        self.setLayout(layout)
        
    def browse_file(self):
        """Open file dialog to select CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", "", "CSV Files (*.csv);;All Files (*.*)"
        )
        
        if file_path:
            self.file_path.setText(file_path)
            self.import_button.setEnabled(True)
            self.log_message(f"Selected file: {file_path}")
            
    def start_import(self):
        """Start the import process"""
        if not self.file_path.text():
            QMessageBox.warning(self, "Warning", "Please select a CSV file.")
            return
            
        self.import_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_message("Starting import...")
        
        # Create and start worker thread
        self.import_worker = ImportWorker(
            self.db_manager,
            self.file_path.text(),
            self.encoding_combo.currentText(),
            self.detect_properties_checkbox.isChecked()
        )
        
        # Connect signals
        self.import_worker.progress_updated.connect(self.update_progress)
        self.import_worker.status_updated.connect(self.log_message)
        self.import_worker.import_finished.connect(self.import_finished)
        
        # Start import
        self.import_worker.start()
        
    def update_progress(self, current, total):
        """Update progress bar"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        
    def log_message(self, message):
        """Add message to status log"""
        self.status_log.append(message)
        
    def import_finished(self, success, message):
        """Handle import completion"""
        self.import_button.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Import Complete", message)
        else:
            QMessageBox.critical(self, "Import Failed", message)
