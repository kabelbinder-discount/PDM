# Design Document: Product Data Extractor and Manager

## 1. Project Overview

### Purpose
Develop a Python GUI application that extracts structured product data from HTML tables embedded in CSV exports from an online shop, transforms this data into a structured database, and allows for exporting the data back to CSV format for reimporting into the shop system.

### Problem Statement
- Product data in the online shop is exported as a CSV file in ISO-8859-1 encoding
- Product descriptions are stored as HTML content in columns named "p_desc.de" and "p_desc.en"
- These HTML descriptions contain structured data in tabular format (as shown in screenshots)
- Need to extract this structured data to create a centralized database
- Must be able to export this structured data back to CSV format compatible with shop import requirements

## 2. System Architecture

### Components
1. **GUI Frontend**
   - User interface for importing CSV files, viewing data, and exporting results
   - Controls for data extraction, transformation, and database operations

2. **Data Import Module**
   - CSV parsing with correct encoding (ISO-8859-1)
   - Extraction of HTML content from "p_desc.de" and "p_desc.en" columns

3. **HTML Parser Module**
   - Extraction of tabular data from HTML content using pattern recognition
   - Handling of different table formats as shown in screenshots
   - Data normalization and validation

4. **Database Module**
   - SQLite database for storing structured product data
   - Tables for products and their properties

5. **Export Module**
   - Generation of standardized CSV output
   - Preservation of proper encoding for reimport

### Technology Stack
- **Language**: Python 3.x
- **GUI Framework**: PyQt5 or Tkinter
- **HTML Parsing**: Beautiful Soup 4
- **CSV Handling**: pandas
- **Database**: SQLite

## 3. Data Flow

1. **Import Phase**
   - User selects CSV file through GUI
   - Application reads CSV with ISO-8859-1 encoding
   - For each product row:
     - Extract HTML content from "p_desc.de" and "p_desc.en"
     - Parse HTML to identify property tables
     - Extract key-value pairs from tables
   - Store extracted data in database

2. **Database Phase**
   - Organize data with article numbers as primary keys
   - Store extracted properties with appropriate data types
   - Maintain relationship between products and properties

3. **Export Phase**
   - Query database for structured data
   - Format data according to shop import requirements
   - Generate CSV with correct encoding
   - Allow user to save to file system

## 4. Data Model

### Database Schema

```sql
-- Products table for main product information
CREATE TABLE Products (
    article_id TEXT PRIMARY KEY,
    name TEXT,
    price REAL,
    -- Other fields from CSV that aren't in the HTML tables
);

-- Properties table for extracted data from HTML tables
CREATE TABLE Properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT,
    property_name TEXT,
    property_value TEXT,
    property_unit TEXT,
    language TEXT,  -- 'de' or 'en'
    FOREIGN KEY (article_id) REFERENCES Products(article_id)
);

-- PropertyDefinitions for standardizing property names
CREATE TABLE PropertyDefinitions (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_de TEXT,  -- German name of property
    name_en TEXT,  -- English name of property
    data_type TEXT,  -- string, number, boolean
    expected_unit TEXT
);
```

## 5. Parsing Logic

### Key Properties to Extract
Based on the screenshots, the application should identify and extract properties such as:

#### Cable Ties (First Two Screenshots):
- Farbe / Color
- Material
- Zugkraft / Tensile strength
- Max. Bündeldurchmesser / Max. bundle diameter
- Min. Bündeldurchmesser / Min. bundle diameter
- Temperaturbeständigkeit / Temperature resistance
- Zulassungen / Certifications
- Verpackungseinheit / Packaging unit

#### Terminal Connectors (Third Screenshot):
- Farbe / Color
- Isolationsmaterial / Insulation material
- Werkstoff des Leiters / Conductor material
- Länge / Length
- Nenngröße / Nominal size
- Kabelquerschnitt / Cable cross-section
- Verpackungseinheit / Packaging unit

### Pattern Recognition for Tables
The application will need to handle various HTML table structures:
1. Two-column tables (property name | property value)
2. Single-row multi-value properties (e.g., certifications)
3. Different units and formats for similar properties

## 6. User Interface Design

### Main Window Layout
- Top menu bar with File, Database, and Help menus
- Left sidebar for navigating between functions
- Main panel with tabbed interface:
  - Import tab
  - Data View/Edit tab
  - Export tab

### Import Panel
- File selection control with encoding options
- Preview of CSV data
- Progress indicator for parsing
- Log window for import operations

