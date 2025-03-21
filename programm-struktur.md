## Implementierung der neuen Funktionalitäten

### Dynamische Eigenschaftserkennung

Der Prozess zur Erkennung neuer Eigenschaften in Import-Dateien wird wie folgt implementiert:

1. **In der HTMLParser-Klasse**:
   ```python
   def detect_new_properties(self, properties_dict, known_properties):
       """
       Identifiziert neue Eigenschaften, die noch nicht in der Datenbank definiert sind.
       
       Args:
           properties_dict (dict): Extrahierte Eigenschaften aus HTML
           known_properties (list): Liste bereits bekannter Eigenschaftsnamen
           
       Returns:
           list: Liste neuer Eigenschaftsnamen
       """
       new_properties = []
       for prop_name in properties_dict.keys():
           # Normalisieren des Eigenschaftsnamens
           std_name, _, _ = self.normalize_property(prop_name, "", "")
           
           # Prüfen, ob die normalisierte Eigenschaft bereits bekannt ist
           if std_name not in known_properties:
               new_properties.append(std_name)
               
       return new_properties
   ```

2. **Im ImportWorker**:
   ```python
   def _detect_and_register_new_properties(self):
       """
       Erkennt neue Eigenschaften in der CSV-Datei und registriert sie in der Datenbank.
       """
       self.status_updated.emit("Erkenne neue Eigenschaften...")
       
       # Laden bekannter Eigenschaften
       known_properties = [prop[0] for prop in self.db_manager.get_property_definitions()]
       
       # Scannen der HTML-Inhalte nach Eigenschaften
       new_properties = set()
       total_rows = len(self.df)
       
       for index, row in self.df.iterrows():
           if 'p_desc.de' in self.df.columns and pd.notna(row['p_desc.de']):
               html_content = row['p_desc.de']
               properties = self.html_parser.parse_html_table(html_content)
               new_props_de = self.html_parser.detect_new_properties(properties, known_properties)
               new_properties.update([(prop, 'de') for prop in new_props_de])
               
           if 'p_desc.en' in self.df.columns and pd.notna(row['p_desc.en']):
               html_content = row['p_desc.en']
               properties = self.html_parser.parse_html_table(html_content)
               new_props_en = self.html_parser.detect_new_properties(properties, known_properties)
               new_properties.update([(prop, 'en') for prop in new_props_en])
       
       # Registrieren neuer Eigenschaften in der Datenbank
       for prop_name, lang in new_properties:
           self.db_manager.add_new_property_if_not_exists(prop_name, lang)
           self.status_updated.emit(f"Neue Eigenschaft erkannt: {prop_name} ({lang})")
       
       self.status_updated.emit(f"Insgesamt {len(new_properties)} neue Eigenschaften erkannt.")
   ```

### Attributzuordnung

Die Attributzuordnung wird in der AttributeMapper-Klasse implementiert:

