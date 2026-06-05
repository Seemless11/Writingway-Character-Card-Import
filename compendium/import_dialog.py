"""
Import Dialog for SillyTavern characters
Provides UI to import characters and add them to the compendium
"""

import os
from gettext import gettext as _

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QFormLayout,
)

from util.sillytavern_importer import SillyTavernImporter, SillyTavernImportError, validate_import_result
from compendium.compendium_manager import CompendiumManager


class SillyTavernImportDialog(QDialog):
    """Dialog for importing SillyTavern characters into the compendium"""

    import_complete = pyqtSignal(str)  # Emits character name on success

    def __init__(self, project_name: str, parent=None):
        """
        Initialize the import dialog.
        
        Args:
            project_name: Name of the project to import into
            parent: Parent widget
        """
        super().__init__(parent)
        self.project_name = project_name
        self.manager = CompendiumManager(project_name)
        self.importer = SillyTavernImporter()
        self.imported_data = None
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle(_("Import SillyTavern Character"))
        self.setGeometry(100, 100, 500, 300)

        layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        file_label = QLabel(_("Character File:"))
        self.file_label_display = QLabel(_("No file selected"))
        self.file_label_display.setStyleSheet("color: #999;")
        self.browse_button = QPushButton(_("Browse..."))
        self.browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.file_label_display)
        file_layout.addWidget(self.browse_button)
        layout.addLayout(file_layout)

        # Category selection
        category_layout = QFormLayout()
        category_label = QLabel(_("Category:"))
        self.category_combo = QComboBox()
        self.populate_categories()
        category_layout.addRow(category_label, self.category_combo)
        layout.addLayout(category_layout)

        # Preview section
        self.preview_label = QLabel(_("Preview:"))
        self.preview_text = QLabel(_("Select a file to preview character data"))
        self.preview_text.setStyleSheet("color: #666; font-size: 10pt; padding: 10px; background-color: #f5f5f5;")
        self.preview_text.setWordWrap(True)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_text)

        # Buttons
        button_layout = QHBoxLayout()
        self.import_button = QPushButton(_("Import Character"))
        self.import_button.clicked.connect(self.import_character)
        self.import_button.setEnabled(False)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def populate_categories(self):
        """Load categories from compendium into dropdown"""
        try:
            compendium_data = self.manager.load_data()
            categories = [cat.get("name", "") for cat in compendium_data.get("categories", [])]
            
            if categories:
                self.category_combo.addItems(sorted(categories))
                # Set to "Characters" if it exists
                if "Characters" in categories:
                    self.category_combo.setCurrentText("Characters")
            else:
                self.category_combo.addItem("Characters")
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to load categories: {}").format(str(e)))
            self.category_combo.addItem("Characters")

    def browse_file(self):
        """Open file browser to select character file"""
        file_path, _Filter = QFileDialog.getOpenFileName(
            None,
            _("Select SillyTavern Character File"),
            "",
            "Character Files (*.json *.png);;JSON Files (*.json);;PNG Files (*.png);;All Files (*)"
        )

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        """
        Load and preview a character file.
        
        Args:
            file_path: Path to the file
        """
        try:
            # Validate format
            file_format = self.importer.detect_format(file_path)

            # Import the file
            self.imported_data = self.importer.import_file(file_path)

            # Validate
            is_valid, error_msg = validate_import_result(self.imported_data)
            if not is_valid:
                raise SillyTavernImportError(error_msg)

            # Update UI
            self.file_label_display.setText(os.path.basename(file_path))
            self.file_label_display.setStyleSheet("color: #000;")
            self.import_button.setEnabled(True)

            # Show preview
            self.show_preview()

        except SillyTavernImportError as e:
            QMessageBox.critical(self, _("Import Error"), _("Failed to import file:\n{}").format(str(e)))
            self.imported_data = None
            self.import_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Unexpected error:\n{}").format(str(e)))
            self.imported_data = None
            self.import_button.setEnabled(False)

    def show_preview(self):
        """Display preview of character data"""
        if not self.imported_data:
            return

        preview_lines = []
        preview_lines.append(f"<b>{_('Name')}:</b> {self.imported_data['name']}")

        if self.imported_data.get("personality"):
            personality_preview = self.imported_data["personality"][:100]
            if len(self.imported_data["personality"]) > 100:
                personality_preview += "..."
            preview_lines.append(f"<b>{_('Personality')}:</b> {personality_preview}")

        if self.imported_data.get("scenario"):
            scenario_preview = self.imported_data["scenario"][:100]
            if len(self.imported_data["scenario"]) > 100:
                scenario_preview += "..."
            preview_lines.append(f"<b>{_('Scenario')}:</b> {scenario_preview}")

        if self.imported_data.get("image_path"):
            preview_lines.append(f"<b>{_('Image')}:</b> {_('Detected')}")

        preview_html = "<br>".join(preview_lines)
        self.preview_text.setText(preview_html)

    def import_character(self):
        """Import the character into the compendium"""
        if not self.imported_data:
            QMessageBox.warning(self, _("Warning"), _("No character data loaded"))
            return

        try:
            category = self.category_combo.currentText()

            # Convert to compendium format
            entry_data = self.importer.convert_to_compendium_entry(self.imported_data, category)

            # Load current compendium data
            compendium_data = self.manager.load_data()

            # Find or create category
            category_obj = None
            for cat in compendium_data.get("categories", []):
                if cat.get("name") == category:
                    category_obj = cat
                    break

            if not category_obj:
                category_obj = {"name": category, "entries": []}
                compendium_data["categories"].append(category_obj)

            # Check for duplicate
            for entry in category_obj.get("entries", []):
                if entry.get("name") == entry_data["name"]:
                    result = QMessageBox.question(
                        self,
                        _("Character Exists"),
                        _("A character named '{}' already exists. Replace it?").format(entry_data["name"]),
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if result == QMessageBox.Yes:
                        # Remove old entry
                        category_obj["entries"] = [e for e in category_obj["entries"] if e.get("name") != entry_data["name"]]
                        # Remove from extensions
                        if entry_data["name"] in compendium_data["extensions"]["entries"]:
                            del compendium_data["extensions"]["entries"][entry_data["name"]]
                    else:
                        return

            # Add new entry
            from uuid import uuid4
            entry_data["uuid"] = str(uuid4())
            category_obj["entries"].append({
                "name": entry_data["name"],
                "content": entry_data["content"],
                "uuid": entry_data["uuid"]
            })

            # Add extensions
            compendium_data["extensions"]["entries"][entry_data["name"]] = entry_data["extended"]

            # Save to file
            self.manager.save_data(compendium_data)

            # Success
            QMessageBox.information(
                self,
                _("Import Successful"),
                _("Character '{}' imported successfully to '{}'").format(entry_data["name"], category)
            )

            self.import_complete.emit(entry_data["name"])
            self.accept()

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self,
                _("Import Failed"),
                _("Failed to import character:\n{}").format(str(e))
            )
            print(traceback.format_exc())


def show_import_dialog(project_name: str, parent=None) -> bool:
    """
    Show the SillyTavern import dialog.
    
    Args:
        project_name: Project to import into
        parent: Parent widget
        
    Returns:
        True if import was successful, False otherwise
    """
    dialog = SillyTavernImportDialog(project_name, parent)
    return dialog.exec_() == QDialog.Accepted
