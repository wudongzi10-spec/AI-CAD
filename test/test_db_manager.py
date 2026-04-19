import os
import unittest

from database.db_manager import DatabaseManager


class DatabaseManagerReindexTests(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_history_reindex.db"
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "database", self.db_name)
        self.db_path = os.path.abspath(self.db_path)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = DatabaseManager(db_name=self.db_name)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_delete_reindexes_ids_and_clears_missing_source_reference(self):
        first_id = self.db.insert_history("first record")
        second_id = self.db.insert_history("second record")
        third_id = self.db.insert_history("third record", source_record_id=second_id)

        self.assertEqual((first_id, second_id, third_id), (1, 2, 3))

        deleted_rows = self.db.delete_history(second_id)
        self.assertEqual(deleted_rows, 1)

        first_record = self.db.get_history_by_id(1)
        second_record = self.db.get_history_by_id(2)

        self.assertEqual(first_record["instruction"], "first record")
        self.assertEqual(second_record["instruction"], "third record")
        self.assertIsNone(second_record["source_record_id"])
        self.assertIsNone(self.db.get_history_by_id(3))

        fourth_id = self.db.insert_history("fourth record", source_record_id=2)
        fourth_record = self.db.get_history_by_id(fourth_id)

        self.assertEqual(fourth_id, 3)
        self.assertEqual(fourth_record["source_record_id"], 2)

        history = sorted(self.db.get_all_history(limit=10), key=lambda item: item["id"])
        self.assertEqual([item["id"] for item in history], [1, 2, 3])
        self.assertEqual(
            [item["instruction"] for item in history],
            ["first record", "third record", "fourth record"],
        )


if __name__ == "__main__":
    unittest.main()
