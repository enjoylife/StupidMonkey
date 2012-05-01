from cherrypy.test.webtest import WebCase
from enwrapper import *
import unittest

class TestApp(WebCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def test_something(self):
        pass

    def _test_evernote_note(self):
        """ test evernote connector """
        E = EvernoteConnector(ENHOST, AUTHTOKEN)
        #creation
        note = E.create_note('Test Note', "A really Cool Test Note")
        self.assertEqual('Test Note', note.title)
        #deletion
        note = E.delete_note(note)
        self.assertEqual(False, note.active)
        E.noteStore.expungeInactiveNotes(E.authToken)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestApp,)
    unittest.TextTestRunner(verbosity=2).run(suite)
