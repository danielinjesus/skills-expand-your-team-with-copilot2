import copy
import sys
import unittest
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(REPO_SRC))

from backend.routers import activities as activities_router
from fastapi import HTTPException

MISSING = object()


class FakeActivitiesCollection:
    def __init__(self, documents):
        self.documents = documents
        self.last_query = None

    def find(self, query):
        self.last_query = query
        return [
            copy.deepcopy(document)
            for document in self.documents
            if self._matches(document, query)
        ]

    def _matches(self, document, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._matches(document, option) for option in value):
                    return False
                continue

            field_value = self._get_field_value(document, key)

            if isinstance(value, dict):
                if "$in" in value and not self._matches_in(field_value, value["$in"]):
                    return False
                if "$gte" in value and field_value < value["$gte"]:
                    return False
                if "$lte" in value and field_value > value["$lte"]:
                    return False
                if "$exists" in value and (field_value is not MISSING) != value["$exists"]:
                    return False
            elif field_value is MISSING or field_value != value:
                return False

        return True

    def _get_field_value(self, document, dotted_key):
        value = document
        for key in dotted_key.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return MISSING
        return value

    def _matches_in(self, field_value, expected_values):
        if field_value is MISSING:
            return False

        if isinstance(field_value, list):
            return any(item in expected_values for item in field_value)

        return field_value in expected_values


class GetActivitiesDifficultyTests(unittest.TestCase):
    def setUp(self):
        self.original_collection = activities_router.activities_collection
        activities_router.activities_collection = FakeActivitiesCollection(
            [
                {
                    "_id": "Chess Club",
                    "description": "Learn strategies",
                    "schedule_details": {
                        "days": ["Monday"],
                        "start_time": "15:15",
                        "end_time": "16:45",
                    },
                    "difficulty": "Beginner",
                    "participants": [],
                    "max_participants": 10,
                },
                {
                    "_id": "Math Club",
                    "description": "Solve problems",
                    "schedule_details": {
                        "days": ["Tuesday"],
                        "start_time": "07:15",
                        "end_time": "08:00",
                    },
                    "difficulty": "Intermediate",
                    "participants": [],
                    "max_participants": 10,
                },
                {
                    "_id": "Art Club",
                    "description": "Create art",
                    "schedule_details": {
                        "days": ["Thursday"],
                        "start_time": "15:15",
                        "end_time": "17:00",
                    },
                    "participants": [],
                    "max_participants": 15,
                },
                {
                    "_id": "Drama Club",
                    "description": "Perform on stage",
                    "schedule_details": {
                        "days": ["Wednesday"],
                        "start_time": "15:30",
                        "end_time": "17:30",
                    },
                    "difficulty": None,
                    "participants": [],
                    "max_participants": 20,
                },
            ]
        )

    def tearDown(self):
        activities_router.activities_collection = self.original_collection

    def test_returns_all_activities_without_difficulty_filter(self):
        activities = activities_router.get_activities()

        self.assertEqual(
            set(activities.keys()),
            {"Chess Club", "Math Club", "Art Club", "Drama Club"},
        )

    def test_specific_difficulty_includes_level_agnostic_activities(self):
        activities = activities_router.get_activities(difficulty="Beginner")

        self.assertEqual(set(activities.keys()), {"Chess Club", "Art Club", "Drama Club"})

    def test_all_difficulty_returns_only_level_agnostic_activities(self):
        activities = activities_router.get_activities(difficulty="All")

        self.assertEqual(set(activities.keys()), {"Art Club", "Drama Club"})

    def test_invalid_difficulty_raises_bad_request(self):
        with self.assertRaises(HTTPException) as context:
            activities_router.get_activities(difficulty="Expert")

        self.assertEqual(context.exception.status_code, 400)

    def test_day_and_difficulty_filters_work_together(self):
        activities = activities_router.get_activities(day="Monday", difficulty="Beginner")

        self.assertEqual(set(activities.keys()), {"Chess Club"})


if __name__ == "__main__":
    unittest.main()
