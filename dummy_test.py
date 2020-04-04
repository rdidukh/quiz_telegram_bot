import unittest


class TestDummy(unittest.TestCase):
    def test_upper(self):
        dummy = 'dummy'
        self.assertEqual('dummy', dummy)


if __name__ == '__main__':
    unittest.main()
