#!/usr/bin/python -u
#
# wrapper for entry access methods, part one
#
#



import sys
import os
import collections
import pprint

# self for __init__ exports
#
sys.path.append( os.path.realpath( "%s/../" % (os.path.split( __file__ )[0],) ) )
import starobj

class NMRSTAREntry( starobj.BaseClass ) :

    """BMRB entry methods"""

    CONNECTION = "entry"

    #
    # no good place for these...
    #
    # there's neither a "standard" way to retrieve last inserted auto-generated key,
    # nor to have one aut-generated.
    # just don't use this fro multiple threads.
    #
    @classmethod
    def last_sfid( cls, db, verbose = False ) :
        if verbose : sys.stdout.write( "%s.last_sfid()\n" % (cls.__name__,) )
        assert isinstance( db, starobj.DbWrapper )

        sql = "select max(sfid) from "
        scam = db.schema( cls.CONNECTION )
        if scam is not None : 
            sql += scam 
            sql += "."
        sql += "entry_saveframes"
        if verbose :
            sys.stdout.write( sql + "\n" )
        rs = db.query( cls.CONNECTION, sql )
        row = next(rs)
        if verbose :
            pprint.pprint( row )
        rc = 0
        if row is not None :
            if row[0] is not None :
                rc = int( row[0] )
        if rc < 0 : rc = 0
        return rc

    #
    # create tables for the entry
    #
    @classmethod
    def create_tables( cls, dictionary, db, use_types = True, tables = None, verbose = False ) :
        if verbose :
            sys.stdout.write( "%s._create_tables()\n" % (cls.__name__,) )

        assert isinstance( dictionary, starobj.StarDictionary )
        assert isinstance( db, starobj.DbWrapper )
        if tables is not None : assert isinstance( tables, collections.abc.Iterable )

        cols = []
        for table in dictionary.iter_tables() :
            if tables is not None :
                if not table in tables :
                    if verbose :
                        sys.stdout.write( "skipping %s: not in list\n" % (table,) )
                    continue

            del cols[:]
            for (t,column,dbtype) in dictionary.iter_tags( columns = ("dbtype",), tables = (table,) ) :

# NOTE! this stores floats as varchar( 63 ) to keep training zeroes and sidestep teh precision and
# rounding error issues.
#
                if dbtype.lower() == "float" :
                    cols.append( '"%s" varchar(63)' % (column,) )
                else :

# 2018-06-07 dictionary now uses boolean for what previously was yes/no char(3)
#  the values are still yes/no though
#
                    if use_types :
                        if dbtype.lower().startswith( "char" ) \
                        or dbtype.lower().startswith( "varchar" ) \
                        or dbtype.lower().startswith( "vchar" ) \
                        or dbtype.lower().startswith( "boolean" ) \
                        or dbtype.lower().startswith( "text" ) :
                            cols.append( '"%s" text' % (column,) )
                        elif dbtype.lower().startswith( "date" ) :
                            cols.append( '"%s" date' % (column,) )
                        elif dbtype.lower().startswith( "int" ) :
                            cols.append( '"%s" integer' % (column,) )
                        else :
#                            raise LookupError
                            sys.stderr.write( "Unsupported DBTYPE %s for _%s.%s" % (dbtype, table, column ) )
                            cols.append( '"%s" text' % (column,) )
                    else :
                        cols.append( '"%s" text' % (column,) )

            if len( cols ) < 1 :
                sys.stderr.write( "No columns in %s\n" % (table,) )
                continue

# schema names are not quoted but table names are
#
            scam = db.schema( cls.CONNECTION )
            if scam is not None : dbtable = '%s."%s"' % (scam, table,)
            else : dbtable = '"%s"' % (table,)

            stmt = 'create table %s (%s)' % (dbtable,",".join( c for c in cols ))
            if verbose :
                sys.stdout.write( stmt + "\n" )

            db.execute( connection = cls.CONNECTION, sql = stmt )

# entry saveframes
#
        stmt = "create table "
        if scam is not None : 
            stmt += scam
            stmt += "."
        stmt += "entry_saveframes (category text,entryid text,sfid integer primary key,name text,line integer)"
        if verbose :
            sys.stdout.write( stmt + "\n" )
        db.execute( connection = cls.CONNECTION, sql = stmt, commit = True )

    ###########################################################################################
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
        scam = self._db.schema( self.CONNECTION )
        if scam is not None : sql = 'select distinct "ID" from %s."Entry"' % (scam,)
        else : sql = 'select distinct "ID" from "Entry"'

        rs = self.query( sql )

# there should be only one row
#
        for row in rs :
            if self._id is None : self._id = row[0]
            else : raise Exception( "More than one ID in Entry!" )

    #
    #

    ########################
    # shortcut for db.query
    #
    def query( self, sql, params = None, newcursor = False ) :
        return self._db.query( self.CONNECTION, sql, params, newcursor )

    #########################
    # shortcut for db.execute
    #
    def execute( self, sql, params = None, newcursor = False, commit = False ) :
        return self._db.execute( self.CONNECTION, sql, params, newcursor, commit )


##################################################
# query methods
#
    # return saveframe name for sfid.
    # This is from entry_saveframes.
    #
    def get_saveframe_name( self, sfid ) :
        if self._verbose : sys.stdout.write( "%s.get_saveframe_name(%s)\n" % (self.__class__.__name__,sfid,) )

        rc = None
        scam = self._db.schema( self.CONNECTION )
        if scam is not None :
            dbtable = "%s.entry_saveframes" % (scam,)
        else :
            dbtable = "entry_saveframes"
        qry = "select name from %s where sfid=:id" % (dbtable,)
        rs = self.query( sql = qry, params = { "id" : sfid } )

