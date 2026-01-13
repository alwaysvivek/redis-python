import unittest
from resp_server.parser import parsed_resp_array

class TestParser(unittest.TestCase):
    def test_parsed_resp_array_empty(self):
        self.assertEqual(parsed_resp_array(b""), ([], 0))
        self.assertEqual(parsed_resp_array(None), ([], 0))
    
    def test_parsed_resp_array_simple(self):
        # *2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n
        data = b"*2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n"
        elements, new_index = parsed_resp_array(data)
        self.assertEqual(elements, ["ECHO", "hey"])
        self.assertEqual(new_index, len(data))

    def test_parsed_resp_array_partial(self):
        # Should return empty if incomplete
        data = b"*2\r\n$4\r\nEC"
        elements, _ = parsed_resp_array(data)
        self.assertEqual(elements, [])

    def test_parsed_resp_array_invalid(self):
        data = b"NOT_RESP"
        elements, _ = parsed_resp_array(data)
        self.assertEqual(elements, [])

if __name__ == '__main__':
    unittest.main()
