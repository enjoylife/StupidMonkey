"""Ideas for use
{collections}= [users, groups, goals, awards]
things to think about:
a) embed one to many relationships within the one
b) what needs to be queried the most often
c) catching typing errors before model insertion (dev side)
d) indexing over multiple properties (aka shared key)

Rember no templates, redirects, just simple json return values
mongo.(type)s    *type is always plural

first case is the object and no identifier -> returns collection
'/api/user' or '/api/goal'
second case is a specific object identifier -> returns object specified
'/api/user/219df93' or '/api/user?uid=219df93' 
'/api/goal/13213' or '/api/goal/?gid=13213'

"""

from __future__ import unicode_literals
import datetime
import sys
from urllib2 import urlopen, HTTPError
from urllib import urlencode, quote

import simplejson as json
import cherrypy

from pymongo import Connection 
from bson import json_util
from pymongo.errors import ConnectionFailure, OperationFailure

# currently not focusing on this functionality
#import redis
#from redis import ConnectionError

### Generaic Functions  ###

def redis_connect():
    """ 
    Connect to a Redis instance, and write to stdio if failure. 
    """
    try:
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.ping()
        sys.stdout.write(" ** Redis connected **\n")
    except ConnectionError, e:
        sys.stderr.write("Could note connect to Redis: %s\n" %e)
        sys.exit(1)

def mongo_connect(name,extra=False):
    """ 
    Connect to a MongoDB database, and write to stdio if failure. 
    Params: 
        name: the database name to connect to EX: test
    """
    try:
        #global connection
        connection = Connection()
        #database connection 
        db = connection[name]
        if extra:
            sys.stdout.write(" ** MongoDB connected to %s **\n" % name)

        # Good time to ensure that we have fast indexs, or should I wait?? 
        #db.users.ensureIndex({'username':1}, {unique: True})
        return db
    except ConnectionFailure, e:
        sys.stderr.write("Could Not connect to MongoDB: %s\n" %e)
        sys.exit(1)

def graph_facebook(query,a_token=None, args={}):
    """
    Helper for calling url of facebook graph api.

    Params: 
        query: the string for the specific graph endpoint.
        a_token: the acces_token 
        args: The query string args 

    Success: dict of query response.
    Failure: False. 
    """
    if a_token:
        s = ("https://graph.facebook.com%s?"% query) + a_token +urlencode(args)
        try:
            return json.load(urlopen(s))
        except HTTPError, e:
            return e 
    else:
        return "NO ACCEsS_TOKEN"
    #TODO:else: get acces_token from db

### Functions needed for logging in a simple user ###

def facebook_2nd_leg(code, config):
    """
    Helper to complete Auth dance by using the acess_token needed for
    querying the facebook graph on a given user's information.

    Params:
        code: access_token from Facebook login dance
        config: the flask app.config 

    Success: auth_token.  
    Failure: returns False.
    """
    s = "{0:s}".format(config['FACEBOOK_ENDPOINT']) +\
        "/oauth/access_token?client_id={0:s}".format(config['FACEBOOK_ID']) +\
        "&redirect_uri={0:s}&client_secret={1:s}&code={2:s}".format(
                quote(config['FACEBOOK_REDIRECT']),
                config['FACEBOOKSECRET'], code)
    try:
        f = urlopen(s)
        token= f.read()
        return token
    except HTTPError, e:
        return False

    # TODO:store id
    # TODO: create User in DB


### Classes for Exposed REST Interface ###

mongo = mongo_connect('test', extra=True)

class Welcome(object):

    exposed = True

    def default(self, extras='', more=''):
        return 'Hello World plus: %s' % extras, more
    default.exposed = True

class Home(object):
    pass

def error( code,extras=None):
    """
    Possible error msg's for API?
    """
    if code== -1:
        reason = ['Server Error', code]
    elif code == 1:
        reason == ['Wrong input', code ,extras]
    elif code == 2:
        reason = ['Incorrect Permissions', code]
    return json.dumps({"Error": reason})


