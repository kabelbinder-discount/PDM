"""
Database Manager Module for handling database operations
"""
import sqlite3
import pandas as pd

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
        return self.conn
        
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
            stock INTEGER,
            category TEXT
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
        
        # Create PropertyMappings table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS PropertyMappings (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT,
            standard_name TEXT,
            language TEXT,
            confidence REAL,
            UNIQUE(original_name, language)
        )
        ''')
        
        # Create PropertyOverrides table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS PropertyOverrides (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id TEXT,
            property_name TEXT,
            override_value TEXT,
            language TEXT,
            FOREIGN KEY (article_id) REFERENCES Products(article_id)
        )
        ''')
        
        # Create CategoryPropertyOverrides table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS CategoryPropertyOverrides (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            property_name TEXT,
            override_value TEXT,
            language TEXT
        )
        ''')
        
        self.conn.commit()
        self.close()
        
    def store_product(self, article_id, name=None, price=None, stock=None, category=None):
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
                
            if category is not None:
                query += 'category = ?, '
                params.append(category)
                
            # Remove last comma and space
            query = query.rstrip(', ')
            
            query += ' WHERE article_id = ?'
            params.append(article_id)
            
            self.cursor.execute(query, params)
        else:
            # Insert new product
            self.cursor.execute(
                'INSERT INTO Products (article_id, name, price, stock, category) VALUES (?, ?, ?, ?, ?)',
                (article_id, name, price, stock, category)
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
    
    def add_new_property_if_not_exists(self, property_name, language):
        """Add a new property to the definitions if it doesn't exist"""
        self.connect()
        
        # Check if property definition exists
        if language == 'de':
            self.cursor.execute('SELECT property_id FROM PropertyDefinitions WHERE name_de = ?', (property_name,))
        else:
            self.cursor.execute('SELECT property_id FROM PropertyDefinitions WHERE name_en = ?', (property_name,))
            
        exists = self.cursor.fetchone()
        
        if not exists:
            # Insert new property definition
            if language == 'de':
                self.cursor.execute(
                    'INSERT INTO PropertyDefinitions (name_de, name_en, data_type, expected_unit) VALUES (?, NULL, "string", NULL)',
                    (property_name,)
                )
            else:
                self.cursor.execute(
                    'INSERT INTO PropertyDefinitions (name_de, name_en, data_type, expected_unit) VALUES (NULL, ?, "string", NULL)',
                    (property_name,)
                )
            
            self.conn.commit()
            result = True
        else:
            result = False
            
        self.close()
        return result
        
    def get_all_products(self):
        """Get all products from database"""
        self.connect()
        self.cursor.execute('SELECT * FROM Products')
        products = self.cursor.fetchall()
        self.close()
        return products
    
    def get_products_by_category(self, category):
        """Get products filtered by category"""
        self.connect()
        self.cursor.execute('SELECT * FROM Products WHERE category = ?', (category,))
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
    
    def get_property_definitions(self):
        """Get all property definitions"""
        self.connect()
        self.cursor.execute('SELECT name_de, name_en, data_type, expected_unit FROM PropertyDefinitions')
        definitions = self.cursor.fetchall()
        self.close()
        return definitions
    
    def store_property_override(self, article_id, property_name, override_value, language):
        """Store a property override for a specific article"""
        self.connect()
        
        # Check if override exists
        self.cursor.execute(
            'SELECT override_id FROM PropertyOverrides WHERE article_id = ? AND property_name = ? AND language = ?',
            (article_id, property_name, language)
        )
        override_id = self.cursor.fetchone()
        
        if override_id:
            # Update existing override
            self.cursor.execute(
                'UPDATE PropertyOverrides SET override_value = ? WHERE override_id = ?',
                (override_value, override_id[0])
            )
        else:
            # Insert new override
            self.cursor.execute(
                'INSERT INTO PropertyOverrides (article_id, property_name, override_value, language) VALUES (?, ?, ?, ?)',
                (article_id, property_name, override_value, language)
            )
            
        self.conn.commit()
        self.close()
        
    def store_category_property_override(self, category, property_name, override_value, language):
        """Store a property override for a category"""
        self.connect()
        
        # Check if override exists
        self.cursor.execute(
            'SELECT override_id FROM CategoryPropertyOverrides WHERE category = ? AND property_name = ? AND language = ?',
            (category, property_name, language)
        )
        override_id = self.cursor.fetchone()
        
        if override_id:
            # Update existing override
            self.cursor.execute(
                'UPDATE CategoryPropertyOverrides SET override_value = ? WHERE override_id = ?',
                (override_value, override_id[0])
            )
        else:
            # Insert new override
            self.cursor.execute(
                'INSERT INTO CategoryPropertyOverrides (category, property_name, override_value, language) VALUES (?, ?, ?, ?)',
                (category, property_name, override_value, language)
            )
            
        self.conn.commit()
        self.close()
        
    def get_property_overrides(self, article_id):
        """Get all property overrides for a specific article"""
        self.connect()
        self.cursor.execute(
            'SELECT property_name, override_value, language FROM PropertyOverrides WHERE article_id = ?',
            (article_id,)
        )
        article_overrides = self.cursor.fetchall()
        
        # Get article category
        self.cursor.execute('SELECT category FROM Products WHERE article_id = ?', (article_id,))
        category_result = self.cursor.fetchone()
        
        category_overrides = []
        if category_result and category_result[0]:
            category = category_result[0]
            # Get category overrides
            self.cursor.execute(
                'SELECT property_name, override_value, language FROM CategoryPropertyOverrides WHERE category = ?',
                (category,)
            )
            category_overrides = self.cursor.fetchall()
            
        self.close()
        return article_overrides, category_overrides
    
def export_products_csv(self, output_file, include_html=True):
    """Export products to CSV format for shop import"""
    self.connect()
    
    # Get all products
    self.cursor.execute('SELECT article_id, name, price, stock, category FROM Products')
    products = self.cursor.fetchall()
    
    # Create DataFrame for export
    export_data = []
    
    for product in products:
        article_id, name, price, stock, category = product
        
        # Get properties for this product
        self.cursor.execute(
            'SELECT property_name, property_value, property_unit, language FROM Properties WHERE article_id = ?', 
            (article_id,)
        )
        properties = self.cursor.fetchall()
        
        # Get overrides
        article_overrides, category_overrides = self.get_property_overrides(article_id)
        
        # Organize properties by language
        de_properties = {}
        en_properties = {}
        
        # First add regular properties
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
        
        # Apply category overrides
        for prop_name, override_value, lang in category_overrides:
            if lang == 'de' and prop_name in de_properties:
                de_properties[prop_name] = override_value
            elif lang == 'en' and prop_name in en_properties:
                en_properties[prop_name] = override_value
        
        # Apply article-specific overrides (higher priority)
        for prop_name, override_value, lang in article_overrides:
            if lang == 'de':
                de_properties[prop_name] = override_value
            elif lang == 'en':
                en_properties[prop_name] = override_value
        
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
        
        # Create row for this product - adding XTSOL as a constant column
        product_row = {
            'XTSOL': 'XTSOL',  # Adding the XTSOL column with constant value
            'article_id': article_id,
            'name': name,
            'price': price,
            'stock': stock,
            'category': category,
            'p_desc.de': p_desc_de,
            'p_desc.en': p_desc_en
        }
        
        # Add individual properties
        for prop_name, prop_value in de_properties.items():
            product_row[f"prop_{prop_name}"] = prop_value
            
        for prop_name, prop_value in en_properties.items():
            product_row[f"prop_{prop_name}.en"] = prop_value
            
        export_data.append(product_row)
    
    self.close()
    
    # Create DataFrame and export to CSV
    df = pd.DataFrame(export_data)
    
    # Ensure XTSOL is the first column
    if 'XTSOL' in df.columns:
        cols = ['XTSOL'] + [col for col in df.columns if col != 'XTSOL']
        df = df[cols]
        
    df.to_csv(output_file, index=False, encoding='iso-8859-1', sep=';')
    
    return len(export_data)
