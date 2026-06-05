"""
SillyTavern Character Importer for Writingway
Handles both JSON and PNG character files from SillyTavern
"""

import base64
import json
import os
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class SillyTavernImportError(Exception):
    """Custom exception for import errors with actual messages"""
    pass


class SillyTavernImporter:
    """Importer for SillyTavern character files (JSON and PNG)"""

    # SillyTavern JSON fields that map to Writingway compendium
    SILLYTAVERN_FIELDS = {
        "name": "name",
        "description": "personality",  # Main character description
        "scenario": "scenario",
        "first_mes": "first_message",
        "char_persona": "personality",
        "world_scenario": "world_scenario",
        "example_dialogue": "examples",
    }

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the importer.
        
        Args:
            output_dir: Directory to save extracted images. If None, uses temp location.
        """
        self.output_dir = output_dir or os.path.join(os.path.expanduser("~"), ".writingway_imports")
        os.makedirs(self.output_dir, exist_ok=True)

    def detect_format(self, file_path: str) -> str:
        """
        Detect the format of a character file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            'json', 'png', or raises SillyTavernImportError
        """
        if not os.path.exists(file_path):
            raise SillyTavernImportError(f"File not found: {file_path}")

        file_ext = Path(file_path).suffix.lower()

        if file_ext == ".json":
            return "json"
        elif file_ext == ".png":
            return "png"
        else:
            raise SillyTavernImportError(f"Unsupported file format: {file_ext}. Expected .json or .png")

    def _extract_json_from_png(self, png_path: str) -> Dict[str, Any]:
        """
        Extract character data from PNG file (SillyTavern embeds JSON in PNG).
        
        Args:
            png_path: Path to PNG file
            
        Returns:
            Parsed character data dictionary
            
        Raises:
            SillyTavernImportError: If extraction fails
        """
        try:
            with open(png_path, "rb") as f:
                data = f.read()

            # Look for "chara" marker in the PNG file (SillyTavern uses this)
            marker = b"chara"
            idx = data.rfind(marker)

            if idx == -1:
                raise SillyTavernImportError("No character data found in PNG file")

            # Extract the chunk after the marker
            chunk_data = data[idx + len(marker):]

            # Try to decompress and decode
            try:
                import zlib
                decompressed = zlib.decompress(chunk_data)
                char_data = json.loads(decompressed.decode("utf-8"))
                return char_data
            except Exception as e:
                raise SillyTavernImportError(f"Failed to decompress PNG data: {str(e)}")

        except SillyTavernImportError:
            raise
        except Exception as e:
            raise SillyTavernImportError(f"Error reading PNG file: {str(e)}")

    def _extract_image_from_png(self, png_path: str) -> Optional[str]:
        """
        Extract and save the PNG image as base64.
        
        Args:
            png_path: Path to PNG file
            
        Returns:
            Base64 encoded image or None if extraction fails
        """
        try:
            with open(png_path, "rb") as f:
                image_data = f.read()
            # Return base64 encoded data
            return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            print(f"Warning: Could not extract image from PNG: {str(e)}")
            return None

    def _parse_json_file(self, json_path: str) -> Dict[str, Any]:
        """
        Parse a JSON character file.
        
        Args:
            json_path: Path to JSON file
            
        Returns:
            Parsed character data
            
        Raises:
            SillyTavernImportError: If parsing fails
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise SillyTavernImportError(f"Invalid JSON file: {str(e)}")
        except Exception as e:
            raise SillyTavernImportError(f"Error reading JSON file: {str(e)}")

    def _validate_character_data(self, data: Dict[str, Any]) -> None:
        """
        Validate that the data contains required character fields.
        
        Args:
            data: Character data to validate
            
        Raises:
            SillyTavernImportError: If required fields are missing
        """
        if not data:
            raise SillyTavernImportError("Character data is empty")

        # SillyTavern typically has at minimum a name
        if "name" not in data or not data["name"]:
            raise SillyTavernImportError("Character data missing 'name' field")

    def _save_image_to_disk(self, image_base64: str, character_name: str) -> str:
        """
        Save base64 encoded image to disk.
        
        Args:
            image_base64: Base64 encoded image data
            character_name: Name of character for filename
            
        Returns:
            Path to saved image file
            
        Raises:
            SillyTavernImportError: If save fails
        """
        try:
            # Sanitize filename
            safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '_', '-')).strip()
            filename = f"{safe_name}_avatar.png"
            filepath = os.path.join(self.output_dir, filename)

            # Decode and save
            image_data = base64.b64decode(image_base64)
            with open(filepath, "wb") as f:
                f.write(image_data)

            return filepath
        except Exception as e:
            raise SillyTavernImportError(f"Failed to save image: {str(e)}")

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """
        Import a SillyTavern character file.
        
        Args:
            file_path: Path to character file (.json or .png)
            
        Returns:
            Dictionary with structure ready for Writingway compendium:
            {
                'name': str,
                'personality': str,
                'scenario': str,
                'first_message': str,
                'examples': str,
                'image_path': Optional[str],
                'image_base64': Optional[str],
                'raw_data': Dict
            }
            
        Raises:
            SillyTavernImportError: If import fails
        """
        try:
            file_format = self.detect_format(file_path)
            
            if file_format == "png":
                char_data = self._extract_json_from_png(file_path)
                image_base64 = self._extract_image_from_png(file_path)
            else:  # json
                char_data = self._parse_json_file(file_path)
                image_base64 = None

            # Validate the data
            self._validate_character_data(char_data)

            # Extract fields with fallbacks
            result = {
                "name": char_data.get("name", "Unknown Character").strip(),
                "personality": self._extract_text_field(char_data, ["char_persona", "personality", "description"]),
                "scenario": char_data.get("scenario", "").strip(),
                "first_message": char_data.get("first_mes", "").strip(),
                "examples": self._extract_examples(char_data),
                "image_path": None,
                "image_base64": None,
                "raw_data": char_data
            }

            # Save image if present
            if image_base64:
                try:
                    result["image_path"] = self._save_image_to_disk(image_base64, result["name"])
                    result["image_base64"] = image_base64
                except SillyTavernImportError as e:
                    print(f"Warning: {str(e)}")
                    # Continue without image

            return result

        except SillyTavernImportError:
            raise
        except Exception as e:
            raise SillyTavernImportError(f"Unexpected error during import: {str(e)}")

    @staticmethod
    def _extract_text_field(data: Dict[str, Any], field_names: list) -> str:
        """
        Extract text field with multiple fallback names.
        
        Args:
            data: Source data dictionary
            field_names: List of field names to try
            
        Returns:
            First non-empty field value or empty string
        """
        for field in field_names:
            value = data.get(field, "")
            if value and isinstance(value, str):
                return value.strip()
        return ""

    @staticmethod
    def _extract_examples(data: Dict[str, Any]) -> str:
        """
        Extract dialogue examples from various formats.
        
        Args:
            data: Character data
            
        Returns:
            Formatted examples string
        """
        examples = []

        # Check for example_dialogue field (array format)
        if "example_dialogue" in data and data["example_dialogue"]:
            examples.append(data["example_dialogue"])

        # Check for mes_example field (string format)
        if "mes_example" in data and data["mes_example"]:
            examples.append(data["mes_example"])

        return "\n---\n".join(examples).strip()

    def convert_to_compendium_entry(self, import_data: Dict[str, Any], category: str = "Characters") -> Dict[str, Any]:
        """
        Convert imported data to Writingway compendium entry format.
        
        Args:
            import_data: Data from import_file()
            category: Category to place character in (default: "Characters")
            
        Returns:
            Dictionary ready to add to compendium
        """
        return {
            "name": import_data["name"],
            "content": self._build_compendium_content(import_data),
            "uuid": None,  # Will be assigned by compendium manager
            "category": category,
            "extended": {
                "details": f"Imported from SillyTavern\nImage: {'Yes' if import_data['image_path'] else 'No'}",
                "tags": ["imported", "sillytavern"],
                "relationships": [],
                "images": [import_data["image_path"]] if import_data["image_path"] else []
            }
        }

    @staticmethod
    def _build_compendium_content(import_data: Dict[str, Any]) -> str:
        """
        Build the main content field for compendium entry.
        
        Args:
            import_data: Imported character data
            
        Returns:
            Formatted content string
        """
        lines = []

        if import_data["personality"]:
            lines.append("## Personality\n")
            lines.append(import_data["personality"])

        if import_data["scenario"]:
            lines.append("\n## Scenario\n")
            lines.append(import_data["scenario"])

        if import_data["first_message"]:
            lines.append("\n## First Message\n")
            lines.append(import_data["first_message"])

        if import_data["examples"]:
            lines.append("\n## Example Dialogue\n")
            lines.append(import_data["examples"])

        return "\n".join(lines).strip()


def validate_import_result(import_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate imported data structure.
    
    Args:
        import_data: Result from import_file()
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    errors = []

    if not import_data.get("name"):
        errors.append("Character name is missing or empty")

    if not isinstance(import_data.get("personality", ""), str):
        errors.append("Personality field is not valid text")

    if errors:
        return False, "; ".join(errors)

    return True, ""
