"""
Export Tab Module for exporting product data
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, 
                            QLabel, QTextEdit, QMessageBox, QComboBox, QLineEdit, 
                            QGroupBox, QFormLayout, QCheckBox)
from workers.export_worker import ExportWorker

class ExportTab(QWidget):
    """Tab for exporting data"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.init_ui()
        self.export_worker = None
        
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # Export settings
        settings_group = QGroupBox("Export Settings")
        settings_layout = QFormLayout()
        
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse_button = QPushButton("Save As...")
        browse_button.clicked.connect(self.browse_file)
        
        file_button_layout = QHBoxLayout()
        file_button_layout.addWidget(self.file_path)
        file_button_layout.addWidget(browse_button)
        
        self.include_html_checkbox = QCheckBox("Generate HTML tables")
        self.include_html_checkbox.setChecked(True)
        
        self.apply_overrides_checkbox = QCheckBox("Apply property overrides")
        self.apply_overrides_checkbox.setChecked(True)
        
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["iso-8859-1", "utf-8", "utf-16", "cp1252"])
        
        settings_layout.addRow("File:", file_button_layout)
        settings_layout.addRow("Encoding:", self.encoding_combo)
        settings_layout.addRow("", self.include_html_checkbox)
        settings_layout.addRow("", self.apply_overrides_checkbox)
        settings_group.setLayout(settings_layout)
        
        # Export controls
        control_layout = QHBoxLayout()
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.start_export)
        self.export_button.setEnabled(False)
        control_layout.addWidget(self.export_button)
        
        # Status area
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        
        status_layout.addWidget(self.status_log)
        status_group.setLayout(status_layout)
        
        # Add all components to main layout
        layout.addWidget(settings_group)
        layout.addLayout(control_layout)
        layout.addWidget(status_group)
        
        self.setLayout(layout)
        
    def browse_file(self):
        """Open file dialog to select save location"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV File", "", "CSV Files (*.csv);;All Files (*.*)"
        )
        
        if file_path:
            self.file_path.setText(file_path)
            self.export_button.setEnabled(True)
            self.log_message(f"Selected save location: {file_path}")
            
    def start_export(self):
        """Start the export process"""
        if not self.file_path.text():
            QMessageBox.warning(self, "Warning", "Please select a save location.")
            return
            
        self.export_button.setEnabled(False)
        self.log_message("Starting export...")
        
        # Create and start worker thread
        self.export_worker = ExportWorker(
            self.db_manager,
            self.file_path.text(),
            self.include_html_checkbox.isChecked(),
            self.apply_overrides_checkbox.isChecked()
        )
        
        # Connect signals
        self.export_worker.status_updated.connect(self.log_message)
        self.export_worker.export_finished.connect(self.export_finished)
        
        # Start export
        self.export_worker.start()
        
    def log_message(self, message):
        """Add message to status log"""
        self.status_log.append(message)
        
    def export_finished(self, success, message):
        """Handle export completion"""
        self.export_button.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Export Complete", message)
        else:
            QMessageBox.critical(self, "Export Failed", message)
