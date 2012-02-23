#!/bin/env python

import sys
import httplib
import base64


from github import Github

class RecordingHttpResponse( object ):
    def __init__( self, file, res ):
        self.status = res.status
        self.__headers = res.getheaders()
        self.__output = res.read()
        file.write( str( self.status ) + "\n" )
        file.write( str( self.__headers ) + "\n" )
        file.write( str( self.__output ) + "\n" )

    def getheaders( self ):
        return self.__headers

    def read( self ):
        return self.__output

class RecordingHttpsConnection:
    __realHttpsConnection = httplib.HTTPSConnection

    def __init__( self, file, *args, **kwds ):
        self.__file = file
        self.__cnx = self.__realHttpsConnection( *args, **kwds )

    def request( self, verb, url, input, headers ):
        self.__cnx.request( verb, url, input, headers )
        del headers[ "Authorization" ] # Do not let sensitive info in git :-p
        self.__file.write( verb + " " + url + " " + str( headers ) + " " + input + "\n" )

    def getresponse( self ):
        return RecordingHttpResponse( self.__file, self.__cnx.getresponse() )

    def close( self ):
        self.__file.write( "\n" )
        return self.__cnx.close()

class ReplayingHttpResponse( object ):
    def __init__( self, file ):
        self.status = int( file.readline().strip() )
        self.__headers = eval( file.readline().strip() )
        self.__output = file.readline().strip()

    def getheaders( self ):
        return self.__headers

    def read( self ):
        return self.__output

class ReplayingHttpsConnection:
    def __init__( self, file ):
        self.__file = file

    def request( self, verb, url, input, headers ):
        del headers[ "Authorization" ]
        assert self.__file.readline().strip() == verb + " " + url + " " + str( headers ) + " " + input

    def getresponse( self ):
        return ReplayingHttpResponse( self.__file )

    def close( self ):
        self.__file.readline()

