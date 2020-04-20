#!/usr/bin/python -u
#
# poor man's abstraction layer for pgdb and sqlite3
#
# this will replace ":NAME" placeholders in SQL statements with "%(NAME)s" if the engine is pgdb
# input SQL has to use ":NAME" and must include all the proper quoting and schema names etc.
# all parameters must be named, there's no support for '?'/'%s' placeholders
#
# note that connection.autocommit does not work in pgdb but setting it is not an error.
#

from __future__ import absolute_import

import sys
import os
import ConfigParser
import pgdb
import sqlite3
import re
import pprint
import csv
#import json

# self
#
_UP = os.path.join( os.path.split( __file__ )[0], ".." )
sys.path.append( os.path.realpath( _UP ) )
import starobj

class DbWrapper( starobj.BaseClass ) :

    """Simple stupid wrapper for sqlite3 and pgdb"""

    CONNECTIONS = ("dictionary", "entry")
    ENGINES = ("pgdb", "sqlite3")

####################################################################################################
# wrapper for cursor because the one in sqlite3 is not an iterator
# does not close the cursor as it may (should) be reused later
#
    class ResultSet( object ) :
        def __init__( self, cursor ) :
#            print "ResultSet: init",
            self._curs = cursor
        def __iter__( self ) :
#            print "ResultSet: iter",
            return self
        def __next__( self ) :
#            print "ResultSet: _next",
            rc = self._curs.fetchone()
#            print "*** row"
#            pprint.pprint( rc )
#            print "***"
            if rc is None :
                raise StopIteration
            return rc
        def next( self ) :
#            print "ResultSet: next",
            return self.__next__()
        @property
        def cursor( self ) :
            """underlying cursor"""
            return self._curs

####################################################################################################
# wrapper for sql insert statement for entry loader.
# SOP for NMR-STAR loops: collect tags first, then add values and insert entire rows.
# For free tables: collect tag-value pairs for the entire row then insert.
# Either way, this emulates a dict of tag(column) - value mappings with extra attributes: target
# table and target saveframe ID.
#
# Insers do not require removal of keys, nor iteration over values, so those aren't implemented.
#
# Unlike sqlalchemy version, this does not validate table & column names. So it'll fail on insert()
# rather than on setitem()
#
    class InsertStatement( object ) :

        """dict-like wrapper for SQL insert"""

        # db: DbWrapper
        # connection: name, entry or dictionary
        #
        def __init__( self, db, connection, table = None, verbose = False ) :
            try :
                assert isinstance( db, starobj.DbWrapper )
            except :
                sys.stderr.write( type( db ).__name__ + "\n" )
                raise

            self._db = db
            self._connection = connection
            self._items = {}
            self._table = table
#            self._schema = schema
            self._verbose = bool( verbose )

        #
        #
#        @property
#        def schema( self ) :
#            """in case there's a db schema"""
#            return self._schema
#        @schema.setter
#        def schema( self, name ) :
#            self._schema = str( name ).strip()
#            if self._schema == "" : self._schema = None

        #
        #
        @property
        def table( self ) :
            """db table we're inserting into"""
            if str( self._table ).strip() == "" :
                self._table = None
            return self._table
        @table.setter
        def table( self, name ) :
            assert name is not None
            self._table = str( name ).strip()
            assert self._table != ""
            self._items.clear()

        #
        #
