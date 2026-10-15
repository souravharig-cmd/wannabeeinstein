import os
import csv
from typing import Dict, Any, List

class OutputVerifier:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def verify_csv(self, file_path: str, required_columns: List[str] = None) -> Dict[str, Any]:
        if required_columns is None:
            required_columns = ["id", "title", "organization", "eligibility", "deadline", "source_url", "match_explanation"]
            
        full_path = file_path if os.path.isabs(file_path) else os.path.join(self.data_dir, file_path)
        
        if not os.path.exists(full_path):
            return {
                "valid": False,
                "file_exists": False,
                "errors": [f"CSV file does not exist at {full_path}"]
            }

        try:
            with open(full_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                
                missing_cols = [col for col in required_columns if col not in headers]
                if missing_cols:
                    return {
                        "valid": False,
                        "file_exists": True,
                        "errors": [f"Missing required columns: {missing_cols}"]
                    }

                rows = list(reader)
                if len(rows) == 0:
                    return {
                        "valid": False,
                        "file_exists": True,
                        "errors": ["CSV file is empty"]
                    }

                ids = [r.get("id") for r in rows if r.get("id")]
                duplicate_ids = [item for item in set(ids) if ids.count(item) > 1]
                
                if duplicate_ids:
                    return {
                        "valid": False,
                        "file_exists": True,
                        "row_count": len(rows),
                        "errors": [f"Duplicate record IDs found: {duplicate_ids}"]
                    }

                return {
                    "valid": True,
                    "file_exists": True,
                    "row_count": len(rows),
                    "headers": headers,
                    "errors": []
                }
        except Exception as e:
            return {
                "valid": False,
                "file_exists": True,
                "errors": [f"Failed to parse CSV file: {str(e)}"]
            }

    def verify_email_drafts(self, draft_paths: List[str], expected_count: int = 3) -> Dict[str, Any]:
        errors = []
        verified_files = []

        if len(draft_paths) < expected_count:
            errors.append(f"Expected {expected_count} draft files, but got {len(draft_paths)}")

        for path in draft_paths:
            full_path = path if os.path.isabs(path) else os.path.join(self.data_dir, path)
            if not os.path.exists(full_path):
                errors.append(f"Draft file not found: {path}")
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "Subject:" not in content or "Dear" not in content:
                        errors.append(f"Draft {path} lacks standard email structure")
                    else:
                        verified_files.append(path)
            except Exception as e:
                errors.append(f"Error reading draft {path}: {str(e)}")

        is_valid = len(errors) == 0 and len(verified_files) >= expected_count
        return {
            "valid": is_valid,
            "draft_count": len(verified_files),
            "errors": errors
        }
