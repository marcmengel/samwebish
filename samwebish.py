#!/usr/bin/env python
import base64
import json
from fastapi import FastAPI
from fastapi_utils.cbv  import cbv
from fastapi_utils.iinferring_router import InferringRouter
import os
import os.path
import re
import time
import threading
import traceback

from version import samwebish_version
from data_dispatcher.api import DataDispatcherClient
from metacat.webapi import MetaCatClient
from metacat.webapi.webapi import (
    AlreadyExistsError,
    InvalidMetadataError,
    BadRequestError,
)
from rucio.client import Client as RClient
from rucio.client.replicaclient import ReplicaClient
from query_converter.parse_tree import SAM_query_to_MetaCat
from metadata_converter import MetadataConverter

app = FastAPI()
router = InferringRouter()

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
        self.rucio_env_lock = threading.Lock()

    def get_scitoken(self):
        """extract scitoken from Authorization: header"""
        print(f"headers: {cherrypy.request.headers}")
        authheader = cherrypy.request.headers.get("Authorization", "")
        if not authheader:
            raise cherrypy.HTTPError(401, "SciToken athentication required")
        return authheader[self.token_offset :]

    def cheap_decode_token(self, scitok):
        """extract json data from jwt token without validating, etc."""

        tp = scitok.split(".")
        return json.loads(base64.b64decode(tp[1] + "==", altchars="_-"))

    def get_username(self, scitok):
        """get username from scitoken"""
        # Scitoken purists will tell us *not* to do this, nor to map
        # tokens to users at all, but SAMweb and MetaCat do, via db tables
        # so we can either setup one of these tables, or cheat.
        # Currently we cheat:
        # our subjects are often not usernames, (except production accounts)
        # if our subject is username@fnal.gov, take that
        # otherwise look for a username in the scope
        # i.e. "storage.write:.../users/username"
        #
        # note that this username guess isn't actually used except to log
        # into backend services...

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
        """get DataDispatcherClient for this client"""
        scitok = self.get_scitoken()
        if not scitok in self.ddccache or self.ddcexp[scitok] < time.time():
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            self.ddccache[scitok] = DataDispatcherClient()
            try:
                self.ddccache[scitok].login_token(username, scitok)
            except:
                raise cherrypy.HTTPError(401, "SciToken athentication failed")
            self.ddcexp[scitok] = time.time() + 300
        return self.ddccache[scitok]

    def getmc_client(self):
        """get MetaCatClient for this client"""
        scitok = self.get_scitoken()
        if not scitok in self.mcccache or self.mccexp[scitok] < time.time():
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            # self.mcccache[scitok] = MetaCatClient(token_file="/tmp/tok")
            self.mcccache[scitok] = MetaCatClient()
            try:
                self.mcccache[scitok].login_token(username, scitok)
            except:
                raise cherrypy.HTTPError(401, "SciToken athentication failed")
            # cache for 5 minutes
            self.mccexp[scitok] = time.time() + 300
        return self.mcccache[scitok]

    def getr_client(self):
        """get rucio Client for this client"""
        scitok = self.get_scitoken()
        if not scitok in self.rccache or self.mccexp[scitok] < time.time():
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            try:
                # can't pass token into rucio client, so briefly set
                # BEARER_TOKEN, thread lock it so we don't get misplaced
                # authentication if we have multiple threads running...
                with self.rucio_env_lock:
                    os.environ["BEARER_TOKEN"] = scitok
                    self.rccache[scitok] = RClient(
                        auth_type="oidc", creds={"user": username}
                    )
                    self.rccache[scitok].whoami()
                    del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"getr_client: {self.rccache[scitok]=}")
            except:
                if "BEARER_TOKEN" in os.environ:
                    del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"Exception: {traceback.format_exc()}")
                raise cherrypy.HTTPError(401, "SciToken athentication failed")
            # cache for 5 minutes
            self.rcexp[scitok] = time.time() + 300
        return self.rccache[scitok]

    def getrrp_client(self):
        """get rucio Client for this client"""
        scitok = self.get_scitoken()
        if not scitok in self.rrpccache or self.rrpcexp[scitok] < time.time():
            username = self.get_username(scitok)
            # set token_file on client to /dev/null so we don't have to
            # track/clean up token_library files.
            try:
                # can't pass token into rucio client, so briefly set
                # BEARER_TOKEN (?)
                os.environ["BEARER_TOKEN"] = scitok
                self.rrpccache[scitok] = ReplicaClient(
                    auth_type="oidc", creds={"user": username}
                )
                del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"getrrp_client: {self.rrpccache[scitok]=}")
            except:
                if "BEARER_TOKEN" in os.environ:
                    del os.environ["BEARER_TOKEN"]
                cherrypy.log(f"Exception: {traceback.format_exc()}")
                raise cherrypy.HTTPError(401, "SciToken athentication failed")
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



