# -*- coding: utf-8 -*-
import sys
import hashlib
import time
import re

#evernote Thrift protocol
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.notestore.constants as NoteStoreConstants
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors
import evernote.edam.limits.constants as Limits

from lxml import etree
from helpers import BasicXmlExtract

from pattern.vector import Document, Corpus, LEMMA

__all__ = ['Errors','Limits', 'Types', 'ENHOST', 'AUTHTOKEN',
        'en_userstore_setup', 'en_notestore_setup',
        'NoteStore',
        'EvernoteConnector',]

# Once completed development, simply change "sandbox.evernote.com" to "www.evernote.com".
ENHOST = "sandbox.evernote.com"

# Real applications authenticate with Evernote using OAuth
AUTHTOKEN = "S=s1:U=fc7c:E=13e57279f84:C=136ff767384:P=4f:A=en-devtoken:H=d34397f92bc6d8ec8d63f0fb47815e92"

###############
### Helpers ###
###############

def en_check_version():
    """ Checks the evernote version """
    versionOK = userStore.checkVersion("Evernote EDAMTest (Python)",
                                   UserStoreConstants.EDAM_VERSION_MAJOR,
                                   UserStoreConstants.EDAM_VERSION_MINOR)
    print "Is my Evernote API version up to date? ", str(versionOK)
    print ""
    if not versionOK:
        exit(1)

def en_userstore_setup(enviroment):
    """ Simplifies the obnoxious Thrift setup functions
    Param: the url for which we talk talk with Evernote on(dev, or production)
    Returns: a  userstore client.
    """
    ustore = UserStore.Client(
            TBinaryProtocol.TBinaryProtocol(
                THttpClient.THttpClient("https://" + enviroment + "/edam/user")))
    return ustore

def en_notestore_setup(user_note_store_url):
    """ Simplifies the obnoxious Thrift setup functions
    Param: the url for a user from an auth request
    Returns: a  user's notestore client.
    """
    nstore =  NoteStore.Client(
            TBinaryProtocol.TBinaryProtocol(
                THttpClient.THttpClient(user_note_store_url)))
    return nstore

####################
### Main Classes ###
####################

class EvernoteConnector(object):
    """ Basic class to connect to the evernote thrift api. 
    Naming convention of the public methods is to be pep8, while the
    inner vars/methods/properties be consistent with the already inplace thrift mixedCase.
    TODO:
        Error checking, alot of it, that's the whole reseason behind the verbose
        method calling.
    """

    def __init__(self, base_uri, note_url=None):
        self.user_client = en_userstore_setup(base_uri)
        # Get the URL used to interact with the contents of the user's account
        if note_url == AUTHTOKEN:
            noteStoreUrl = self.user_client.getNoteStoreUrl(AUTHTOKEN)
            self.auth_token = AUTHTOKEN
        else:
            #TODO oauth handshake
            pass
        self.note_client = en_notestore_setup(noteStoreUrl)

    #### Public methods ####

    def create_note(self, title, content , **kwargs):
        """ Helper to create an evernote note"""""
        note = Types.Note( title , content,  **kwargs)
        # cant contain extra whitespace
        note.title = title.strip()
        note.content = self._formatNoteContent(content)
        # evernote wants miliseconds. . . time return seconds
        note.created = int(time.time() * 1000)
        note.updated = note.created
        return self.noteStore.createNote(self.auth_token, note)

    def delete_note(self, note):
        return self.update_note(note, active=False, deleted=int(time.time()*1000))

    def update_note(self, note, **kwargs):

        for key, value in kwargs.iteritems():
            setattr(note, key, value)

        note.updated = int(time.time() * 1000)
        return self.noteStore.updateNote(self.auth_token, note)

    def yield_note_content(self, filter_dic=None):
        """ TODO: 
        limits and offsets, yeild whole content, pass in whole filter
        """
        filter = NoteStore.NoteFilter(filter_dic)
        
        note_list =  self.note_client.findNotes(
                self.auth_token, filter, 0, Limits.EDAM_USER_NOTES_MAX)
        for note in note_list.notes:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note

    @property
    def default_notebook(self):
        return self.noteStore.getDefaultNotebook(self.auth_token)

    @default_notebook.setter
    def default_notebook(self,notebook):
        #TODO implement changing of default notebook
        pass

    ### Private methods ###
    def _formatNoteContent(self, innerContent):
        content = '<?xml version="1.0" encoding="UTF-8"?>'
        content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">'
        content += '<en-note>' + innerContent
        content += '</en-note>'
        return content