class User(object):
    """ 

    User Mongo manager
    
    TODO:
    1. create_group and create_Award def's
    2. __enter__ and __exit__ context managers for easy connection cleanup

    """

    # Think of slots as being the dev api guidlines to follow
    # These are the only things passed around by models?
    __slots__ =('_id', 'type', 'is_alive')


    def __init__(self,  id, type):
        self.type = type
        self.is_alive = True

        ### for use externally 
        self._id = id

    def __del__(self):
        # Helpful for returning socket to pool??
        # Or should just use context managers?
        mongo.connection.end_request()

    ### Functions needed for a simple user ###

    @staticmethod
    def create(user, type='default', scaffold=True):
        """
        Used to add a new user into a mongo users Collection.

        Success: class with uid populated .
        Failure: False if mongo write fails.

        The id contained in the user can be either a 
        "googleid" or "facebook id" if using the
        scaffold, or you can put whatever into the users 
        collection if scaffold
        is false.
        """
        try:
            if not scaffold:
                # Important that we have safe write?? 
                # save time without or too risky?
                return User(mongo.users.insert(user,
                    safe=True),type)
            else:
                # This is the most basic thing I could think of... 
                # Don't want to waste or wait on longer io times 
                user_scaffold ={
                        'str_type': type,
                        'str_name': user.get('name',None),
                        'date_joindate': str(datetime.datetime.utcnow()),
                        'int_awardCount':0,
                        'int_completedGoals':0,
                        'int_startedGoals':0,
                        '_id_goals':[],
                        '_id_groups':[],
                        'awards':[],
                        }
                if type is not 'default':
                    user_scaffold['_social_id'] = user.get('id')
                return User(mongo.users.insert(user_scaffold,safe=True), type)
        except OperationFailure, e:
            #logging.error()
            return False

    @staticmethod
    def find(id, type='default'):
        """
        Returns a populated User with  the correct uid, or False if find
        fails
        """
        # only return the uid for User constructor
        if  type == 'default':
            user = mongo.users.find_one({'_id':id},{'_id':1})
            if isinstance(user,dict):
                return User(user['_id'], type)
            else: return False #logging.error()
        else: 
            user = mongo.users.find_one({'_social_id':id}, {'_id':1})
            if isinstance(user,dict):
                return  User(user['_id'], type)
            else: return False #logging.error(

    def info(self, properties=None):
        """ 
        Class property that gives back user info 
        Params:
            properties: iterable(list) of properties to return
        """
        if self.is_alive:
            #pymongo already does this
            #properties = dict(map(lambda x: (x,1), properties))
            return mongo.users.find_one({'_id':self._id}, fields=properties)
        else: return False

    def delete(self):
        """
        Returns True if sucess , False otherwise
        TODO: Logging and throw exception?
        """
        # if err msg is None , remove was a success 
        if  mongo.users.remove({'_id':self._id}, safe=True)['err'] is None:
            self.is_alive = False
            return True
        else: 
            return False

    def edit(self,  what_to_change):
        """
        what_to_change is a dict of properties and
        their values to change
        TODO: logging and return error if update fails
        """
        return mongo.users.update({'_id':self._id} ,
                    {"$set": what_to_change }, safe=True)

    def add_goal(self, doc=None):
        """ Returns a Goal object that contains the goal 
        TODO: add goal id to this user."""
        return Goal.create(self._id,  doc)
        
    ### Functions needed for a REST Interface ###

    def GET(self, uid=None, type='default' ):
        """ gets a specific user or  all users if no uid """
        if not uid:
            #TODO: stream response and limit query 
            users =[]
            for u in self.mongo.users.find():
                users.append(u)
            return users
        else:
            return self.find_one(uid, type)

class Goal(object):

    __slots__ =('_id')
    exposed = True

    def __init__(self, id):
        #self.mongo = mongo

        # for use externally
        self._id =  id

    ### Functions that would munilpulate a goal object ###

    @staticmethod
    def create(oid, goal=None, scaffold=True):
        """
        Used to add a new goal into a mongo goals Collection.

        Params: 
            goal: document to add 
            scaffold: Bool, whether to add default scaffold to embedded doc

            Success: _id of inserted doc.
            Failure: False if mongo write fails.
         """
        try:
            if not scaffold:
                goal['_user_id'] = oid
                return Goal(mongo.goals.insert(goal, safe=True))
            else:
                goal_scaffold = {
                    '_user_id': oid,
                     ## Array of ancestors
                    u'_id_tasks':[],
                    # Embedded user data ie; name id etc
                    u'motivators':[],
                    'descrip':{
                      u'str_who':None, u'str_what':None, 
                      u'str_where':None, u'str_why':None,
                        },
                    u'tags':[],
                   u'int_diffuculty':int(0),
                    u'date_start':datetime.datetime.utcnow(),
                    u'date_target':0,
                    u'int_votes':int(0),
                    u'bool_completed':False,
                }
                return Goal(mongo.goals.insert(goal_scaffold,safe=True))
        except OperationFailure:
            return False

    def delete(id):
        pass

    def finish(id):
        pass

class Group(object):
   pass

class Award(object):
    pass

### Functions that work with group objects ###

def add_group(group, meta_data):
    pass

def add_group_memeber(id, user):
    pass

def merge_group(group1, group2, new):
    pass

### Functions that work with Award objects ###

def new_award(doc, award, scaffold=True):
    """ Used to add a new award into a mongo users Collection 
    as a embedded doc.

    Params: 
    doc: query match document
    award: document to add 
    scaffold: Bool, whether to add default scaffold to embedded doc

    Success: _id of inserted doc.
    Failure: False if mongo write fails.
    """


    try:
        if not scaffold:
            return self.db.users.update(doc, {"$push":{'awards':award}},
                    safe=True)

        else:
            award_scaffold = {
                    'name': None,
                    'startDate':datetime.datetime.utcnow(),
                    'completedDate':0,
                    'value': int(0),
                    }
            return self.db.users.update(doc, {"$push":{'awards':award_scaffold}},
                    safe=True)
    except OperationFailure:
        return False


