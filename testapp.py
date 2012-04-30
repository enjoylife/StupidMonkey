from cherrypy.test.webtest import WebCase
import unittest

class TestApp(WebCase):

    
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        ## called for ever test
        pass

    def test_something(self):
        pass



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestApp,)
    unittest.TextTestRunner(verbosity=2).run(suite)
