# -*- coding: utf-8 -*-
import sys
import time
import re
from collections import Counter

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

from helpers import BasicXmlExtract, text_processer

from lxml import etree

from pattern.vector import Corpus

from pymongo import Connection 
from bson import json_util
from pymongo.errors import ConnectionFailure, OperationFailure

__all__ = ['Errors','Limits', 'Types', 'ENHOST', 'AUTHTOKEN',
        'en_userstore_setup', 'en_notestore_setup',
        'NoteStore',
        'EvernoteConnector','EvernoteProfileInferer']

# Once completed development, simply change "sandbox.evernote.com" to "www.evernote.com".
ENHOST = "sandbox.evernote.com"

# Real applications authenticate with Evernote using OAuth
AUTHTOKEN = "S=s1:U=fc7c:E=13e673d7ae6:C=1370f8c4eea:P=4f:A=en-devtoken:H=753c4246972eb63f17cd1677d3c04126"

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

### Main ###
############

class EvernoteConnector(object):
    """ This is to ease the connection to the evernote thrift api, and provide a
    cache layer for reducing calls to the Evernote servers.

    Naming convention of the public methods is to be pep8, which is  
    to help distinguish between the layers of this class and the thrift
    generated classes.

    Local cache stores for a single user the notebooks and tags wihin an
    embedded doc, and keeps note guid references in a _id_notes list. The note
    collection itself is stored seperatly and contains the title (str_title),
    notebook guid (_id_notebook), tags (_id_tags), and it's content (str_content).

    TODO:
        Error checking, alot of it, that's the whole reseason behind the verbose
        method calling.
        Extract word tokens on syncs.
    """

    def __init__(self, base_uri, note_url, mongohandle):
        self.user_client = en_userstore_setup(base_uri)
        # Get the URL used to interact with the contents of the user's account
        if note_url is  AUTHTOKEN:
            noteStoreUrl = self.user_client.getNoteStoreUrl(AUTHTOKEN)
            self.auth_token = AUTHTOKEN

        #TODO oauth handshake

        self.note_client = en_notestore_setup(noteStoreUrl)

        self.mongo = mongohandle

        self.user_id = self.user_client.getUser(self.auth_token).id
        self.latest_usn = 0 
        self.last_updated = 0

        # for properties
        self._default = False
        self._user= False

    #### Public methods ####
    ########################

    @property
    def user(self):
        return self.user_client.getUser(self.auth_token)


    @property
    def default_notebook(self):
        if not self._default:
            self._default = self.noteStore.getDefaultNotebook(self.auth_token)
        return self._default

    @default_notebook.setter
    def default_notebook(self,notebook):
        #TODO implement changing of default notebook
        pass

    ### Editing/Helpers ###

    def create_note(self, title, content , **kwargs):
        """ Helper to create an evernote note"""""
        note = Types.Note( title , content,  **kwargs)
        # cant contain extra whitespace
        note.title = title.strip()
        note.content = self._formatNoteContent(content)
        # evernote wants miliseconds. . . time return seconds
        #note.created = int(time.time() * 1000)
        note.updated = note.created
        return self.note_client.createNote(self.auth_token, note)

    def update_note(self, note, **kwargs):

        for key, value in kwargs.iteritems():
            setattr(note, key, value)
        if kwargs.get('content',None):
            note.content = self._formatNoteContent(note.content)
        return self.note_client.updateNote(self.auth_token, note)

    def delete_note(self, note):
        return self.update_note(note, active=False, deleted=int(time.time()*1000))

    def create_notebok(self, name, **kwargs):
        return self.note_client.createNotebook(Types.Notebook(name=name, **kwargs))

    def get_trash_notes(self):
        return self.yield_note_list_content(self.get_notelist(inactive=True))

    def empty_trash(self):
        self.note_client.expungeInactiveNotes(self.auth_token)

    ### Querying ###

    def get_notelist(self, intial = 0, filter_dic=None):
        filter = NoteStore.NoteFilter(filter_dic)
        
        note_list =  self.note_client.findNotes(
                self.auth_token, filter, intial, Limits.EDAM_USER_NOTES_MAX)
        return note_list 

    def get_notelist_meta(self, intial = 0, filter_dic=None):
        filter = NoteStore.NoteFilter(filter_dic)
        resultSpec = NoteStore.NotesMetadataResultSpec(
                includeTitle=True,includeNotebookGuid=True, includeTagGuids=True)
        
        note_list =  self.note_client.findNotesMetadata(
                self.auth_token, filter, intial, Limits.EDAM_USER_NOTES_MAX,
                resultSpec)
        return note_list 

    def get_note_content(self, note):
        return self.note_client.getNoteContent(self.auth_token, note.guid)

    def yield_notelist_content(self, note_list):
        """Helper to keep huge note contents out of memory.
        TODO: 
        limits and offsets, yeild whole content, pass in whole filter
        """
        for note in note_list.notes:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note


    def yield_note_content(self, intial=0, filter_dic=None):
        """ TODO: 
        limits and offsets, yeild whole content, pass in whole filter
        """
        filter = NoteStore.NoteFilter(filter_dic)
        
        note_list =  self.note_client.findNotes(
                self.auth_token, filter, intial, Limits.EDAM_USER_NOTES_MAX)
        for note in note_list.notes:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note

    def yield_note_content_meta(self, intial=0, filter_dic=None):
        """ TODO: 
        limits and offsets, yeild whole content, pass in whole filter
        """
        filter = NoteStore.NoteFilter(filter_dic)
        
        note_list =  self.get_note_list_meta(intial,filter_dic)
        for note in note_list.notes:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note
    
    ### Syncing ###
    # used for reducing resource and process time for Analytics

    def yield_sync(self,expunged=False ,intial=0):
        """ Gathers any  content for this class to use """
        more = True
        filter = NoteStore.SyncChunkFilter(includeExpunged=expunged,
                includeNotes=True, includeTags=True,includeNotebooks=True)
        while more:
            new_stuff = self.note_client.getFilteredSyncChunk(self.auth_token,intial,
                    1000,filter)
            intial = new_stuff.chunkHighUSN
            ## check to see if anymore stuff
            if  new_stuff.chunkHighUSN == new_stuff.updateCount:
                more = False
                self.latest_usn = new_stuff.chunkHighUSN
                self.last_updated = new_stuff.currentTime
            yield new_stuff

    def initialize_db(self):
        """ Performs the intial content gathering when the database
        encounters an unseen user.
        Returns the _id for the new user
        """
        parser = etree.HTMLParser(target=BasicXmlExtract())
        # already have a user just rsync
        if self.mongo.users.find_one({'_id':self.user_id},{}):
            return self.resync_db()

        user_scaffold =  {
            '_id': self.user.id,
            '_id_notes':[],
            'tags':[],
            'notebooks':[],
            }
        # create the skeletn
        user_id = self.mongo.users.insert(user_scaffold)
        ## now lets  go through the iterable of different types   and update 
        for new_stuff in self.yield_sync():

            notes =[]
            tags = []
            notebooks = []
            
            if new_stuff.notes:
                for note in self.yield_notelist_content(new_stuff):
                    ## dont want to store inactive things
                    if note.active:
                        ## Parsing data into token counts ##
                        data = etree.fromstring(note.content, parser)

                        n = { '_id':note.guid, '__id_user':user_id, 
                            '_id_notebook':note.notebookGuid,
                            'str_title':note.title,'_id_tags':note.tagGuids,
                            'str_content':note.content, 
                            'tokens': text_processer(data),
                            }
                        notes.append(n)
                # insert the  note in its own collection because maybe large note data string?
                notes_id = self.mongo.notes.insert(notes)
                ## update the single user's note list with the new notes_id 
                self.mongo.users.update({'_id': user_id}, 
                         {"$pushAll":{'_id_notes': notes_id}})

            if new_stuff.tags:
                for tag in new_stuff.tags:
                    t = {'_id':tag.guid, 'str_name':tag.name}
                    tags.append(t)

                # update the user's tag list with the embeded tags
                self.mongo.users.update({'_id':user_id},
                     {"$pushAll":{'tags':tags}})

            if new_stuff.notebooks:
                for notebook in new_stuff.notebooks:
                    n = {'_id':notebook.guid, 'str_name':notebook.name}
                    notebooks.append(n)
                # update the user's notebook list with the actuall notebooks
                self.mongo.users.update({'_id':user_id},
                     {"$pushAll":{'notebooks':notebooks}})

    def resync_db(self):
        """ Performs the syncing if we already have initialized """
        parser = etree.HTMLParser(target=BasicXmlExtract())
        for new_stuff in self.yield_sync(True, self.latest_usn):

            if new_stuff.expungedTags:
                # update users embedded docs
                self.mongo.users.update({'_id':self.user_id},{'$pullAll': 
                    {'tags':[{'_id':n} for n in new_stuff.expungedTags]}})

            if new_stuff.expungedNotebooks:
                # update users embedded docs
                self.mongo.users.update({'_id':self.user_id},{'$pullAll':
                    {'notebooks':[{'_id':n} for n in new_stuff.expungedNotebooks]}})

            if new_stuff.expungedNotes:
                inactive_notes = [{'_id':n} for n in new_stuff.expungedNotes]
                self.mongo.users.update({'_id':self.user_id},{'$pullAll': 
                        {'_id_notes': inactive_notes}})
                # collection 
                self.mongo.notes.remove({'_id':{'$in': inactive_notes}})

            if new_stuff.notes:
                new_notes = []
                inactive_notes =[]
                for note in self.yield_notelist_content(new_stuff):
                    ## dont want to store inactive things
                    if not note.active:
                        inactive_notes.append(note.guid)
                    data = etree.fromstring(note.content, parser)
                    n = { '_id':note.guid, '__id_user':self.user_id, 
                        '_id_notebook':note.notebookGuid,
                        'str_title':note.title,'_id_tags':note.tagGuids,
                        'str_content':note.content, 
                        'tokens' :text_processer(data),
                        }
                    self.mongo.notes.update({'_id':note.guid},n,  upsert=True)
                    new_notes.append(note.guid)

                # update users note list
                self.mongo.users.update({'_id':self.user_id},{"$addToSet": {
                    '_id_notes': {'$each': new_notes}}})

                if inactive_notes:
                    # _id list
                    self.mongo.users.update({'_id':self.user_id},{'$pullAll': 
                        {'_id_notes': inactive_notes}})
                    # collection 
                    self.mongo.notes.remove({'_id':{'$in': inactive_notes}})

            if new_stuff.tags:
                for tag in new_stuff.tags:
                    t = {'_id':tag.guid, 'str_name':tag.name}
                    # insert or full change of the embedded tag doc
                    self.mongo.users.update({'tags._id':tag.guid},t, upsert=True)

            if new_stuff.notebooks:
                for notebook in new_stuff.notebooks:
                    n = {'_id':notebook.guid, 'str_name':notebook.name}
                    # insert or full change of the embedded tag doc
                    self.mongo.users.update({'notebooks._id':notebook.guid},n,upsert=True)

    def update_user_db(self):
        pass

    def remove_from_db(self):
        """ Removes a note's content from the database
        """
        pass

    def update_corpus(self):
        """ Updates the users analityc corpus if their is any changes
        in their note's content.
        """
        pass

    @property
    def need_sync(self):
        syncState = self.note_client.getSyncState(self.auth_token)
        return (self.last_updated < syncState.fullSyncBefore) or \
                (self.latest_usn < syncState.updateCount)

    ### Private methods ###
    
    def _formatNoteContent(self, innerContent):
        """ Simplifies creating notes
        """
        content = '<?xml version="1.0" encoding="UTF-8"?>'
        content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">'
        content += '<en-note>' + innerContent
        content += '</en-note>'
        return content
    
