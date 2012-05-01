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
        'EvernoteConnector']

# Once completed development, simply change "sandbox.evernote.com" to "www.evernote.com".
ENHOST = "sandbox.evernote.com"

# Real applications authenticate with Evernote using OAuth
AUTHTOKEN = "S=s1:U=fc7c:E=13e57279f84:C=136ff767384:P=4f:A=en-devtoken:H=d34397f92bc6d8ec8d63f0fb47815e92"

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
    Returns: a  userstore.
    """
    return UserStore.Client(
            TBinaryProtocol.TBinaryProtocol(
                THttpClient.THttpClient("https://" + enviroment + "/edam/user")))

def en_notestore_setup(user_note_store_url):
    """ Simplifies the obnoxious Thrift setup functions
    Param: the url for a user from an auth request
    Returns: a specific user's notestore.
    """
    return NoteStore.Client(
            TBinaryProtocol.TBinaryProtocol(
                THttpClient.THttpClient(user_note_store_url)))

class EvernoteConnector(object):
    """ Basic class to connect to the evernote thrift api. 
    Naming convention of the public methods is to be pep8, while the
    inner vars be consistent with the already inplace thrift mixedCase.
    TODO:
        Error checking, alot of it.
    """

    def __init__(self, base_uri, note_url=None):
        self.userStore = en_userstore_setup(base_uri)
        # Get the URL used to interact with the contents of the user's account
        if note_url == AUTHTOKEN:
            noteStoreUrl = self.userStore.getNoteStoreUrl(AUTHTOKEN)
            self.authToken = AUTHTOKEN
        else:
            #TODO oauth handshake
            pass
        self.noteStore = en_notestore_setup(noteStoreUrl)

    #### Public methods ####

    def get_notebooks(self, filter=None):
        """
        get notebooks, set default and search for specified notebooks
        """
        self.noteBooks = self.noteStore.listNotebooks(self.authToken)
        matchingNotebooks = []

        for notebook in self.noteBooks:
            if filter is not None:
                nbRe = re.compile(filter, re.I)
                if re.search(nbRe, notebook.name) is not None:
                    matchingNotebooks.append(notebook)
        
        return matchingNotebooks

    def create_note(self, title, content, notebook=False):
        note = Types.Note()
        # cant contain extra whitespace
        note.title = title.strip()
        note.content = self._formatNoteContent(content)
        if notebook is not False:
            note.notebookGuid = notebook.guid
        # evernote wants miliseconds. . . time return seconds
        note.created = int(time.time() * 1000)
        note.updated = note.created
        return self.noteStore.createNote(self.authToken, note)

    def delete_note(self, note):
        return self.update_note(note, active=False, deleted=int(time.time()*1000))

    def update_note(self, note, **kwargs):

        for key, value in kwargs.iteritems():
            setattr(note, key, value)

        note.updated = int(time.time() * 1000)
        return self.noteStore.updateNote(self.authToken, note)

    def get_notes(self, notebook=None, list=False, inactive=False):
        """ TODO: 
        limits and offsets,
        yeild whole content,
        pass in whole filter
        """
        filter = NoteStore.NoteFilter()
        filter.inactive = inactive
        
        if notebook is not None:
            filter.notebookGuid = notebook.guid

        noteList = self.noteStore.findNotes(self.authToken, filter, 0, 9999)
        if list:
            return noteList
        else:
            for note in noteList.notes:
                note.content = self.noteStore.getNoteContent(self.authToken, note.guid)
        return noteList.notes


    @property
    def default_notebook(self):
        return self.noteStore.getDefaultNotebook(self.authToken)

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

class EvernoteInference(EvernoteConnector):
    
    def __init__(self, base_uri, note_url=None):
        EvernoteConnector.__init__(self, base_uri,note_url)

    def build(self):
        docs = []
        parser = etree.HTMLParser(target=BasicXmlExtract())
        for  note in self.get_notes():
            data = etree.fromstring(note.content, parser)
            docs.append(Document(data, stemmer=LEMMA))
        self.corpus = Corpus(docs)
        return self.corpus



if __name__ == "__main__":
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
     
