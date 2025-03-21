"""
Property Manager Module for managing product properties
"""
import pandas as pd
from core.html_parser import HTMLParser

class PropertyManager:
    """Class for managing product properties and their definitions"""
    
    def __init__(self, db_manager):
        """
        Initialize the Property Manager.
        
        Args:
            db_manager: Instance of DatabaseManager
        """
        self.db_manager = db_manager
        self.html_parser = HTMLParser()
        
    def load_property_definitions(self):
        """Load all property definitions from the database"""
        return self.db_manager.get_property_definitions()
    
    def add_property_definition(self, name_de, name_en, data_type, expected_unit):
        """
        Add a new property definition
        
        Args:
            name_de (str): German name of property
            name_en (str): English name of property
            data_type (str): Data type (string, number, boolean)
            expected_unit (str): Expected unit for the property
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        
        try:
            # Check if property definition exists
            cursor.execute('SELECT property_id FROM PropertyDefinitions WHERE name_de = ? OR name_en = ?', (name_de, name_en))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing definition
                cursor.execute(
                    'UPDATE PropertyDefinitions SET name_de = ?, name_en = ?, data_type = ?, expected_unit = ? WHERE property_id = ?',
                    (name_de, name_en, data_type, expected_unit, exists[0])
                )
            else:
                # Insert new definition
                cursor.execute(
                    'INSERT INTO PropertyDefinitions (name_de, name_en, data_type, expected_unit) VALUES (?, ?, ?, ?)',
                    (name_de, name_en, data_type, expected_unit)
                )
                
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding property definition: {str(e)}")
            return False
        finally:
            self.db_manager.close()
    
    def get_properties_for_product(self, article_id):
        """
        Get all properties for a product, including overrides
        
        Args:
            article_id (str): Article ID
            
        Returns:
            dict: Dictionary with property values by language
        """
        # Get regular properties
        properties = self.db_manager.get_product_properties(article_id)
        
        # Get overrides
        article_overrides, category_overrides = self.db_manager.get_property_overrides(article_id)
        
        # Organize properties by language
        de_properties = {}
        en_properties = {}
        
        # First add regular properties
        for prop_name, prop_value, prop_unit, lang in properties:
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
        
        # Apply category overrides
        for prop_name, override_value, lang in category_overrides:
            if lang == 'de':
                de_properties[prop_name] = override_value
            elif lang == 'en':
                en_properties[prop_name] = override_value
        
        # Apply article-specific overrides (higher priority)
        for prop_name, override_value, lang in article_overrides:
            if lang == 'de':
                de_properties[prop_name] = override_value
            elif lang == 'en':
                en_properties[prop_name] = override_value
                
        return {'de': de_properties, 'en': en_properties}
    
    def apply_overrides(self, article_id, properties):
        """
        Apply article-specific and category-based overrides.
        
        Args:
            article_id (str): Article ID
            properties (dict): Dictionary with property values
            
        Returns:
            dict: Dictionary with applied overrides
        """
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        
        # Get article category
        cursor.execute('SELECT category FROM Products WHERE article_id = ?', (article_id,))
        result = cursor.fetchone()
        category = result[0] if result and result[0] else None
        
        # Copy of properties
        overridden_properties = properties.copy()
        
        # Apply category-based overrides (if category is known)
        if category:
            cursor.execute(
                'SELECT property_name, override_value, language FROM CategoryPropertyOverrides WHERE category = ?',
                (category,)
            )
            category_overrides = cursor.fetchall()
            
            for prop_name, override_value, language in category_overrides:
                # Only override property if it exists in the corresponding language
                key = (prop_name, language)
                if key in overridden_properties:
                    overridden_properties[key] = override_value
        
        # Apply article-specific overrides (higher priority)
        cursor.execute(
            'SELECT property_name, override_value, language FROM PropertyOverrides WHERE article_id = ?',
            (article_id,)
        )
        article_overrides = cursor.fetchall()
        
        for prop_name, override_value, language in article_overrides:
            key = (prop_name, language)
            overridden_properties[key] = override_value
        
        self.db_manager.close()
        return overridden_properties
    
    def set_property_override(self, article_id, property_name, override_value, language):
        """
        Set an override for a property of a specific article
        
        Args:
            article_id (str): Article ID
            property_name (str): Property name
            override_value (str): Override value
            language (str): Language ('de' or 'en')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.db_manager.store_property_override(article_id, property_name, override_value, language)
            return True
        except Exception as e:
            print(f"Error setting property override: {str(e)}")
            return False
    
    def set_category_property_override(self, category, property_name, override_value, language):
        """
        Set an override for a property of a category
        
        Args:
            category (str): Category name
            property_name (str): Property name
            override_value (str): Override value
            language (str): Language ('de' or 'en')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.db_manager.store_category_property_override(category, property_name, override_value, language)
            return True
        except Exception as e:
            print(f"Error setting category property override: {str(e)}")
            return False
    
    def detect_new_properties(self, csv_file, encoding='iso-8859-1'):
        """
        Detect new properties in a CSV file
        
        Args:
            csv_file (str): Path to CSV file
            encoding (str): File encoding
            
        Returns:
            list: List of new properties
        """
        # Load CSV file
        df = pd.read_csv(csv_file, encoding=encoding, sep=';')
        
        # Load known properties
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT name_de, name_en FROM PropertyDefinitions')
        definitions = cursor.fetchall()
        self.db_manager.close()
        
        # Create list of known property names
        known_properties = []
        for name_de, name_en in definitions:
            if name_de:
                known_properties.append(name_de)
            if name_en:
                known_properties.append(name_en)
        
        # Scan HTML contents for new properties
        new_properties = set()
        
        for index, row in df.iterrows():
            # Process German description
            if 'p_desc.de' in df.columns and pd.notna(row['p_desc.de']):
                html_content = row['p_desc.de']
                properties = self.html_parser.parse_html_table(html_content)
                new_props_de = self.html_parser.detect_new_properties(properties, known_properties)
                new_properties.update([(prop, 'de') for prop in new_props_de])
                
            # Process English description
            if 'p_desc.en' in df.columns and pd.notna(row['p_desc.en']):
                html_content = row['p_desc.en']
                properties = self.html_parser.parse_html_table(html_content)
                new_props_en = self.html_parser.detect_new_properties(properties, known_properties)
                new_properties.update([(prop, 'en') for prop in new_props_en])
                
        return list(new_properties)
