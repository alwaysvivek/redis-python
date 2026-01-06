import unittest
import subprocess
import time
import redis
import sys
import os

class TestIntegration(unittest.TestCase):
    server_process = None

    @classmethod
    def setUpClass(cls):
        # Start the server in a separate process
        # Using sys.executable to ensure we use the same python interpreter
        cls.server_process = subprocess.Popen(
            [sys.executable, "-m", "app.main", "--port", "6380"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        # Give it a moment to start
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()

    def setUp(self):
        try:
            self.client = redis.Redis(host='localhost', port=6380, decode_responses=True)
            self.client.ping()
        except redis.ConnectionError:
            self.fail("Could not connect to Redix server")

    def test_ping(self):
        self.assertEqual(self.client.ping(), True)

    def test_set_get(self):
        self.assertTrue(self.client.set("foo", "bar"))
        self.assertEqual(self.client.get("foo"), "bar")

    def test_expiry(self):
        self.client.set("expire_me", "val", px=200)
        self.assertEqual(self.client.get("expire_me"), "val")
        time.sleep(0.3)
        self.assertIsNone(self.client.get("expire_me"))

    def test_list(self):
        self.client.delete("mylist")
        self.assertEqual(self.client.rpush("mylist", "1", "2"), 2)
        self.assertEqual(self.client.lpush("mylist", "0"), 3)
        self.assertEqual(self.client.lrange("mylist", 0, -1), ["0", "1", "2"])
        self.assertEqual(self.client.lpop("mylist"), "0")

    def test_concurrent_clients(self):
        # Verification of thread safety is hard in a simple test, but this ensures concurrency doesn't crash it
        client2 = redis.Redis(host='localhost', port=6380, decode_responses=True)
        self.client.set("concurrent", "0")
        
        self.client.incr("concurrent")
        client2.incr("concurrent")
        
        val = int(self.client.get("concurrent"))
        self.assertEqual(val, 2)

if __name__ == '__main__':
    unittest.main()
