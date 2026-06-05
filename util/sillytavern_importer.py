"""
SillyTavern Character Importer for Writingway
Handles both JSON and PNG character card files (V1, V2, V3 spec)
"""

import base64
import json
import os
import struct
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class SillyTavernImportError(Exception):
    """Custom exception for import errors"""
    pass


class SillyTavernImporter:
    """Importer for SillyTavern character card files (JSON and PNG)"""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(os.path.expanduser("~"), ".writingway_imports")
        os.makedirs(self.output_dir, exist_ok=True)

    def detect_format(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise SillyTavernImportError(f"File not found: {file_path}")
        ext = Path(file_path).suffix.lower()
        if ext == ".json":
            return "json"
        elif ext == ".png":
            return "png"
        else:
            raise SillyTavernImportError(f"Unsupported file format: {ext}. Expected .json or .png")

    def _read_png_text_chunks(self, png_path: str) -> Dict[str, bytes]:
        """
        Read all tEXt chunks from a PNG file.
        Returns dict of keyword -> raw value bytes.
        """
        chunks = {}
        with open(png_path, "rb") as f:
            sig = f.read(8)
            if sig != b"\x89PNG\r\n\x1a\n":
                raise SillyTavernImportError("File is not a valid PNG")
            while True:
                length_data = f.read(4)
                if len(length_data) < 4:
                    break
                length = struct.unpack(">I", length_data)[0]
                chunk_type = f.read(4).decode("ascii", errors="replace")
                data = f.read(length)
                f.read(4)  # CRC
                if chunk_type == "tEXt":
                    null_idx = data.find(b"\x00")
                    if null_idx != -1:
                        keyword = data[:null_idx].decode("utf-8", errors="replace")
                        value = data[null_idx + 1:]
                        chunks[keyword] = value
                if chunk_type == "IEND":
                    break
        return chunks

    def _extract_json_from_png(self, png_path: str) -> Dict[str, Any]:
        """
        Extract character JSON from a PNG card file.
        Supports V2 (keyword: chara) and V3 (keyword: ccv3).
        """
        chunks = self._read_png_text_chunks(png_path)

        # Try V3 first, then V2
        raw = chunks.get("ccv3") or chunks.get("chara")

        if raw is None:
            raise SillyTavernImportError(
                "No character data found in PNG. "
                "Make sure this is a SillyTavern character card, not a plain image."
            )

        try:
            decoded = base64.b64decode(raw)
            return json.loads(decoded.decode("utf-8"))
        except Exception as e:
            raise SillyTavernImportError(f"Failed to decode character data: {str(e)}")

    def _normalize_card_data(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize V1/V2/V3 card data to a flat dict of fields.
        V2/V3 wraps everything inside a 'data' key.
        V1 has fields at the top level.
        """
        if "data" in raw and isinstance(raw["data"], dict):
            # V2 or V3
            return raw["data"]
        else:
            # V1 - fields are at top level
            return raw

    def _parse_json_file(self, json_path: str) -> Dict[str, Any]:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise SillyTavernImportError(f"Invalid JSON file: {str(e)}")
        except Exception as e:
            raise SillyTavernImportError(f"Error reading JSON file: {str(e)}")

    def _extract_image_from_png(self, png_path: str) -> Optional[str]:
        try:
            with open(png_path, "rb") as f:
                image_data = f.read()
            return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            print(f"Warning: Could not extract image from PNG: {str(e)}")
            return None

    def _save_image_to_disk(self, image_base64: str, character_name: str) -> str:
        try:
            safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '_', '-')).strip()
            filename = f"{safe_name}_avatar.png"
            filepath = os.path.join(self.output_dir, filename)
            image_data = base64.b64decode(image_base64)
            with open(filepath, "wb") as f:
                f.write(image_data)
            return filepath
        except Exception as e:
            raise SillyTavernImportError(f"Failed to save image: {str(e)}")

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """
        Import a SillyTavern character card file (.json or .png).
        Returns a flat dict ready for Writingway compendium.
        """
        try:
            file_format = self.detect_format(file_path)

            if file_format == "png":
                raw_data = self._extract_json_from_png(file_path)
                image_base64 = self._extract_image_from_png(file_path)
            else:
                raw_data = self._parse_json_file(file_path)
                image_base64 = None

            # Normalize V1/V2/V3 into flat fields
            data = self._normalize_card_data(raw_data)

            name = data.get("name", "").strip()
            if not name:
                raise SillyTavernImportError("Character data is missing a 'name' field")

            result = {
                "name": name,
                "description": data.get("description", "").strip(),
                "personality": data.get("personality", "").strip(),
                "scenario": data.get("scenario", "").strip(),
                "first_message": data.get("first_mes", "").strip(),
                "examples": data.get("mes_example", "").strip(),
                "system_prompt": data.get("system_prompt", "").strip(),
                "creator_notes": data.get("creator_notes", "").strip(),
                "image_path": None,
                "image_base64": None,
                "raw_data": data
            }

            if image_base64:
                try:
                    result["image_path"] = self._save_image_to_disk(image_base64, name)
                    result["image_base64"] = image_base64
                except SillyTavernImportError as e:
                    print(f"Warning: {str(e)}")

            return result

        except SillyTavernImportError:
            raise
        except Exception as e:
            raise SillyTavernImportError(f"Unexpected error during import: {str(e)}")

    def convert_to_compendium_entry(self, import_data: Dict[str, Any], category: str = "Characters") -> Dict[str, Any]:
        return {
            "name": import_data["name"],
            "content": self._build_compendium_content(import_data),
            "uuid": None,
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
        lines = []

        if import_data.get("description"):
            lines.append("## Description\n")
            lines.append(import_data["description"])

        if import_data.get("personality"):
            lines.append("\n## Personality\n")
            lines.append(import_data["personality"])

        if import_data.get("scenario"):
            lines.append("\n## Scenario\n")
            lines.append(import_data["scenario"])

        if import_data.get("first_message"):
            lines.append("\n## First Message\n")
            lines.append(import_data["first_message"])

        if import_data.get("examples"):
            lines.append("\n## Example Dialogue\n")
            lines.append(import_data["examples"])

        if import_data.get("system_prompt"):
            lines.append("\n## System Prompt\n")
            lines.append(import_data["system_prompt"])

        if import_data.get("creator_notes"):
            lines.append("\n## Creator Notes\n")
            lines.append(import_data["creator_notes"])

        return "\n".join(lines).strip()


def validate_import_result(import_data: Dict[str, Any]) -> Tuple[bool, str]:
    errors = []
    if not import_data.get("name"):
        errors.append("Character name is missing or empty")
    if errors:
        return False, "; ".join(errors)
    return True, ""