```python
class AttributeMapper:
    """Klasse zur Zuordnung unterschiedlich benannter Attribute."""
    
    def __init__(self, db_manager):
        """
        Initialisiert den Attribute-Mapper.
        
        Args:
            db_manager: Instanz des DatabaseManager
        """
        self.db_manager = db_manager
        self.mappings = {}  # Format: {(original_name, language): standard_name}
        self.load_mappings()
        
    def load_mappings(self):
        """Lädt bestehende Attributzuordnungen aus der Datenbank."""
        self.mappings = {}
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT original_name, standard_name, language FROM PropertyMappings')
        rows = cursor.fetchall()
        
        for original_name, standard_name, language in rows:
            self.mappings[(original_name, language)] = standard_name
            
        self.db_manager.close()
        
    def add_mapping(self, original_name, standard_name, language):
        """
        Erstellt ein neues Mapping zwischen Original- und Standardnamen.
        
        Args:
            original_name (str): Original-Attributname
            standard_name (str): Standardisierter Name
            language (str): Sprache ('de' oder 'en')
            
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'INSERT OR REPLACE INTO PropertyMappings (original_name, standard_name, language, confidence) VALUES (?, ?, ?, ?)',
                (original_name, standard_name, language, 1.0)  # Manuelle Mappings haben Konfidenz 1.0
            )
            conn.commit()
            self.mappings[(original_name, language)] = standard_name
            return True
        except Exception as e:
            print(f"Fehler beim Speichern des Mappings: {str(e)}")
            return False
        finally:
            self.db_manager.close()
            
    def get_standard_name(self, original_name, language):
        """
        Ermittelt den standardisierten Namen für einen Original-Attributnamen.
        
        Args:
            original_name (str): Original-Attributname
            language (str): Sprache ('de' oder 'en')
            
        Returns:
            str: Standardisierter Name oder original_name wenn kein Mapping existiert
        """
        return self.mappings.get((original_name, language), original_name)
    
    def suggest_mappings(self, property_names):
        """
        Schlägt automatisch mögliche Zuordnungen für unbekannte Attributnamen vor.
        
        Args:
            property_names (list): Liste von Eigenschaftsnamen
            
        Returns:
            dict: Dictionary mit Vorschlägen {original_name: [(standard_name, confidence), ...]}
        """
        suggestions = {}
        
        # Bekannte Standardnamen laden
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT name_de, name_en FROM PropertyDefinitions')
        standard_names = cursor.fetchall()
        self.db_manager.close()
        
        # Alle standard_names in einer flachen Liste
        all_standard_names = [name for pair in standard_names for name in pair if name]
        
        for prop_name in property_names:
            if not any(prop_name == orig for (orig, _) in self.mappings.keys()):
                # Ähnlichkeit zu bekannten Standardnamen berechnen
                prop_suggestions = []
                
                for std_name in all_standard_names:
                    # Einfache Ähnlichkeitsberechnung (kann durch komplexere Algorithmen ersetzt werden)
                    similarity = self._calculate_similarity(prop_name, std_name)
                    if similarity > 0.6:  # Schwellenwert für Vorschläge
                        prop_suggestions.append((std_name, similarity))
                
                # Nach Ähnlichkeit sortieren
                prop_suggestions.sort(key=lambda x: x[1], reverse=True)
                suggestions[prop_name] = prop_suggestions[:3]  # Bis zu 3 Vorschläge
                
        return suggestions
    
    def _calculate_similarity(self, str1, str2):
        """
        Berechnet die Ähnlichkeit zwischen zwei Strings (einfache Implementierung).
        
        Args:
            str1 (str): Erster String
            str2 (str): Zweiter String
            
        Returns:
            float: Ähnlichkeitswert zwischen 0 und 1
        """
        # Diese Implementierung ist vereinfacht und kann durch bessere Algorithmen ersetzt werden
        str1_lower = str1.lower()
        str2_lower = str2.lower()
        
        # Einfache Enthaltensein-Prüfung
        if str1_lower in str2_lower or str2_lower in str1_lower:
            return 0.8
            
        # Gemeinsame Zeichen zählen
        common_chars = set(str1_lower) & set(str2_lower)
        return len(common_chars) / max(len(set(str1_lower)), len(set(str2_lower)))
```

### Eigenschafts-Überschreibungen

Die PropertyManager-Klasse implementiert die Verwaltung von Überschreibungen:

```python
def apply_overrides(self, article_id, properties):
    """
    Wendet artikelspezifische und kategoriebasierte Überschreibungen an.
    
    Args:
        article_id (str): Artikel-ID
        properties (dict): Dictionary mit Eigenschaftswerten
        
    Returns:
        dict: Dictionary mit angewendeten Überschreibungen
    """
    conn = self.db_manager.connect()
    cursor = conn.cursor()
    
    # Kategorie des Artikels abrufen
    cursor.execute('SELECT category FROM Products WHERE article_id = ?', (article_id,))
    result = cursor.fetchone()
    category = result[0] if result and result[0] else None
    
    # Kopie der Eigenschaften erstellen
    overridden_properties = properties.copy()
    
    # Kategoriebasierte Überschreibungen anwenden (falls Kategorie bekannt)
    if category:
        cursor.execute(
            'SELECT property_name, override_value, language FROM CategoryPropertyOverrides WHERE category = ?',
            (category,)
        )
        category_overrides = cursor.fetchall()
        
        for prop_name, override_value, language in category_overrides:
            # Eigenschaft nur überschreiben, wenn sie in der passenden Sprache existiert
            key = (prop_name, language)
            if key in overridden_properties:
                overridden_properties[key] = override_value
    
    # Artikelspezifische Überschreibungen anwenden (höhere Priorität)
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
```

