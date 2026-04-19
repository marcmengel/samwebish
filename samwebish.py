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


def main():
    # need to move this all into the __cp_dispatch of an Api(), and just mount that
    # 'cause the api needs the backwards compat methods.
    cherrypy.tree.mount(Definitions(), '/api/definitions')
    cherrypy.tree.mount(Files(), '/api/files')
    cherrypy.tree.mount(Users(), '/api/users')
    cherrypy.tree.mount(Values(), '/api/values')
    cherrypy.tree.mount(Projects(), '/api/projects')

    cherrypy.engine.start()
    cherrypy.engine.block()
