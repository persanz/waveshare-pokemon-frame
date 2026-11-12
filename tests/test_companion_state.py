import unittest
from companion_state import Pet

class PetTests(unittest.TestCase):
    def test_time_accumulates_across_small_updates(self):
        p = Pet()
        for _ in range(360):
            p.advance(1)
        self.assertEqual((p.food, p.joy), (72, 73))

    def test_actions_have_cooldown_and_bounds(self):
        p = Pet(food=98, joy=99)
        p.action('feed')
        self.assertEqual(p.food, 100)
        p.action('play')
        self.assertEqual(p.joy, 99)
        p.advance(2)
        p.action('play')
        self.assertEqual((p.food, p.joy), (97, 100))

    def test_hungry_pet_needs_food_before_play(self):
        p = Pet(food=3, joy=20)
        self.assertEqual(p.action('play'), 'DAME COMIDA PRIMERO')
        self.assertEqual((p.food, p.joy), (3, 20))
        p.advance(100000)
        self.assertEqual((p.food, p.joy), (0, 0))

    def test_restore_and_new_encounter(self):
        p = Pet(index=25, food=42, joy=56)
        self.assertEqual((p.index, p.food, p.joy), (25, 42, 56))
        p.encounter(150)
        self.assertEqual((p.index, p.food, p.joy), (150, 75, 75))
        self.assertEqual(p.mood(), 'FELIZ')

if __name__ == '__main__':
    unittest.main()