### Implementierung im Export-Prozess

Die Überschreibungen und Attributzuordnungen werden während des Exports angewendet:

```python
def _apply_property_overrides(self):
    """
    Wendet Eigenschafts-Überschreibungen auf die Exportdaten an.
    """
    self.status_updated.emit("Wende Eigenschafts-Überschreibungen an...")
    
    property_manager = PropertyManager(self.db_manager)
    
    # Für jedes Produkt Überschreibungen anwenden
    for product in self.export_data:
        article_id = product['article_id']
        
        # Eigenschaften in ein standardisiertes Format bringen
        properties = {}
        for key, value in product.items():
            if key.startswith('prop_'):
                prop_name = key[5:]  # 'prop_' entfernen
                # Sprachcode extrahieren (falls vorhanden)
                if '.' in prop_name:
                    base_name, lang = prop_name.rsplit('.', 1)
                    properties[(base_name, lang)] = value
                else:
                    # Standardmäßig als deutsche Eigenschaft betrachten
                    properties[(prop_name, 'de')] = value
        
        # Überschreibungen anwenden
        overridden_properties = property_manager.apply_overrides(article_id, properties)
        
        # Überschriebene Werte zurück in das Produktdictionary schreiben
        for (prop_name, lang), value in overridden_properties.items():
            if lang:
                key = f"prop_{prop_name}.{lang}"
            else:
                key = f"prop_{prop_name}"
            product[key] = value
    
    self.status_updated.emit("Überschreibungen erfolgreich angewendet.")
```
## Erweiterungsmöglichkeiten

1. **Fortgeschrittene Datenanalyse**: Implementierung von Analysetools zur Identifizierung von Dateninkonsistenzen oder fehlenden Werten.
2. **Bulk-Import/Export**: Unterstützung für die gleichzeitige Verarbeitung mehrerer Dateien.
3. **Validierungsregeln**: Benutzerdefinierte Regeln für die Überprüfung von Eigenschaftswerten (z.B. Wertebereiche, Formate).
4. **API-Integration**: Direktverbindung zu Shop-Systemen für automatisierten Import/Export.
5. **Versionierung**: Protokollierung von Änderungen an Produkteigenschaften mit Möglichkeit zum Rollback.
6. **Intelligente Vorschläge**: Machine-Learning-basierte Vorschläge für Attributzuordnungen basierend auf historischen Daten.
7. **Multi-User-Unterstützung**: Benutzerrollen und Berechtigungen für kollaborative Datenbearbeitung.
8. **Template-System**: Vordefinierte Eigenschaftssets für verschiedene Produktkategorien.
9. **Import/Export-Vorlagen**: Speichern und Wiederverwenden von Import/Export-Konfigurationen.
10. **Audit-Trail**: Vollständige Protokollierung aller Änderungen an Produktdaten für Nachverfolgbarkeit.# Produktdaten-Extraktor: Programmstruktur und Funktionserläuterung

Basierend auf den gegebenen Anforderungen und dem Python-Implementierungsbeispiel habe ich eine strukturierte Aufteilung des Programms in verschiedene Dateien entwickelt. Diese Dokumentation erklärt die Struktur des Programms und die Funktionen in jeder Datei.

## Programmstruktur