class ClientCacheMixin:

    def __init__(self, *args, **kwargs):
        self.client_cache = client_cache
        # self.namespace = "sam"
        # for testing:
        self.namespace = "mengel"
        self.default_dataset = "mengel:all"
        self.mcc = MetadataConverter(experiment=os.environ.get("SAM_EXPERIMENT", ""))


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# classes for dispatching/handling web calls via CherryPy


@cbv(router)
class Definitions(ClientCacheMixin):
    """dispatcher and methods for /api/definitions paths"""

    @router.get("/sam/{experiment}/api/definitions/list")
    def list(self, experiment,  defname="", user="", group="", after="", before="", format=""):
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
        return "\n".join([x["name"] for x in dlist])

    @router.post("/sam/{experiment}/api/definitions/create")
    def create(self, experiment, defname, dims, user, group=none):
        client = self.client_cache.getmc_client()
        mq = SAM_query_to_MetaCat(dims)
        client.create_named_query(self.namespace, defname, mq)

    @router.delete("/sam/{experiment}/api/definitions/name/{defname}")
    def delete(self, experiment, defname ):
        raise NotImplementedError()

    @router.get("/sam/{experiment}/api/definitions/name/{defname}")
    def get(self, experiment,  defname, format="json"):
        client = self.client_cache.getmc_client()
        res = client.get_named_query(self.namespace, defname)
        cherrypy.log(f"got {res=} for {defname=}")
        if format == "plain":
            res = f"""
Definition Name: {defname}
  Definition Id: {res['created_timestamp']}
  Creation Date: {time.strftime("%Y-%M-%D %h:%m:%s", time.gmtime(res['created_timestamp']))}
       Username: {res['creator']}
          Group: None
     Dimensions: {res['source']}"""

        return res

    @router.get("/sam/{experiment}/api/definitions/name/{defname}/files/count")
    def files_count(self, experiment, defname):
        sdict = self.summary(defname)
        cherrypy.log(f"got {sdict=} {sdict['count']}")
        return str(sdict["count"])

    def summary(self, defname):
        client = self.client_cache.getmc_client()
        res = list(
            client.query(
                f"files selected by {self.namespace}:{defname}", summary="count"
            )
        )[0]
        return res

    @router.get("/sam/{experiment}/api/definitions/name/{defname}/files/summary")
    def files_summary(self, experiment, defname):
        sdict = self.summary(defname)
        sdict["file_count"] = sdict["count"]
        sdict["total_file_size"] = sdict["total_size"]
        sdict["total_event_count"] = 0
        cherrypy.log(f"{sdict=}")
        return json.dumps(sdict)

    @router.get("/sam/{experiment}/api/definitions/name/{defname}/files/list")
    def files_list(self, experiment, defname="", format=""):
        client = self.client_cache.getmc_client()
        res = list(client.query(f"files selected by {self.namespace}:{defname}"))
        cherrypy.log(f"{res=}")
        if format == "json":
            return json.dumps(res)
        else:
            return "\n".join([e["name"] for e in res])


