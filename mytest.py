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

import os.path

# Text processing
from lxml import etree
import unicodedata
from collections import Counter
from helpers import  ngrams, gen_stops

import cherrypy
# cherrypy json dispatcher
import simplejson as json
from bson import json_util

# Once completed development, simply change "sandbox.evernote.com" to "www.evernote.com".
ENHOST = "sandbox.evernote.com"
# Real applications authenticate with Evernote using OAuth
AUTHTOKEN = "S=s1:U=fc7c:E=13e4bc83ae7:C=136f4170ee7:P=4f:A=en-devtoken:H=24ec040d53309543177af5b3a9b2a33c"

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

def en_check_version():
    versionOK = userStore.checkVersion("Evernote EDAMTest (Python)",
                                   UserStoreConstants.EDAM_VERSION_MAJOR,
                                   UserStoreConstants.EDAM_VERSION_MINOR)
    print "Is my Evernote API version up to date? ", str(versionOK)
    print ""
    if not versionOK:
        exit(1)


class EnExtract(object):

    def __init__(self):
        self.container = Counter()
        self.stops = gen_stops()

    def data(self, data):
        data = unicodedata.normalize('NFKD',
                 data).encode('ascii','ignore').lower().split()
        if data:
            self.container.update([d for d in data if d not in self.stops])
            self.container.update([x for x in ngrams(tuple(data),2,2)])

    def close(self):
        return  self.container

class Welcome(object):

    exposed = True

    def default(self, extras='', more=''):
        return {"test": "hellow world"}
    default.exposed = True

class EnData(object):

    exposed = True

    def GET(self, en_user=AUTHTOKEN):
        """ Loads a evernote users data """ 
        userStore = en_userstore_setup(ENHOST)
        # Get the URL used to interact with the contents of the user's account
        if en_user == AUTHTOKEN:
            noteStoreUrl = userStore.getNoteStoreUrl(AUTHTOKEN)
        noteStore = en_notestore_setup(noteStoreUrl)

        # we have all the required en_thrift crap, lets put it to use
        emptyfilter = NoteStore.NoteFilter()
        parser = etree.HTMLParser(target=EnExtract())
        notes = noteStore.findNotes(AUTHTOKEN,emptyfilter,0,Limits.EDAM_USER_NOTES_MAX)
        for n in notes.notes:
            data = noteStore.getNoteContent(AUTHTOKEN,n.guid)
            # resuses the same parser instance, aka same counts
            stuff= etree.fromstring(data, parser)
        return stuff.most_common(50)




########################################
### Cherrypy Custom Tools and Hooks ####
########################################

def bson_json_handler(*args, **kwargs):
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.JSONEncoder(default=json_util.default).iterencode(value)


root = Welcome()
root.data = EnData()


conf = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8000,
    },
    '/': {
        'tools.staticdir.root': os.path.dirname(os.path.abspath(__file__))
        },
    '/static': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir':'static'
        },
    '/data': {
        'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        'tools.json_out.on' : True ,
        'tools.json_out.handler' : bson_json_handler,
    }
}
if __name__ == '__main__':
    cherrypy.engine.autoreload.on = True
    cherrypy.quickstart(root, '/', conf)