```
product_data_extractor/
│
├── main.py                  # Haupteinstiegspunkt der Anwendung
│
├── ui/                      # UI-Komponenten
│   ├── __init__.py
│   ├── main_window.py       # Hauptfenster der Anwendung
│   ├── import_tab.py        # Tab für den CSV-Import
│   ├── data_view_tab.py     # Tab für die Datenansicht
│   ├── mapping_tab.py       # Tab für die Attributzuordnung
│   ├── override_tab.py      # Tab für die Eigenschaften-Überschreibungen
│   └── export_tab.py        # Tab für den CSV-Export
│
├── core/                    # Kernfunktionalität
│   ├── __init__.py
│   ├── html_parser.py       # HTML-Parsing-Funktionalität
│   ├── database_manager.py  # Datenbankoperationen
│   ├── attribute_mapper.py  # Mapping von Attributen zwischen verschiedenen Benennungen
│   ├── property_manager.py  # Verwaltung von Eigenschaften und deren Definitionen
│   └── csv_handler.py       # CSV Import/Export-Handling
│
└── workers/                 # Thread-Worker für Hintergrundprozesse
    ├── __init__.py
    ├── import_worker.py     # Worker für den Import-Prozess
    ├── mapping_worker.py    # Worker für die Attributzuordnung
    └── export_worker.py     # Worker für den Export-Prozess
```

## Detaillierte Funktionserläuterung

### `main.py`

Diese Datei dient als Einstiegspunkt für die Anwendung.

- `main()`: Initialisiert die Anwendung, erstellt das Hauptfenster und startet die Ereignisschleife.

### UI-Komponenten

#### `ui/main_window.py`

Enthält die `MainWindow`-Klasse, die das Hauptfenster der Anwendung implementiert.

- `MainWindow.__init__()`: Initialisiert das Hauptfenster und erstellt die Tab-Struktur.
- `MainWindow.init_ui()`: Richtet die Benutzeroberfläche ein, erstellt das Tab-Widget und fügt die Tabs hinzu.
- `MainWindow.initialize_database()`: Initialisiert die Datenbank für die erste Nutzung.
- `MainWindow.load_application_settings()`: Lädt gespeicherte Anwendungseinstellungen.

#### `ui/import_tab.py`

Enthält die `ImportTab`-Klasse, die den Tab für den CSV-Import implementiert.

- `ImportTab.__init__()`: Initialisiert den Import-Tab.
- `ImportTab.init_ui()`: Erstellt UI-Elemente für die Dateiauswahl, Kodierungsoptionen und Fortschrittsanzeige.
- `ImportTab.browse_file()`: Öffnet einen Dateidialog zur Auswahl einer CSV-Datei.
- `ImportTab.start_import()`: Startet den Importprozess mit den ausgewählten Optionen.
- `ImportTab.update_progress()`: Aktualisiert die Fortschrittsanzeige während des Imports.
- `ImportTab.log_message()`: Fügt Statusmeldungen zum Log-Bereich hinzu.
- `ImportTab.import_finished()`: Behandelt den Abschluss des Importvorgangs.

#### `ui/data_view_tab.py`

Enthält die `DataViewTab`-Klasse für die Anzeige und Bearbeitung der Produktdaten.

- `DataViewTab.__init__()`: Initialisiert den Datenansichts-Tab.
- `DataViewTab.init_ui()`: Erstellt Tabellen für Produkte und Eigenschaften.
- `DataViewTab.showEvent()`: Wird aufgerufen, wenn der Tab angezeigt wird; lädt Produktdaten.
- `DataViewTab.load_products()`: Lädt Produktdaten aus der Datenbank in die Tabelle.
- `DataViewTab.load_properties()`: Lädt Eigenschaften für das ausgewählte Produkt.
- `DataViewTab.filter_products_by_category()`: Filtert die Produktliste nach Kategorie.
- `DataViewTab.edit_property()`: Ermöglicht das Bearbeiten einer Produkteigenschaft.

#### `ui/mapping_tab.py`

Enthält die `MappingTab`-Klasse für die Verwaltung von Attributzuordnungen.

- `MappingTab.__init__()`: Initialisiert den Mapping-Tab.
- `MappingTab.init_ui()`: Erstellt UI-Elemente für die Attributzuordnung.
- `MappingTab.load_mappings()`: Lädt bestehende Attributzuordnungen.
- `MappingTab.add_mapping()`: Fügt eine neue Attributzuordnung hinzu.
- `MappingTab.edit_mapping()`: Bearbeitet eine bestehende Attributzuordnung.
- `MappingTab.delete_mapping()`: Löscht eine bestehende Attributzuordnung.
- `MappingTab.import_mappings()`: Importiert Attributzuordnungen aus einer Datei.
- `MappingTab.export_mappings()`: Exportiert Attributzuordnungen in eine Datei.
- `MappingTab.detect_new_properties()`: Erkennt neue Eigenschaften in einer CSV-Datei.

