"""
Main Window Module for the application
"""
from PyQt5.QtWidgets import QMainWindow, QTabWidget
from PyQt5.QtCore import Qt
from core.database_manager import DatabaseManager
from ui.import_tab import ImportTab
from ui.data_view_tab import DataViewTab
from ui.export_tab import ExportTab

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager('product_data.db')
        self.init_ui()
        
    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("Product Data Extractor")
        self.setGeometry(100, 100, 800, 600)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.import_tab = ImportTab(self.db_manager)
        self.data_view_tab = DataViewTab(self.db_manager)
        self.export_tab = ExportTab(self.db_manager)
        
        # Add tabs to widget
        self.tab_widget.addTab(self.import_tab, "Import")
        self.tab_widget.addTab(self.data_view_tab, "Data View")
        self.tab_widget.addTab(self.export_tab, "Export")
        
        # Set central widget
        self.setCentralWidget(self.tab_widget)
        
        # Initialize database
        self.db_manager.initialize_database()
        
        # Show window
        self.show()
