"""Contracts for Victor's persistent local authority identity."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest

from victor_identity_kernel import IdentityKernel
from victor_sovereign_driver import VictorSovereignDriver


class IdentityKernelTests(unittest.TestCase):
    def test_hmac_proof_verifies_and_tampering_fails(self):
        identity = IdentityKernel(key=b"k" * 32)
        envelope = {"actor": "victor.driver", "action": "authorize", "n": 1}
        proof = identity.sign(envelope)
        self.assertTrue(identity.verify(envelope, proof))
        tampered = dict(envelope)
        tampered["n"] = 2
        self.assertFalse(identity.verify(tampered, proof))

    def test_sovereign_driver_authority_events_are_reconstructably_signed(self):
        driver = VictorSovereignDriver(identity_key=b"v" * 32)
        driver.start_project("Create a backend API")
        signed = [
            event
            for event in driver.vehicle.get_trace0_events()
            if event.get("actor") == "victor.driver"
            and (event.get("provenance") or {}).get("identity_proof")
        ]
        self.assertGreater(len(signed), 0)
        self.assertTrue(all(driver.verify_authority_event(event) for event in signed))

        tampered = copy.deepcopy(signed[-1])
        tampered["payload"]["tampered"] = True
        self.assertFalse(driver.verify_authority_event(tampered))

    def test_saved_identity_requires_same_key_for_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/project.json"
            driver = VictorSovereignDriver(identity_key=b"a" * 32)
            driver.start_project("Create a backend API")
            driver.save_project(path)

            same = VictorSovereignDriver(identity_key=b"a" * 32)
            same.load_project(path)
            self.assertEqual(same.identity.key_id, driver.identity.key_id)

            different = VictorSovereignDriver(identity_key=b"b" * 32)
            with self.assertRaises(ValueError):
                different.load_project(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
