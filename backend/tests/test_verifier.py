import os
import csv
import pytest
from backend.verifier import OutputVerifier

def test_csv_verification(tmp_path):
    verifier = OutputVerifier(data_dir=str(tmp_path))
    csv_file = tmp_path / "test.csv"
    
    # Test file missing
    res = verifier.verify_csv(str(csv_file))
    assert res["valid"] is False
    assert res["file_exists"] is False
    
    # Write valid CSV
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "organization", "eligibility", "deadline", "source_url", "match_explanation"])
        writer.writeheader()
        writer.writerow({
            "id": "1",
            "title": "Software Intern",
            "organization": "TechCorp",
            "eligibility": "CS Majors",
            "deadline": "2025-05-01",
            "source_url": "https://example.com",
            "match_explanation": "Great fit"
        })
        
    res_valid = verifier.verify_csv(str(csv_file))
    assert res_valid["valid"] is True
    assert res_valid["row_count"] == 1
    
    # Write CSV with duplicate ID
    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "organization", "eligibility", "deadline", "source_url", "match_explanation"])
        writer.writerow({
            "id": "1",
            "title": "Software Intern Duplicate",
            "organization": "TechCorp",
            "eligibility": "CS Majors",
            "deadline": "2025-05-01",
            "source_url": "https://example.com",
            "match_explanation": "Duplicate ID"
        })
        
    res_dup = verifier.verify_csv(str(csv_file))
    assert res_dup["valid"] is False
    assert "Duplicate record IDs found" in res_dup["errors"][0]
