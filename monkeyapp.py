# -*- coding: utf-8 -*-
import os.path

# Web App
import cherrypy
import simplejson as json
from bson import json_util

class Welcome(object):

    exposed = True

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
