#!/usr/bin/python -u
#
# wrapper for entry access methods, part one
#
#

from __future__ import absolute_import

import sys
import os
#import pprint

# self for __init__ exports
#
sys.path.append( os.path.realpath( "%s/../" % (os.path.split( __file__ )[0],) ) )
import starobj

class NMRSTAREntry( starobj.BaseClass ) :

    """BMRB entry methods"""

    CONNECTION = "entry"

    #
    #
    def __init__( self, db, *args, **kwargs ) :
        super( self.__class__, self ).__init__( *args, **kwargs )
        assert isinstance( db, starobj.DbWrapper )
        self._db = db
        self._schema = db.schema( self.CONNECTION )
        self._id = None


    # write out rows with this entry id only. if null: first entry id from entry_saveframes (which
    #  in a one-entry database should be *the* entry id)
    #
    @property
    def id( self ) :
        """Entry ID"""
        if self._id is None :
            self._get_id()
        return self._id
    @id.setter
    def id( self, entryid ) :
        self._id = entryid
    #
    def _get_id( self ) :
        if self._verbose :
            sys.stdout.write( "%s._get_id()\n" % (self.__class__.__name__,) )
        rs = self.query( sql = 'select distinct "ID" from "Entry"' )

# there should be only one row
#
        for row in rs :
            if self._id is None : self._id = row[0]
            else : raise Exception( "More than one ID in Entry!" )

    ########################
    # shortcut for db.query
    #
    def query( self, sql, params = None, newcursor = False ) :
        return self._db.query( self.CONNECTION, sql, params, newcursor )

##################################################
# query methods
#
    # return saveframe name for sfid.
    # This is from entry_saveframes.
    #
    def get_saveframe_name( self, sfid ) :
        if self._verbose : print self.__class__.__name__, "get_saveframe_name(%s)" % (sfid,)

        rc = None
        qry = "select name from entry_saveframes where sfid=:id"
        rs = self.query( sql = qry, params = { "id" : sfid } )

# there can be only one
#
        for row in rs :
            rc = row[0]
        return rc


    # saveframes as (sfid [, extra columns]) (ordered) from index table
    #
#    def iter_saveframes( self, columns = None, entryid = None ) :
#        if self._verbose : print self.__class__.__name__, "iter_saveframes()"

    # return line number for saveframe id
    #
#    def get_saveframe_line( self, sfid ) :
#        if self._verbose : print self.__class__.__name__, "get_saveframe_line( %s )" % (str( sfid ),)


    # values in table : column(s)
    #
#    def iter_values( self, table, columns, sfid = None, entryid = None, distinct = False ) :
#        if self._verbose : print self.__class__.__name__, "iter_values( %s )" % (table,)

    # update value
    #
#    def set_value( self, table, column, sfid = None, value = None ) :
#        if self._verbose : print self.__class__.__name__, "set_value( %s, %s, %s, %s )" % (table,column,sfid,value)


#
#
if __name__ == "__main__" :

    sys.stdout.write( "move along\n" )

#
