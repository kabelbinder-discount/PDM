"""
Import Worker Module for handling CSV import in a background thread
"""
import pandas as pd
import traceback
from PyQt5.QtCore import QThread, pyqtSignal
from core.html_parser import HTMLParser
from core.attribute_mapper import AttributeMapper

class ImportWorker(QThread):
    """Worker thread for CSV import and processing"""
    progress_updated = pyqtSignal(int, int)
    status_updated = pyqtSignal(str)
    import_finished = pyqtSignal(bool, str)
    
    def __init__(self, db_manager, csv_file, encoding='iso-8859-1', detect_new_properties=True):
        super().__init__()
        self.db_manager = db_manager
        self.csv_file = csv_file
        self.encoding = encoding
        self.detect_new_properties = detect_new_properties
        self.html_parser = HTMLParser()
        self.attribute_mapper = AttributeMapper(db_manager)
        self.df = None
        
    def run(self):
        try:
            self.status_updated.emit("Initializing database...")
            self.db_manager.initialize_database()
            
            self.status_updated.emit(f"Reading CSV file: {self.csv_file}")
            try:
                self.df = pd.read_csv(self.csv_file, encoding=self.encoding, sep=';', error_bad_lines=False)
                self.status_updated.emit(f"Successfully read CSV file with {len(self.df)} rows")
            except Exception as e:
                self.status_updated.emit(f"Error reading CSV: {str(e)}")
                self.import_finished.emit(False, f"Failed to read CSV: {str(e)}")
                return
            
            total_rows = len(self.df)
            self.status_updated.emit(f"Found {total_rows} products to process")
            
            # Check if required columns exist
            if 'p_desc.de' not in self.df.columns and 'p_desc.en' not in self.df.columns:
                self.import_finished.emit(False, "Error: Neither p_desc.de nor p_desc.en columns found in CSV")
                return
                
            # Get article ID column name, ignoring XTSOL as it's just a placeholder
            article_id_column = None
            for col in ['p_model', 'article_id', 'XTINR']:
                if col in self.df.columns:
                    article_id_column = col
                    break
                    
            if not article_id_column:
                self.status_updated.emit("Warning: Could not identify standard article ID column. Attempting to use first non-XTSOL column.")
                # Try to use the first column that is not XTSOL as article ID
                for col in self.df.columns:
                    if col != 'XTSOL':
                        article_id_column = col
                        self.status_updated.emit(f"Using '{col}' as article ID column")
                        break
            
            if not article_id_column:
                self.import_finished.emit(False, "Error: Could not identify any usable article ID column")
                return
            
            # Detect and register new properties if enabled
            if self.detect_new_properties:
                try:
                    self._detect_and_register_new_properties()
                except Exception as e:
                    self.status_updated.emit(f"Warning: Error detecting new properties: {str(e)}")
                    # Continue with import even if property detection fails
            
            # Process each row
            for index, row in self.df.iterrows():
                try:
                    # Update progress
                    self.progress_updated.emit(index + 1, total_rows)
                    
                    if article_id_column not in row or pd.isna(row[article_id_column]):
                        self.status_updated.emit(f"Skipping row {index+1}: Missing article ID")
                        continue
                    
                    article_id = row[article_id_column]
                    self.status_updated.emit(f"Processing article {article_id}")
                    
                    # Store basic product info
                    name = row.get('p_name', None)
                    price = row.get('p_price', row.get('p_priceNoTax', None))
                    stock = row.get('p_stock', None)
                    category = row.get('p_category', row.get('category', None))
                    
                    # Store product in database
                    self.db_manager.store_product(article_id, name, price, stock, category)
                    
                    # Process German description if available
                    if 'p_desc.de' in self.df.columns and pd.notna(row['p_desc.de']):
                        try:
                            html_content = str(row['p_desc.de'])
                            properties = self.html_parser.parse_html_table(html_content)
                            
                            for prop_name, prop_value in properties.items():
                                # Apply attribute mapping
                                mapped_name = self.attribute_mapper.get_standard_name(prop_name, 'de')
                                
                                # Normalize property
                                std_name, std_value, unit = self.html_parser.normalize_property(mapped_name, prop_value, 'de')
                                
                                # Store property
                                self.db_manager.store_property(article_id, std_name, std_value, unit, 'de')
                        except Exception as e:
                            self.status_updated.emit(f"Error processing German description for {article_id}: {str(e)}")
                    
                    # Process English description if available
                    if 'p_desc.en' in self.df.columns and pd.notna(row['p_desc.en']):
                        try:
                            html_content = str(row['p_desc.en'])
                            properties = self.html_parser.parse_html_table(html_content)
                            
                            for prop_name, prop_value in properties.items():
                                # Apply attribute mapping
                                mapped_name = self.attribute_mapper.get_standard_name(prop_name, 'en')
                                
                                # Normalize property
                                std_name, std_value, unit = self.html_parser.normalize_property(mapped_name, prop_value, 'en')
                                
                                # Store property
                                self.db_manager.store_property(article_id, std_name, std_value, unit, 'en')
                        except Exception as e:
                            self.status_updated.emit(f"Error processing English description for {article_id}: {str(e)}")
                
                except Exception as e:
                    self.status_updated.emit(f"Error processing row {index+1}: {str(e)}")
                    # Continue with next row instead of aborting the entire import
            
            self.status_updated.emit("Import completed successfully!")
            self.import_finished.emit(True, f"Successfully imported {total_rows} products")
            
        except Exception as e:
            error_details = traceback.format_exc()
            self.status_updated.emit(f"Error during import: {str(e)}")
            self.status_updated.emit(f"Error details: {error_details}")
            self.import_finished.emit(False, f"Import failed: {str(e)}")
    
    def _detect_and_register_new_properties(self):
        """
        Detect new properties in the CSV file and register them in the database.
        """
        self.status_updated.emit("Detecting new properties...")
        
        # Load known properties
        known_properties = []
        for name_de, name_en, _, _ in self.db_manager.get_property_definitions():
            if name_de:
                known_properties.append(name_de)
            if name_en:
                known_properties.append(name_en)
        
        # Scan HTML contents for new properties
        new_properties = set()
        total_rows = len(self.df)
        
        # Process a sample of rows to improve performance
        sample_size = min(100, total_rows)
        sample_indices = list(range(0, total_rows, max(1, total_rows // sample_size)))
        
        for i, index in enumerate(sample_indices):
            row = self.df.iloc[index]
            self.progress_updated.emit(i + 1, len(sample_indices))
                
            # Process German description
            if 'p_desc.de' in self.df.columns and pd.notna(row['p_desc.de']):
                try:
                    html_content = str(row['p_desc.de'])
                    properties = self.html_parser.parse_html_table(html_content)
                    new_props_de = self.html_parser.detect_new_properties(properties, known_properties)
                    new_properties.update([(prop, 'de') for prop in new_props_de])
                except Exception as e:
                    self.status_updated.emit(f"Error detecting properties in German description: {str(e)}")
                
            # Process English description
            if 'p_desc.en' in self.df.columns and pd.notna(row['p_desc.en']):
                try:
                    html_content = str(row['p_desc.en'])
                    properties = self.html_parser.parse_html_table(html_content)
                    new_props_en = self.html_parser.detect_new_properties(properties, known_properties)
                    new_properties.update([(prop, 'en') for prop in new_props_en])
                except Exception as e:
                    self.status_updated.emit(f"Error detecting properties in English description: {str(e)}")
        
        # Register new properties in the database
        for prop_name, lang in new_properties:
            try:
                added = self.db_manager.add_new_property_if_not_exists(prop_name, lang)
                if added:
                    self.status_updated.emit(f"New property detected: {prop_name} ({lang})")
            except Exception as e:
                self.status_updated.emit(f"Error registering property {prop_name}: {str(e)}")
        
        self.status_updated.emit(f"Total {len(new_properties)} new properties detected.")