### Data View/Edit Panel
- Product list with search and filter
- Property editor for selected product
- Bulk edit capabilities for multiple products

### Export Panel
- Export configuration options
- Field mapping for custom exports
- Preview of export data
- Export format selection

## 7. Implementation Plan

### Phase 1: Core Functionality (2-3 weeks)
- Set up project structure and dependencies
- Implement CSV import with encoding handling
- Develop basic HTML parsing for property extraction
- Create database schema and basic operations
- Build minimal GUI for testing functionality

### Phase 2: Enhanced Features (2-3 weeks)
- Improve HTML parsing with pattern recognition
- Implement data validation and normalization
- Add support for both "p_desc.de" and "p_desc.en" columns
- Develop complete GUI with all planned panels
- Add search and filter capabilities

### Phase 3: Refinement and Testing (1-2 weeks)
- Optimize performance for large datasets
- Enhance error handling and user feedback
- Implement export functionality with custom formatting
- Add batch processing capabilities
- Create user documentation

## 8. Code Structure

```
productdata/
├── main.py               # Application entry point
├── gui/
│   ├── __init__.py
│   ├── main_window.py    # Main application window
│   ├── import_panel.py   # Import functionality
│   ├── view_panel.py     # Data viewing/editing
│   ├── export_panel.py   # Export functionality
│   └── widgets.py        # Custom widgets
├── data/
│   ├── __init__.py
│   ├── csv_handler.py    # CSV import/export
│   ├── html_parser.py    # HTML parsing logic
│   └── db_manager.py     # Database operations
├── models/
│   ├── __init__.py
│   ├── product.py        # Product data model
│   └── property.py       # Property data model
└── utils/
    ├── __init__.py
    ├── config.py         # Application configuration
    └── logger.py         # Logging functionality
```

## 9. Technical Challenges and Solutions

### Encoding Issues
- Use pandas with explicit encoding parameter:
  ```python
  import pandas as pd
  df = pd.read_csv('export.csv', encoding='iso-8859-1')
  ```

### HTML Parsing Variability
- Use BeautifulSoup with pattern recognition:
  ```python
  from bs4 import BeautifulSoup
  
  def parse_html_table(html_content):
      soup = BeautifulSoup(html_content, 'html.parser')
      properties = {}
      
      # Find tables in the HTML
      tables = soup.find_all('table')
      
      for table in tables:
          rows = table.find_all('tr')
          for row in rows:
              cells = row.find_all(['th', 'td'])
              if len(cells) >= 2:
                  property_name = cells[0].get_text().strip()
                  property_value = cells[1].get_text().strip()
                  properties[property_name] = property_value
                  
      return properties
  ```

### Data Normalization
- Create standardized property definitions:
  ```python
  def normalize_property(property_name, property_value):
      # Map common variations to standard names
      name_mapping = {
          'Farbe': 'color',
          'Farbe:': 'color',
          # Add more mappings as needed
      }
      
      # Normalize property name
      normalized_name = name_mapping.get(property_name, property_name)
      
      # Process value based on property type
      if normalized_name == 'color':
          return normalized_name, property_value.lower()
      elif normalized_name == 'temperature_resistance':
          # Extract numeric values and units
          import re
          match = re.search(r'(-?\d+)\s*°C\s*bis\s*(\+?\d+)\s*°C', property_value)
          if match:
              min_temp, max_temp = match.groups()
              return normalized_name, {'min': int(min_temp), 'max': int(max_temp)}
              
      return normalized_name, property_value
  ```

## 10. Testing Strategy

### Unit Tests
- Test CSV import with various encodings
- Test HTML parsing with sample HTML from screenshots
- Test database operations for data integrity

### Integration Tests
- End-to-end import to database tests
- Database to export tests
- Full workflow tests

### User Testing
- Test with real CSV exports
- Verify database integrity
- Validate export compatibility with shop import

## 11. Future Enhancements

### Potential Additions
- Pattern learning from user corrections
- Multi-language support for UI
- Integration with online shop API for direct updates
- Data analysis and reporting features
- Bulk edit capabilities for multiple products
- Data validation rules customization
- Auto-detect encoding of CSV files

## 12. Conclusion

This design document outlines the development of a Python GUI application for extracting, managing, and exporting product data from HTML tables embedded in CSV exports. The application will provide a centralized way to manage product data for an online shop, improving data consistency and management efficiency.

The implementation will focus on robust HTML parsing, data normalization, and a user-friendly interface, with SQLite database for local data storage. The application will handle CSV files with ISO-8859-1 encoding and extract data from both German and English product descriptions.
