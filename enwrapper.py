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

from helpers import BasicXmlExtract, text_processer, flesch_reading_ease

from lxml import etree

from pattern.web import Wikipedia
from pattern.vector import Corpus, Document

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
AUTHTOKEN = "S=s1:U=fc7c:E=13e8519dcbf:C=1372d68b0bf:P=1cd:A=en-devtoken:H=0f5db37f979a59c51f7695aba6d0145c"

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

    mongo.users:
        {_id: user_id} =  user guid
        {bool_lsa: False}  =  a boolean for lsa analysis. 
    mongo.notes:
        {_id_user: self.user_id} = the owner's guid
        {str_title: note.title} = note title 
        {_id_notebook: note.notebook} = this note's notebook guid 
        {_id_tags: [note.tags]} =  the array of tags this note 
        {str_content: note.content} = note content
        {tokens_content: [~note.content.split()]} =  the extracted words for this note
        {tokens_lsa: [~tokens.lsa.reduce()]} = the reduced vectors for note

    TODO:
        Error checking, alot of it, that's the whole reseason behind the verbose
        method calling.
        caching of Analytic methods too.
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

    @property
    def user(self):
        return self.user_client.getUser(self.auth_token)

    ### Editing / Testing Helpers ###

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
        if kwargs.get('content',False):
            note.content = self._formatNoteContent(note.content)
        return self.note_client.updateNote(self.auth_token, note)

    def delete_note(self, note):
        """ able to give a note, or a guid """
        if hasattr(note,'guid'):
            return self.note_client.deleteNote(self.auth_token, note.guid)
        else:
            return self.note_client.deleteNote(self.autho_token,note)
            
    def get_trash_notes(self):
        return self.yield_note_list_content(self.get_notelist(inactive=True))

    def empty_trash(self):
        self.note_client.expungeInactiveNotes(self.auth_token)

    ### Querying ###

    def get_note_content(self, note):
        return self.note_client.getNoteContent(self.auth_token, note.guid)

    def get_notelist(self, initial = 0, **filterargs):
        filter = NoteStore.NoteFilter(**filterargs)
        
        note_list =  self.note_client.findNotes(
                self.auth_token, filter, initial, Limits.EDAM_USER_NOTES_MAX)
        return note_list 

    def get_notelist_meta(self, initial = 0, **filterargs):
        filter = NoteStore.NoteFilter(**filterargs)
        resultSpec = NoteStore.NotesMetadataResultSpec(
                includeTitle=True,includeNotebookGuid=True, includeTagGuids=True)
        
        note_list =  self.note_client.findNotesMetadata(
                self.auth_token, filter, initial, Limits.EDAM_USER_NOTES_MAX,
                resultSpec)
        return note_list 

    def get_notelist_guid_only(self, initial = 0, **filterargs):
        filter = NoteStore.NoteFilter(**filterargs)
        resultSpec = NoteStore.NotesMetadataResultSpec()
        
        note_list =  self.note_client.findNotesMetadata(
                self.auth_token, filter, initial, Limits.EDAM_USER_NOTES_MAX,
                resultSpec)
        return note_list 

    def yield_notelist_content(self, note_list):
        """Helper to keep huge note contents out of memory.
        TODO: 
        limits and offsets, yeild whole content, pass in whole filter
        """
        for note in note_list:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note

    def yield_note_content_meta(self, initial=0, **filterargs):
        """ Yields a  note plus content from a meta data object that has the
        notebooks, and tag guids as well as title 
        """
        
        note_list =  self.get_note_list_meta(initial,**filterargs)
        for note in note_list.notes:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note
    
    ### Syncing ###
    # used for reducing resource and process time for Analytics

    def yield_sync(self,expunged=False ,initial=0):
        """ Gathers any  content for this class to use 
        TODO: 
            Retrieve more by adding more to the SyncChunkFilter.
            """
        more = True
        filter = NoteStore.SyncChunkFilter(includeExpunged=expunged,
                includeNotes=True )
        while more:
            new_stuff = self.note_client.getFilteredSyncChunk(self.auth_token,initial,
                    1000,filter)
            initial = new_stuff.chunkHighUSN
            ## check to see if anymore stuff
            if  new_stuff.chunkHighUSN == new_stuff.updateCount:
                more = False
                self.latest_usn = new_stuff.chunkHighUSN
                self.last_updated = new_stuff.currentTime
            yield new_stuff

    def initialize_db(self):
        """ Performs the initial content gathering when the database
        encounters an unseen user.
        Returns the _id for the new user
        """
        parser = etree.HTMLParser(target=BasicXmlExtract())
        # already have a user just rsync
        if self.mongo.users.find_one({'_id':self.user_id},{'_id':1}):
            return self.resync_db()

        user_scaffold =  {
            '_id': self.user.id,
            'bool_lsa':False,
            }
        # create the skeletn
        user_id = self.mongo.users.insert(user_scaffold)
        ## now lets  go through the iterable of different types   and update 
        for new_stuff in self.yield_sync():
            # hold all the notes till ready to send a batch to mongo
            notes =[]
            if new_stuff.notes:
                for note in self.yield_notelist_content(new_stuff.notes):
                    ## dont want to store inactive things
                    if note.active:
                        ## Parsing data with lxml into token counts ##
                        data = etree.fromstring(note.content, parser)

                        n = { '_id':note.guid, '_id_user':user_id, 
                            '_id_notebook':note.notebookGuid,
                            'str_title':note.title,'_id_tags':note.tagGuids,
                            'str_content':note.content, 
                            'tokens_content': text_processer(data),
                            }
                        notes.append(n)
                # insert the  note in its own collection 
                # because maybe large note data string?
                notes_id = self.mongo.notes.insert(notes)

    def resync_db(self):
        """ Performs the syncing if we already have initialized 
        TODO: also sync Analytic methods
        """
        parser = etree.HTMLParser(target=BasicXmlExtract())
        for new_stuff in self.yield_sync(expunged=True, initial=self.latest_usn):

            if new_stuff.expungedNotes:
                inactive_notes = [{'_id':n} for n in new_stuff.expungedNotes]
                # collection 
                self.mongo.notes.remove({'_id':{'$in': inactive_notes}})

            if new_stuff.notes:
                new_notes = []
                inactive_notes =[]
                for note in self.yield_notelist_content(new_stuff.notes):
                    ## dont want to store inactive things
                    if not note.active:
                        inactive_notes.append(note.guid)
                    data = etree.fromstring(note.content, parser)
                    n = { '_id':note.guid, '__id_user':self.user_id, 
                        '_id_notebook':note.notebookGuid,
                        'str_title':note.title,'_id_tags':note.tagGuids,
                        'str_content':note.content, 
                        'tokens_content' :text_processer(data),
                        }
                    self.mongo.notes.update({'_id':note.guid},n,  upsert=True)
                    new_notes.append(note.guid)
                if inactive_notes:
                    # collection 
                    self.mongo.notes.remove({'_id':{'$in': inactive_notes}})

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
    
