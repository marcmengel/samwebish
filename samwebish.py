#!/usr/bin/env python
from metacat.webapi import MetaCatClient
from data_dispatcher.api import DataDispatcherClient
from rucio.client import Client as RClient
from rucio.client.replicaclient import ReplicaClient
import time
import jwt
import re

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# classes for authentication, client connection caching

class ClientCache:

    def __init__(self):
        self.mcccache = {}
        self.mccexp = {}
        self.ddccache = {}
        self.ddcexp = {}
        self.rccache = {}
        self.rcexp = {}
        # for get_username, below
        self.subj_user_re = re.compile("(.*)@fnal.gov")
        self.scope_user_re = re.compile("storage.write:[^ ]*/users/([^ ]*)")
        self.token_offset = len("Bearer ")

    def get_scitoken(self):
        """ extract scitoken from Authorization: header """
        authheader = cherrypy.request.headers.get("Authorization","")
        if not authheader:
            raise cherrypy.HTTPError(401, 'SciToken athentication required')
        return autheader[token_offset:]

    def get_username(self, scitok):
        """ get username from scitoken """
        # Scitoken purists will tell us *not* to do this, nor to map
        # tokens to users at all, but SAMweb and MetaCat do, via db tables
        # so we can either setup one of these tables, or cheat.
        # Currently we cheat:
        # our subjects are often not usernames, (except production accounts)
        # if our subject is username@fnal.gov, take that
        # otherwise look for a username in the scope 
        # i.e. "storage.write:.../users/username" 
        decoded = jwt.decode(scitok, algorithms=["RS256","ES256"])
        m = self.subj_user_re.match(decoded["sub"])
        if m:
             return m.group(1)
        m = self.scope_user_re.search(decoded["scope"])
        if m:
             return m.group(1)
        return None
       
    def getdd_client(self):
        """ get DataDispatcherClient for this client """
        scitok = self.get_scitoken()
        if not scitok in self.ddccache or self.ddcexp[scitok] < time.time():
            username = self.getusername(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            self.ddccache[scitok] = DataDispatcherClient(token_file="/dev/null")
            try:
                self.ddccache[scitok].login_token(username, scitok)
            except:
                raise cherrypy.HTTPError(401, 'SciToken athentication failed')
            self.ddcexp[scitok] = time.time() + 300
        return self.ddccache[scitok]

    def getmc_client(self):
        """ get MetaCatClient for this client """
        scitok = self.get_scitoken()
        if not scitok in self.mcccache or self.mccexp[scitok] < time.time():
            username = self.getusername(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            self.mcccache[scitok] = MetaCatClient(token_file="/dev/null")
            try:
                self.mcccache[scitok].login_token(username, scitok)
            except:
                raise cherrypy.HTTPError(401, 'SciToken athentication failed')
            # cache for 5 minutes
            self.mccexp[scitok] = time.time() + 300
        return self.mcccache[scitok]

    def getr_client(self):
        """ get rucio Client for this client """
        scitok = self.get_scitoken()
        if not scitok in self.rccache or self.mccexp[scitok] < time.time():
            username = self.getusername(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            try:
                # can't pass token into rucio client, so briefly set
                # BEARER_TOKEN (?)
                os.environ["BEARER_TOKEN"]=scitok
                self.rccache[scitok] = RClient(auth_type="oidc", creds={"user":username})
                del os.environ["BEARER_TOKEN"]
            except:
                del os.environ["BEARER_TOKEN"]
                raise cherrypy.HTTPError(401, 'SciToken athentication failed')
            # cache for 5 minutes
            self.rcexp[scitok] = time.time() + 300
        return self.rccache[scitok]

    def clean_expired(self):
        now = time.time()
        for tok in self.mccexp:
            if self.mccexp < now:
                del self.mccexp[tok]
                del self.mcccache[tok]
        for tok in self.ddcexp:
            if self.ddcexp < now:
                del self.ddcexp[tok]
                del self.ddccache[tok]

client_cache = ClientCache()

class ClientCacheMixin():
    def __init__(self):
        self.client_cache = client_cache

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# classes for dispatching/handling web calls via CherryPy

class Definitions(ClientCacheMixin):
    """ dispatcher and methods for /api/definitions paths """

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb definitions api """
        if len(vpath) == 1:
            # simple method like create
            return self
        if len(vpath) == 2:
            # /name/defname --  method is the lower case of request type (GET, POST, DELETE)
            vpath.pop(0)  # /name/
            cherrypy.request.params['defname'] = vpath.pop(0)
            vpath.insert(0, cherrypy.request.method.lower())
            return self
        if len(vpath) == 3:
            # /name/defname/snapshot 
            vpath.pop(0)  # /name/
            cherrypy.request.params['defname'] = vpath.pop(0)
            return self
        if len(vpath) == 4:
            # /name/defname/files/method
            vpath.pop(0)  # /name/
            cherrypy.request.params['defname'] = vpath.pop(0)
            vpath.pop(0) # /files/
            return self

    @cherrypy.expose
    def list(self, defname="", user="", group="", after="", before=""):
        client = self.client_cache.getmc_client()
        if not defname:
            defname = "*"
        query = r"queries matching sam:{defname}"
        sep = "where"
        if user:
            query = f"{query} {sep} creator={user}"
            sep = "and"
        if after:
            query = f"{query} {sep} created_timestamp>'{after}'"
            sep = "and"
        if before:
            query = f"{query} {sep} created_timestamp<'{before}'"
            sep = "and"
            
        dlist = client.search_named_queries(query)
        return "\n".join([ x["name"] for x in dlist ])
                    
    @cherrypy.expose
    def create(self, defname, dims, user):
        pass

    @cherrypy.expose
    def delete(self, defname, dims, user):
        pass

    @cherrypy.expose
    def get(self, defname)
        pass   

    @cherrypy.expose
    def list(self, defname)
        pass   

    @cherrypy.expose
    def count(self, defname):
        pass

    @cherrypy.expose
    def summary(self, defname):
        pass


class Files(ClientCacheMixin):
    """ dispatcher and methods for /api/files paths """

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        if len(vpath) == 0:
            vpath.insert(0, cherrypy.request.method.lower())
        if len(vpath) == 1:
            # simple method like create
            return self
        if len(vpath) == 3:
            # /name/fname/method --  method is the lower case of request type (GET, POST, DELETE) 
            # /id/fname/method --  method is the lower case of request type (GET, POST, DELETE) 
            #       prepended to component and  method (get_name_metadata, put_id_metadata, etc.)
            comp = vpath.pop(0)  # /name/ or /id/
            cherrypy.request.params['name'] = vpath.pop(0)
            vpath.insert(0, f"{cherrypy.request.method.lower()}_{comp}_{vpath.pop(0)}")
            return self
        if len(vpath) == 4:
            # /name/fname/lineage/type
            vpath.pop(0)  # /name/
            cherrypy.request.params['name'] = vpath.pop(0)
            meth = vpath.pop(0)  # /lineage/
            cherrypy.request.params['ltype'] = vpath.pop(0)
            vpath.insert(0, "lineage")
            return self

    @cherrypy.expose
    def list(self, **kwargs):
        pass

    @cherrypy.expose
    def count(self, **kwargs):
        pass

    @cherrypy.expose
    def summary(self, **kwargs):
        pass

    def samloc(self, rpdict):
        pathoffset = rpdict['path'].find('/',9)
        return f"{rpdict['rse']}:{rpdict[path][pathoffset:]}"

    @cherrypy.expose
    def get_name_locations(self, name="", **kwargs):
        rpclient = ReplicaClient(self.getr_client())
        res = rpclient.list_replicas( [("sam",name)] )
        return "\n".join([self.samloc(x) for x in res])

    @cherrypy.expose
    def put_name_locations(self, **kwargs):
        pass

    @cherrypy.expose
    def get_name_metadata(self, **kwargs):
        pass

    @cherrypy.expose
    def lineage(self, **kwargs):
        pass

    @cherrypy.expose
    def post(self, **kwargs):
        pass

    @cherrypy.expose
    def validate_metadata(self, **kwargs):
        pass

    @cherrypy.expose
    def put_name_metadata(self, **kwargs):
        pass

    @cherrypy.expose
    def put_id_metadata(self, **kwargs):
        pass

    @cherrypy.expose
    def put_name_content_status(self, **kwargs):
        pass

    @cherrypy.expose
    def put_id_content_status(self, **kwargs):
        pass

class Users(ClientCacheMixin):
    """ dispatcher and methods for /api/users paths """

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        if len(vpath) == 0:
            vpath.insert(0, cherrypy.request.method.lower())
        if len(vpath) == 2:
            cherrypy.request.params['findby'] = vpath.pop(0)
            cherrypy.request.params['nameorid'] = vpath.pop(0)
            cherrypy.request.params['method'] = cherrypy.request.method.lower())
            vpath.insert(0,f"{method}_by_{findby}")

    @cherrypy.expose
    def get(self, username=None, status=None)
        pass

    @cherrypy.expose
    def post(self, jsondata)
        pass

    @cherrypy.expose
    def get_by_name(self, nameorid):
        pass

    @cherrypy.expose
    def get_by_id(self, nameorid):
        pass

    @cherrypy.expose
    def put_by_name(self, nameorid, jsondata):
        pass

    @cherrypy.expose
    def put_by_id(self, nameorid, jsondata):
        pass

class Values(ClientCacheMixin):
    """ dispatcher and methods for /api/values paths """

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        if len(vpath) == 1:
            cherrypy.request.params['value_type'] = vpath.pop(0)
            vpath.insert(0, f"{cherrypy.request.method.lower()}_{vpath.pop(0)}")

    @cherrypy.expose
    def get_parameters(self, **kwargs):
        pass

    @cherrypy.expose
    def post_parameters(self, **kwargs):
        pass

    @cherrypy.expose
    def get_applications(self, **kwargs):
        pass

    @cherrypy.expose
    def post_applications(self, **kwargs):
        pass

class Projects(ClientCacheMixin):
    """ dispatcher and methods for /api/project paths """

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        if len(vpath) == 0:
            vpath.insert(0, cherrypy.request.method.lower())
        if len(vpath) == 2:
            # stationname/projectname
            cherrypy.request.params['station'] = vpath.pop(0)
            cherrypy.request.params['project'] = vpath.pop(0)
            vpath.insert(0, cherrypy.request.method.lower())
        if len(vpath) == 3:
            # stationname/projectname/method
            cherrypy.request.params['station'] = vpath.pop(0)
            cherrypy.request.params['project'] = vpath.pop(0)
        if len(vpath) == 5:
            # stationname/projectname/processes/<processid>/method
            cherrypy.request.params['station'] = vpath.pop(0)
            cherrypy.request.params['project'] = vpath.pop(0)
            vpath.pop()
            cherrypy.request.params['processid'] = vpath.pop(0)

    @cherrypy.expose
    def status(self, **kwargs):
        pass
    @cherrypy.expose
    def establishProcess(self, **kwargs):
        pass
    @cherrypy.expose
    def getNextFile(self, **kwargs):
        pass
    @cherrypy.expose
    def updateFileStatus(self, **kwargs):
        pass
    @cherrypy.expose
    def releaseFile(self, **kwargs):
        pass
    @cherrypy.expose
    def endProcess(self, **kwargs):
        pass
    @cherrypy.expose
    def status(self, **kwargs):
        pass
    @cherrypy.expose
    def endProject(self, **kwargs):
        pass
    @cherrypy.expose
    def get(self, **kwargs):
        pass
    @cherrypy.expose
    def dumpProject(self, **kwargs):
        pass
    @cherrypy.expose
    def summary(self, **kwargs):
        pass
    @cherrypy.expose
    def recovery_dimensions(self, **kwargs):
        pass


class Api(ClientCacheMixin):
    """ dispatcher and methods for /api/ paths """

    def __init__(self):
        self.parts = {
            "definitions": Definitions(),
            "files": Files(),
            "users": Users(),
            "values": Values(),
            "projects": Projects(),
        }

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb api """
        if len(vpath) == 0:
            vpath.insert(0, 'index')
            return self
        if vpath[0] in self.parts:
            # for things in our parts array, hand off
            return self.parts[vpath.pop(0)]
        if len(vpath) == 3:
            vpath.pop(0)
            cherrypy.request.params['projectname'] = vpath.pop(0)
            return self
        return self 
    
    @cherrypy.expose
    def index(self, **kwargs):
        pass
    @cherrypy.expose
    def createDefinition(self, **kwargs):
        pass
    @cherrypy.expose
    def deleteDefinition(self, **kwargs):
        pass
    @cherrypy.expose
    def describeDefinition(self, **kwargs):
        pass
    @cherrypy.expose
    def translateConstraints(self, **kwargs):
        pass
    @cherrypy.expose
    def locateFile(self, **kwargs):
        pass
    @cherrypy.expose
    def getMetadata(self, **kwargs):
        pass
    @cherrypy.expose
    def setStatus(self, **kwargs):
        pass
    @cherrypy.expose
    def dumpStation(self, **kwargs):
        pass

    @cherrypy.expose
    def startProject(self, **kwargs):
        pass

    @cherrypy.expose
    def findProject(self, **kwargs):
        pass


def main():
    cherrypy.tree.mount(Api(), '/api')

    cherrypy.engine.start()
    cherrypy.engine.block()
