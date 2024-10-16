#!/usr/bin/python -u
#
#



import sys
import os
import re
#import pprint
#import traceback

# self
#
_UP = os.path.join( os.path.split( __file__ )[0], ".." )
sys.path.append( os.path.realpath( _UP ) )
import starobj

#
# Entry loader
#
#
class StarParser:

    """NMR-STAR parser for DB loader"""

    # tag for error messages
    #
    SRC = "LDR"

    # target DB
    #
    CONNECTION = "entry"

####################################################################################################

    #
    #
    #
    @classmethod
    def parse( cls, fp, db, dictionary, errlist = None, types = True, create_tables = True, verbose = False ) :
        if verbose :
            sys.stdout.write( "%s.parse()\n" % (cls.__name__,) )

        if errlist is None : errlist = []

        h = cls( db = db, dictionary = dictionary, errlist = errlist )
        h.verbose = verbose
        h.use_types = types
        h.create_tables = create_tables

        l = starobj.sas.StarLexer( fp = fp, bufsize = 0, verbose = verbose )
        p = starobj.sas.SansParser.parse( lexer = l, content_handler = h, error_handler = h, verbose = verbose )
        if h.has_errors : return False
        return True

    #
    #
    #
    @classmethod
    def parse_file( cls, filename, db, dictionary, errlist = None, types = True, create_tables = True, verbose = False ) :

        if not os.path.exists( filename ) :
            raise IOError( "File not found: %s" % (filename,) )
        rc = False
        with open( filename, "rb" ) as inf :
            rc = cls.parse( fp = inf, db = db, dictionary = dictionary, errlist = errlist, types = types,
                    create_tables = create_tables, verbose = verbose )
        return rc

    #
    #
    def __init__( self, db, dictionary, entry = None, errlist = None, verbose = False ) :
        if verbose :
            sys.stdout.write( "%s.__init__()\n" % (self.__class__.__name__,) )

        assert isinstance( db, starobj.DbWrapper )
        self._db = db

        assert isinstance( dictionary, starobj.StarDictionary )
        self._dictionary = dictionary

        if errlist is not None : self._errlist = errlist
        else : self._errlist = []

        self._verbose = bool( verbose )

        self._stat = None
        if entry is not None :
            assert isinstance( entry, starobj.NMRSTAREntry )
            self._entry = entry
        else :
            self._entry = starobj.NMRSTAREntry( db = db, verbose = verbose )

        self._tag_pat = re.compile( r"_([^.]+)\.(.+)" )
        self._int_pat = re.compile( r"^\d+$" )
        self._entryid = None
        self._table_name = None
        self._first_tag = None
        self._row_num = 0
        self._use_types = False
        self._free_table = None
        self._create_tables = True

    # error list may contain warning and/or info messages, or garbage from before. if it's the latter:
    #  we get to keep the pieces.
    #
    @property
    def has_errors( self ) :
        """True if there were errors during parse"""
        for e in self._errlist :
            if e.svr in (starobj.Error.CRIT, starobj.Error.ERR) :
                return True
        return False

    #
    #
    @property
    def errorlist( self ) :
        """Error list"""
        return self._errlist
    @errorlist.setter
    def errorlist( self, errlist ) :
        self._errlist = errlist

    #
    #
    @property
    def statement( self ) :
        """statement wrapper"""
        return self._stat
    @statement.setter
    def statement( self, stmt ) :
        self._stat = stmt

    #
    #
    @property
    def use_types( self ) :
        """if false, all columns are text"""
        return self._use_types
    @use_types.setter
    def use_types( self, flag ) :
        self._use_types = bool( flag )

    #
    #
    @property
    def create_tables( self ) :
        """if false, don't create database tables"""
        return self._create_tables
    @create_tables.setter
    def create_tables( self, flag ) :
        self._create_tables = bool( flag )

####################################################################################################
#
    # create tables for the entry
    #
    def _create_tables( self, dictionary ) :
        if self._verbose :
            sys.stdout.write( "%s._create_tables()\n" % (self.__class__.__name__,) )
        raise DeprecationWarning( "use NMRSTAREntry.create_tables() instead" )

    # insert into entry_saveframes table
    # columns: entryid, sfid, name, line, category
    # categories are added after the fact
    #
    def _insert_saveframe( self, name, line, category = None ) :
        if self._verbose :
            sys.stdout.write( "%s._insert_saveframe(%s,%s)\n" % (self.__class__.__name__,name,line) )
        raise DeprecationWarning( "use NMRSTAREntry.insert_saveframe() instead" )

####################################################################################################
# SAS handlers
#
    #
    #
    def fatalError( self, line, msg ) :
        self._errlist.append( starobj.Error( starobj.Error.CRIT, line, self.SRC, "parse error: " + msg ) )

    #
    #
    def error( self, line, msg ) :
        self._errlist.append( starobj.Error( starobj.Error.ERR, line, self.SRC, "parse error: " + msg ) )
        return True

    #
    #
    def warning( self, line, msg ) :
        self._errlist.append( starobj.Error( starobj.Error.WARN, line, self.SRC, "parse warning: " + msg ) )
        return True

    #
    #
    def comment( self, line, text ) : return False
    def endData( self, line, name ) : pass

    # data_NAME : check encoding
    #
    def startData( self, line, name ) :
        self._entryid = name
        try :
            name.decode( starobj.ENCODING )
        except UnicodeError :
            self._errlist.append( starobj.Error( starobj.Error.ERR, line, self.SRC,
                    "Data block ID not an %s string: %s" % (starobj.ENCODING, name) ) )

        if self._create_tables :
            starobj.NMRSTAREntry.create_tables( dictionary = self._dictionary, db = self._db,
                    use_types = self.use_types, verbose = self._verbose )

        self._stat = starobj.DbWrapper.InsertStatement( db = self._db, connection = self.CONNECTION,
                 verbose = self._verbose )
