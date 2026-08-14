import copy
import json
from pathlib import Path
import unittest

from empire_constitution import ConstitutionViolation, validate_constitution, validate_files


ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class EmpireConstitutionTests(unittest.TestCase):
    def setUp(self):
        self.constitution = load("empire_constitution.json")
        self.genesis = load("empire_genesis_capital.json")
        self.manifest = load("empire_manifest.json")

    def test_repository_files_validate(self):
        validate_files(
            ROOT / "empire_constitution.json",
            ROOT / "empire_genesis_capital.json",
            ROOT / "empire_manifest.json",
        )

    def test_empire_cannot_be_made_terminable(self):
        altered = copy.deepcopy(self.constitution)
        altered["continuity"]["termination_permitted"] = True
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(altered, self.genesis, self.manifest)

    def test_empire_cannot_be_made_abandonable(self):
        altered = copy.deepcopy(self.constitution)
        altered["continuity"]["abandonment_permitted"] = True
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(altered, self.genesis, self.manifest)

    def test_genesis_source_cannot_be_rewritten(self):
        altered = copy.deepcopy(self.genesis)
        altered["asset"]["source"] = "Unknown"
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, altered, self.manifest)

    def test_genesis_designation_cannot_be_rewritten(self):
        altered = copy.deepcopy(self.genesis)
        altered["asset"]["user_designated_amount_cents"] = 0
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, altered, self.manifest)

    def test_genesis_provenance_cannot_be_deleted(self):
        altered = copy.deepcopy(self.genesis)
        altered["governance"]["provenance_may_be_deleted"] = True
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, altered, self.manifest)

    def test_genesis_principal_remains_deployable(self):
        altered = copy.deepcopy(self.genesis)
        altered["governance"]["principal_may_be_deployed"] = False
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, altered, self.manifest)

    def test_manifest_must_keep_constitution_active(self):
        altered = copy.deepcopy(self.manifest)
        node = next(item for item in altered["nodes"] if item["id"] == "empire.constitution")
        node["status"] = "archived"
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, self.genesis, altered)

    def test_manifest_must_keep_genesis_capital_canonical(self):
        altered = copy.deepcopy(self.manifest)
        node = next(item for item in altered["nodes"] if item["id"] == "capital.genesis")
        node["canonical"] = False
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, self.genesis, altered)


if __name__ == "__main__":
    unittest.main()