class EvernoteProfileInferer(EvernoteConnector):
    """ This is the type of  class that is responsible for extracting all the info
    hidden within the cloud of data from a particular service.

    Ideas:
        Boxplot over all users in a certain method, so you would show their
    totals but then also show how that number is relative to others. Maybe this
    should be an ABC?

    Storage: 
        perhaps pickling the objects and saving them for a week or something, or
    go all out and store full user state.
    """ 

    def __init__(self, base_uri, note_url=None):
        EvernoteConnector.__init__(self,base_uri, note_url)

    def topic_summary(self, docs):
        """ Returns what are the main features that make up this topic.
        Features, setiment analysis, lsa main features, time deltas,
        could be any  mashup of other statistical technique.
        Ideas:
            Features are not just word counts and tags,
            Could be any number of other methods.
        """
        pass

    def word_count(self, word_container):
        """ Counts the total number of words in some sort of content of 
        a user's profile. 
        Ideas:
            By time, cluster and not just a single object?
        """
        pass
    
    def readability(self, doc):
        """ Computes a score based upon what an douchebag would mark you
        down for when student critiqing papers.
        Ideas:
            pattern.metrics.flesh_reading_ease
        """
        pass
    
    def word_importance(self, word):
        """ How important is this word/phrases, or more techniquely what is the
        ratio of this word affect on topic, and other statistics.
        Ideas:
            relative to parts of speach
            relative to time, "recent topic of intrest for you has been ..."
            basic word, or more complex, detrmined by wiki topic complexity search.
        """
        pass
    
    def wiki_complexity_search(self, topic):
        """ Determines the complexity of a topic in wikipedia by starting at the
        topic and then using  monte carlo techniques visit a few links of "see
        also" and the "intro". Use dimision reduction techniques on the vectors
        and then apply anaylsis. 
            That analysis is clustering links and detriming the more basic
        topic, or the more abstract(based on wordnet sysnset stuff), or more
        important(page rank?). Or a simple lookup in a premade model of
        intro topics for a large range, and then monte carlo your way from
        their. 
        """
        pass

    def outside_knowledge(self, doc):
        """ Gather resources that are related to this doc from other services.
        Prime canidates are wikipedia, duckduckgo, freebase, the times, etc..
        """
        pass

    def average_location_of(self,obj):
        """ Using lat, long coordinetes detrmine the places where the most data
        is coming from. 
        """
        pass
            
    def learning_process(self):
        """ Compute the tree or path that the data has taken over time based
        upon wiki_complexity_search. 
        """
        pass

    def time_between(self, obj1, obej2):
        """ What is the time deltas of interaction of between these two things.
        """
        pass

    def fix_data(self, training_data, testing_data):
        """ Uses classification to suggest labels to the data according to the
        learned classifications.
        """
        pass
     
def build(self):
    docs = []
    parser = etree.HTMLParser(target=BasicXmlExtract())
    for  note in self.get_notes():
        data = etree.fromstring(note.content, parser)
        docs.append(Document(data, stemmer=LEMMA))
    self.corpus = Corpus(docs)
    return self.corpus

if __name__ == "__main__":
    E = EvernoteConnector(ENHOST, AUTHTOKEN)
    E = EvernoteProfileInferer(ENHOST, AUTHTOKEN)
    notes = E.yield_note_content()
    for n in notes:
        print n.content

    
