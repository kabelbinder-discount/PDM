"""
Product Data Extractor - Main Application File
"""
import sys
import os
import pandas as pd
from bs4 import BeautifulSoup
import sqlite3
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QFileDialog, QLabel, QTableWidget, 
                           QTableWidgetItem, QProgressBar, QTextEdit, QMessageBox,
                           QComboBox, QLineEdit, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class HTMLParser:
    """Class to handle HTML parsing for product descriptions"""
    
    def parse_html_table(self, html_content):
        """Parse HTML tables from product descriptions"""
        soup = BeautifulSoup(html_content, 'html.parser')
        properties = {}
        
        # Find tables in the HTML
        tables = soup.find_all('table')
        
        # If no tables found directly, look for table rows which might be in a div
        if not tables:
            rows = soup.find_all('tr')
            if rows:
                # Create a virtual table
                properties = self._parse_rows(rows)
        else:
            # Process each table
            for table in tables:
                rows = table.find_all('tr')
                table_properties = self._parse_rows(rows)
                properties.update(table_properties)
                
        # Look for properties outside tables (sometimes they appear as key-value pairs in divs or paragraphs)
        property_patterns = [
            r'(\w+):\s*([^<]+)', 
            r'<strong>([^<]+)</strong>\s*([^<]+)'
        ]
        
        for pattern in property_patterns:
            matches = re.findall(pattern, str(soup))
            for match in matches:
                property_name = match[0].strip()
                property_value = match[1].strip()
                if property_name and property_value and property_name not in properties:
                    properties[property_name] = property_value
        
        return properties
    
    def _parse_rows(self, rows):
        """Parse table rows into property key-value pairs"""
        properties = {}
        
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                # First cell is usually property name
                property_name = cells[0].get_text().strip()
                # Second cell is usually property value
                property_value = cells[1].get_text().strip()
                
                # Clean up property name (remove colon if present)
                property_name = property_name.rstrip(':')
                
                # Store property if not empty
                if property_name and property_value:
                    properties[property_name] = property_value
                    
        return properties
    
    def normalize_property(self, property_name, property_value, language='de'):
        """Normalize property names and values"""
        # Map common German property names to standardized names
        de_to_standard = {
            'Farbe': 'color',
            'Material': 'material',
            'Zugkraft': 'tensile_strength',
            'Max. Bündeldurchmesser': 'max_bundle_diameter',
            'Min. Bündeldurchmesser': 'min_bundle_diameter',
            'Temperaturbeständigkeit': 'temperature_resistance',
            'Min. Installationstemperatur': 'min_installation_temperature',
            'Zulassungen': 'certifications',
            'Verpackungseinheit': 'packaging_unit',
            'Isolationsmaterial': 'insulation_material',
            'Werkstoff des Leiters': 'conductor_material',
            'Länge': 'length',
            'Nenngröße': 'nominal_size',
            'Kabelquerschnitt': 'cable_cross_section'
            # Add more mappings as needed
        }
        
        # Normalize property name
        if language == 'de':
            standard_name = de_to_standard.get(property_name, property_name.lower().replace(' ', '_'))
        else:
            # For English, just convert to lowercase with underscores
            standard_name = property_name.lower().replace(' ', '_')
        
        # Process value based on property type
        normalized_value = property_value
        unit = None
        
        # Extract units for numeric properties
        if standard_name in ['tensile_strength', 'max_bundle_diameter', 'min_bundle_diameter', 'length']:
            # Extract number and unit
            match = re.search(r'(\d+(?:[,.]\d+)?)\s*(\w+)?', property_value)
            if match:
                numeric_value = match.group(1).replace(',', '.')
                try:
                    normalized_value = float(numeric_value)
                    if match.group(2):
                        unit = match.group(2)
                except ValueError:
                    # Keep original if conversion fails
                    pass
        
        # Special handling for temperature ranges
        elif standard_name == 'temperature_resistance':
            match = re.search(r'(-?\d+)\s*°C\s*bis\s*(\+?\d+)\s*°C', property_value)
            if match:
                min_temp, max_temp = match.group(1), match.group(2)
                normalized_value = f"{min_temp} to {max_temp}"
                unit = "°C"
        
        return standard_name, normalized_value, unit