#schema = self._db.schema( connection = self.CONNECTION ),
        return False

    # save_NAME
    # we don't know what free table name is yet
    #
    def startSaveframe( self, line, name ) :
        assert self._stat is not None
        self._table_name = None
        self._free_table = None
        try :
            name.decode( starobj.ENCODING )
        except UnicodeError :
            self._errlist.append( starobj.Error( starobj.Error.ERR, line, self.SRC,
                "Saveframe name not an %s string: %s" % (starobj.ENCODING, name) ) )

        self._entry.insert_saveframe( name = name, line = line )

        return False

    # save_
    #
    def endSaveframe( self, line, name ) :
        assert self._stat is not None
        if len( self._stat ) > 0 :

# this can happen if savefreaem has no loops (e.g. entry interview)
#
            if not self._stat.insert() :
                self._errlist.append( starobj.Error( starobj.Error.CRIT, line, self.SRC,
                    "DB insert error in row %d" % (self._row_num) ) )
                return True
            self._stat.reset()

# add saveframe category to index table
#
        if self._free_table is None : raise Exception( "No free table" )
        cat = self._dictionary.get_saveframe_category( self._free_table )
        if cat is None : raise Exception( "No saveframe category for free table " + self._free_table )
        if self._db.schema( self.CONNECTION ) is not None :
            sql = "update %s.entry_saveframes set category=:cat where name=:nip" % (self._db.schema( self.CONNECTION ),)
        else :
            sql = "update entry_saveframes set category=:cat where name=:nip" 
        self._entry.execute( sql, params = { "cat" : cat, "nip" : name } )

        return False

    # new table
    # first loop in a saveframe will have a pending statement (free table)
    # we don't know what the table name is yet
    #
    def startLoop( self, line ) :

        assert self._stat is not None

# commit free tags, if there are any
#
        if len( self._stat ) > 0 :
            rc = self._stat.insert()
            if rc != 1 :
                msg = "insert error: %s rows inserted (there should be only one)" % (rc,)
                self._errlist.append( starobj.Error( starobj.Error.CRIT, line, self.SRC, msg ) )
                return True

            self._stat.reset()

        self._first_tag = None
        self._row_num = 0

        return False

    # stop_
    #
    def endLoop( self, line ) :
        assert self._stat is not None

# there shold be last row pending
#
        rc = self._stat.insert()
        if rc != 1 :
            msg = "insert error: %s rows inserted (there should be only one)" % (rc,)
            self._errlist.append( starobj.Error( starobj.Error.CRIT, line, self.SRC, msg ) )
            return True

        self._stat.reset()

        self._first_tag = None
        self._row_num = 0
        return False

    # tag/value
    #
    def data( self, tag, tagline, val, valline, delim, inloop ) :
        assert self._stat is not None

# basic checks first
#
        try :
            tag.decode( starobj.ENCODING )
        except UnicodeError :
            self._errlist.append( starobj.Error( starobj.Error.ERR, tagline, self.SRC, \
                "Tag is not an %s string: %s" % (starobj.ENCODING, tag) ) )
            return True

        if val is not None :
            try :
                val.decode( starobj.ENCODING )
            except UnicodeError :
                self._errlist.append( starobj.Error( starobj.Error.ERR, valline, self.SRC, \
                    "Value is not an %s string: %s" % (starobj.ENCODING, val[:30]) ) )

        m = self._tag_pat.search( tag )
        if not m :
            e = starobj.Error( starobj.Error.CRIT, tagline, self.SRC, "Invalid tagname" )
            e.tag = tag
            self._errlist.append( e )
            return True

# first tag - no table name
#
        if self._stat.table is None :
            self._stat.table = m.group( 1 )

# if free table: we'll need its name in endSaveframe()
#
            if not inloop :
                self._free_table = m.group( 1 )

        else :
            if self._stat.table != m.group( 1 ) :
                e = starobj.Error( starobj.Error.CRIT, tagline, self.SRC,
                    "tag category changed, was %s" % (self._table_name) )
                e.tag = tag
                self._errlist.append( e )
                return True

        if inloop :

# true @ start of loop
#
            if self._first_tag is None :
                self._first_tag = m.group( 2 )
                self._row_num += 1 # = 1
            else :
                if self._first_tag == m.group( 2 ) :

# new loop row: commit previous one
#
                    if not self._stat.insert() :
                        self._errlist.append( starobj.Error( starobj.Error.CRIT, valline, self.SRC,
                            "db insert error in row %d" % (self._row_num) ) )
                        return True
                    self._row_num += 1


#
#
#        sys.stdout.write( "==> parser: val %s, delim %s\n" % (val, delim) )
        self._stat[m.group( 2 )] = val

        return False

#
#
#
if __name__ == "__main__" :

    import configparser

    cp = configparser.SafeConfigParser()
    cp.read( sys.argv[1] )

    wrp = starobj.DbWrapper( config = cp, verbose = True )
    wrp.connect()

    sd = starobj.StarDictionary( wrp, verbose = True )
    sd.print_all_tags = False
    sd.public = True

    errors = []

    p = StarParser.parse_file( db = wrp, dictionary = sd, filename = sys.argv[2], errlist = errors, verbose = True )
    if len( errors ) > 0 :
        sys.stderr.write( "---------------------------------" )
        for e in errors :
            sys.stderr.write( e )
            sys.stderr.write( "\n" )

#