# there can be only one
#
        for row in rs :
            rc = row[0]
        return rc

    # return line number for saveframe id
    #
    def get_saveframe_line( self, sfid ) :
        if self._verbose : sys.stdout.write( "%s.get_saveframe_line( %s )\n" % (self.__class__.__name__,str( sfid ),) )
        rc = None
        scam = self._db.schema( self.CONNECTION )
        if scam is not None :
            dbtable = "%s.entry_saveframes" % (scam,)
        else :
            dbtable = "entry_saveframes"
        qry = "select line from %s where sfid=:id" % (dbtable,)
        rs = self.query( sql = qry, params = { "id" : sfid } )

# there can be only one
#
        for row in rs :
            rc = row[0]
        return rc


    # saveframes as (sfid [, extra columns]) (ordered) from index table
    #
    def iter_saveframes( self, columns = None, entryid = None ) :
        if self._verbose : sys.stdout.write(  "%s.iter_saveframes()\n" % (self.__class__.__name__,) )
        colstr = ""
        if columns is not None :
            colstr = "," + ",".join( i for i in columns )
        rc = None

        scam = self._db.schema( self.CONNECTION )
        if scam is not None :
            dbtable = "%s.entry_saveframes" % (scam,)
        else :
            dbtable = "entry_saveframes"

        if entryid is None :
            wherestr = ""
        else :
            wherestr = " where entryid=:id"

        qry = ("select sfid%s from %s" % (colstr,dbtable)) + wherestr
        rs = self.query( sql = qry, params = { "id" : entryid }, newcursor = True )

        try :
            for row in rs :
                yield (row)
        finally :
            rs.cursor.close()

    # values in table : column(s)
    # these come from entry tables, SQL identifiers have to be double-quoted
    #
    def iter_values( self, table, columns, sfid = None, entryid = None, distinct = False ) :
        if self._verbose : sys.stdout.write( "%s.iter_values( %s )\n" % (self.__class__.__name__,table,) )
        assert isinstance( columns, collections.abc.Iterable )
        colstr = '","'.join( i for i in columns )

        scam = self._db.schema( self.CONNECTION )
        if scam is not None :
            dbtable = '%s."%s"' % (scam,table)
        else :
            dbtable = '"%s"' % (table,)

        qry = 'select %s "%s" from %s' % ((distinct and "distinct" or ""), colstr, dbtable,)

# really should fetch the flag from teh dictionary instaed of hardcoding column names
#
        if entryid is not None :
            qry += ' where "%s"=:id' % ((table == "Entry" and "ID" or "Entry_ID"),)
        if self._verbose :
            sys.stdout.write( "%s, id=%s\n" % (qry,(entryid is None and "None" or entryid),) )
        rs = self.query( sql = qry, params = { "id" : entryid }, newcursor = True )
        try :
            for row in rs :
                yield (row)
        finally :
            rs.cursor.close()

####################################################
#
#
    # this just inserts the savefame in index table
    # does not check unique/dupes etc.
    #
    # very big NOTE: this can only be used to insert one saveframe at a time
    #  becasue it runs a query for max sfid then inserts a row with sfid + 1.
    #
    def insert_saveframe( self, name, line = None, entryid = None, category = None ) :
        """add new saveframe and return its Sf_ID"""
        if self._verbose : 
            sys.stdout.write( "%s.insert_saveframe( %s, %s, %s, %s)\n" % (self.__class__.__name__, name, line, entryid, category) )

        scam = self._db.schema( self.CONNECTION )
        if scam is not None :
            dbtable = "%s.entry_saveframes" % (scam,)
        else :
            dbtable = "entry_saveframes"

        sql = ("insert into %s (category,entryid,sfid,name,line) " % (dbtable,)) \
            + "values(:sfcat,:entryid,:sfid,:name,:line)"

        sfid = self.last_sfid( db = self._db, verbose = self._verbose ) + 1

        params = { "name" : name, "line" : line, "entryid" : entryid, "sfcat" : category, "sfid" : sfid }

        if self._verbose :
            sys.stdout.write( sql + "\n" )
            pprint.pprint( params )
        rc = self.execute( sql, params )
        if self._verbose :
            sys.stdout.write( "=> %d rows inserted\n" % (rc.rowcount,) )

        return sfid

    # update value
    #
    def set_value( self, table, column, sfid = None, value = None ) :
        if self._verbose :
            sys.stdout.write( "%s.set_value( %s, %s, %s, %s )\n" % (self.__class__.__name__,table,column,sfid,value) )
        sql = 'update "%s" set "%s"=:val' % (table, column,)
        params = { "val" : value }
        if sfid is not None :
            sql += ' where "Sf_ID"=:id'
            params["id"] = sfid
        if self._verbose :
            sys.stdout.write( sql + "\n" )
            pprint.pprint( params )
        rc = self.execute( sql, params, newcursor = False, commit = True )
        if self._verbose :
            sys.stdout.write( "-> %d rows updated\n" % (rc.rowcount,) )
        return rc.rowcount

#
#
if __name__ == "__main__" :

    sys.stdout.write( "move along\n" )

#