class DatabaseManager:
    """Class to handle database operations"""
    
    def __init__(self, db_path='product_data.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            
    def initialize_database(self):
        """Create database schema if not exists"""
        self.connect()
        
        # Create Products table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS Products (
            article_id TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            stock INTEGER
        )
        ''')
        
        # Create Properties table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS Properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id TEXT,
            property_name TEXT,
            property_value TEXT,
            property_unit TEXT,
            language TEXT,
            FOREIGN KEY (article_id) REFERENCES Products(article_id)
        )
        ''')
        
        # Create PropertyDefinitions table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS PropertyDefinitions (
            property_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_de TEXT,
            name_en TEXT,
            data_type TEXT,
            expected_unit TEXT
        )
        ''')
        
        self.conn.commit()
        self.close()
        
    def store_product(self, article_id, name=None, price=None, stock=None):
        """Store or update product information"""
        self.connect()
        
        # Check if product exists
        self.cursor.execute('SELECT article_id FROM Products WHERE article_id = ?', (article_id,))
        exists = self.cursor.fetchone()
        
        if exists:
            # Update existing product
            query = 'UPDATE Products SET '
            params = []
            
            if name is not None:
                query += 'name = ?, '
                params.append(name)
            
            if price is not None:
                query += 'price = ?, '
                params.append(price)
                
            if stock is not None:
                query += 'stock = ?, '
                params.append(stock)
                
            # Remove last comma and space
            query = query.rstrip(', ')
            
            query += ' WHERE article_id = ?'
            params.append(article_id)
            
            self.cursor.execute(query, params)
        else:
            # Insert new product
            self.cursor.execute(
                'INSERT INTO Products (article_id, name, price, stock) VALUES (?, ?, ?, ?)',
                (article_id, name, price, stock)
            )
            
        self.conn.commit()
        self.close()
        
    def store_property(self, article_id, property_name, property_value, property_unit=None, language='de'):
        """Store product property"""
        self.connect()
        
        # Check if property exists
        self.cursor.execute(
            'SELECT id FROM Properties WHERE article_id = ? AND property_name = ? AND language = ?', 
            (article_id, property_name, language)
        )
        property_id = self.cursor.fetchone()
        
        if property_id:
            # Update existing property
            self.cursor.execute(
                'UPDATE Properties SET property_value = ?, property_unit = ? WHERE id = ?',
                (property_value, property_unit, property_id[0])
            )
        else:
            # Insert new property
            self.cursor.execute(
                'INSERT INTO Properties (article_id, property_name, property_value, property_unit, language) VALUES (?, ?, ?, ?, ?)',
                (article_id, property_name, property_value, property_unit, language)
            )
            
        self.conn.commit()
        self.close()
        
    def get_all_products(self):
        """Get all products from database"""
        self.connect()
        self.cursor.execute('SELECT * FROM Products')
        products = self.cursor.fetchall()
        self.close()
        return products
    
    def get_product_properties(self, article_id):
        """Get properties for a specific product"""
        self.connect()
        self.cursor.execute('SELECT property_name, property_value, property_unit, language FROM Properties WHERE article_id = ?', (article_id,))
        properties = self.cursor.fetchall()
        self.close()
        return properties
    
    def export_products_csv(self, output_file, include_html=True):
        """Export products to CSV format for shop import"""
        self.connect()
        
        # Get all products
        self.cursor.execute('SELECT article_id, name, price, stock FROM Products')
        products = self.cursor.fetchall()
        
        # Create DataFrame for export
        export_data = []
        
        for product in products:
            article_id, name, price, stock = product
            
            # Get properties for this product
            self.cursor.execute(
                'SELECT property_name, property_value, property_unit, language FROM Properties WHERE article_id = ?', 
                (article_id,)
            )
            properties = self.cursor.fetchall()
            
            # Organize properties by language
            de_properties = {}
            en_properties = {}
            
            for prop in properties:
                prop_name, prop_value, prop_unit, lang = prop
                if lang == 'de':
                    if prop_unit:
                        de_properties[prop_name] = f"{prop_value} {prop_unit}"
                    else:
                        de_properties[prop_name] = prop_value
                elif lang == 'en':
                    if prop_unit:
                        en_properties[prop_name] = f"{prop_value} {prop_unit}"
                    else:
                        en_properties[prop_name] = prop_value
            
            # Build HTML content if requested
            p_desc_de = ""
            p_desc_en = ""
            
            if include_html:
                # Generate HTML table for German description
                p_desc_de = "<table>"
                for prop_name, prop_value in de_properties.items():
                    p_desc_de += f"<tr><td>{prop_name}</td><td>{prop_value}</td></tr>"
                p_desc_de += "</table>"
                
                # Generate HTML table for English description
                p_desc_en = "<table>"
                for prop_name, prop_value in en_properties.items():
                    p_desc_en += f"<tr><td>{prop_name}</td><td>{prop_value}</td></tr>"
                p_desc_en += "</table>"
            
            # Create row for this product
            product_row = {
                'article_id': article_id,
                'name': name,
                'price': price,
                'stock': stock,
                'p_desc.de': p_desc_de,
                'p_desc.en': p_desc_en
            }
            
            # Add individual properties
            for prop_name, prop_value in de_properties.items():
                product_row[f"prop_{prop_name}"] = prop_value
                
            export_data.append(product_row)
        
        self.close()
        
        # Create DataFrame and export to CSV
        df = pd.DataFrame(export_data)
        df.to_csv(output_file, index=False, encoding='iso-8859-1', sep=';')
        
        return len(export_data)

class ImportWorker(QThread):
    """Worker thread for CSV import and processing"""
    progress_updated = pyqtSignal(int, int)
    status_updated = pyqtSignal(str)
    import_finished = pyqtSignal(bool, str)
    
    def __init__(self, csv_file, encoding='iso-8859-1'):
        super().__init__()
        self.csv_file = csv_file
        self.encoding = encoding
        self.html_parser = HTMLParser()
        self.db_manager = DatabaseManager()
        
    def run(self):
        try:
            self.status_updated.emit("Initializing database...")
            self.db_manager.initialize_database()
            
            self.status_updated.emit(f"Reading CSV file: {self.csv_file}")
            df = pd.read_csv(self.csv_file, encoding=self.encoding, sep=';')
            
            total_rows = len(df)
            self.status_updated.emit(f"Found {total_rows} products to process")
            
            # Check if required columns exist
            if 'p_desc.de' not in df.columns and 'p_desc.en' not in df.columns:
                self.import_finished.emit(False, "Error: Neither p_desc.de nor p_desc.en columns found in CSV")
                return
                
            # Get article ID column name (might be XTINR, XTSOL, p_model, etc.)
            article_id_column = None
            for col in ['XTINR', 'XTSOL', 'p_model', 'article_id']:
                if col in df.columns:
                    article_id_column = col
                    break
                    
            if not article_id_column:
                self.import_finished.emit(False, "Error: Could not identify article ID column")
                return
                
            # Process each row
            for index, row in df.iterrows():
                # Update progress
                self.progress_updated.emit(index + 1, total_rows)
                
                article_id = row[article_id_column]
                self.status_updated.emit(f"Processing article {article_id}")
                
                # Store basic product info
                name = row.get('p_name', None)
                price = row.get('p_price', row.get('p_priceNoTax', None))
                stock = row.get('p_stock', None)
                
                # Store product in database
                self.db_manager.store_product(article_id, name, price, stock)
                
                # Process German description if available
                if 'p_desc.de' in df.columns and pd.notna(row['p_desc.de']):
                    html_content = row['p_desc.de']
                    properties = self.html_parser.parse_html_table(html_content)
                    
                    for prop_name, prop_value in properties.items():
                        # Normalize property
                        std_name, std_value, unit = self.html_parser.normalize_property(prop_name, prop_value, 'de')
                        # Store property
                        self.db_manager.store_property(article_id, std_name, std_value, unit, 'de')
                
                # Process English description if available
                if 'p_desc.en' in df.columns and pd.notna(row['p_desc.en']):
                    html_content = row['p_desc.en']
                    properties = self.html_parser.parse_html_table(html_content)
                    
                    for prop_name, prop_value in properties.items():
                        # Normalize property
                        std_name, std_value, unit = self.html_parser.normalize_property(prop_name, prop_value, 'en')
                        # Store property
                        self.db_manager.store_property(article_id, std_name, std_value, unit, 'en')
            
            self.status_updated.emit("Import completed successfully!")
            self.import_finished.emit(True, f"Successfully imported {total_rows} products")
            
        except Exception as e:
            self.status_updated.emit(f"Error during import: {str(e)}")
            self.import_finished.emit(False, f"Import failed: {str(e)}")

class ExportWorker(QThread):
    """Worker thread for CSV export"""
    status_updated = pyqtSignal(str)
    export_finished = pyqtSignal(bool, str)
    
    def __init__(self, output_file, include_html=True):
        super().__init__()
        self.output_file = output_file
        self.include_html = include_html
        self.db_manager = DatabaseManager()
        
    def run(self):
        try:
            self.status_updated.emit(f"Exporting data to: {self.output_file}")
            
            # Export products to CSV
            count = self.db_manager.export_products_csv(self.output_file, self.include_html)
            
            self.status_updated.emit(f"Export completed successfully! {count} products exported.")
            self.export_finished.emit(True, f"Successfully exported {count} products")
            
        except Exception as e:
            self.status_updated.emit(f"Error during export: {str(e)}")
            self.export_finished.emit(False, f"Export failed: {str(e)}")

class ImportTab(QWidget):
    """Tab for importing CSV files"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.import_worker = None
        
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # File selection area
        file_group = QGroupBox("CSV Datei")
        file_layout = QFormLayout()
        
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse_button = QPushButton("Durchsuchen...")
        browse_button.clicked.connect(self.browse_file)
        
        file_button_layout = QHBoxLayout()
        file_button_layout.addWidget(self.file_path)
        file_button_layout.addWidget(browse_button)
        
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["iso-8859-1", "utf-8", "utf-16", "cp1252"])
        
        file_layout.addRow("Datei:", file_button_layout)
        file_layout.addRow("Kodierung:", self.encoding_combo)
        file_group.setLayout(file_layout)
        
        # Import controls
        control_layout = QHBoxLayout()
        self.import_button = QPushButton("Importieren")
        self.import_button.clicked.connect(self.start_import)
        self.import_button.setEnabled(False)
        control_layout.addWidget(self.import_button)
        
        # Progress area
        progress_group = QGroupBox("Fortschritt")
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
            self, "CSV Datei öffnen", "", "CSV Dateien (*.csv);;Alle Dateien (*.*)"
        )
        
        if file_path:
            self.file_path.setText(file_path)
            self.import_button.setEnabled(True)
            self.log_message(f"Datei ausgewählt: {file_path}")
            
    def start_import(self):
        """Start the import process"""
        if not self.file_path.text():
            QMessageBox.warning(self, "Warnung", "Bitte wählen Sie eine CSV Datei aus.")
            return
            
        self.import_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_message("Import wird gestartet...")
        
        # Create and start worker thread
        self.import_worker = ImportWorker(
            self.file_path.text(),
            self.encoding_combo.currentText()
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
            QMessageBox.information(self, "Import abgeschlossen", message)
        else:
            QMessageBox.critical(self, "Import fehlgeschlagen", message)

class DataViewTab(QWidget):
    """Tab for viewing and editing product data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.db_manager = DatabaseManager()
        
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # Product list
        list_group = QGroupBox("Produkte")
        list_layout = QVBoxLayout()
        
        self.product_table = QTableWidget()
        self.product_table.setColumnCount(4)
        self.product_table.setHorizontalHeaderLabels(["Artikel-ID", "Name", "Preis", "Bestand"])
        self.product_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SingleSelection)
        self.product_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.product_table.selectionModel().selectionChanged.connect(self.load_properties)
        
        refresh_button = QPushButton("Aktualisieren")
        refresh_button.clicked.connect(self.load_products)
        
        list_layout.addWidget(self.product_table)
        list_layout.addWidget(refresh_button)
        list_group.setLayout(list_layout)
        
        # Property view
        property_group = QGroupBox("Eigenschaften")
        property_layout = QVBoxLayout()
        
        self.property_table = QTableWidget()
        self.property_table.setColumnCount(4)
        self.property_table.setHorizontalHeaderLabels(["Eigenschaft", "Wert", "Einheit", "Sprache"])
        
        property_layout.addWidget(self.property_table)
        property_group.setLayout(property_layout)
        
        # Add components to main layout
        layout.addWidget(list_group, 1)
        layout.addWidget(property_group, 1)
        
        self.setLayout(layout)
        
    def showEvent(self, event):
        """Called when tab is shown"""
        super().showEvent(event)
        self.load_products()
        
    def load_products(self):
        """Load products from database"""
        products = self.db_manager.get_all_products()
        
        self.product_table.setRowCount(len(products))
        
        for row, product in enumerate(products):
            article_id, name, price, stock = product
            
            self.product_table.setItem(row, 0, QTableWidgetItem(str(article_id)))
            self.product_table.setItem(row, 1, QTableWidgetItem(str(name) if name else ""))
            self.product_table.setItem(row, 2, QTableWidgetItem(str(price) if price else ""))
            self.product_table.setItem(row, 3, QTableWidgetItem(str(stock) if stock else ""))
            
        self.product_table.resizeColumnsToContents()
        
    def load_properties(self):
        """Load properties for selected product"""
        selected_rows = self.product_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        article_id = self.product_table.item(row, 0).text()
        
        properties = self.db_manager.get_product_properties(article_id)
        
        self.property_table.setRowCount(len(properties))
        
        for row, prop in enumerate(properties):
            property_name, property_value, property_unit, language = prop
            
            self.property_table.setItem(row, 0, QTableWidgetItem(str(property_name)))
            self.property_table.setItem(row, 1, QTableWidgetItem(str(property_value)))
            self.property_table.setItem(row, 2, QTableWidgetItem(str(property_unit) if property_unit else ""))
            self.property_table.setItem(row, 3, QTableWidgetItem(str(language)))
            
        self.property_table.resizeColumnsToContents()

class ExportTab(QWidget):
    """Tab for exporting data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.export_worker = None
        
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # Export settings
        settings_group = QGroupBox("Export Einstellungen")
        settings_layout = QFormLayout()
        
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse_button = QPushButton("Speichern unter...")
        browse_button.clicked.connect(self.browse_file)
        
        file_button_layout = QHBoxLayout()
        file_button_layout.addWidget(self.file_path)
        file_button_layout.addWidget(browse_button)
        
        self.include_html_checkbox = QComboBox()
        self.include_html_checkbox.addItems(["Ja, HTML-Tabellen generieren", "Nein, nur Daten exportieren"])
        
        settings_layout.addRow("Datei:", file_button_layout)
        settings_layout.addRow("HTML generieren:", self.include_html_checkbox)
        settings_group.setLayout(settings_layout)
        
        # Export controls
        control_layout = QHBoxLayout()
        self.export_button = QPushButton("Exportieren")
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
            self, "CSV Datei speichern", "", "CSV Dateien (*.csv);;Alle Dateien (*.*)"
        )
        
        if file_path:
            self.file_path.setText(file_path)
            self.export_button.setEnabled(True)
            self.log_message(f"Speicherort ausgewählt: {file_path}")
            
    def start_export(self):
        """Start the export process"""
        if not self.file_path.text():
            QMessageBox.warning(self, "Warnung", "Bitte wählen Sie einen Speicherort aus.")
            return
            
        self.export_button.setEnabled(False)
        self.log_message("Export wird gestartet...")
        
        # Create and start worker thread
        include_html = self.include_html_checkbox.currentIndex() == 0
        self.export_worker = ExportWorker(
            self.file_path.text(),
            include_html
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
            QMessageBox.information(self, "Export abgeschlossen", message)
        else:
            QMessageBox.critical(self, "Export fehlgeschlagen", message)

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("Produkt Daten Extraktor")
        self.setGeometry(100, 100, 800, 600)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.import_tab = ImportTab()
        self.data_view_tab = DataViewTab()
        self.export_tab = ExportTab()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.import_tab, "Import")
        self.tab_widget.addTab(self.data_view_tab, "Daten Ansicht")
        self.tab_widget.addTab(self.export_tab, "Export")
        
        # Set central widget
        self.setCentralWidget(self.tab_widget)
        
        # Show window
        self.show()

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()