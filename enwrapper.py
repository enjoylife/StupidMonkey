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


__all__ = ['Errors','Limits', 'Types', 'ENHOST', 'AUTHTOKEN',
        'en_userstore_setup', 'en_notestore_setup',
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

    @property
    def defaultNotebook(self):
        return self.noteStore.getDefaultNotebook(self.authToken)

    @defaultNotebook.setter
    def defaultNotebook(self,notebook):
        #TODO implement changing of default notebook
        pass

    def create_note(self, title, content, notebook=False):
        note = self._newNote(notebook)
        note.title = title
        note.content = self.formatNoteContent(content)
        note.created = int(time.time() * 1000)
        note.updated = note.created

        return self.noteToDic(
                self.noteStore.createNote(self.authToken, note))

    def update_note(self, guid, title=False, content=False, notebook=False):
        note = self._newNote(notebook)
        note.guid = guid

        #TODO fetch already existent title/content if not given
        note.title = title
        note.content = self._formatNoteContent(content)

        note.updated = int(time.time() * 1000)

        return self._noteToDic(
                self.noteStore.updateNote(self.authToken, note))

    def get_note_list(self, notebook=None):
        return self._getNotes(notebook=notebook, list=True)

    def get_notes(self, notes=False, notebook=None):
        return self._getNotes(wantedNotes=notes, notebook=notebook, list=False)

    def _noteToDic(self, note):
         return {
            "guid": note.guid,
            "title": note.title,
            "created": note.created,
            "updated": note.updated,
            "tags": note.tagNames
        }

    def _getNotes(self, wantedNotes=False, notebook=None, list=False):
        filter = NoteStore.NoteFilter()
        
        if notebook is not None:
            filter.notebookGuid = notebook.guid
        else:
            filter.notebookGuid = self.defaultNotebook.guid

        noteList = self.noteStore.findNotes(self.authToken, filter, 0, 9999)
        notes = []

        for note in noteList.notes:
            if note.active is True:
                #TODO add more properties 
                if wantedNotes is False or\
                    wantedNotes is not False and note.guid in wantedNotes:
                    if list is False:
                        note.content = self.noteStore.getNoteContent(
                                self.authToken, note.guid)
                        notes.append(note)
        
        return notes

    def _newNote(self, notebook):
        note = Types.Note()
        
        if notebook is not False:
            note.notebookGuid = notebook.guid
        else:
            note.notebookGuid = self.defaultNotebook.guid

        return note

    def _formatNoteContent(self, innerContent):
        content = '<?xml version="1.0" encoding="UTF-8"?>'
        content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">'
        content += '<en-note>' + innerContent
        content += '</en-note>'
        return content


if __name__ == "__main__":
    pass
