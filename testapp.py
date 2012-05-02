# -*- coding: utf-8 -*-

from coverage import coverage
import unittest
from cherrypy.test.webtest import WebCase
cov = coverage(source = ['enwrapper.py'])
cov.start()
from enwrapper import *
from database import mongo,  User, Goal

import evernote.edam.type.ttypes as Types

testuser = {u'first_name': u'Matthew', u'last_name': u'Clemens', u'middle_name': u'Donavan', u'name': u'Matthew Donavan Clemens', u'locale': u'en_US', u'gender': u'male', u'link': u'http://www.facebook.com/people/Matthew-Donavan-Clemens/100000220742923', u'id': u'100000220742923'}



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


class TestMongo(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        mongo.connection.drop_database('test')

    def setUp(self):
        mongo.users.remove()

    def test_mongo_user(self):
        user = User.create(testuser,'facebook')
        self.assertTrue( user ) 
        self.assertIsInstance(user , User )
        self.assertIn('str_name', user.info())

        uid = user._id 

        usersame = User.find(uid)
        self.assertEqual(usersame.info(), user.info())
        self.assertIsInstance(user.info(), dict)

        #edit
        self.assertTrue( user.edit({'str_name':'BurgerKing'}) )
        self.assertIn('BurgerKing', str(user.info()))
        self.assertIn('facebook', str(user.info(['str_type'])))

        # Remove does it return True? if so sucessful remove.
        self.assertTrue( user.delete() )
        self.assertFalse( user.is_alive)
        self.assertFalse( user.info())
        self.assertFalse(User.find(uid))

    def test_mongo_goal(self):
        pass
        user = User.create( testuser,'facebook')
        goal = user.add_goal()
        self.assertTrue(goal._id)


    def _test_welcome(self):
        self.getPage('/')
        self.assertInBody('Hello World')

    def _test_User(self):
        testuser_id = create_user(mongo,  testuser, 'facebook')

        #make sure that query or url vars are capable
        self.getPage('/api/user?uid=100000220742923&type=facebook')
        self.assertInBody('Matthew Donavan Clemens')
        self.assertInBody('100000220742923')

        self.getPage('/api/user/100000220742923/facebook')
        self.assertInBody('Matthew Donavan Clemens')
        self.assertInBody('100000220742923')

        self.getPage('/api/user/')

class TestEvernoteWrapper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.en = EvernoteConnector(ENHOST, AUTHTOKEN)
    @classmethod
    def tearDownClass(cls):
        mongo.connection.drop_database('test')
        for note in cls.en.get_notelist(intial=1).notes:
            cls.en.delete_note(note)
        cls.en.empty_trash()

    def test_evernote_service(self):
        self.assertIsInstance(self.en.user,Types.User)
        self.assertEqual(self.en.user.username, 'tester1234')

    def test_evernote_create(self):
        note = self.en.create_note('first test note', 'this is the body of the stuff')
        self.assertEqual('first test note',note.title)
        self.assertIn('this is the body',self.en.get_note_content(note))
        self.assertIsNotNone(note.guid)
        self.en.delete_note(note)

        ### TODO: test for copying and different updating 
        self.assertEqual(1, self.en.get_notelist().totalNotes)
       
    def test_evernote_querying(self):
        pass

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestEvernoteWrapper))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestApp))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestMongo))
    return suite
if __name__=='__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
    cov.stop()
    cov.report()
