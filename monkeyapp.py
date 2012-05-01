# -*- coding: utf-8 -*-
import os.path
# Text processing
from lxml import etree
from helpers import  ngrams, gen_stops, TokenXmlExtract

#evernote
from enwrapper import *

# Web App
import cherrypy
import simplejson as json
from bson import json_util

class Welcome(object):

    exposed = True

    @cherrypy.expose
    def default(self, extras='', more=''):
        return {"test": "hellow world"}

class EnInfer(object):
    """ Class that interacts with evernote Thrift classes """
    exposed = True

    def __init__(self, en_user=None):
        self.userStore = en_userstore_setup(ENHOST)
        # Get the URL used to interact with the contents of the user's account
        if en_user == AUTHTOKEN:
            noteStoreUrl = self.userStore.getNoteStoreUrl(AUTHTOKEN)
        self.note_store = en_notestore_setup(noteStoreUrl)

    @cherrypy.expose
    def wordcount(self,num=50, filter=None):
        """ shows word counts of users data """ 
        # we have all the required en_thrift crap, lets put it to use
        emptyfilter = NoteStore.NoteFilter(filter)
        parser = etree.HTMLParser(target=TokenXmlExtract())
        notes = self.note_store.findNotes(AUTHTOKEN,emptyfilter,0,Limits.EDAM_USER_NOTES_MAX)
        for n in notes.notes:
            data = self.note_store.getNoteContent(AUTHTOKEN,n.guid)
            # resuses the same parser instance, aka same counts
            stuff= etree.fromstring(data, parser)
        return stuff.most_common(num)

    @cherrypy.expose
    def topic(self, num=50, filter=None):
        """ Shows infered topics from users data """
        emptyfilter = NoteStore.NoteFilter(filter)

########################################
### Cherrypy Custom Tools and Hooks ####
########################################

def bson_json_handler(*args, **kwargs):
    """ Mongodb json handler for cherrypy """
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.JSONEncoder(default=json_util.default).iterencode(value)

###############################################
### Cherrypy APP Settings and root classes ####
###############################################


root = Welcome()
root.data = EnInfer(AUTHTOKEN)


conf = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8000,
    },
    '/': {
        'tools.staticdir.root': os.path.dirname(os.path.abspath(__file__)),
        },
    '/static': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir':'static',
        },
    '/evernote': {
        #'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        'tools.json_out.on' : True ,
    },
    '/data': {
        'tools.json_out.on' : True ,
        'tools.json_out.handler' : bson_json_handler,
    }
}
if __name__ == '__main__':
    cherrypy.engine.autoreload.on = True
    cherrypy.quickstart(root, '/', conf)