#### `ui/override_tab.py`

Enthält die `OverrideTab`-Klasse für die Verwaltung von Eigenschafts-Überschreibungen.

- `OverrideTab.__init__()`: Initialisiert den Override-Tab.
- `OverrideTab.init_ui()`: Erstellt UI-Elemente für die Überschreibungsverwaltung.
- `OverrideTab.show_article_overrides()`: Zeigt artikelspezifische Überschreibungen an.
- `OverrideTab.show_category_overrides()`: Zeigt kategoriebasierte Überschreibungen an.
- `OverrideTab.add_article_override()`: Fügt eine artikelspezifische Überschreibung hinzu.
- `OverrideTab.add_category_override()`: Fügt eine kategoriebasierte Überschreibung hinzu.
- `OverrideTab.edit_override()`: Bearbeitet eine bestehende Überschreibung.
- `OverrideTab.delete_override()`: Löscht eine bestehende Überschreibung.
- `OverrideTab.load_products()`: Lädt Produkte für die Artikelauswahl.
- `OverrideTab.load_categories()`: Lädt Kategorien für die Kategorieauswahl.

#### `ui/export_tab.py`

Enthält die `ExportTab`-Klasse für den Export der Produktdaten.

- `ExportTab.__init__()`: Initialisiert den Export-Tab.
- `ExportTab.init_ui()`: Erstellt UI-Elemente für Export-Einstellungen und Statusanzeige.
- `ExportTab.browse_file()`: Öffnet einen Speicherort-Dialog für die Export-Datei.
- `ExportTab.start_export()`: Startet den Exportprozess mit den gewählten Optionen.
- `ExportTab.log_message()`: Fügt Statusmeldungen zum Log-Bereich hinzu.
- `ExportTab.export_finished()`: Behandelt den Abschluss des Exportvorgangs.

### Core-Komponenten

#### `core/html_parser.py`

Enthält die `HTMLParser`-Klasse für die Extraktion strukturierter Daten aus HTML-Tabellen.

- `HTMLParser.parse_html_table(html_content)`: Parst HTML-Inhalt, um Tabellendaten zu extrahieren.
- `HTMLParser._parse_rows(rows)`: Hilfsmethode zum Parsen von Tabellenzeilen in Property-Wert-Paare.
- `HTMLParser.normalize_property(property_name, property_value, language)`: Normalisiert Eigenschaftsnamen und -werte, vereinheitlicht Maßeinheiten und übersetzt zwischen Sprachen.
- `HTMLParser.detect_new_properties(properties_dict, known_properties)`: Identifiziert neue Eigenschaften, die noch nicht in der Datenbank definiert sind.

#### `core/attribute_mapper.py`

Enthält die `AttributeMapper`-Klasse für die Zuordnung unterschiedlich benannter Attribute.

- `AttributeMapper.__init__(db_manager)`: Initialisiert den Attribute-Mapper mit einer Datenbankverbindung.
- `AttributeMapper.load_mappings()`: Lädt bestehende Attributzuordnungen aus der Datenbank.
- `AttributeMapper.add_mapping(original_name, standard_name, language)`: Erstellt ein neues Mapping zwischen einem Original-Attributnamen und einem standardisierten Namen.
- `AttributeMapper.get_standard_name(original_name, language)`: Ermittelt den standardisierten Namen für einen Original-Attributnamen.
- `AttributeMapper.suggest_mappings(property_names)`: Schlägt automatisch mögliche Zuordnungen für unbekannte Attributnamen vor.
- `AttributeMapper.save_mappings()`: Speichert die aktuellen Mappings in der Datenbank.

#### `core/property_manager.py`

Enthält die `PropertyManager`-Klasse für die Verwaltung von Produkteigenschaften und deren Definitionen.

