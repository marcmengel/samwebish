#!/usr/bin/env python
import base64
import cherrypy
import json
import os
import re
import time
import traceback
from data_dispatcher.api import DataDispatcherClient
from metacat.webapi import MetaCatClient
from rucio.client import Client as RClient
from rucio.client.replicaclient import ReplicaClient

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# classes for authentication, client connection caching

class ClientCache:

    # Note: there are now 4 caches in here that work almost the same
    #     except for the object called to create the connection.
    #     Better might be to have one cache class that you pass the
    #     connection creator into, and make 4 instances of that class...

    def __init__(self):
        self.mcccache = {}
        self.mccexp = {}
        self.ddccache = {}
        self.ddcexp = {}
        self.rccache = {}
        self.rcexp = {}
        self.rrpccache = {}
        self.rrpcexp = {}
        # for get_username, below
        self.subj_user_re = re.compile("(.*)@fnal.gov")
        self.scope_user_re = re.compile("storage[^ ]*/users/([^ ]*)")
        self.token_offset = len("Bearer ")

    def get_scitoken(self):
        """ extract scitoken from Authorization: header """
        authheader = cherrypy.request.headers.get("Authorization","")
        if not authheader:
            raise cherrypy.HTTPError(401, 'SciToken athentication required')
        return authheader[self.token_offset:]

    def cheap_decode_token(self, scitok):
        """ extract json data from jwt token without validating, etc. """
        tp = scitok.split(".")
        return json.loads(base64.b64decode(tp[1]+'=='))

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
        
        cherrypy.log(f"get_username: {scitok=}")
        decoded = self.cheap_decode_token(scitok)
        cherrypy.log(f'checking subject: {decoded["sub"]}')
        m = self.subj_user_re.match(decoded["sub"])
        if m:
             cherrypy.log(f"Returning: {m.group(1)}")
             return m.group(1)
        cherrypy.log(f'checking scope: {decoded["scope"]}')
        m = self.scope_user_re.search(decoded["scope"])
        if m:
             cherrypy.log(f"Returning: {m.group(1)}")
             return m.group(1)
        cherrypy.log(f"Returning: None!")
        return None
       
    def getdd_client(self):
        """ get DataDispatcherClient for this client """
        scitok = self.get_scitoken()
        if not scitok in self.ddccache or self.ddcexp[scitok] < time.time():
            username = self.get_username(scitok)
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
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            self.mcccache[scitok] = MetaCatClient(token_file="/tmp/tok")
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
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            try:
                # can't pass token into rucio client, so briefly set
                # BEARER_TOKEN (?)
                os.environ["BEARER_TOKEN"]=scitok
                self.rccache[scitok] = RClient(auth_type="oidc", creds={"user":username})
                del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"getr_client: {self.rccache[scitok]=}")
            except:
                if "BEARER_TOKEN" in os.environ:
                    del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"Exception: {traceback.format_exc()}")
                raise cherrypy.HTTPError(401, 'SciToken athentication failed')
            # cache for 5 minutes
            self.rcexp[scitok] = time.time() + 300
        return self.rccache[scitok]

    def getrrp_client(self):
        """ get rucio Client for this client """
        scitok = self.get_scitoken()
        if not scitok in self.rrpccache or self.rrcpexp[scitok] < time.time():
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            try:
                # can't pass token into rucio client, so briefly set
                # BEARER_TOKEN (?)
                os.environ["BEARER_TOKEN"]=scitok
                self.rrpccache[scitok] = ReplicaClient(auth_type="oidc", creds={"user":username})
                del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"getrrp_client: {self.rrpccache[scitok]=}")
            except:
                if "BEARER_TOKEN" in os.environ:
                    del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"Exception: {traceback.format_exc()}")
                raise cherrypy.HTTPError(401, 'SciToken athentication failed')
            # cache for 5 minutes
            self.rrpcexp[scitok] = time.time() + 300
        return self.rrpccache[scitok]

    def clean_expired(self):
        # needs rucio caches!
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
    def __init__(self, *args, **kwargs):
        self.client_cache = client_cache
        self.namespace = "sam"

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# classes for dispatching/handling web calls via CherryPy