@cbv(router)
class Files(ClientCacheMixin):
    """dispatcher and methods for /api/files paths"""

    def convert_sam_query(self, dims):
        return SAM_query_to_MetaCat(dims)

    @router.get("/sam/{experiment}/api/files/list")
    def list(self, experiment, dims="", fileinfo="", **kwargs):
        mquery = self.convert_sam_query(dims)
        cherrypy.log(f"list: converted {dims=} to {mquery=}")
        client = self.client_cache.getmc_client()
        res = client.query(mquery)
        return "\n".join([x["name"] for x in res])

    @router.get("/sam/{experiment}/api/files/count")
    def count(self, experiment, dims, **kwargs):
        return self._summary(dims)["count"]

    def _summary(self, dims, **kwargs):
        mquery = self.convert_sam_query(dims)
        client = self.client_cache.getmc_client()
        res = list(client.query(mquery, summary="count"))[0]
        return res

    @router.get("/sam/{experiment}/api/files/summary")
    def summary(self, experiment, dims, **kwargs):
        sdict = self._summary(dims)
        sdict["file_count"] = sdict["count"]
        sdict["total_file_size"] = sdict["total_size"]
        sdict["total_event_count"] = 0
        cherrypy.log(f"{sdict=}")
        return json.dumps(sdict)

    @router.get("/sam/{experiment}/api/files/name/{name}/locations")
    def get_name_locations(self, experiment, name="", **kwargs):
        cherrypy.log(f"get_name_locations {name=}")
        rpclient = self.client_cache.getrrp_client()
        data = list(rpclient.list_replicas([{"scope": self.namespace, "name": name}]))
        cherrypy.log(f"get_name_locations: {data=}")
        if not data:
            return "[]"
            # raise cherrypy.HTTPError(404, 'Location not found')
        pfns = data[0]["pfns"]
        res = []
        for pfn, dat in pfns.items():
            rse = dat["rse"]
            ploc = pfn.find("/", 9)
            res.append({"location": f"{rse}:{pfn[ploc:]}"})
        if "format" in kwargs and kwargs["format"] == "plain":
            res = "\n".join(res)
        else:
            res = json.dumps(res)

        cherrypy.log(f"get_name_locations: {res=}")
        return res

    @router.put("/sam/{experiment}/api/files/name/{name}/locations")
    def put_name_locations(self, experiment, file, add="", remove=""):
        rpclient = self.client_cache.getrrp_client()
        mcclient = self.client_cache.getmc_client()

        if add:
            samloc = add
            rse, path = samloc.split(":", 1)
            metadata = mcclient.get_file(
                name=file, namespace=self.namespace, with_metadata=True
            )
            rclient.add_replica(
                rse,
                self.namespace,
                file,
                metadata["size"],
                metadata["checksums"]["adler32"],
            )
        if remove:
            samloc = remove
            rse, path = samloc.split(":", 1)
            # not sure we should do this... I think for now this is a noop
            # also not an api call to remove just one replica on an rse...
        return "ok"

    @router.get("/sam/{experiment}/api/files/name/{name}/locations")
    def get_name_metadata(self, experiment, name=None, format="plain"):
        mcclient = self.client_cache.getmc_client()
        metadata = mcclient.get_file(
            name=name, namespace=self.namespace, with_metadata=True
        )
        converted_metadata = self.mcc.convert_all_mc_sam(metadata)
        if format == "json":
            return json.dumps(converted_metadata)
        else:
            return "\n".join([f"{k:>20}:\t{v}" for k, v in converted_metadata.items()])

    def traverse_linage(self, mcclient, name, ltype, raw=False):
        data = mcclient.get_file(
            name=name, namespace=self.namespace, with_provenance=True
        )
        res1 = data[ltype]
        res = []
        if raw:
            if len(res1) == 0:
                res.append(f"{self.namespace}:{name}")
        else:
            res.extend(res1)
        for fid in res1:
            cname = res1.split(":")[1]
            nextgen = self.traverse_lineage(mcclient, cname, ltype, raw)
            if raw and len(nextgen == 0):
                res.append(f"{self.namespace}:{cname}")
            else:
                res.extend(nextgen)
        return res

    @router.get("/sam/{experiment}/api/files/name/{name}/lineage/{ltype}")
    def lineage(self, name, ltype, format="plain"):
        # ltype is: parents, children, rawancestors
        mcclient = self.client_cache.getmc_client()
        data = mcclient.get_file(
            name=file, namespace=self.namespace, with_provenance=True
        )
        if ltype in {"parents", "children"}:
            res = data[ltype]
        if ltype == "ancestors":
            res = self.traverse_lineage(mcclient, name, "parents")
        if ltype == "descendants":
            res = self.traverse_lineage(mcclient, name, "children")
        if ltype == "rawancestors":
            res = self.traverse_lineage(mcclient, name, "parents", raw=True)

        if format == "json":
            return json.dumps(res)
        else:
            return "\n".join(res)

    @router.post("/sam/{experiment}/api/files", metadata_text)
    def post(self, experiment, metadata_text):
        """declare a file..."""
        metadata = json.loads(metadata_text)
        mcclient = self.client_cache.getmc_client()
        try:
            mc_metadata = self.mcc.convert_all_sam_mc(
                metadata, namespace=self.namespace
            )
            mcclient.declare_files(self.default_dataset, [mc_metadata], self.namespace)
        except AlreadyExistsError as e:
            raise cherrypy.HTTPError(409, "File already exists")
        except InvalidMetadataError as e:
            raise cherrypy.HTTPError(400, f"Invalid metadata: {e}")

        cherrypy.response.status = 204
        return ""

    @router.post("/sam/{experiment}/api/files/validate_metadata")
    def validate_metadata(self, experiment, metadata_text):
        mcclient = self.client_cache.getmc_client()
        metadata = json.loads(metadata_text)
        mc_metadata = self.mcc.convert_all_sam_mc(metadata)
        try:
            resp = mcclient.declare_files(files=[mc_metadata], dry_run=True)
            cherrypy.response.status = 204
            return ""
        except:
            raise cherrypy.HTTPError(400, f"Invalid metadata: {e}")

    @router.put("/sam/{experiment}/api/files/name/{name}/metadata")
    def put_name_metadata(self, experiment, name, metadata_text):
        mcclient = self.client_cache.getmc_client()
        metadata = json.loads(metadata_text)
        mc_metadata = self.mcc.convert_all_sam_mc(metadata)
        did = f"{self.default_dataset}:{name}"
        mcclient.update_file_metadata(mc_metadata["metadata"], dids=[did])
        cherrypy.response.status = 204
        return ""

    @router.put("/sam/{experiment}/api/files/id/{file_id}/metadata")
    def put_id_metadata(self, experiment, file_id, metadata_text):
        mcclient = self.client_cache.getmc_client()
        metadata = json.loads(metadata_text)
        mc_metadata = self.mcc.convert_all_sam_mc(metadata)
        mcclient.update_file_metadata(mc_metadata["metadata"], fids=[file_id])
        cherrypy.response.status = 204
        return ""

    @router.put("/sam/{experiment}/api/files/name/{name}/metadata")
    def put_name_content_status(self, experiment, name, metadata_text)
        status = cherrypy.request.body
        mcclient = self.client_cache.getmc_client()
        metadata = json.loads(metadata_text)
        mcclient.update_file_metadata({"core.content_status": status}, fids=[file_id])
        cherrypy.response.status = 204
        return ""

    @router.put("/sam/{experiment}/api/files/id/{file_id}/metadata")
    def put_id_content_status(self, experiment, file_id, metadata_text):
        status = cherrypy.request.body
        metadata = json.loads(metadata_text)
        mc_metadata = self.mcc.convert_all_sam_mc(metadata)
        did = f"{self.default_dataset}:{name}"
        mcclient.update_file_metadata({"core.content_status": status}, dids=[did])
        cherrypy.response.status = 204
        return ""


