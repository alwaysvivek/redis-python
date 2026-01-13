import unittest
from resp_server.protocol.resp import parse_resp_array

class TestParser(unittest.TestCase):
    def test_parsed_resp_array_empty(self):
        self.assertIsNone(parse_resp_array(b""))
        self.assertIsNone(parse_resp_array(None))
    
    def test_parsed_resp_array_simple(self):
        # *2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n
        data = b"*2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n"
        elements = parse_resp_array(data)
        self.assertEqual(elements, ["ECHO", "hey"])

    def test_parsed_resp_array_partial(self):
        # Should return None if incomplete
        data = b"*2\r\n$4\r\nEC"
        elements = parse_resp_array(data)
        self.assertIsNone(elements)

    def test_parsed_resp_array_invalid(self):
        data = b"NOT_RESP"
        elements = parse_resp_array(data)
        self.assertIsNone(elements)

if __name__ == '__main__':
    unittest.main()
