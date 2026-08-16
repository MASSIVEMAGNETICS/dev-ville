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

    def test_human_termination_authority_cannot_be_removed(self):
        altered = copy.deepcopy(self.constitution)
        altered["continuity"]["human_termination_permitted"] = False
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(altered, self.genesis, self.manifest)

    def test_human_abandonment_authority_cannot_be_removed(self):
        altered = copy.deepcopy(self.constitution)
        altered["continuity"]["human_abandonment_permitted"] = False
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(altered, self.genesis, self.manifest)

    def test_software_cannot_block_human_exit(self):
        altered = copy.deepcopy(self.constitution)
        altered["human_sovereignty"]["software_may_block_human_exit"] = True
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(altered, self.genesis, self.manifest)

    def test_termination_must_preserve_provenance(self):
        altered = copy.deepcopy(self.constitution)
        altered["human_sovereignty"]["termination_preserves_provenance"] = False
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(altered, self.genesis, self.manifest)

    def test_terminated_state_is_representable_without_erasing_history(self):
        altered = copy.deepcopy(self.manifest)
        altered["operating_status"] = "terminated"
        constitution_node = next(item for item in altered["nodes"] if item["id"] == "empire.constitution")
        capital_node = next(item for item in altered["nodes"] if item["id"] == "capital.genesis")
        constitution_node["status"] = "archived"
        capital_node["status"] = "archived"
        validate_constitution(self.constitution, self.genesis, altered)

    def test_invalid_operating_status_is_rejected(self):
        altered = copy.deepcopy(self.manifest)
        altered["operating_status"] = "immortal"
        with self.assertRaises(ConstitutionViolation):
            validate_constitution(self.constitution, self.genesis, altered)

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

    def test_manifest_must_preserve_human_termination_authority(self):
        altered = copy.deepcopy(self.manifest)
        node = next(item for item in altered["nodes"] if item["id"] == "empire.constitution")
        node["metadata"]["human_termination_permitted"] = False
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