class IntegrationTest:
    __fileName = "ReplayDataForIntegrationTest.txt"

    def main( self ):
        if len( sys.argv ) == 2 and sys.argv[ 1 ] == "--record":
            print "Record mode: I'm really going to do requests to github.com. Please type 'yes' and return"
            sys.stdout.flush()
            confirm = sys.stdin.readline().strip()
            if confirm != "yes":
                exit( 1 )
            self.record()
        else:
            self.replay()

        exit()

    def record( self ):
        self.prepareRecord()
        self.playScenario()

    def replay( self ):
        self.prepareReplay()
        self.playScenario()

    def prepareRecord( self ):
        try:
            import GithubCredentials
            self.g = Github( GithubCredentials.login, GithubCredentials.password )
            file = open( self.__fileName, "w" )
            httplib.HTTPSConnection = lambda *args, **kwds: RecordingHttpsConnection( file, *args, **kwds )
        except ImportError:
            print "Please create a 'GithubCredentials.py' file containing:"
            print "login = '<your github login>'"
            print "password = '<your github password>'"
            exit( 1 )

    def prepareReplay( self ):
        try:
            file = open( self.__fileName )
            httplib.HTTPSConnection = lambda *args, **kwds: ReplayingHttpsConnection( file )
            self.g = Github( "login", "password" )
        except IOError:
            print "Please re-run this script with argument '--record' to be able to replay the integration tests based on recorded first execution"
            exit( 1 )

    def playScenario( self ):
        self.doSomeReads()
        self.doSomeWrites()

    def doSomeReads( self ):
        self.dumpUser( self.g.get_user() )
        jacquev6 = self.g.get_user( "jacquev6" )
        self.dumpUser( jacquev6 )
        self.dumpOrganization( self.g.get_organization( "github" ), doTeams = False )
        self.dumpOrganization( self.g.get_organization( "BeaverSoftware" ), doTeams = True )
        self.dumpRepository( jacquev6.get_repo( "PyGithub" ) )

    def doSomeWrites( self ):
        self.doSomeWritesToUser()
        self.doSomeWritesToRepository()

    def doSomeWritesToUser( self ):
        u = self.g.get_user()
        oldBio = u.bio
        u.edit( bio = oldBio + " (Edited by PyGithub)" )
        u.edit( bio = oldBio )
        jacquev6 = self.g.get_user( "jacquev6" )
        u.remove_from_following( jacquev6 )
        u.add_to_following( jacquev6 )
        PyGithub = jacquev6.get_repo( "PyGithub" )
        u.remove_from_watched( PyGithub )
        u.add_to_watched( PyGithub )

    def doSomeWritesToRepository( self ):
        u = self.g.get_user()
        r = u.create_repo( name = "TestPyGithub", description = "Created by PyGithub", has_wiki = False )
        b1 = r.create_git_blob( "This blob was created by PyGithub", encoding = "latin1" )
        t1 = r.create_git_tree( [ { "path": "foo.bar", "mode": "100644", "type": "blob", "sha": b1.sha } ] )
        c1 = r.create_git_commit( "This commit was created by PyGithub", t1.sha, [] )
        master = r.create_git_ref( "refs/heads/master", c1.sha )
        b2 = r.create_git_blob( "This blob was also created by PyGithub", encoding = "latin1" )
        t2 = r.create_git_tree( [ { "path": "foo.bar", "mode": "100644", "type": "blob", "sha": b2.sha }, { "path": "old", "mode": "040000", "type": "tree", "sha": t1.sha } ] )
        c2 = r.create_git_commit( "This commit was also created by PyGithub", t2.sha, [ c1.sha ] )
        master.edit( c2.sha )
        tag = r.create_git_tag( "a_tag", "This tag was created by PyGithub", c2.sha, "commit" )
        r.create_git_ref( "refs/tags/a_tag", tag.sha )
        self.dumpRepository( r )

    def dumpUser( self, u ):
        print u.login, "(", u.name, ")"
        print "  Repos:"
        for r in u.get_repos():
            print "   ", r.name,
            if r.fork:
                print "<-", r.parent.owner.login + "/" + r.parent.name,
                print "<-", r.source.owner.login + "/" + r.source.name,
            print
        print "  Watched:", ", ".join( r.name for r in u.get_watched() )
        print "  Organizations:", ", ".join( o.login for o in u.get_orgs() )
        print "  Following:", ", ".join( f.login for f in u.get_following() )
        print "  Followers:", ", ".join( f.login for f in u.get_followers() )
        print
        sys.stdout.flush()

    def dumpOrganization( self, o, doTeams ):
        print o.login, "(", o.name, ")"
        print "  Members:", ", ".join( u.login for u in o.get_members() )
        print "  Repos:", ", ".join( r.name for r in o.get_repos() )
        if doTeams:
            print "  Teams:"
            for team in o.get_teams():
                print "   ", team.name, "(" + team.permission + "):", ", ".join( u.login for u in team.get_members() ), "->", ", ".join( r.name for r in team.get_repos() )
        print
        sys.stdout.flush()

    def dumpRepository( self, r ):
        print r.owner.login + "/" + r.name
        print "  Collaborators:", ", ".join( u.login for u in r.get_collaborators() )
        print "  Contributors:", ", ".join( u.login for u in r.get_contributors() )
        print "  Watchers:", ", ".join( u.login for u in r.get_watchers() )
        print "  Forks:", ", ".join( f.owner.login + "/" + f.name for f in r.get_forks() )
        print "  References:", ", ".join( ref.ref + " (" + ref.object[ "sha" ][ :7 ] + ")" for ref in r.get_git_refs() )
        masterCommitSha = r.get_git_ref( "refs/heads/master" ).object[ "sha" ]
        masterCommit = r.get_git_commit( masterCommitSha )
        masterTreeSha = masterCommit.tree[ "sha" ]
        masterTree = r.get_git_tree( masterTreeSha )
        for element in masterTree.tree:
            if element[ "type" ] == "blob":
                blobSha = element[ "sha" ]
                break
        blob = r.get_git_blob( blobSha )
        print "  Master:", masterCommitSha, masterCommit.message, ", ".join( element[ "path" ] + " (" + element[ "type" ] + ")" for element in masterTree.tree )
        print "    blob:", blob.content, blob.encoding,
        if blob.encoding == "base64":
            print base64.b64decode( blob.content ),
        print
        print
        sys.stdout.flush()

IntegrationTest().main()