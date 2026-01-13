import unittest
import time
import threading
from resp_server.core.datastore import (
    DATA_STORE, set_string, get_data_entry, set_list, 
    append_to_list, size_of_list, lrange_rtn, remove_elements_from_list, DATA_LOCK
)

class TestDataStore(unittest.TestCase):
    def setUp(self):
        # Clear data store before each test
        with DATA_LOCK:
            DATA_STORE.clear()

    def test_set_get_string(self):
        set_string("key1", "value1", None)
        entry = get_data_entry("key1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["value"], "value1")
        self.assertEqual(entry["type"], "string")

    def test_expiry(self):
        # Set expiry to 100ms from now
        expiry_time = int(time.time() * 1000) + 100
        set_string("key_exp", "val", expiry_time)
        
        # Immediate check
        self.assertIsNotNone(get_data_entry("key_exp"))
        
        # Wait for expiration
        time.sleep(0.2)
        self.assertIsNone(get_data_entry("key_exp"))

    def test_list_operations(self):
        set_list("mylist", ["a", "b"], None)
        self.assertEqual(size_of_list("mylist"), 2)
        
        append_to_list("mylist", "c")
        self.assertEqual(size_of_list("mylist"), 3)
        
        elements = lrange_rtn("mylist", 0, -1)
        self.assertEqual(elements, ["a", "b", "c"])
        
        popped = remove_elements_from_list("mylist", 1)
        self.assertEqual(popped, ["a"])
        self.assertEqual(size_of_list("mylist"), 2)



if __name__ == '__main__':
    unittest.main()
