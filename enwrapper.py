# -*- coding: utf-8 -*-

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

from pymongo.binary import Binary # must store md5hash in mongo binary

from lxml import etree

__all__ = ['Errors','Limits', 'Types', 'ENHOST', 'AUTHTOKEN',
        'en_userstore_setup', 'en_notestore_setup',
        'NoteStore', 'EvernoteConnector']

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
        {doc_notebooks} = array of  docs, ex:{_id: b.guid, str_name: b.name, _id_tags:[ tags.guid[}
        {doc_tags} = array of embedded docs, exx {_id: t.guid, str_name: t.name}
        {int_logins} = counter for how many times we have created class 

    mongo.notes:
        {_id_user: self.user_id} = the owner's guid
        {str_title: note.title} = note title 
        {_id_notebook: note.notebook} = this note's notebook guid 
        {_id_tags: [note.tags]} =  the array of tags  guids 
        {str_tags: [tag_names]} = array of actual tag names
        {str_content: note.content} = note content
        {tokens_resources: resource} = extracted tokens from note resource
        {str_content_hash: hash} = content md5 Hash stored in pymongo.Binary

    TODO:
        1. Error checking, alot of it, that's the whole reseason behind the verbose
       method calling.
        2. storing of time info for notebooks, tags, resources and note content.
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
        # for content extraction
        self.parser = etree.HTMLParser(target=BasicXmlExtract())
        self.mongo = mongohandle
        if not self.mongo.users.find_one({'_id':self.user_id},{'_id':1}):
            user_scaffold =  {
                '_id': self.user.id,
                }
            # create the skeletn
            user_id = self.mongo.users.insert(user_scaffold,safe=True)
            #self.initialize_db()
            #TODO: fix this bug where I have to resync because highUSN is None
            # when using self.yeild_sync in initialize_db() 
            self.resync_db()
            self.mongo.users.update({'_id':self.user_id},{'$inc':{'int_logins':1}})
        else:
            self.resync_db()
            self.mongo.users.update({'_id':self.user_id},{'$inc':{'int_logins':1}})

    @property
    def user(self):
        """ returns the user object from evernote 
        TODO:
            Currently only used for the user's guid so it could just be a stored
            variable on this class, rather than calling the getUser everytime."""
        return self.user_client.getUser(self.auth_token)

    @property
    def m_user(self):
        return self.mongo.users.find_one({'_id':self.user_id})

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

    def yield_notelist_content_meta(self, initial=0, **filterargs):
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
        print 'getting syncState'
        print self.latest_usn
        print syncState.updateCount
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
            * Notebooks
            * Tags
            * expunged (if expunged is True)
            * TODO.... more evernote data
        """
        more = True
        filter = NoteStore.SyncChunkFilter(includeExpunged=expunged,
                includeNotes=True, includeResources=True, 
                includeNotebooks=True, includeTags=True)
        while more:
            new_stuff = self.note_client.getFilteredSyncChunk(self.auth_token, initial,
                    500,filter)
            # carfull if no objects in this chunk this is None and we dont want 
            # to have a none object for our self.latest_usn
            print new_stuff.chunkHighUSN
            if new_stuff.chunkHighUSN:
                initial = new_stuff.chunkHighUSN
            ## check to see if anymore stuff
            if  new_stuff.updateCount == new_stuff.chunkHighUSN or not new_stuff.chunkHighUSN: 
                more = False
                self.latest_usn = initial
                self.last_updated = new_stuff.currentTime
            yield new_stuff

    def sync_note(self, note):
        """ simplifies the code for the resync_db method """
        tag_names = None
        resource_string = None
        # check if this is a completley new note
        is_new = self.mongo.notes.find_one(
                {'_id':note.guid},{'str_content_hash':1})
        # dont want to fetch same content
        if not is_new or is_new.get('str_content_hash') != Binary(note.contentHash):
            content =  self.note_client.getNoteContent(self.auth_token, note.guid)
            data = etree.fromstring(content, self.parser)
            self.mongo.notes.update({'_id':note.guid},
                    {"$set":{'str_content':content, 'tokens_content':text_processer(data),
                        'str_content_hash':Binary(note.contentHash)}},upsert=True)

        if note.tagGuids:
            # we want  string names too
            tag_names = [tag.name for tag in self.note_client.listTagsByNotebook(
                self.auth_token,note.notebookGuid) if tag.guid in note.tagGuids]

        if note.resources:
            resource_string = text_processer(
                    " ".join([self.note_client.getResourceSearchText(
                    self.auth_token,r.guid) for r in
                    note.resources]))
        self.mongo.notes.update({'_id':note.guid},
            {"$set":{
            '_id_user':self.user_id, '_id_notebook':note.notebookGuid,
            'str_title':note.title,'_id_tags':note.tagGuids,
            'str_tags': tag_names, 'tokens_resources': resource_string,
            }},  upsert=True)
        return note.guid

    def resync_db(self, expunged=True):
        """ Performs the syncing if we already have initialized 
        Returns new note guids in a list
        """
        new_notes = []
        if not self.need_sync:
            return None
        for new_stuff in self.yield_sync( initial=self.latest_usn, expunged=expunged):
            print "GETTING RESYNCED NEW THINGS"

            # database deleted notes
            if new_stuff.expungedNotes:
                inactive_notes = [{'_id':n} for n in new_stuff.expungedNotes]
                self.mongo.notes.remove({'_id':{'$in': inactive_notes}})

            # new/updated notebooks 
            if new_stuff.notebooks:
                notebooks = [{'_id':b.guid, 'str_name':b.name,
                    '_id_tags':[t.guid for t in 
                        self.note_client.listTagsByNotebook(self.auth_token,b.guid)]} 
                            for b in new_stuff.notebooks]
                self.mongo.users.update({'_id':self.user_id},{'$addToSet':{'doc_notebooks':{'$each':notebooks}}})


            # new tags
            if new_stuff.tags:
                tags = [{'_id':t.guid, 'str_name': t.name} for t in new_stuff.tags]
                self.mongo.users.update({'_id':self.user_id},{'$addToSet':{'doc_tags':{'$each':tags}}})

            # new notes
            if new_stuff.notes:
                new_notes = [self.sync_note(n) for n in new_stuff.notes if n.active]
                # user deleted notes
                inactive_notes = [self.sync_note(n) for n in new_stuff.notes if not n.active]
                self.mongo.notes.remove({'_id':{'$in': inactive_notes}})

        return new_notes

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
 
if __name__ == "__main__":
    pass
