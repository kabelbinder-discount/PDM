"""
Data View Tab Module for viewing and editing product data
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
                            QTableWidgetItem, QGroupBox, QComboBox, QLabel, QMessageBox,
                            QDialog, QFormLayout, QLineEdit)
from PyQt5.QtCore import Qt
from core.property_manager import PropertyManager

class PropertyEditDialog(QDialog):
    """Dialog for editing property values"""
    
    def __init__(self, article_id, prop_name, prop_value, prop_unit, language, parent=None):
        super().__init__(parent)
        self.article_id = article_id
        self.prop_name = prop_name
        self.language = language
        
        self.setWindowTitle(f"Edit Property: {prop_name}")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        # Property name (read-only)
        self.name_edit = QLineEdit(prop_name)
        self.name_edit.setReadOnly(True)
        form_layout.addRow("Property Name:", self.name_edit)
        
        # Property value
        self.value_edit = QLineEdit(str(prop_value) if prop_value is not None else "")
        form_layout.addRow("Value:", self.value_edit)
        
        # Property unit
        self.unit_edit = QLineEdit(str(prop_unit) if prop_unit else "")
        form_layout.addRow("Unit:", self.unit_edit)
        
        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItems(["de", "en"])
        self.language_combo.setCurrentText(language)
        form_layout.addRow("Language:", self.language_combo)
        
        # Add buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_values(self):
        """Get the edited values"""
        return {
            'value': self.value_edit.text(),
            'unit': self.unit_edit.text() if self.unit_edit.text() else None,
            'language': self.language_combo.currentText()
        }

class DataViewTab(QWidget):
    """Tab for viewing and editing product data"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.property_manager = PropertyManager(db_manager)
        self.init_ui()
        
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout()
        
        # Filter area
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories", None)
        self.category_combo.currentIndexChanged.connect(self.filter_products_by_category)
        filter_layout.addWidget(self.category_combo)
        
        # Product list
        list_group = QGroupBox("Products")
        list_layout = QVBoxLayout()
        
        self.product_table = QTableWidget()
        self.product_table.setColumnCount(5)
        self.product_table.setHorizontalHeaderLabels(["Article ID", "Name", "Price", "Stock", "Category"])
        self.product_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SingleSelection)
        self.product_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.product_table.selectionModel().selectionChanged.connect(self.load_properties)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.load_products)
        
        list_layout.addWidget(self.product_table)
        list_layout.addWidget(refresh_button)
        list_group.setLayout(list_layout)
        
        # Property view
        property_group = QGroupBox("Properties")
        property_layout = QVBoxLayout()
        
        self.property_table = QTableWidget()
        self.property_table.setColumnCount(4)
        self.property_table.setHorizontalHeaderLabels(["Property", "Value", "Unit", "Language"])
        self.property_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.property_table.setSelectionMode(QTableWidget.SingleSelection)
        self.property_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        property_button_layout = QHBoxLayout()
        edit_button = QPushButton("Edit Property")
        edit_button.clicked.connect(self.edit_property)
        add_override_button = QPushButton("Add Override")
        add_override_button.clicked.connect(self.add_property_override)
        
        property_button_layout.addWidget(edit_button)
        property_button_layout.addWidget(add_override_button)
        
        property_layout.addWidget(self.property_table)
        property_layout.addLayout(property_button_layout)
        property_group.setLayout(property_layout)
        
        # Add components to main layout
        layout.addLayout(filter_layout)
        layout.addWidget(list_group, 1)
        layout.addWidget(property_group, 1)
        
        self.setLayout(layout)
        
    def showEvent(self, event):
        """Called when tab is shown"""
        super().showEvent(event)
        self.load_products()
        self.load_categories()
        
    def load_products(self, category=None):
        """Load products from database, optionally filtered by category"""
        if category:
            products = self.db_manager.get_products_by_category(category)
        else:
            products = self.db_manager.get_all_products()
        
        self.product_table.setRowCount(len(products))
        
        for row, product in enumerate(products):
            article_id, name, price, stock, category = product
            
            self.product_table.setItem(row, 0, QTableWidgetItem(str(article_id)))
            self.product_table.setItem(row, 1, QTableWidgetItem(str(name) if name else ""))
            self.product_table.setItem(row, 2, QTableWidgetItem(str(price) if price else ""))
            self.product_table.setItem(row, 3, QTableWidgetItem(str(stock) if stock else ""))
            self.product_table.setItem(row, 4, QTableWidgetItem(str(category) if category else ""))
            
        self.product_table.resizeColumnsToContents()
        
    def load_categories(self):
        """Load unique categories for filter dropdown"""
        # Clear existing items except "All Categories"
        while self.category_combo.count() > 1:
            self.category_combo.removeItem(1)
            
        # Get all products to extract unique categories
        products = self.db_manager.get_all_products()
        categories = set()
        
        for product in products:
            category = product[4]  # Category is the 5th column (index 4)
            if category:
                categories.add(category)
                
        # Add categories to combo box
        for category in sorted(categories):
            self.category_combo.addItem(category, category)
            
    def filter_products_by_category(self):
        """Filter product list by selected category"""
        category = self.category_combo.currentData()
        if category:
            self.load_products(category)
        else:
            self.load_products()
        
    def load_properties(self):
        """Load properties for selected product"""
        selected_rows = self.product_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        article_id = self.product_table.item(row, 0).text()
        
        # Get properties with overrides applied
        properties = self.property_manager.get_properties_for_product(article_id)
        
        # Combine all properties for display
        all_properties = []
        for lang, props in properties.items():
            for prop_name, prop_value in props.items():
                # Try to extract unit if present
                unit = None
                if isinstance(prop_value, str) and " " in prop_value:
                    value_parts = prop_value.rsplit(" ", 1)
                    if len(value_parts) == 2 and value_parts[1] in ["mm", "cm", "m", "g", "kg", "°C", "V", "A"]:
                        prop_value = value_parts[0]
                        unit = value_parts[1]
                        
                all_properties.append((prop_name, prop_value, unit, lang))
                
        # Sort properties by name
        all_properties.sort(key=lambda x: x[0])
        
        # Display in table
        self.property_table.setRowCount(len(all_properties))
        
        for row, prop in enumerate(all_properties):
            property_name, property_value, property_unit, language = prop
            
            self.property_table.setItem(row, 0, QTableWidgetItem(str(property_name)))
            self.property_table.setItem(row, 1, QTableWidgetItem(str(property_value)))
            self.property_table.setItem(row, 2, QTableWidgetItem(str(property_unit) if property_unit else ""))
            self.property_table.setItem(row, 3, QTableWidgetItem(str(language)))
            
        self.property_table.resizeColumnsToContents()
        
    def edit_property(self):
        """Edit the selected property"""
        selected_rows = self.product_table.selectionModel().selectedRows()
        property_rows = self.property_table.selectionModel().selectedRows()
        
        if not selected_rows or not property_rows:
            QMessageBox.warning(self, "Warning", "Please select a product and a property to edit.")
            return
            
        product_row = selected_rows[0].row()
        property_row = property_rows[0].row()
        
        article_id = self.product_table.item(product_row, 0).text()
        prop_name = self.property_table.item(property_row, 0).text()
        prop_value = self.property_table.item(property_row, 1).text()
        prop_unit = self.property_table.item(property_row, 2).text()
        language = self.property_table.item(property_row, 3).text()
        
        # Open edit dialog
        dialog = PropertyEditDialog(article_id, prop_name, prop_value, prop_unit, language, self)
        
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            
            # Store updated property
            self.db_manager.store_property(
                article_id,
                prop_name,
                values['value'],
                values['unit'],
                values['language']
            )
            
            # Refresh properties
            self.load_properties()
            
    def add_property_override(self):
        """Add an override for the selected property"""
        selected_rows = self.product_table.selectionModel().selectedRows()
        property_rows = self.property_table.selectionModel().selectedRows()
        
        if not selected_rows or not property_rows:
            QMessageBox.warning(self, "Warning", "Please select a product and a property to override.")
            return
            
        product_row = selected_rows[0].row()
        property_row = property_rows[0].row()
        
        article_id = self.product_table.item(product_row, 0).text()
        prop_name = self.property_table.item(property_row, 0).text()
        prop_value = self.property_table.item(property_row, 1).text()
        language = self.property_table.item(property_row, 3).text()
        
        # Create dialog for override value
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Add Override for {prop_name}")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout()
        
        form = QFormLayout()
        value_edit = QLineEdit(prop_value)
        form.addRow("Override Value:", value_edit)
        
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(form)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        save_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        if dialog.exec_() == QDialog.Accepted:
            override_value = value_edit.text()
            
            # Store override
            self.db_manager.store_property_override(article_id, prop_name, override_value, language)
            
            # Refresh properties
            self.load_properties()
            QMessageBox.information(self, "Override Added", f"Override for {prop_name} has been added.")