@cbv(router)
class Users(ClientCacheMixin):
    """dispatcher and methods for /api/users paths"""

    @router.get("/sam/{experiment}/api/users/")
    def get(self, experiment,  username=None, format="plain", status=None):
        raise NotImplementedError()

    @router.post("/sam/{experiment}/api/users/")
    def post(self, experiment, jsondata):
        raise NotImplementedError()

    @router.get("/sam/{experiment}/api/users/name/{name}")
    def get_by_name(self, experiment, name):
        raise NotImplementedError()

    @router.get("/sam/{experiment}/api/users/id/{uid}")
    def get_by_id(self, experiement, uid):
        raise NotImplementedError()

    @router.put("/sam/{experiment}/api/users/name/{name}")
    def put_by_name(self, experiment, name, jsondata):
        raise NotImplementedError()

    @router.put("/sam/{experiment}/api/users/id/{uid}")
    def put_by_id(self, experiment, uid, jsondata):
        raise NotImplementedError()


@cbv(router)
class Values(ClientCacheMixin):
    """dispatcher and methods for /api/values paths"""

    @router.get("/sam/{experiment}/api/values/parameters")
    def get_parameters(self, experiment):
        mcclient = self.client_cache.getmc_client()
        keylist = list(mcclient.report_metadata_keys())
        return "\n".join(keylist)

    @router.post("/sam/{experiment}/api/values/parameters")
    def post_parameters(self, experimient, name, category, data_type):
        # don't need to pre-post parameters in MetaCat, so
        cherrypy.response.status = 204
        return ""

    @router.get("/sam/{experiment}/api/values/applications")
    def get_applications(self, experiment):
        mcclient = self.client_cache.getmc_client()
        vlist = mcclient.report_metadata_values("app.version")
        flist = mcclient.report_metadata_values("app.family")
        nlist = mcclient.report_metadata_values("app.name")
        # well, we don't actually easily get the correlations, so...
        # just permute the families, names and verions.
        res = []
        for f in flist:
            for n in nlist:
                for v in vlist:
                    res.append(f"{f}   {n}    {v}")
        return "\n".join(res)

    @router.post("/sam/{experiment}/api/values/applications")
    def post_applications(self, experiment, family, name, version):
        # don't need to pre-post applications in MetaCat, so
        # just say its "ok"...
        cherrypy.response.status = 204
        return ""