#        @property
#        def sfid( self ) :
#            """last inserted saveframe id"""
#            return self._sfid
#        @sfid.setter
#        def sfid( self, sfid ) :
#            assert sfid is not None
#            self._sfid = int( sfid )

        #
        #
        def __len__( self ) :
            return len( self._items )

        #
        #
        def __getitem__( self, key ) :
            return self._items[key]
        def __setitem__( self, key, value ) :
            if value is not None :
                val = str( value ).strip()
                if val == "" : val = None
                elif val in ("?", ".") : val = None
            else : val = None
            self._items[key] = val

        #
        #
        def __contains__( self, key ) :
            return (key in self._items)

        #
        #
        def keys( self ) :
            if self._verbose :
                sys.stdout.write( "%s.keys()\n" % (self.__class__.__name__,) )
            assert isinstance( self._items, dict )
            return self._items.keys()
        def values( self ) :
            if self._verbose :
                sys.stdout.write( "%s.values()\n" % (self.__class__.__name__,) )
            assert isinstance( self._items, dict )
            return self._items.values()
        def items( self ) :
            if self._verbose :
                sys.stdout.write( "%s.items()\n" % (self.__class__.__name__,) )
            assert isinstance( self._items, dict )
            return self._items.items()

        #
        #
        def clear( self ) :
            if self._verbose :
                sys.stdout.write( "%s.clear()\n" % (self.__class__.__name__,) )
            assert isinstance( self._items, dict )
            self._items.clear()
            if self._verbose :
                sys.stdout.write( "*** items is now ***\n" )
                pprint.pprint( self._items )
                sys.stdout.write( "********************\n" )

        # clear + wipe out table name
        #
        def reset( self ) :
            if self._verbose :
                sys.stdout.write( "%s.reset()\n" % (self.__class__.__name__,) )
            self.clear()
            self._table = None

        # insert current row
        #
        def insert( self ) :
            if self._verbose :
                sys.stdout.write( "%s.insert()\n" % (self.__class__.__name__,) )
            assert self._table is not None
            assert str( self._table ).strip() != ""
            assert isinstance( self._items, dict )
            if len( self._items ) < 1 :
                if self._verbose :
                    sys.stdout.write( "noting to insert\n" )
                return 0

# make sure primary key is in there. It may not be the last inserted ID.
#
            have_sfid = (("Sf_ID" in self._items.keys()) and (self._items["Sf_ID"] is not None))
            if not have_sfid :
                self._items["Sf_ID"] = starobj.NMRSTAREntry.last_sfid( db = self._db )

# we don't quote scheme names but do need to quote table and column names
#
            scam = self._db.schema( self._connection )
            if scam is not None :
                tbl = '%s."%s"' % (scam, self._table,)
            else :
                tbl = '"%s"' % (self._table,)

# sort order should be the same
#
            tmpwtf = sorted( self._items.keys() )
            colstr = '","'.join( c for c in tmpwtf )
            valstr = ",:x".join( c.lower() for c in tmpwtf )
            params = {}
            for c in tmpwtf : # self._items.keys() :
                params[ "x%s"% (c.lower(),) ] = self._items[c]

            stmt = 'insert into %s ("%s") values (:x%s)' % (tbl,colstr,valstr,)
            if self._verbose :
                sys.stdout.write( stmt )
                sys.stdout.write( "\n" )
                pprint.pprint( self._items )
                sys.stdout.write( "***\n" )
                pprint.pprint( params )

            rc = self._db.execute( connection = self._connection, sql = stmt, params = params )
            return rc.rowcount