### Analytic Class for infering things ###
class EvernoteProfileInferer(EvernoteConnector):
    """ This is the  class that is responsible for extracting all the info
    hidden within the cloud of data from the Evernote service.

    Ideas:
        Boxplot over all users in a certain method, so you would show their
    totals but then also show how that number is relative to others. Maybe this
    should be an ABC?

    Caching: 
        perhaps pickling the objects and saving them for a week or something, or
    go all out and store full user state.

    http://stackoverflow.com/questions/2775864/python-datetime-to-unix-timestamp
    """ 

    def __init__(self, base_uri, note_url, mongohandle):
        EvernoteConnector.__init__(self,base_uri, note_url,mongohandle)

    def topic_summary(self, docs):
        """ Returns what are the main features that make up this topic.
        Features, setiment analysis, lsa main features, time deltas,
        could be any  mashup of other statistical technique.
        Ideas:
            Features are not just word counts and tags,
            Could be any number of other methods.
        """
        pass

    def word_count(self, note_filter=None):
        """ Counts the total number of words in some sort of content of 
        a user's profile. 
        Ideas:
            By time, cluster and not just a single object?
        """

        c = Counter()
        meta_list = [x.guid for x in self.get_notelist_meta(note_filter).notes]
        print meta_list
        for x in self.mongo.notes.find({'_id':{'$in':meta_list}}, {'tokens':1}):
            c.update(x['tokens'])
        return c


    
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
 
if __name__ == "__main__":
    pass

