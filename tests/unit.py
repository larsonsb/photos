import os
import unittest
import unittest.mock
import datetime

os.environ["CONFIG_PATH"] = "photos.config.TestingConfig"

from photos import app
from photos.database import Base, engine, session

VALID_USER = 'cabot'
INVALID_USER = 'jf93324112312312aaaa3ngn'
PRIVATE_USER = 'wes'

class UnitTests(unittest.TestCase):
    """Tests."""

    def setUp(self):
        """Test setup."""
        self.client = app.test_client()
        Base.metadata.create_all(engine)

    def test_homepage(self):
        """Go to a valid public user's page."""
        res = self.client.get('/')

        self.assertEqual(res.status_code, 200)

    def test_get_user(self):
        """Go to a valid public user's page."""
        res = self.client.get('/photos/{}'.format(VALID_USER))

        self.assertEqual(res.status_code, 200)

    def test_get_non_existent_user(self):
        res = self.client.get('/photos/{}'.format(INVALID_USER))
        self.assertEqual(res.status_code, 302)

    def test_get_private_user(self):
        res = self.client.get('/photos/{}'.format(PRIVATE_USER))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'Sorry, this user is private.' in res.data)

    def test_get_user_photos(self):
        with unittest.mock.patch('celeryconfig.CELERY_ALWAYS_EAGER', True, create=True):
            data = {'email': 'youwantthephotos@gmail.com'}
            res = self.client.post('/photos/{}'.format(VALID_USER), data=data)
            check_file = os.popen('ls youwantthedownloads/*{}*.zip'.format(VALID_USER)).read()
            self.assertEqual(res.status_code, 302)
            self.assertTrue(len(check_file))

    def tearDown(self):
        """Test teardown."""
        session.close()
        Base.metadata.drop_all(engine)


if __name__ == "__main__":
    unittest.main()
