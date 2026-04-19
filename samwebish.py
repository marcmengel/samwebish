class Definitions:

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
    def list(self, defname=None, user=None, group=None, after=None, before=None):
        pass

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


class Files:
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

    @cherrypy.expose
    def get_name_locations(self, **kwargs):
        pass

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

class Users:
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

class Values:
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

class Projects:
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


class Api:
    def __init__(self):
        self.parts = {
            "definitions": Definitions(),
            "files": Files(),
            "users": Users(),
            "values": Values(),
            "projects": Projects(),
        }

    def __cp_dispatch(self, vpath):
        """ handle various REST-ish parsing of samweb files api """
        if len(vpath) == 0:
            vpath.insert(0, 'index')
            return self
        if vpath[0] in self.parts:
            return self.parts[vpath.pop(0)]
        if len(vpath) == 3:
            vpath.pop(0)
            cherrypy.request.params['projectname'] = vpath.pop(0)
            return self
        return self 
    
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
