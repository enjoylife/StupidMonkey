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


class TestEvernoteWrapper(unittest.TestCase):

    def setUp(self):
        pass

    def test_creation(self):
        pass

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestEvernoteWrapper))
    return suite
d = """
def test_lsa():
    E = EvernoteInference(ENHOST, AUTHTOKEN)
    corpus =  E.build()
    for d in corpus.documents:
        pass
        #print d.terms
    corpus.lsa = None
    corpus.reduce(4)
    print corpus.lsa.u

    for concept in corpus.lsa.concepts:
        print "NEW CONCEPT"
        for word, weight in concept.items():
            if abs(weight) > 0.1:
                print word
"""

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=1).run(suite())