### Analytic ###
################

class EvernoteProfileInferer(EvernoteConnector):
    """ This is the  class that is responsible for extracting all the info
    hidden within the cloud of data from the Evernote service.

    Holds a self.wiki search class to provide searching for related wiki
    articles

    Analytic method importance:
    1. topic_summary
    2. outside_knowledge
    3. fix_data
    4. learning_process

    Ideas:
        Boxplot over all users in a certain method, so you would show their
    totals but then also show how that number is relative to others. Maybe this
    should be an ABC?

    Caching: 
        perhaps pickling the objects and saving them for a week or something, or
    go all out and store full user state, and continually update the corpus and
    docs?.

    http://stackoverflow.com/questions/2775864/python-datetime-to-unix-timestamp
    """ 

    def __init__(self, base_uri, note_url, mongohandle):
        EvernoteConnector.__init__(self,base_uri, note_url,mongohandle)
        self.wiki = Wikipedia(language='en')

    def _lsa_extract(self, update_guids=None):
        """ runs lsa on a user and creates corpus or updates a corpus and lsa
        TODO:
            Store other data in the corpus besides basic text content, ie,
            extracted image, attribute note data, etc...
        """
        docs =[]
        # update the corpus with the only these notes
        if update_guids:
            corpus = Corpus.load(cls, '/data/corpus/'+str(self.user_id))
            # only those that need to be updated from the update_guids
            for x in self.mongo.notes.find(
                    {'_id':{'$in':update_guids}},{'tokens_content':1,'str_title':1}):
                # create the updated doc
                d =  Document(x['tokens_content'],name=x['str_title'],top=50)
                # set the id to what we want
                d._id = x['_id']
                docs.append(d)
                # remove old doc because corpus will still have old content
                corpus.remove(d)
            corpus.extend(docs)

        else: # LSA not been done before
            for x in self.mongo.notes.find( # all notes of this user
                        {'_id_user':self.user_id},{'tokens_content':1,'str_title':1}):
                    d =  Document(x['tokens_content'],name=x['str_title'],top=30)
                    d._id = x['_id']
                    docs.append(d)
            corpus = Corpus(docs)

        # picked arbitrarily
        corpus.reduce(50)
        vectors = corpus.lsa.vectors
        #doc.id and dic of concept vectors
        for doc, conc in vectors.items():
            words=[]
            for index, weight in conc.items():
                if abs(weight) >0.5:
                        words.append(corpus.lsa.terms[index])
            # add only if not already present the minimaized tokens to the note
            self.mongo.notes.update({'_id':doc},{'$addToSet':{'tokens_lsa':{'$each': words}}})
        # boolean to signal lsa has been done
        self.mongo.users.update({'_id':self.user_id},{'$set':{'tokens_lsa':True}})
        ## this might block for a while. TODO: split it into a new thread
        corpus.save('/data/corpus/'+str(self.user_id))

    def topic_summary(self, **filterargs):
        """ Returns what are the main features that make up this topic.
        Features, setiment analysis, lsa main features, time deltas,
        could be any  mashup of other statistical technique.
        Ideas:
            Features are not just word counts and tags,
            Could be any number of other methods.
        """
        note_words ={}
        if not self.mongo.users.find_one({'_id':self.user_id, 'bool_lsa':True},{'bool_lsa':1}):
            # we have not done lsa before, do it now
            self._lsa_extract()
        if filterargs.keys():
            # check if lsa has already been done
        
            for x in self.mongo.notes.find({'_id_user':self.user_id},{'tokens_lsa':1}):
                note_words[(x['_id'])] = x['tokens_lsa']
            return note_words
           
        meta_list = [x.guid for x in self.get_notelist_guid_only(**filterargs).notes]
        for x in self.mongo.notes.find({'_id':{'$in':meta_list}}, {'tokens_lsa':1}):
            note_words[(x['_id'])] = x['tokens_lsa']
        return note_words

    #def wiki_knowledge(self, data):
    def wiki_knowledge(self, note_guid, query, data):
        """ Helper for storing a pattern wiki search query object. 
        Must return the newly creaded data object  """
        document = {}
        document['title'] = data.title
        # links to other perhaps simialr topics
        document['intra_links'] = data.links[:5]
        # outside learning?
        document['extern_links'] = data.external[:5]
        # only want first section not a huge file
        document['data'] = data.sections[0].content
        self.mongo.notes.update(
                {'_id':note_guid, 'knowledge.str_query':query}, 
                {'set':{ 'wikipedia':document}})
        # to set a constistant method call across all knowledge funcs??
        return  {'wikipedia':document}

    def outside_knowledge(self, note_guid, query,  service='wiki'):
        """ Gather resources that are related to this note from other services.
        Prime canidates are wikipedia, duckduckgo, freebase, news feeds, etc..
        Params:
            note_guid
            query = the string that you want searched for
            service = (optional) which service to query, default wikipedia
        mongo.notes{ knowledge scheme layout
        "An doc of  of past query strings that contain result objects with service
        specific data.
        {knowledge: 
            {
            str_query: string that was queried on {
            wikipedia: {
                intra_links: [links], extern_links:[links], data:str
            }
            duckduckgo:{
            }
                ....
            }
        }
        """
        # retrive note that has this query string embedded
        # return only the embedded query doc?
        note = self.mongo.notes.find_one(
                {'_id':note_guid, 'knowledge.str_query':query}, 
                    {'knowledge.str_query':1})
        # query returned sucessful
        if note and service:
            return note[service]
        elif note:
            return note
        # failed, must not have done it before
        else:
            # get the search engine attached to the class
            api = getattr(self, service)
            data = api.search(query,cached=True,timeout=10) 
            if data:
                #call the right method for this service
                f = getattr(self,service+'_knowledge','wiki_knowledge')
                return f(note_guid, query, data) 

    def fix_data(self, training_data, testing_data):
        """ Uses classification to suggest labels to the data according to the
        learned classifications.
        """
        pass

    def word_count(self, **filterargs):
        """ Counts the total number of words in some sort of content of 
        a user's profile. 
        Ideas:
            By time, cluster and not just a single object?
            Note html links in their own counter?
        """
        c = Counter()

        if not filterargs:
            for x in self.mongo.notes.find(
                    {'_id_user':self.user_id},{'tokens_content':1}):
                c.update(x['tokens_content'])
            return c

        meta_list = [x.guid for x in self.get_notelist_guid_only(**filterargs).notes]
        for x in self.mongo.notes.find({'_id':{'$in':meta_list}},
                {'tokens_content':1}):
            c.update(x['tokens_content'])
        return c
    
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

    def readability(self, **filterargs):
        """ Computes a score based upon what an douchebag would mark you
        down for when student critiqing papers.
        Ideas:
            pattern.metrics.flesh_reading_ease
        """
        output={}
        if not filterargs.keys():
            for x in self.mongo.notes.find(
                    {'_id_user':self.user_id},{'str_content':1}):
                output[(x['_id'])] = flesch_reading_ease(x['str_content'])
        return output

        meta_list = [x.guid for x in self.get_notelist_guid_only(**filterargs).notes]
        for x in self.mongo.notes.find(
                {'_id':{'$in':meta_list}}, {'str_content':1}):
            output[(x['_id'])] = flesch_reading_ease(x['str_content'])
        return output

 
if __name__ == "__main__":
    pass