- `PropertyManager.__init__(db_manager)`: Initialisiert den Property-Manager mit einer Datenbankverbindung.
- `PropertyManager.load_property_definitions()`: Lädt alle definierten Eigenschaften aus der Datenbank.
- `PropertyManager.add_property_definition(name_de, name_en, data_type, expected_unit)`: Fügt eine neue Eigenschaftsdefinition hinzu.
- `PropertyManager.get_properties_for_product(article_id)`: Ruft alle Eigenschaften für ein Produkt ab, inklusive Überschreibungen.
- `PropertyManager.apply_overrides(article_id, properties)`: Wendet artikelspezifische und kategoriebasierte Überschreibungen an.
- `PropertyManager.set_property_override(article_id, property_name, override_value, language)`: Erstellt eine Überschreibung für eine Eigenschaft eines bestimmten Artikels.
- `PropertyManager.set_category_property_override(category, property_name, override_value, language)`: Erstellt eine Überschreibung für eine Eigenschaft einer Kategorie.
- `PropertyManager.detect_new_properties(csv_file, encoding)`: Erkennt neue Eigenschaften in einer CSV-Datei.
- `PropertyManager.import_property_values(csv_file, encoding)`: Importiert Eigenschaftswerte aus einer CSV-Datei.

#### `core/database_manager.py`

Enthält die `DatabaseManager`-Klasse für die Verwaltung der SQLite-Datenbank.

- `DatabaseManager.__init__(db_path)`: Initialisiert den Datenbankmanager mit dem Pfad zur Datenbankdatei.
- `DatabaseManager.connect()`: Stellt eine Verbindung zur Datenbank her.
- `DatabaseManager.close()`: Schließt die Datenbankverbindung.
- `DatabaseManager.initialize_database()`: Erstellt das Datenbankschema, falls es nicht existiert.
- `DatabaseManager.store_product(article_id, name, price, stock, category=None)`: Speichert oder aktualisiert Produktinformationen mit optionaler Kategorie.
- `DatabaseManager.store_property(article_id, property_name, property_value, property_unit, language)`: Speichert Produkteigenschaften.
- `DatabaseManager.store_property_definition(name_de, name_en, data_type, expected_unit)`: Speichert oder aktualisiert eine Eigenschaftsdefinition.
- `DatabaseManager.add_new_property_if_not_exists(property_name, language)`: Fügt eine neue Eigenschaft zur Definition hinzu, wenn sie noch nicht existiert.
- `DatabaseManager.get_all_products()`: Ruft alle Produkte aus der Datenbank ab.
- `DatabaseManager.get_products_by_category(category)`: Ruft Produkte nach Kategorie ab.
- `DatabaseManager.get_product_properties(article_id)`: Ruft Eigenschaften für ein bestimmtes Produkt ab.
- `DatabaseManager.get_property_definitions()`: Ruft alle definierten Eigenschaften ab.
- `DatabaseManager.get_property_mapping(original_name)`: Ruft das Mapping für einen Eigenschaftsnamen ab.
- `DatabaseManager.store_property_override(article_id, property_name, override_value, language)`: Speichert eine Überschreibung für eine Eigenschaft eines bestimmten Produkts.
- `DatabaseManager.store_category_property_override(category, property_name, override_value, language)`: Speichert eine Überschreibung für eine Eigenschaft einer Kategorie.
- `DatabaseManager.get_property_overrides(article_id)`: Ruft alle Überschreibungen für ein Produkt ab.
- `DatabaseManager.export_products_csv(output_file, include_html)`: Exportiert Produkte im CSV-Format für den Shop-Import.

#### `core/csv_handler.py`

Enthält Hilfsfunktionen für den CSV-Import und -Export, um die Handhabung von Kodierungen und speziellen Formaten zu erleichtern.

- `read_csv(file_path, encoding)`: Liest CSV-Datei mit der angegebenen Kodierung.
- `identify_article_id_column(df)`: Identifiziert die Spalte, die die Artikel-ID enthält.
- `check_required_columns(df)`: Überprüft, ob die erforderlichen Spalten in der CSV vorhanden sind.
- `write_csv(df, output_file, encoding)`: Schreibt DataFrame in eine CSV-Datei mit der angegebenen Kodierung.

### Worker-Komponenten

#### `workers/import_worker.py`

Enthält die `ImportWorker`-Klasse, einen QThread für die Durchführung des CSV-Imports im Hintergrund.

