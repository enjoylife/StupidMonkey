# -*- coding: utf-8 -*-

import os.path

import cherrypy
import simplejson as json
from bson import json_util

from helpers import mongo_connect
from enwrapper import *
from analytics import EvernoteProfileInferer

mongo = mongo_connect('test', extra=True)

class Welcome(object):

    exposed = True

    def __init__(self):
        self.evernote = EvernoteProfileInferer(ENHOST, AUTHTOKEN, mongo)

    @cherrypy.expose
    def home(self):
        """ Creates the user tree where the top root is the username. 
        The root's immediate children are the notebooks. 
        The notebooks children are the notes. 
        """
        self.evernote.resync_db()
        tree = {}
        tree['name'] = self.evernote.user.username
        tree['children'] = []
        user = self.evernote.m_user
        for book in user.get('doc_notebooks'):
            subtree = {}
            subtree['name'] = book.get('str_name')
            subtree['children'] = []
            # find notes with this notebook and tag
            for note in self.evernote.mongo.notes.find(
                    {'_id_notebook':book.get('_id')},{'str_title':1}):
                n = {'name':note.get('str_title')}
                subtree['children'].append(n)
            tree['children'].append(subtree)
        return tree

    @cherrypy.expose
    def notes(self):
        n = [n for n in self.evernote.mongo.notes.find()]
        return str(n)


    @cherrypy.expose
    def default(self, extras='', more=''):
        return {"test": "hellow world"}

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
root.data = Welcome()

conf = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 5000,
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
