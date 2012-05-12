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

from helpers import (BasicXmlExtract, text_processer, flesch_reading_ease)

from lxml import etree

from pattern.web import Wikipedia
from pattern.vector import Corpus, Document

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
    Returns: a notestore client.
    """
    nstore =  NoteStore.Client(
            TBinaryProtocol.TBinaryProtocol(
                THttpClient.THttpClient(user_note_store_url)))
    return nstore

### Main ###
############
class EvernoteConnector(object):
    """ This is to ease the connection to the evernote thrift api, and provide a
    mongo database layer for speeding up requests for analytic content or just
    straight up  reducing calls to the Evernote servers.

    Naming convention of the public methods is to be pep8, which is  
    to help distinguish between the methods of this class and the thrift
    generated classes, in which they use camelCase.

    These are the fields used in the mongo collections 
    mongo.users:
        {_id: user_id} =  user guid
    mongo.notes:
        {_id_user: self.user_id} = the owner's guid
        {str_title: note.title} = note title 
        {_id_notebook: note.notebook} = this note's notebook guid 
        {_id_tags: [note.tags]} =  the array of tags  guids 
        {str_tags: [tag_names]} = array of actual tag names
        {str_content: note.content} = note content

    TODO:
        1. Error checking, alot of it, that's the whole reseason behind the verbose
       method calling.
        2. storing of time info for both resource and note content.
    """

    def __init__(self, base_uri, note_url, mongohandle):
        """ We must create the user and note clients in order to get access to
        the Evernote API.
        """
        self.user_client = en_userstore_setup(base_uri)

        # Get the URL used to interact with the contents of the user's account
        # but first check and see if were still using dev token
        if note_url is  AUTHTOKEN:
            noteStoreUrl = self.user_client.getNoteStoreUrl(AUTHTOKEN)
            # set the auth_token for all later api calls
            self.auth_token = AUTHTOKEN
        else:
            #TODO oauth handshake
            pass

        self.note_client = en_notestore_setup(noteStoreUrl)

        # evernote  data for api and sync calls
        self.user_id = self.user_client.getUser(self.auth_token).id
        self.mongo = mongohandle
        if not self.mongo.users.find_one({'_id':self.user_id},{'_id':1}):
            self.initialize_db()
            #TODO: fix this bug where I have to resync because highUSN is None
            # when using self.yeild_sync in initialize_db() 
            self.resync_db()
            self.mongo.users.update({'_id':self.user_id},{'$inc':{'logins':1}})
        self.resync_db()
    @property
    def user(self):
        """ returns the user object from evernote 
        TODO:
            Currently only used for the user's guid so it could just be a stored
            variable on this class, rather than calling the getUser everytime."""
        return self.user_client.getUser(self.auth_token)

    ### Editing / Testing Helpers ###

    def create_note(self, title, content , **kwargs):
        """ Helper to create an evernote note"""""
        note = Types.Note( title , content,  **kwargs)
        # cant contain extra whitespace
        note.title = title.strip()
        note.content = self._formatNoteContent(content)
        return self.note_client.createNote(self.auth_token, note)

    def update_note(self, note, **kwargs):
        """ Helper to update the note """
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
            
    def trash_notes(self):
        """ yeilds the inactive notes from this user """
        return self.yield_note_list_content(self.get_notelist(inactive=True))

    def empty_trash(self):
        self.note_client.expungeInactiveNotes(self.auth_token)

    ### Querying ###

    def get_note_content(self, note):
        """ Returns a single notes  string content """
        return self.note_client.getNoteContent(self.auth_token, note.guid)

    def get_notelist(self, initial = 0, **filterargs):
        """ Returns a evernote noteList offset by intial and filtered with any
        extra keyargs that are sent to a NoteFilter.
        """
        filter = NoteStore.NoteFilter(**filterargs)
        
        note_list =  self.note_client.findNotes(
                self.auth_token, filter, initial, Limits.EDAM_USER_NOTES_MAX)
        return note_list 

    def get_notelist_meta(self, initial = 0, **filterargs):
        """ Returns a evernote NotesMetadataList offset by intial and filtered with any
        extra keyargs that are sent to a NoteFilter.
        Fields that are returned:
            * Titles
            * Notebook guid
            * Tags' guid's
        """ 
        filter = NoteStore.NoteFilter(**filterargs)
        resultSpec = NoteStore.NotesMetadataResultSpec(
                # titles, notebooks guid, and tag guids
                includeTitle=True,includeNotebookGuid=True, includeTagGuids=True)
        
        notes_metadata_list =  self.note_client.findNotesMetadata( self.auth_token,
                filter, initial, Limits.EDAM_USER_NOTES_MAX, resultSpec)
        return  notes_metadata_list

    def get_notelist_guid_only(self, initial = 0, **filterargs):
        """ Returns a evernote NotesMetadataList with only the notes' guid's
        filled in,  offset by intial and filtered with any
        extra keyargs that are sent to a NoteFilter.
        """
        filter = NoteStore.NoteFilter(**filterargs)
        resultSpec = NoteStore.NotesMetadataResultSpec()
        
        note_list =  self.note_client.findNotesMetadata(
                self.auth_token, filter, initial, Limits.EDAM_USER_NOTES_MAX,
                resultSpec)
        return note_list 

    def yield_notelist_content(self, note_list):
        """Helper to keep huge note contents out of memory. """
        for note in note_list:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note

    def yield_note_content_meta(self, initial=0, **filterargs):
        """ Yields a note plus content from a noteMetadata object that has it's
        fields filled in according to the self.get_notelist_meta function.
        """
        
        note_list =  self.get_note_list_meta(initial,**filterargs)
        for note in note_list.notes:
                note.content = self.note_client.getNoteContent(self.auth_token, note.guid)
                yield note
    
    ### Syncing ###
    # used for reducing resource and process time for Analytics

    @property
    def need_sync(self):
        """ Determines if this user needs to sync with evernotes servers. 
        TODO: put latest_usn and last_updated into class properties that call
        mongo.users"""
        syncState = self.note_client.getSyncState(self.auth_token)
        return (self.last_updated < syncState.fullSyncBefore) or (self.latest_usn < syncState.updateCount)

    @property
    def latest_usn(self):
        return self.mongo.users.find_one(
            {'_id':self.user_id}).get('latest_usn',0)

    @latest_usn.setter
    def latest_usn(self, u):
        self.mongo.users.update({'_id':self.user.id},
                {'$set':{'latest_usn':u}},safe=True)

    @property
    def last_updated(self):
        return self.mongo.users.find_one(
            {'_id':self.user_id}).get('last_updated',0)

    @last_updated.setter
    def last_updated(self, t):
        self.mongo.users.update({'_id':self.user.id},
                {'$set':{'last_updated':t}},safe=True)

    def yield_sync(self,initial=0, expunged=False):
        """ Gathers any  content for this class to use 
        Fields that are returned:
            * Notes
            * expunged (if expunged is True)
            * TODO.... more evernote data
        """
        more = True
        filter = NoteStore.SyncChunkFilter(includeExpunged=expunged,
                includeNotes=True, includeResources=True)
        while more:
            new_stuff = self.note_client.getFilteredSyncChunk(self.auth_token, initial,
                    256,filter)
            # carfull if no objects in this chunk this is None and we dont want 
            # to have a none object for our self.latest_usn
            if new_stuff.chunkHighUSN:
                initial = new_stuff.chunkHighUSN
            ## check to see if anymore stuff
            if  new_stuff.updateCount == new_stuff.chunkHighUSN or not new_stuff.chunkHighUSN: 
                more = False
                self.latest_usn = initial
                self.last_updated = new_stuff.currentTime
            yield new_stuff

    def initialize_db(self):
        """ Performs the initial content retrieval when the database
        encounters an unseen user.The amount of content
        and certain types returned are determined by the
        self.yield_notelist_content

        Returns the mongo.users _id  for the new user if this is really the
        first time we have seen this user, else it returns None and just calls
        self.resync_db
        """
        resource_string = None
        tag_names = None
        
        parser = etree.HTMLParser(target=BasicXmlExtract())
        user_scaffold =  {
            '_id': self.user.id,
            'bool_lsa':False,
            }
        # create the skeletn
        user_id = self.mongo.users.insert(user_scaffold,safe=True)
        ## now lets  go through the iterable of different types   and update 
        for new_stuff in self.yield_sync(expunged=False, initial=0):
            # hold all the notes till ready to send a batch to mongo
            notes =[]
            if new_stuff.notes:
                for note in self.yield_notelist_content(new_stuff.notes):
                    ## dont want to store inactive things
                    if note.active:
                        ## Parsing data with lxml into a big string ##
                        data_string = etree.fromstring(note.content, parser)
                        ## add tag string names from this notebook if they are in this note
                        if note.tagGuids:
                            tag_names = [tag.name for tag in \
                                self.note_client.listTagsByNotebook(
                                self.auth_token,note.notebookGuid) if tag.guid
                                in note.tagGuids]
                        if note.resources:
                            resource_string = text_processer(
                                    " ".join([self.note_client.getResourceSearchText(
                                self.auth_token,r.guid) for r in
                                note.resources]))

                        n = { '_id':note.guid, '_id_user':user_id, 
                            '_id_notebook':note.notebookGuid,
                            'str_title':note.title,'_id_tags':note.tagGuids,
                            'str_tags': tag_names,
                            'str_content':note.content, 
                            'tokens_content': text_processer(data_string),
                            'tokens_resources': resource_string,
                            }
                        notes.append(n)
                # insert the  note in its own collection 
                # because maybe large note data string?
                notes_id = self.mongo.notes.insert(notes)
        return user_id

    def resync_db(self):
        """ Performs the syncing if we already have initialized 
        Returns the resynced note guids
        TODO: also sync Analytic methods
        """
        tag_names = None
        resource_string = None
        new_note_guids = []
        parser = etree.HTMLParser(target=BasicXmlExtract())
        if not self.need_sync:
            return None
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
                        continue

                    new_note_guids.append(note.guid)
                    data = etree.fromstring(note.content, parser)
                    ## add tag string names from this notebook if they are in this note
                    if note.tagGuids:
                        tag_names = [tag.name for tag in \
                                self.note_client.listTagsByNotebook(
                                self.auth_token,note.notebookGuid) if tag.guid
                                in note.tagGuids]

                    if note.resources:
                        resource_string = text_processer(
                                " ".join([self.note_client.getResourceSearchText(
                                self.auth_token,r.guid) for r in
                                note.resources]))
                    self.mongo.notes.update({'_id':note.guid},
                        {"$set":{
                        '__id_user':self.user_id, '_id_notebook':note.notebookGuid,
                        'str_title':note.title,'_id_tags':note.tagGuids,
                        'str_tags': tag_names, 'str_content':note.content, 
                        'tokens_content' :text_processer(data),
                        'tokens_resources': resource_string,
                        }},  upsert=True)
                    new_notes.append(note.guid)
                if inactive_notes:
                    # collection 
                    self.mongo.notes.remove({'_id':{'$in': inactive_notes}})
        return new_note_guids

    def remove_from_db(self):
        """ Removes a note's content from the database
        """
        pass

    ### Private methods ###
    
    def _formatNoteContent(self, innerContent):
        """ Simplifies creating notes
        """
        content = '<?xml version="1.0" encoding="UTF-8"?>'
        content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">'
        content += '<en-note>' + innerContent
        content += '</en-note>'
        return content

### Analytic subclass
class EvernoteProfileInferer(EvernoteConnector):
    """ This is the  class that is responsible for extracting all the info
    hidden within the cloud of data from the Evernote service.

    Holds a self.wiki search class to provide searching for related wiki
    articles

    Ideas:
        Boxplot over all users in a certain method, so you would show their
    totals but then also show how that number is relative to others. Maybe this
    should be an ABC?
    http://stackoverflow.com/questions/2775864/python-datetime-to-unix-timestamp

    Caching: 
        perhaps pickling the objects and saving them for a week or something, or
    go all out and store full user state, and continually update the corpus and
    docs? Right now the corpus object is pickled into a basic file, we could
    better yet connect to a mongo GridFS and store it their?

    These are the fields used in the mongo collections 
    mongo.users:
        {_id: user_id} 
        {bool_lsa: False}  =  a boolean for lsa analysis. 

    mongo.notes:
        {_id_user: self.user_id} 
        {str_title: note.title}  
        {_id_notebook: note.notebook} 
        {_id_tags: [note.tags]} 
        {str_tags: [tag_names]}
        {str_content: note.content}

        {tokens_content: [~note.content.split()]} =  the extracted words for this note
        {tokens_lsa: [~tokens.lsa.reduce()]} = the reduced vectors for note
    """ 

    def __init__(self, base_uri, note_url, mongohandle):
        """ Create the wipedia search object 
        """
        EvernoteConnector.__init__(self,base_uri, note_url,mongohandle)
        self.wiki = Wikipedia(language='en')

    def load_corpus(self):
        """ Load a corpus, used because we might change corpus saving and
        retrieving and with this we can be sure any changes wont affect other
        methods
        """
        return Corpus.load(cls, '/data/corpus/'+str(self.user_id))

    def save_corpus(corpus, update=False):
        """ Save a corpus, used because we might change corpus saving and
        retrieving and with this we can be sure any changes wont affect other
        methods
        """
        corpus.save('/data/corpus/'+str(self.user_id), update)

    def sync_corpus(update_guids=None):
        """Creates  a new corpus on all notes if we dont supply a note guid
        list, if list, we only updates a corpus.
        TODO:
            Store other data in the corpus besides basic text content, ie,
            extracted image, attribute note data, etc...
            catch corpus not found file error?
        """
        docs =[]
        old_corpus =  self.mongo.users.find_one({'_id':self.user_id},
                {'corpus':1}).get('corpus')
        # make sure we already created corpus
        if old_corpus and self.need_sync:
            if not update_guids:
                # nothing given to update
                return
            corpus = self.load_corpus()
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
            self.save_corpus(corpus)
        # dont need the sync, do nothing
        elif old_corpus:
            return
        # not been done before
        else: 
            for x in self.mongo.notes.find( # all notes of this user
                        {'_id_user':self.user_id},{'tokens_content':1,'str_title':1}):
                    d =  Document(x['tokens_content'],name=x['str_title'],top=30)
                    d._id = x['_id']
                    docs.append(d)
            corpus = Corpus(docs)
            self.save_corpus(corpus)
            self.mongo.users.update({'_id':self.user_id},{'$set':{'corpus':True}})

    def _lsa_extract(self, update_guids=None):
        """ runs lsa on a user and creates  a new corpus on all notes if we dont
        supply a note guid list, if list, we only updates a corpus.
        TODO:
            Store other data in the corpus besides basic text content, ie,
            extracted image, attribute note data, etc...
        """
        corpus = self.load_corpus()
        # picked arbitrarily
        corpus.reduce(25)
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
        self.save_corpus(corpus,update=True)

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

    def suggest_tags(self, ):
        """ Uses cosine similarity to suggest tags to the note 
        IDEAS:
            more weight for same notebook
            more weight for relative creation time
        """
        corrected_notes = {}

        if not self.mongo.users.find_one({'_id':self.user_id, 'bool_lsa':True},{'bool_lsa':1}):
            # we have not done lsa before, do it now we want a fast KNN
            self._lsa_extract()
        
        corpus = Corpus.load(cls, '/data/corpus/'+str(self.user_id))
        ## only untagged notes
        untaged_notes = self.mongo.notes.find({'_id_tags':None},{})
        for note in untaged_notes:
            suggested_tags =  set()
            # get the doc from the corpus
            for weight, doc in corpus.nearest_neigbors(corpus[(note['_id'])], top=5):
                # get the similar doc
                tags = self.mongo.notes.find_one(
                        {'_id':doc.id},{'str_tags':1}).get('str_tags')
                if tags:
                    suggested_tags.update(tags)
            corrected_notes[(note['_id'])] = suggested_tags
        return corrected_notes

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

    def update_corpus(self):
        """ Updates the users analityc corpus if their is any changes
        in their note's content.
        """
        pass
 
if __name__ == "__main__":
    pass