- `ImportWorker.__init__(csv_file, encoding, detect_new_properties=True)`: Initialisiert den Worker mit Datei, Kodierung und Option zur Erkennung neuer Eigenschaften.
- `ImportWorker.run()`: Implementiert den Importprozess: CSV lesen, HTML parsen, Eigenschaften extrahieren und in Datenbank speichern.
- `ImportWorker._detect_and_register_new_properties()`: Erkennt neue Eigenschaften in der CSV-Datei und registriert sie in der Datenbank.
- `ImportWorker._apply_attribute_mappings()`: Wendet Attributmappings auf erkannte Eigenschaften an.

#### `workers/mapping_worker.py`

Enthält die `MappingWorker`-Klasse, einen QThread für die Erkennung und Zuordnung von Attributen.

- `MappingWorker.__init__(csv_files, encoding)`: Initialisiert den Worker mit einer Liste von CSV-Dateien und der Kodierung.
- `MappingWorker.run()`: Implementiert den Prozess zur Erkennung und Zuordnung von Attributen.
- `MappingWorker._scan_csv_for_properties()`: Scannt CSV-Dateien nach Eigenschaften.
- `MappingWorker._suggest_mappings()`: Schlägt Zuordnungen für neu erkannte Eigenschaften vor.

#### `workers/export_worker.py`

Enthält die `ExportWorker`-Klasse, einen QThread für die Durchführung des CSV-Exports im Hintergrund.

- `ExportWorker.__init__(output_file, include_html, apply_overrides=True)`: Initialisiert den Worker mit Ausgabedatei, HTML-Option und Option zum Anwenden von Überschreibungen.
- `ExportWorker.run()`: Implementiert den Exportprozess: Daten aus der Datenbank abfragen, CSV formatieren und speichern.
- `ExportWorker._apply_property_overrides()`: Wendet artikelspezifische und kategoriebasierte Überschreibungen auf die Exportdaten an.

## Funktionsüberblick und Datenfluss

1. **Import-Prozess**:
   - Benutzer wählt CSV-Datei und Kodierung im Import-Tab
   - `ImportWorker` wird gestartet und liest die CSV-Datei
   - Für jede Zeile werden HTML-Tabellen aus `p_desc.de` und `p_desc.en` extrahiert
   - `HTMLParser` extrahiert Eigenschaften aus den HTML-Tabellen und normalisiert sie
   - Neue, bisher unbekannte Eigenschaften werden erkannt und in der Datenbank registriert
   - Attributmappings werden angewendet, um unterschiedlich benannte Eigenschaften zu vereinheitlichen
   - `DatabaseManager` speichert die Produkte und ihre Eigenschaften in der Datenbank

2. **Attributzuordnung**:
   - Benutzer kann im Mapping-Tab Attributzuordnungen verwalten
   - `MappingWorker` scannt CSV-Dateien nach Eigenschaften und schlägt Zuordnungen vor
   - Manuelle Zuordnungen können erstellt, bearbeitet und gelöscht werden
   - Zuordnungen werden in der Datenbank gespeichert und bei Import/Export angewendet

3. **Eigenschafts-Überschreibungen**:
   - Benutzer kann im Override-Tab artikelspezifische und kategoriebasierte Überschreibungen verwalten
   - Überschreibungen können für einzelne Artikel oder für ganze Kategorien erstellt werden
   - Diese werden bei der Datenansicht und beim Export berücksichtigt

4. **Datenansicht**:
   - `DataViewTab` lädt Produkte aus der Datenbank mit `DatabaseManager.get_all_products()`
   - Die Produkte können nach Kategorie gefiltert werden
   - Wenn ein Produkt ausgewählt wird, werden dessen Eigenschaften mit Überschreibungen geladen
   - Eigenschaften können direkt im Datenansichts-Tab bearbeitet werden

5. **Export-Prozess**:
   - Benutzer wählt Exportoptionen im Export-Tab
   - `ExportWorker` wird gestartet und ruft Daten aus der Datenbank ab
   - Eigenschafts-Überschreibungen werden angewendet
   - Je nach Einstellung werden HTML-Tabellen für die Produktbeschreibung generiert
   - Die Daten werden im CSV-Format für den Shop-Import gespeichert

