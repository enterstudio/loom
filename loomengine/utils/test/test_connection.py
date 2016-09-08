import unittest

from loomengine.utils import connection

class MockResponse:

    def json(self):
        # Return mock data
        return {}


class MockConnection(connection.Connection):

    def _get(self, relative_url):
        self.method = 'GET'
        self.url = relative_url
        return MockResponse()

    def _post(self, data, relative_url):
        self.method = 'POST'
        self.data = data
        self.url = relative_url
        return MockResponse()

    def _put(self, data, relative_url):
        self.method = 'PUT'
        self.data = data
        self.url = relative_url
        return MockResponse()

    def _patch(self, data, relative_url):
        self.method = 'PATCH'
        self.data = data
        self.url = relative_url
        return MockResponse()


class TestConnection(unittest.TestCase):

    ROOT_URL = 'root'

    def setUp(self):
        self.connection = MockConnection(self.ROOT_URL)

    def test_post_file_data_object(self):
        data = {'mock', 'data'}
        self.connection.post_file_data_object(data)

        self.assertTrue(self.connection.url, self.ROOT_URL + '/api/files/')


if __name__ == '__main__':
    unittest.main()
                
