# -*- coding: utf-8 -*-

#from coverage import coverage
import unittest
#from cherrypy.test.webtest import WebCase
#cov = coverage(source = ['enwrapper.py'])
#cov.start()
from enwrapper import *
from helpers import mongo_connect

#import evernote.edam.type.ttypes as Types

mongo = mongo_connect('test', extra=True)


class TestEvernoteWrapper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.en = EvernoteConnector(ENHOST, AUTHTOKEN, mongo)
        for note in cls.en.get_notelist(0).notes:
            cls.en.delete_note(note)
        cls.en.empty_trash()

    @classmethod
    def tearDownClass(cls):
        print cls.en.mongo.users.find_one()
        mongo.connection.drop_database('test')
        mongo.users.drop()
        mongo.notes.drop()
        # keep first test note
        for note in cls.en.get_notelist(0).notes:
            cls.en.delete_note(note)
        cls.en.empty_trash()

    def test_evernote_1creation(self):
        self.assertIsInstance(self.en.user,Types.User)
        self.assertEqual(self.en.user.username, 'tester1234')
        self.assertEqual(False, self.en.need_sync)
        self.assertEqual(None, self.en.resync_db())

    def test_evernote_2note(self):
        note = self.en.create_note('first test note', 'this is the body of the stuff')
        self.assertEqual('first test note',note.title)
        self.assertIn('this is the body',self.en.get_note_content(note))
        self.assertIsNotNone(note.guid)
        self.en.delete_note(note)
        # TODO: test for copying and different updating 

        note = self.en.create_note('first test note', 'this is the body of the stuff')
        newnote = self.en.update_note(note,content='new test body', title='a new title')
        self.assertIn('new test body', self.en.get_note_content(note))
        self.assertEqual('a new title',newnote.title)
        self.en.delete_note(newnote)

    def test_syncing_3initial(self):
        note = self.en.create_note('test', 'this is the body of test')
        #self.assertEqual(True, self.en.need_sync)
        self.en.resync_db()
        self.assertEqual(1, mongo.users.find().count())
        self.assertEqual(1, mongo.notes.find().count())
        self.assertEqual(1, mongo.notes.find({'_id':note.guid}).count())
        self.assertIsNotNone(mongo.notes.find_one({'_id':note.guid}))

        n = self.en.update_note(note, content='NEW')
        self.assertEqual(n.guid,note.guid)
        self.assertIsNot(n, note)
        #self.assertTrue( self.en.need_sync)

        self.assertIn('this is the body of test',
                mongo.notes.find_one({'_id':n.guid})['str_content'])
        self.assertIn('this is the body of test',
                mongo.notes.find_one({'_id':note.guid})['str_content'])

    def test_syncing_4resync(self):
        #  new thing,  simple update
        self.assertEqual(True, self.en.need_sync)
        note = self.en.create_note('test2', 'this is the body of test 2')
        self.en.resync_db()
        # is it updated in the note collection too?
        self.assertTrue(mongo.notes.find_one({'_id':note.guid}))

        # same thing but updated
        n = self.en.update_note(note, content="NEW")
        old = mongo.notes.find_one({'_id':n.guid})
        self.assertEqual(True, self.en.need_sync)
        # should be unsynced
        self.assertNotEqual(old['str_content'], self.en.get_note_content(note))

        self.en.resync_db()
        # now we should be back again
        mongonote = mongo.notes.find_one({'_id':note.guid})
        self.assertEqual(mongonote['str_content'], self.en.get_note_content(n))

class TestEvernoteAnalytic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.en = EvernoteProfileInferer(ENHOST, AUTHTOKEN, mongo)
        for note in cls.en.get_notelist(1).notes:
            cls.en.delete_note(note)
        cls.en.empty_trash()

    @classmethod
    def tearDownClass(cls):
        mongo.connection.drop_database('test')
        mongo.users.drop()
        mongo.notes.drop()
        # keep first test note
        for note in cls.en.get_notelist(1).notes:
            cls.en.delete_note(note)
        cls.en.empty_trash()

    def test_analytic_word_count(self):
        """ Word count depends on mongo find syntax and note_filters 
        TODO TESTS: 
            Test for note resource text being counted too
        """
        note = self.en.create_note('test', 'this is the body of test 2')
        note = self.en.create_note('test', 'this is the body of test')
        note = self.en.create_note('test3', 'this is the body of test3')
        self.en.resync_db()
        self.assertIn(u'test', self.en.word_count())
        self.assertTrue(dict(self.en.word_count()))
        self.assertTrue(self.en.word_count(words='intitle:test'))

    def test_analytic_topic_summary(self):
        """ topic summary depends on _lsa_extract """
        note = self.en.create_note('test', 'this is the body of test 2')
        self.en.resync_db()

    def test_analytic_flesch_reading_ease(self):
        pass

    def test_outside_knowledge(self):
        note = self.en.create_note('My math title', 'lets talk about science')
        self.en.resync_db()
        self.assertTrue(self.en.outside_knowledge(note.guid, 'science'))
        print(self.en.outside_knowledge(note.guid, 'science'))
       
    def test_evernote_querying(self):
        pass

def suite():
    suite = unittest.TestSuite()
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestEvernoteWrapper))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestEvernoteAnalytic))
    return suite
if __name__=='__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
    #cov.stop()
    #cov.report()