## Besondere Funktionalitäten

1. **HTML-Parsing-Strategien**:
   - Erkennung von Tabellen mit BeautifulSoup
   - Extraktion von Eigenschaften aus verschiedenen Tabellenformaten
   - Suche nach Eigenschaften außerhalb von Tabellen mit regulären Ausdrücken

2. **Normalisierung von Eigenschaften**:
   - Übersetzung zwischen deutschen und englischen Eigenschaftsnamen
   - Extraktion von numerischen Werten und Einheiten aus Texteigenschaften
   - Vereinheitlichung von Temperatur- und Maßangaben

3. **Dynamische Eigenschaftserkennung**:
   - Automatische Erkennung neuer Eigenschaften in Import-Dateien
   - Registrierung dieser Eigenschaften in der Datenbank
   - Vorschläge für Attributzuordnungen basierend auf Namensähnlichkeit

4. **Attributzuordnung**:
   - Mapping von unterschiedlich benannten Attributen auf standardisierte Namen
   - Unterstützung für manuelle und automatische Zuordnungen
   - Import/Export von Zuordnungsdefinitionen

5. **Eigenschafts-Überschreibungen**:
   - Artikelspezifische Überschreibungen für individuelle Anpassungen
   - Kategoriebasierte Überschreibungen für gruppenbasierte Anpassungen
   - Priorisierung von Überschreibungen (artikelspezifisch > kategoriebasiert > Standard)

6. **Mehrsprachige Unterstützung**:
   - Verarbeitung von deutschen (`p_desc.de`) und englischen (`p_desc.en`) Produktbeschreibungen
   - Speicherung von Eigenschaften mit Sprachkennzeichnung
   - Sprachspezifische Attributmappings und Überschreibungen

7. **Erweitertes Datenbank-Schema**:
   - `Products`-Tabelle für Produktbasisinformationen, inkl. Kategorie
   - `Properties`-Tabelle für extrahierte Eigenschaften
   - `PropertyDefinitions`-Tabelle für Standardisierung von Eigenschaftsnamen
   - `PropertyMappings`-Tabelle für die Zuordnung von Attributnamen
   - `PropertyOverrides`-Tabelle für artikelspezifische Überschreibungen
   - `CategoryPropertyOverrides`-Tabelle für kategoriebasierte Überschreibungen

8. **Multithreading**:
   - Verwendung von QThread für Import- und Exportprozesse, um die Benutzeroberfläche reaktionsfähig zu halten
   - Fortschritts- und Statusaktualisierungen während der Verarbeitung

## Neues erweitertes Datenbankschema

```sql
-- Products table for main product information
CREATE TABLE Products (
    article_id TEXT PRIMARY KEY,
    name TEXT,
    price REAL,
    stock INTEGER,
    category TEXT
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

-- PropertyMappings for mapping different attribute names to standard names
CREATE TABLE PropertyMappings (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name TEXT,  -- Original name found in CSV
    standard_name TEXT,  -- Name to map to
    language TEXT,       -- 'de' or 'en'
    confidence REAL,     -- Confidence score for automatic mappings
    UNIQUE(original_name, language)
);

-- PropertyOverrides for article-specific property overrides
CREATE TABLE PropertyOverrides (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT,
    property_name TEXT,
    override_value TEXT,
    language TEXT,  -- 'de' or 'en'
    FOREIGN KEY (article_id) REFERENCES Products(article_id)
);

-- CategoryPropertyOverrides for category-based property overrides
CREATE TABLE CategoryPropertyOverrides (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    property_name TEXT,
    override_value TEXT,
    language TEXT,  -- 'de' or 'en'
);

-- ImportHistory to track imported files and detected properties
CREATE TABLE ImportHistory (
    import_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    new_properties_count INTEGER,
    products_count INTEGER
);

-- NewPropertiesLog to log newly detected properties
CREATE TABLE NewPropertiesLog (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER,
    property_name TEXT,
    language TEXT,
    detected_in_count INTEGER,  -- Number of products this property was found in
    suggested_mapping TEXT,
    FOREIGN KEY (import_id) REFERENCES ImportHistory(import_id)
);
```