@cbv(router)
class Projects(ClientCacheMixin):
    """dispatcher and methods for /api/project paths"""

    def __init__(self):
        ClientCacheMixin.__init__(self)
        self.last_process_file = {}
        self.project_finished = {}

    @router.post("/sam/{experiment}/project/{project_id}")
    def establishProcess(self, experiment, project_id=None, appname, appversion, deliverylocation, username=None, subject=None, appfamily=None, description=None, filelimit=None, schemas=None):
        ddclient = self.client_cache.getdd_client()
        cherrypy.log("establishProcess...")
        return ddclient.new_worker_id()

    @router.post("/sam/{experiment}/project/{project_id}/process/{process_id}/getNextFile")
    def getNextFile(self, experiment, project_id, process_id):
        ddclient = self.client_cache.getdd_client()
        res = ddclient.next_file(project_id=project_id, worker_id=process_id)
        # just return the url from the first replica
        cherrypy.log(f"next_file gives: {res=}")
        if res:
            rname, rdict = list(res["replicas"].items())[0]
            name = res["name"]
            namespace = res["namespace"]
            self.last_process_file[process_id] = name
            return rdict["url"]
        else:
            self.project_finished[project_id] = True
            cherrypy.response.status = 204
            return ""

    @router.post("/sam/{experiment}/project/{project_id}/process/{process_id}/updateFileStatus")
    def updateFileStatus( self, experiment, process_id, project_id, status="consumed", filename=None ):
        cherrypy.log(
            f"updateFileStatus: {process_id=} {status=} {filename=} {project_id=}"
        )
        if cherrypy.request.method == "POST":
            data = cherrypy.request.body.read()
            cherrypy.log(f"updateFileStatus: {data=}")
        if status == "consumed":
            return self.releaseFile(
                process_id, "ok", project_id=project_id, filename=filename
            )
        if status == "skipped":
            return self.releaseFile(
                process_id, "bad", project_id=project_id, filename=filename
            )
        cherrypy.response.status = 204
        return ""

    @router.post("/sam/{experiment}/project/{project_id}/process/{process_id}/releaseFile")
    def releaseFile(self, process_id, status, project_id=None, filename=None, **kwargs):
        cherrypy.log(f"releaseFile: {process_id=} {status=} {filename=} {project_id=}")
        if not filename and self.last_process_file.get(process_id, ""):
            filename = self.last_process_file[process_id]
            del self.last_process_file[process_id]
        if not filename:
            cherrypy.response.status = 204
            return ""
        ddclient = self.client_cache.getdd_client()
        filename = os.path.basename(filename)
        did = f"{self.namespace}:{filename}"
        if status == "ok":
            ddclient.file_done(project_id, did, process_id)
        else:
            ddclient.file_failed(project_id, did, process_id)
        cherrypy.response.status = 204
        return ""

    @router.post("/sam/{experiment}/project/{project_id}/process/{process_id}/endProcess")
    def endProcess(self, experiment, project_id, process_id):
        # don't need to do this...
        cherrypy.response.status = 204
        return ""

    @router.post("/sam/{experiment}/project/{project_id}/endProject")
    def endProject(self, experiment, project_id):
        """if we haven't seen a getNextFile return nothing, cancel it"""
        if project_id not in self.project_finished:
            ddclient = self.client_cache.getdd_client()
            ddclient.cancel_project(project_id)
        cherrypy.response.status = 204
        return ""

    # same function for project or process status, which is a put
    # we ignore..
    @router.put("/sam/{experiment}/project/{project_id}/process/{process_id}/status")
    def status(self, process_id=None, project_id=None, status=None):
        pass

    @router.put("/sam/{experiment}/project/{project_id}/status")
    def status(self, process_id=None, status=None):
        pass

    @cherrypy.expose
    def get(self, project_id=None, **kwargs):
        ddclient = self.client_cache.getdd_client()
        return json.dumps(ddclient.get_project(project_id))

    @cherrypy.expose
    def dumpProject(self, project_id=None, **kwargs):
        ddclient = self.client_cache.getmc_client()
        return json.dumps(ddclient.get_project(project_id))

    @cherrypy.expose
    def summary(self, project_id=None, **kwargs):
        ddclient = self.client_cache.getmc_client()
        proj = json.dumps(ddclient.get_project(project_id))
        #  xxx mimic sam Project summary?
        return json.dumps(ddclient.get_project(project_id))

    @cherrypy.expose
    def recovery_dimensions(self, project_id=None, **kwargs):
        proj = json.dumps(ddclient.get_project(project_id))
        return "project {d['attributes']['name']} minus project_status like 'com%'"


