"""
Export Worker Module for handling CSV export in a background thread
"""
from PyQt5.QtCore import QThread, pyqtSignal
from core.property_manager import PropertyManager

class ExportWorker(QThread):
    """Worker thread for CSV export"""
    status_updated = pyqtSignal(str)
    export_finished = pyqtSignal(bool, str)
    
    def __init__(self, db_manager, output_file, include_html=True, apply_overrides=True):
        super().__init__()
        self.db_manager = db_manager
        self.output_file = output_file
        self.include_html = include_html
        self.apply_overrides = apply_overrides
        self.export_data = []
        
    def run(self):
        try:
            self.status_updated.emit(f"Exporting data to: {self.output_file}")
            
            # Apply property overrides if requested
            if self.apply_overrides:
                self._apply_property_overrides()
            
            # Export products to CSV
            count = self.db_manager.export_products_csv(self.output_file, self.include_html)
            
            self.status_updated.emit(f"Export completed successfully! {count} products exported.")
            self.export_finished.emit(True, f"Successfully exported {count} products")
            
        except Exception as e:
            self.status_updated.emit(f"Error during export: {str(e)}")
            self.export_finished.emit(False, f"Export failed: {str(e)}")
    
    def _apply_property_overrides(self):
        """
        Apply property overrides to the export data.
        """
        self.status_updated.emit("Applying property overrides...")
        
        property_manager = PropertyManager(self.db_manager)
        
        # For each product apply overrides
        for product in self.export_data:
            article_id = product['article_id']
            
            # Convert properties to standardized format
            properties = {}
            for key, value in product.items():
                if key.startswith('prop_'):
                    prop_name = key[5:]  # Remove 'prop_'
                    # Extract language code if present
                    if '.' in prop_name:
                        base_name, lang = prop_name.rsplit('.', 1)
                        properties[(base_name, lang)] = value
                    else:
                        # Treat as German property by default
                        properties[(prop_name, 'de')] = value
            
            # Apply overrides
            overridden_properties = property_manager.apply_overrides(article_id, properties)
            
            # Write overridden values back to product dictionary
            for (prop_name, lang), value in overridden_properties.items():
                if lang:
                    key = f"prop_{prop_name}.{lang}"
                else:
                    key = f"prop_{prop_name}"
                product[key] = value
        
        self.status_updated.emit("Overrides successfully applied.")
