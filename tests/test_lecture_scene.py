import unittest

from app.services.lecture_scene import ensure_slide_scene, materialize_slides


def slide(**overrides):
    base = {
        "number": 1,
        "title": "A lesson",
        "equation": "y = 2x + 1",
        "narration": "A short lesson.",
        "explanation": "Connect the representation to the idea.",
        "visual_type": "equation",
        "steps": ["Find the input", "Apply the rule"],
    }
    base.update(overrides)
    return base


class LectureSceneMaterializationTests(unittest.TestCase):
    def test_subject_defaults_choose_distinct_archetypes(self):
        cases = {
            "math": "math_worked_example",
            "coding": "code_walkthrough",
            "science": "science_process",
            "general": "concept_comparison",
        }
        for subject, archetype in cases.items():
            with self.subTest(subject=subject):
                result = ensure_slide_scene(slide(), subject=subject)
                self.assertEqual(result["scene"]["type"], "basic_boxes")
                self.assertEqual(result["scene"]["archetype"], archetype)
                self.assertGreater(len(result["scene"]["objects"]), 0)

    def test_hint_selects_safe_archetype_without_model_geometry(self):
        result = ensure_slide_scene(
            slide(
                scene_hint={
                    "archetype": "science_force_vector",
                    "focus": "Cart",
                    "concepts": ["normal", "weight"],
                }
            ),
            subject="science",
        )
        self.assertEqual(result["scene"]["archetype"], "science_force_vector")
        self.assertEqual(
            {item["role"] for item in result["scene"]["objects"]},
            {"text", "science.body", "science.vector", "box.explain"},
        )

    def test_existing_scene_is_not_replaced(self):
        saved = {"type": "basic_boxes", "width": 20, "height": 20, "objects": []}
        result = ensure_slide_scene(slide(scene=saved), subject="math")
        self.assertIs(result["scene"], saved)

    def test_materialize_applies_subject_to_each_slide(self):
        result = materialize_slides([slide(), slide(number=2)], subject="coding")
        self.assertTrue(
            all(item["scene"].get("archetype") == "code_walkthrough" for item in result)
        )


if __name__ == "__main__":
    unittest.main()