@cbv(router)
class Api(ClientCacheMixin):
    """dispatcher and methods for /api/ paths"""

    @cherrypy.expose
    def index(self, **kwargs):
        cherrypy.log("test message")
        return '{"app":"samwebish", "version": samwebish_version}'

    @cherrypy.expose
    def createDefinition(self, **kwargs):
        return Definitions.create(self, **kwargs)

    @cherrypy.expose
    def deleteDefinition(self, **kwargs):
        return Definitions.delete(self, **kwargs)

    @cherrypy.expose
    def describeDefinition(self, **kwargs):
        return Definitions.get(self, **kwargs)

    @cherrypy.expose
    def translateConstraints(self, **kwargs):
        return Files.list(**kwargs)

    @cherrypy.expose
    def locateFile(self, **kwargs):
        return Files.get_name_locations(self, **kwargs)

    @cherrypy.expose
    def getMetadata(self, **kwargs):
        return Files.get_name_metadata(self, **kwargs)

    @cherrypy.expose
    def setStatus(self, **kwargs):
        pass

    @cherrypy.expose
    def dumpStation(self, **kwargs):
        ddclient = self.client_cache.getdd_client()
        rlst = list(ddclient.list_projects())
        cherrypy.log(f"dumpStation: got {rlst=}")
        res = f"samwebish version {samwebish_version}\n{len(rlst)} active projects:\n"
        res += "\n".join(
            [
                f"project {x['attributes'].get('name','')} id {x['project_id']} owner: {x['owner']} state: {x['state']} files: {len(x['file_handles'])} "
                for x in rlst
            ]
        )
        return res

    @cherrypy.expose
    def startProject(
        self,
        name,
        station,
        username,
        defname=None,
        def_id=None,
        snapshot_id=None,
        group=None,
        **kwargs,
    ):
        ddclient = self.client_cache.getdd_client()
        mcclient = self.client_cache.getmc_client()
        if defname:
            q = f"files selected by {self.namespace}:{defname}"
        if def_id:
            q = f"files selected by {self.namespace}:{def_id}"
        if snapshot_id:
            q = f"files from {self.namespace}:snapshot_{snapshot_id}"
        try:
            files = list(mcclient.query(q))
        except BadRequestError:
            raise cherrypy.HTTPError(404, f"Defname {defname} not found")
        sid = f"{self.namespace}:snapshot_for_project_{name}"
        cherrypy.log(f"startProject: {q=} {sid=} {files=}")
        ds = mcclient.create_dataset(sid)
        mcclient.add_files(sid, files)
        p = ddclient.create_project(files, project_attributes={"name": name}, query=q)
        b = cherrypy.request.base
        return f"{b}/api/projects/id/{p['project_id']}"

    @cherrypy.expose
    def findProject(self, name, **kwargs):
        ddclient = self.client_cache.getdd_client()
        pl = list(ddclient.list_projects(attributes={"name": name}))
        p = pl[0]
        b = cherrypy.request.base
        return f"{b}/api/projects/id/{p['project_id']}"


def main():
    server_config = {
        "server.socket_host": "0.0.0.0",
        "server.socket_port": 9443,
        "server.ssl_module": "pyopenssl",
        "server.ssl_certificate": "./certs/server_cert.pem",
        "server.ssl_private_key": "./certs/server_key.pem",
    }
    cherrypy.config.update(server_config)
    cherrypy.tree.mount(Api(), "/api", {"/": {"tools.trailing_slash.missing": False}})

    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == "__main__":
    main()
