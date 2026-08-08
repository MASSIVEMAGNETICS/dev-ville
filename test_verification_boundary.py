"""Tests for Dev-Ville's evidence-backed verification boundary."""
import unittest

from verification_boundary import VerificationBoundary


GOOD_BACKEND = '''
class BackendService:
    def __init__(self):
        self.data = {}
        self.started = False

    def start(self):
        self.started = True
        return True

    def process_request(self, method, path, data=None):
        key = path.strip("/")
        if method == "POST":
            self.data[key] = dict(data or {})
            return {"status": 201}
        if method == "GET":
            if key not in self.data:
                return {"status": 404}
            return {"status": 200, "data": self.data[key]}
        if method == "PUT":
            if key not in self.data:
                return {"status": 404}
            self.data[key].update(data or {})
            return {"status": 200}
        if method == "DELETE":
            if key not in self.data:
                return {"status": 404}
            del self.data[key]
            return {"status": 200}
        return {"status": 405}

    def health_check(self):
        return {"status": "healthy" if self.started else "stopped"}
'''

BAD_BACKEND = GOOD_BACKEND.replace(
    'return {"status": 201}', 'return {"status": 500}', 1
)


class VerificationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.boundary = VerificationBoundary(timeout_seconds=5)

    def _bundle(self, source):
        primary = {
            "filename": "backend_123.py",
            "content": source,
            "description": "Develop backend services",
        }
        tests = self.boundary.generate_test_artifacts(
            [primary], "Develop backend services"
        )
        return [primary] + tests

    def test_good_backend_passes_real_behavioral_tests(self):
        receipt = self.boundary.verify(
            self._bundle(GOOD_BACKEND),
            ticket_id=1,
            ticket_title="Develop backend services",
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(len(receipt.artifact_sha256), 64)
        self.assertEqual(len(receipt.evidence_sha256), 64)

    def test_broken_behavior_fails(self):
        receipt = self.boundary.verify(
            self._bundle(BAD_BACKEND),
            ticket_id=2,
            ticket_title="Develop backend services",
        )
        self.assertFalse(receipt.passed)
        failed = {
            check["name"]
            for check in receipt.checks
            if check["required"] and not check["passed"]
        }
        self.assertIn("behavioral_test_execution", failed)

    def test_syntax_error_fails_compile(self):
        primary = {
            "filename": "backend_999.py",
            "content": "class BackendService(:\n    pass\n",
            "description": "Develop backend services",
        }
        receipt = self.boundary.verify(
            [primary], ticket_id=3, ticket_title="Develop backend services"
        )
        self.assertFalse(receipt.passed)
        failed = {
            check["name"]
            for check in receipt.checks
            if check["required"] and not check["passed"]
        }
        self.assertIn("python_compile", failed)
        self.assertIn("behavioral_tests_present", failed)

    def test_path_traversal_is_rejected(self):
        receipt = self.boundary.verify(
            [{"filename": "../escape.py", "content": "print('x')"}],
            ticket_id=4,
            ticket_title="unsafe",
        )
        self.assertFalse(receipt.passed)
        self.assertTrue(
            any(
                check["name"] == "artifact_bundle_hash" and not check["passed"]
                for check in receipt.checks
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