class Definitions(ClientCacheMixin):
    """ dispatcher and methods for /api/definitions paths """

    def _cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb definitions api """
        cherrypy.log(f"Definitions: _cp_dispatch: {vpath=}")
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
        cherrypy.log("entering Definitions:list")
        client = self.client_cache.getmc_client()
        if not defname:
            defname = "*"
        query = f"queries matching {self.namespace}:{defname}"
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
            
        cherrypy.log(f"searching with {query=}")
        dlist = list(client.search_named_queries(query))
        cherrypy.log(f"got back {dlist=}")
        return "\n".join([ x["name"] for x in dlist ])
                    
    @cherrypy.expose
    def create(self, defname, dims, user):
        pass

    @cherrypy.expose
    def delete(self, defname, dims, user):
        pass

    @cherrypy.expose
    def get(self, defname):
        cherrypy.log(f"Definitions.get: {defname=}")
        pass   

    @cherrypy.expose
    def count(self, defname):
        pass

    @cherrypy.expose
    def summary(self, defname):
        pass


class Files(ClientCacheMixin):
    """ dispatcher and methods for /api/files paths """

    def _cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        cherrypy.log(f"Files:_cp_dispatch: {vpath=}")
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

    def convert_sam_query(self, dims):
        # totally insufficient currently...
        dims = dims.replace("isparentof:", "parent")
        dims = dims.replace("ischildof:", "children")
        dims = dims.replace("defname:", "selected by")
        dims = dims.replace("create_date", "created_timestamp")
        dims = dims.replace("update_date", "updated_timestamp")
        dims = dims.replace("user", "creator")
        dims = dims.replace("with limit", "limit")
        dims = dims.replace("with offset", "offset")
        dims = dims.replace("file_id", "id")
        dims = dims.replace("file_name", "name")
        dims = dims.replace("file_size", "size")

        if dims.find("selected by") >= 0:
            return "files " + dims
        else:
            return "files where " + dims

    @cherrypy.expose
    def list(self, dims="", fileinfo="", **kwargs):
        mquery = self.convert_sam_query(dims)
        client = self.client_cache.getmc_client()
        res = client.query(mquery)
        return res

    @cherrypy.expose
    def count(self, **kwargs):
        pass

    @cherrypy.expose
    def summary(self, **kwargs):
        pass

    @cherrypy.expose
    def get_name_locations(self, name="", **kwargs):
        cherrypy.log(f"get_name_locations {name=}")
        rpclient = self.client_cache.getrrp_client()
        data = list(rpclient.list_replicas( [{"scope":self.namespace, "name":name}] ))
        cherrypy.log(f"get_name_locations: {data=}")
        rses = data[0]["rses"]
        res = []
        for rse in rses:
            for pfn in rses[rse]:
                 ploc = pfn.find("/",9)
                 res.append(f"{rse}:{pfn[ploc:]}")
        return "\n".join(res)

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

    def _cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        if len(vpath) == 0:
            vpath.insert(0, cherrypy.request.method.lower())
        if len(vpath) == 2:
            cherrypy.request.params['findby'] = vpath.pop(0)
            cherrypy.request.params['nameorid'] = vpath.pop(0)
            cherrypy.request.params['method'] = cherrypy.request.method.lower()
            vpath.insert(0,f"{method}_by_{findby}")

    @cherrypy.expose
    def get(self, username=None, status=None):
        pass

    @cherrypy.expose
    def post(self, jsondata):
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

    def _cp_dispatch(self, vpath):
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

    def _cp_dispatch(self, vpath):
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

    def _cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb api """
        cherrypy.log(f"Api:_cp_dispatch: {vpath=}")
        if len(vpath) == 0:
            vpath.insert(0, 'index')
            return self
        if vpath[0] in self.parts:
            cherrypy.log(f"Api:_cp_dispatch: handing off to {vpath[0]}..")
            # for things in our parts array, hand off
            return self.parts[vpath.pop(0)]
        if len(vpath) == 3:
            vpath.pop(0)
            cherrypy.request.params['projectname'] = vpath.pop(0)
            return self
        return self 
    
    @cherrypy.expose
    def index(self, **kwargs):
        cherrypy.log("test message")
        return '{"app":"samwebish", "version":0.0}'

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

if __name__ == '__main__':
    main()