####################################################################################################
#
# self._connections is a dict of dicts:
#
#  "entry"|"dictionary" : {
#      "conn" : connection
#      "curs" : cursor (pre-create one for simple stuff)
#      "engine" : "pgdb"|"sqlite3"
#      "schema" : db schema
#  }
#
# "engine" is for fixing pgdb's quoting style
#

    #
    #
    def __init__( self, config, *args, **kwargs ) :
        super( self.__class__, self ).__init__( *args, **kwargs )
        assert isinstance( config, ConfigParser.ConfigParser )
        self._props = config
        self._connections = {}
        self._param_pat = re.compile( r"(:(\w+))" )

    # connect to both dictionary and entry databases and open a cursor in each
    #
    def connect( self ) :
        if self._verbose : sys.stdout.write( self.__class__.__name__ + ".connect()\n" )
        assert isinstance( self._props, ConfigParser.ConfigParser )

        for section in self.CONNECTIONS :
            engine = self._props.get( section, "engine" )
            assert engine in self.ENGINES
            db = self._props.get( section, "database" )
            self._connections[section] = {}
            schema = None
            if self._props.has_option( section, "schema" ) :
                schema = self._props.get( section, "schema" )
            if schema is not None :
                self._connections[section]["schema"] = schema
            if engine == "pgdb" :
                host = None
                if self._props.has_option( section, "host" ) :
                    host = self._props.get( section, "host" )
                user = None
                if self._props.has_option( section, "user" ) :
                    user = self._props.get( section, "user" )
                passwd = None
                if self._props.has_option( section, "password" ) :
                    passwd = self._props.get( section, "password" )

                self._connections[section]["conn"] = pgdb.connect( user = user, password = passwd,
                        host = host, database = db )
                self._connections[section]["curs"] = self._connections[section]["conn"].cursor()
                self._connections[section]["engine"] = "pgdb"
            else :
                self._connections[section]["conn"] = sqlite3.connect( db )
                self._connections[section]["curs"] = self._connections[section]["conn"].cursor()
                self._connections[section]["engine"] = "sqlite3"

    # close database connections
    #
    def close( self ) :
        if self._verbose :
            sys.stdout.write( self.__class__.__name__ + "._close()\n" )
        for c in self.CONNECTIONS :
            if not c in self._connections : continue
            if self._connections[c]["conn"] is not None :
                self._connections[c]["conn"].close()
                self._connections[c] = None

    # schema for the database
    #
    def schema( self, connection ) :
        if self._verbose : sys.stdout.write( "%s.schema(%s)\n" % (self.__class__.__name__,connection,) )
        assert connection in self.CONNECTIONS
        if "schema" in self._connections[connection] : return self._connections[connection]["schema"]
        return None

    # exec an sql statement.
    # connection is a keyword: either "dictionary" or "entry"
    # params must be a dict if not null. This only works with named parameters.
    # placeholders must be DB-style :NAME, not python-style %(NAME)s,
    #   and NAME must match re (\w+)
    # if newcursor is false, re-use existing cursor
    #
    def execute( self, connection, sql, params = None, newcursor = False, commit = False ) :
        if self._verbose : sys.stdout.write( "%s.execute(%s,%s)\n" % (self.__class__.__name__,connection,sql,) )

        assert connection in self.CONNECTIONS
        if params is not None :
            assert isinstance( params, dict )

# if it's pgdb, replace :NAME with %(NAME)s
#
        if (self._connections[connection]["engine"] == "pgdb") and (params is not None) :
            stmt = self._param_pat.sub( r"%(\g<2>)s", sql )
        else :
            stmt = sql

        if newcursor :
            curs = self._connections[connection]["conn"].cursor()
        else :
            curs = self._connections[connection]["curs"]
# debug
#
        if self._verbose :
#            print type( stmt )
            if params is not None :
                sys.stdout.write( self._param_pat.sub( r"%(\g<2>)s", sql ) % params )
            else :
                sys.stdout.write( stmt )
            sys.stdout.write( "\n" )

        try :
            if params is not None :
                curs.execute( stmt, params )
            else :
                curs.execute( stmt )
        except :
            sys.stderr.write( stmt + "\n" )
            pprint.pprint( params )
            raise

        if commit :
            self._connections[connection]["conn"].commit()

        return curs

    # query returns an iterable ResultSet
    # there's no checking that sql is actually a "select"
    #
    def query( self, connection, sql, params = None, newcursor = False ) :
        return DbWrapper.ResultSet( cursor = self.execute( connection, sql, params, newcursor ) )


#
#
if __name__ == "__main__" :

    cp = ConfigParser.SafeConfigParser()
    cp.read( sys.argv[1] )

    wrp = DbWrapper( config = cp, verbose = True )
    wrp.connect()

    schema = wrp.schema( "dictionary" )
    if schema is not None :
        qry = "select defaultvalue from %s.adit_item_tbl where originaltag=:tag" % (schema,)
    else :
        qry = "select defaultvalue from adit_item_tbl where originaltag=:tag"

    rs = wrp.execute( connection = "dictionary", sql = qry, params = { "tag" : "_Entry.NMR_STAR_version" } )
    row = rs.fetchone()
    if row is None : sys.stderr.write( "No version in the dictionary!\n" )
    else : sys.stdout.write( "NMR-STAR version %s\n" % (row[0],) )

    if schema is not None :
        qry = "select originaltag from %s.adit_item_tbl where tagcategory=:tagcat order by dictionaryseq" % (schema,)
    else :
        qry = "select originaltag from adit_item_tbl where tagcategory=:tagcat order by dictionaryseq"

    rs = wrp.query( connection = "dictionary", sql = qry, params = { "tagcat" : "Entry" } )
    for row in rs :
        sys.stdout.write( "%s\n" % (row[0],) )

    wrp.close()

#
