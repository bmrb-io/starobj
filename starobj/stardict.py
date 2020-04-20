#!/usr/bin/python -u
#

from __future__ import absolute_import

import sys
import os
import re
import collections
import ConfigParser
import pprint

# self
#
_UP = os.path.join( os.path.split( __file__ )[0], ".." )
sys.path.append( os.path.realpath( _UP ) )
import starobj

#
#
#
class StarDictionary( starobj.BaseClass ) :

    """Wrapper class for NMR-STAR dictionary queries"""

    CONNECTION = "dictionary"

    #####################
    #
    def __init__( self, db, *args, **kwargs ) :
        super( self.__class__, self ).__init__( *args, **kwargs )
        assert isinstance( db, starobj.DbWrapper )
        self._db = db
        self._schema = db.schema( self.CONNECTION )
        self._public_tags_only = True
        self._printable_tags_only = True
        self._tag_pat = re.compile( r"^_([^.]+)\.(.+)$" )

#
# 2 flags control tag visibility
#  public vs internal tags, e.g. contact information is non-public
#  printable vs unprintable, e.g. Sf_IDs are internal to the DB, change every time,
#   and so are never printed. Unless we want to actually see them.
    #
    #
    @property
    def public_tags_only( self ) :
        """Return only "release" tags"""
        return bool( self._public_tags_only )
    @public_tags_only.setter
    def public_tags_only( self, flag ) :
        self._public_tags_only = bool( flag )

    #######################
    #
    @property
    def printable_tags_only( self ) :
        """Return only "printable" tags"""
        return bool( self._printable_tags_only )
    @printable_tags_only.setter
    def printable_tags_only( self, flag ) :
        self._printable_tags_only = bool( flag )

    ########################
    # NMR-STAR version
    #
    @property
    def version( self ) :
        rc = None
        if self._schema is not None :
            qry = "select defaultvalue from %s.adit_item_tbl where originaltag=:tag" % (self._schema,)
        else :
            qry = "select defaultvalue from adit_item_tbl where originaltag=:tag"
        rs = self.query( sql = qry, params = { "tag" : "_Entry.NMR_STAR_version" } )

# there's only one row
#
        for row in rs : rc = str( row[0] )
        return rc

    ########################
    # split _table.column into table and column
    #
    def _split_tagname( self, tag ) :
        m = self._tag_pat.search( tag.strip() )
        if m is None :
            return None
        return ( m.group( 1 ), m.group( 2 ) )

    ########################
    # shortcut for db.query
    #
    def query( self, sql, params = None, newcursor = False ) :
        return self._db.query( self.CONNECTION, sql, params, newcursor )

####################################################################################
    # a very primitive expression parser for  for entry completeness rules like
    # "must have entry information and chemical shifts or peaks ..."
    #
    # parses an "x and y or z" expression
    #
    # return list of lists: ((a and y) or (b and x and z) ...)
    #
    # for now, very primitive, left-to-right, no precedence or grouping
    # "or" creates a new sub-list, "and" ads to current sub-list
    #
    def _parse_expr( self, expr ) :
        if self._verbose :
            sys.stdout.write( "%s.parse_expr(%s)\n" % (self.__class__.__name__, expr,) )
        if (expr is None) or (len( str( expr ).strip() ) < 1) : return None
        words = str( expr ).strip().split()
#
        rc = []
        sublist = None
        expect = "new"
        for word in words :
            if word.lower() == "and" :
                if expect != "op" :
                    raise Exception( "Expected table name, got 'and'" )
                expect = "add"
                if self._verbose : sys.stdout.write( "got 'and'\n" )
            elif word.lower() == "or" :
                if expect != "op" :
                    raise Exception( "Expected table name, got 'or'" )
                expect = "new"
                if self._verbose : sys.stdout.write( "got 'or'\n" )
            else :
                if not expect in ("add", "new") :
                    raise Exception( "Expected 'and' or 'or', got %s" % (word,) )

                if not self.is_valid_table( word ) :
                    raise Exception( "Invalid table %s" % (word,) )
                if self._verbose : sys.stdout.write( "got %s, op=%s\n" % (word, expect) )
                if expect == "new" :
                    if (sublist is not None) and (len( sublist ) > 0) :
                        rc.append( sublist )
                    sublist = []
                sublist.append( word )
                expect = "op"
# last term
        if (sublist is not None) and (len( sublist ) > 0) :
            rc.append( sublist )
        if self._verbose :
            pprint.pprint( rc )
        if len( rc ) < 1 : return None
        return rc

####################################################################################
# DDL
#
    # return a compiled re object or none
    #
    def get_ddl_regexp( self, ddltype ) :
        if self._verbose :
            sys.stdout.write( "%s.get_ddl_regexp(%s)\n" % (self.__class__.__name__, ddltype,) )

        if self._schema is not None :
            qry = "select regexp from %s.ddltypes where ddltype=:type" % (self._schema,)
        else :
            qry = "select regexp from ddltypes where ddltype=:type"

        rc = None
        rs = self.query( sql = qry, params = { "type" : ddltype } )

# there's only one row
#
        for row in rs :
            rc = re.compile( r"^%s$" % (str( row[0] ).strip(),) )

        return rc

    # get all
    #
    def iter_ddl_regexps( self ) :
        if self._verbose :
            sys.stdout.write( "%s.get_ddl_regexp()\n" % (self.__class__.__name__,) )

        if self._schema is not None :
            qry = "select ddltype,regexp from %s.ddltypes order by ddltype" % (self._schema,)
        else :
            qry = "select ddltype,regexp from ddltypes order by ddltype"

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                yield (str( row[0] ).strip(), re.compile( r"^%s$" % (row[1],) ))
        finally :
            rs.cursor.close()

#####################################################################
# saveframes
#
    # saveframe categories as (category [, extra columns]) (ordered)
    # conditions are AND'ed: e.g. "replicable and mandatory" or "public and printable"
    #
    def iter_saveframe_categories( self, columns = None, which = None ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_saveframe_categories()\n" % (self.__class__.__name__,) )

        if self._schema is None : table = "cat_grp"
        else : table = "%s.cat_grp" % (self._schema,)

        cols = ["sfcategory"]
        if columns is not None :
            assert isinstance( columns, collections.Iterable )
            for col in columns :
                if col == "sfcategory" : pass
                cols.append( col )

        conds = []
        if which is not None :
            assert isinstance( which, collections.Iterable )
            for i in which :
                kind = str( i ).lower()
                if kind == "all" :
                    pass
                else :
                    if kind == "replicable" :
                        conds.append( "replicable='Y'" )
                    elif kind == "unique" :
                        conds.append( "replicable='N'" )
                    elif kind == "public" :
                        conds.append( "internalflag='N'" )
                    elif kind == "private" :
                        conds.append( "internalflag='Y'" )
                    elif kind == "mandatory" :
                        conds.append( "printflag='Y'" )
                    elif kind == "printable" :
                        conds.append( "printflag<>'N'" )
                    elif kind == "data" :
                        conds.append( "printflag='C'" )

                    else : raise NotImplementedError( "dunno how to fetch %s" % (kind,) )

        qry = "select "
        qry += ",".join( col for col in cols )
        qry += " from "
        qry += table
        if len( conds ) > 0 :
            qry += " where "
            qry += " and ".join( c for c in conds )
        qry += " order by groupid"

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                yield (row)
        finally :
            rs.cursor.close()

    #######################################################################
    # returns "internal" (boolean), "print" (ternary), and "replicable" (boolean) flags as a tuple.
    # used by methods below
    #
    def _get_category_flags( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s._get_category_flags(%s)\n" % (self.__class__.__name__,category,) )

        assert category is not None
        rc = None
        if self._schema is None : table = "cat_grp"
        else : table = "%s.cat_grp" % (self._schema,)

        qry = "select upper(internalflag),upper(printflag),upper(replicable) from "
        qry += table
        qry += " where sfcategory=:sfcat"
        rs = self.query( sql = qry, params = { "sfcat" : category } )

# there's only one row
#
        for row in rs :
            if self._verbose :
                pprint.pprint( row )
            rc = tuple( row )

        return rc

    #######################################################################
    # Return true if saveframe category is mandatory (i.e. must print even if there's no real data)
    # false if not. (Internal categories can be mandatory for validation purposes.)
    #
    def is_mandatory_category( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s.is_mandatory_category( %s )" % (self.__class__.__name__, category,) )

        (internal, printable, replicable) = self._get_category_flags( category )
#        if (internal == "Y") and self._public_tags_only : return False
        if printable == "Y" : return True
        return False

    # Return true if saveframe category is printable, false if not.
    #
    def is_printable_category( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s.is_printable_category( %s )" % (self.__class__.__name__, category,) )
        (internal, printable, replicable) = self._get_category_flags( category )
        if self._verbose :
            sys.stdout.write( "Internal = %s, public_tags_only = %s, printable = %s, printable_tags_only = %s\n" \
            % (internal, (self._public_tags_only and "yes" or "no"), printable, (self._printable_tags_only and "yes" or "no")) )
        if (internal == "Y") and self._public_tags_only :
            return False
        if printable != "N" :
            return True
        if not self.printable_tags_only :
            return True   # normally not printable
        return False

    # Return true if saveframe category is not replicable.
    #
    def is_unique_category( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s.is_unique_category( %s )" % (self.__class__.__name__, category,) )

        (internal, printable, replicable) = self._get_category_flags( category )
        return (replicable == "N")

    # Return pair (comment text, every flag) or null
    #
    def get_saveframe_comment( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s.get_saveframe_comment( %s )" % (self.__class__.__name__, category,) )

        assert category is not None
        rc = None
        if self._schema is None : table = "comments"
        else : table = "%s.comments" % (self._schema,)

        qry = "select comment,everyflag from "
        qry += table
        qry += " where sfcategory=:cat and tagname is null"
        rs = self.query( sql = qry, params = { "cat" : category } )

# only one row
# boolean flag is true/false in this table, not Y/N
#
        for row in rs :
            comment = row[0]
            if comment is not None :
                if str( comment ).strip() in (".", "?") :
                    comment = None
            if comment is None :
                return None

            if row[1] is None : rc = (comment, False)
            elif str( row[1] ).strip().upper() in ("N", "FALSE") : rc = (comment, False)
            else : rc = (comment, True)

        return rc

    # List mandatory tables in saveframe category
    #
    # the output is a list of lists: outer lists are or'ed,
    # inner list has tables (tag categories) that are and'ed
    #
    # i.e. a saveframe may need ((Peak and Peak_char) or (Spectral_transition))
    # see also _parse_expr()
    #
    # return None if there aren't any
    #
    def get_mandatory_tables( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s.get_mandatory_tables( %s )" % (self.__class__.__name__, category,) )

# tag_cats is a view that contains sf categories and their "mandatory tables" lists
# (ones that have 'em only)
#
        assert category is not None
        rc = None
        if self._schema is None : tbl = "tag_cats"
        else : tbl = "%s.tag_cats" % (self._schema,)

        qry = "select tagcategory from "
        qry += tbl
        qry += " where sfcategory=:cat"
        rs = self.query( sql = qry, params = { "cat" : category } )

# there should be only one
#
        for row in rs :
            rc = self._parse_expr( row[0] )
        return rc

    # Get the free table in saveframe category (there should be only one)
    #
    def get_free_table( self, category ) :
        if self._verbose :
            sys.stdout.write( "%s.get_free_table( %s )" % (self.__class__.__name__, category,) )
        assert category is not None
        rc = None
        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry = "select distinct tagcategory from "
        qry += tbl
        qry += " where originalcategory=:cat and (loopflag is NULL or upper(loopflag)<>'Y')"
        rs = self.query( sql = qry, params = { "cat" : category } )

        for row in rs :
            rc = row[0]
        return rc

#####################################################################
# tables aka tag categories
#
    # tables (tag categories) (ordered)
    #   sfcategories : limit to specified saveframe categories (using sql "in")
    #   "which" shouldn't be a list, actually... but it is in other methods.
    #     here you can specify "looptable and freetable" and get an empty result.
    #
    def iter_tables( self, sfcategories = None, which = None ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_tables()\n" % (self.__class__.__name__,) )

        if self._schema is None : table = "adit_item_tbl"
        else : table = "%s.adit_item_tbl" % (self._schema,)

        ins = None
        if sfcategories is not None :
            assert isinstance( sfcategories, collections.Iterable )
            ins = "','".join( cat for cat in sfcategories )

        conds = []
        if which is not None :
            assert isinstance( which, collections.Iterable )
            for i in which :
                kind = str( i ).lower()
                if kind == "all" :
                    pass
                elif kind == "freetable" :
                    conds.append( "loopflag='N'" )
                elif kind == "looptable" :
                    conds.append( "loopflag='Y'" )
                else : raise NotImplementedError( "dunno how to fetch %s" % (kind,) )

        where = None
        if ins is not None :
            where = " where originalcategory in ('%s')" % (ins,)
        if len( conds ) > 0 :
            if where is None :
                where = " where " + " and ".join( c for c in conds )
            else :
                where += " and " + " and ".join( c for c in conds )

        sql = "select tagcategory from "
        sql += table
        if where is not None :
            sql += where
        sql += " group by tagcategory order by min(dictionaryseq)"

        rs = self.query( sql = sql, newcursor = True )
        try :
            for row in rs :
                yield (str( row[0] ))
        finally :
            rs.cursor.close()

    # false if it's not a valid table.
    # in NMR-STAR tag category names are unique (so far) so category parameter is redundant
    #
    def is_valid_table( self, name, category = None ) :
        if self._verbose :
            sys.stdout.write( "%s.is_valid_table(%s)\n" % (self.__class__.__name__,name) )
        assert name is not None

        if self._schema is None : table = "adit_item_tbl"
        else : table = "%s.adit_item_tbl" % (self._schema,)

        sql = "select count(*) from "
        sql += table
        sql += " where tagcategory=:tagcat"
        if category is not None :
            sql += " and originalcategory=:sfcat"

        rs = self.query( sql = sql, params = { "tagcat" : name, "sfcat" : category } )
        for row in rs :
            if row[0] > 0 :
                return True

        return False

    # return saveframe category for a table
    #
    def get_saveframe_category( self, table ) :
        if self._verbose :
            sys.stdout.write( "%s.get_saveframe_category(%s)\n" % (self.__class__.__name__,table) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        sql = "select distinct originalcategory from "
        sql += tbl
        sql += " where tagcategory=:cat"

        rc = None
        rs = self.query( sql = sql, params = { "cat" : table } )

# there should be only one
#
        for row in rs :
            rc = row[0]
        return rc

    # Return true if table is the free table.
    # as of NMR-STAR 3.2 tag categories are unique, so category parameter is redundant.
    #
    def is_free_table( self, table, category = None ) :
        if self._verbose :
            sys.stdout.write( "%s.is_free_table(%s)\n" % (self.__class__.__name__,table) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry = "select count(*) from "
        qry += tbl
        qry += " where tagcategory=:tagcat and (loopflag is NULL or upper(loopflag)<>'Y')"
        if category is not None :
            qry += " and originalcategory=:sfcat"

        rc = False
        rs = self.query( sql = qry, params = { "tagcat" : table, "sfcat" : category } )

# there should be only one
#
        for row in rs :
            if row[0] != 0 :
                rc = True
        return rc

    # Return row index flag, primary key tags, or all tags in the table (ordered list)
    # (only column names: intended use is in order by clause)
    # return none if table is not valid
    #
    def get_sort_key( self, table ) :

        if self._verbose :
            sys.stdout.write( "%s.get_sort_key(%s)\n" % (self.__class__.__name__,table) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry = "select tagfield from "
        qry += tbl
        qry += " where upper(rowindexflg)='Y' and tagcategory=:table order by dictionaryseq"

        params = { "table" : table }
        rc = []
        rs = self.query( sql = qry, params = params )

# there should be only one
#
        for row in rs :
            rc.append( (row[0], "int") )

        if len( rc ) > 0 :
            return rc

# try primary key
#
        qry = "select tagfield,bmrbtype from "
        qry += tbl
        qry += " where upper(primarykey)='Y' and tagcategory=:table order by dictionaryseq"
        rs = self.query( sql = qry, params = params )
        for row in rs :
            if row[1] in ("int", "float") :
                rc.append( (row[0], row[1]) )
            else :
                rc.append( (row[0], "text") )

        if len( rc ) > 0 :
            return rc

# if all else fails...
#
        qry = "select tagfield from "
        qry += tbl
        qry += "where tagcategory=:table order by dictionaryseq"
        rs = self.query( sql = qry, params = params )
        for row in rs :
            rc.append( row[0] )

        if len( rc ) > 0 :
            return rc

        return None

#####################################################################
# tags
#
    # iterate over tags, return (table, column [, extra columns if specified])
    #  (ordered)
    #
    #  which: kind(s) of tags to select, e.g. loop or rowindex,
    #   conditions are or'ed: here in most cases "and" doesn't make sense.
    #
    #  sfcategories, tables: limit to specified saveframe and tag categories
    #    sfcategory and table are implemented as "in" conditions.
    #    if both are given they are and'ed
    #
    def iter_tags( self, columns = None, which = None, sfcategories = None, tables = None ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_tags()\n" % (self.__class__.__name__,) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        cols = ["tagcategory","tagfield"]

        if columns is not None :
            assert isinstance( columns, collections.Iterable )
            for col in columns :
                if col in cols : continue
                cols.append( col )

# these are and'ed
#
        sfcatstr = None
        if sfcategories is not None :
            assert isinstance( sfcategories, collections.Iterable )
            sfcatstr = "originalcategory in ('%s')" % ("','".join( c for c in sfcategories ),)

        tablestr = None
        if tables is not None :
            assert isinstance( tables, collections.Iterable )
            sfcatstr = "tagcategory in ('%s')" % ("','".join( c for c in tables ),)

        oars = []
        if which is not None :
            assert isinstance( which, collections.Iterable )
            for i in which :
                kind = str( i ).lower()
                if kind == "all" :
                    pass
                else :
                    if kind == "sfcategory" :
                        oars.append( "sfcategoryflg='Y'" )
                    elif kind == "sfname" :
                        oars.append( "sfnameflg='Y'" )
                    elif kind == "sfpointer" :
                        oars.append( "sfpointerflg='Y'" )
                    elif kind == "notnull" :
                        oars.append( "dbnullable<>'Y'" )
                    elif kind == "primarykey" :
                        oars.append( "primarykey='Y'" )
                    elif kind == "freetable" :
                        oars.append( "loopflag='N'" )
                    elif kind == "looptable" :
                        oars.append( "loopflag='Y'" )
                    elif kind == "rowidx" :
                        oars.append( "rowindexflg='Y'" )
                    elif kind == "sfid" :
                        oars.append( "sfidflg='Y'" )
                    elif kind == "entryid" :
                        oars.append( "entryidflg='Y'" )
                    elif kind == "localid" :
                        oars.append( "lclidflg='Y'" )

                    else : raise NotImplementedError( "dunno how to fetch %s" % (kind,) )

        orstr = None
        if len( oars ) > 0 :
            orstr = "(%s)" % (" or ".join( o for o in oars ),)

#
#
        qry = "select %s from %s" % (",".join( c for c in cols ),tbl)
        where = None
        if sfcatstr is not None : where = sfcatstr
        if tablestr is not None :
            if where is not None :
                where += " and " + tablestr
            else :
                where = tablestr
        if orstr is not None :
            if where is not None :
                where += " and " + orstr
            else :
                where = orstr
        if where is not None :
            qry += " where " + where

        qry += " order by dictionaryseq"

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                yield (tuple( row ))
        finally :
            rs.cursor.close()

    # return all tags that map STAR saveframes to relational schema
    # ordered list of (table name, sfid column name, sfcategory column name, sfname column name, entryid column name)
    # this is for resolving saveframe categories after loading an entry into the db
    #
    # returns tuples (table, "Sf_ID", "Sf_category", "Sf_framecode", "Entry_ID")
    #
    def iter_saveframe_tags( self ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_saveframe_tags()\n" % (self.__class__.__name__,) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry = "select d1.tagcategory,d1.tagfield,d2.tagfield,d3.tagfield,d4.tagfield "
        qry += "from %s d1 join %s d2 on d1.tagcategory=d2.tagcategory " % (tbl,tbl)
        qry += "join %s d3 on d1.tagcategory=d3.tagcategory " % (tbl,)
        qry += "join %s d4 on d1.tagcategory=d4.tagcategory " % (tbl,)
        qry += "where d1.sfidflg='Y' and d2.sfcategoryflg='Y' and d3.sfnameflg='Y' and d4.entryidflg='Y' "
        qry += "order by d1.dictionaryseq"

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                yield (tuple( row ))
        finally :
            rs.cursor.close()

    # List printable tags in tables
    # Logic (same as printable castegories)
    # if (internal == "Y") and self._public_tags_only : not printable
    # if printable != "N" : printable
    # if not self.printable_tags_only : printable -- i.e. even normally not printable
    # not printable by default
    #
    # returns list of (table,column)
    #
    def iter_printable_tags( self, tables ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_printable_tags()\n" % (self.__class__.__name__,) )

        if self._schema is None :
            tbl = "adit_item_tbl a join validator_printflags p on p.dictionaryseq=a.dictionaryseq"
        else :
            tbl = "%s.adit_item_tbl a join %s.validator_printflags p on p.dictionaryseq=a.dictionaryseq" % (self._schema,self._schema)

        qry = "select a.tagcategory,a.tagfield,a.internalflag,p.printflag from " + tbl

        if tables is not None :
            assert isinstance( tables, collections.Iterable )
            qry += " where a.tagcategory in ('%s')" % ("','".join( c for c in tables ),)
        qry += " order by a.dictionaryseq"

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                internal = ("y" == str( row[2] ).strip().lower())
                printable = ("n" != str( row[3] ).strip().lower())
                if self._public_tags_only :
                    if internal :
                        continue
                if printable :
                    yield (row[0],row[1])
                else :
                    if not self._printable_tags_only :
                        yield (row[0],row[1])
        finally :
            rs.cursor.close()

    # return table name, datum count tag and datum name in the tables if there is one
    #
    def iter_datumcount_tags( self, tables = None ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_datumcount_tags()\n" % (self.__class__.__name__,) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry = "select tagcategory,tagfield,datumcountflgs from "
        qry += tbl
        qry += " where datumcountflgs is not null"
        if tables is not None :
            assert isinstance( tables, collections.Iterable )
            qry += " and tagcategory in ('%s')" % ("','".join( c for c in tables ),)
        qry += " order by dictionaryseq"

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                yield (tuple( row ))
        finally :
            rs.cursor.close()

    # this is ugly.
    # there are saveframe id tags that point to other safevrames, listed as foreign keys.
    # tag names that end in "_ID(_.+)?" should have a corrsp. "_label(_.+)?" tag,
    # maked with "sfpointerflg". that one's value whould be the name of the saveframe to which the
    # foreing key ID tag is pointing. that is a STAR way of linking saveframes.
    # (the IDs here are "lclidflg", not "sfidflg")
    #
    # so here we construct a list of
    #   child( table, tag ) -> parent( table, tag )
    # and let the downstream code figure out what to do with it
    #
    # this is limited to local ID and framcode tags for now and exclude entry ids
    #
    def iter_parent_child_tags( self ) :
        if self._verbose :
            sys.stdout.write( "%s.list_parent_child_tags()\n" % (self.__class__.__name__,) )

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry =  "select t1.tagcategory,t1.tagfield,t2.tagcategory,t2.tagfield " \
            + ("from %s t1 join %s t2 " % (tbl,tbl,)) \
            + "on t2.tagcategory=t1.foreigntable and t2.tagfield=t1.foreigncolumn " \
            + "where t1.foreigntable is not null and t1.foreigncolumn is not null " \
            + "and (t2.sfnameflg='Y' or t2.lclsfidflg='Y') and t2.entryidflg<>'Y' " \
            + "order by t2.dictionaryseq" 

        rs = self.query( sql = qry, newcursor = True )
        try :
            for row in rs :
                yield tuple( row )
        finally :
            rs.cursor.close()

    # This one takes full "_<table>.<column>" name or column, table pair.
    #
    def is_valid_tag( self, name, table = None ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_datumcount_tags()\n" % (self.__class__.__name__,) )

# if table is none, assume it's a _table.column name
#
        if table is None :
            tag = self._split_tagname( name )
            if tag is None : return False
            table = tag[0]
            col = tag[1]
        else : col = name

        if self._schema is None : tbl = "adit_item_tbl"
        else : tbl = "%s.adit_item_tbl" % (self._schema,)

        qry = "select count(*) from "
        qry += tbl
        qry += " where tagcategory=:table and tagfield=:column"

        rs = self.query( sql = qry, params = { "table" : table, "column" : col } )
        for row in rs :
            if row[0] > 0 :
                return True

        return False

#####################################################################
#
    # enumeration for a tag
    #
    def iter_enumeration( self, name, table = None ) :
        if self._verbose :
            sys.stdout.write( "%s.iter_enumeration(%s)\n" % (self.__class__.__name__,name) )

        if table is None :
            tag = self._split_tagname( name )
            if tag is None : raise StopIteration
            table = tag[0]
            col = tag[1]
        else : col = name

        if self._schema is None :
            qry = "select e.val from val_enums e join adit_item_tbl i on e.tagseq=i.dictionaryseq " \
                + "where i.tagcategory=:tagcat and i.tagfield=:tagname order by e.val"
        else :
            qry = "select e.val from %s.val_enums e join %s.adit_item_tbl i " % (self._schema,self._schema)
            qry += "on e.tagseq=i.dictionaryseq where i.tagcategory=:tagcat and i.tagfield=:tagname order by e.val"

        rs = self.query( sql = qry, params = { "tagcat" : table, "tagname" : col }, newcursor = True )

        try :
            for row in rs :
                yield (row[0])
        finally :
            rs.cursor.close()

###############################################
# mandatory tags
#
# this requires access to entry data as overrides are based on what's in there.
#
    # "override" part
    # conditionals only apply inside the same saveframe.
    #
    def _check_override( self, sfid, name, table = None ) :
        if self._verbose :
            sys.stdout.write( "%s._check_override(%s)\n" % (self.__class__.__name__,name) )

        assert str( sfid ).isdigit()
        if table is not None :
            fulltag = "_%s.%s" % (table, name)
        else : fulltag = name

        if self._schema is None : tbl = "val_overrides"
        else : tbl = "%s.val_overrides" % (self._schema,)

        qry = "select ctltag,val from "
        qry += tbl
        qry += " where deptag=:tag and dbnullable='N'"

        ovr = None
        rs = self.query( sql = qry, params = { "tag" : fulltag } )

# there can be only one
#
        for row in rs :
            ovr = tuple( row )

        if ovr is None :
            return False

# if we get here, we need to check entry data
#
        m = re.search( r"^_([^.]+)\.(.+)$", str( ovr[0] ).strip() )
        if m is None : raise LookupError( "Invalid ctl tag in overrides: %s" % (ovr[0],) )
        ctltable = m.group( 1 )
        ctltag = m.group( 2 )
        ctlval = str( ovr[1] ).strip()
        if self._verbose :
            sys.stdout.write( "* %s override: control table %s, tag %s, val %s\n" % (fulltag, ctltable, ctltag, ctlval) )

# "trigger" value is a regexp or "*"
#
        if ctlval == "*" : pat = re.compile( r"^.+$" )
        else : pat = re.compile( r"^%s$" % (ctlval,) )

        rc = False

        qry = "select %s" % (ctltag,)
        if self._db.schema( "entry" ) is not None :
            qry += "from %s.%s" % (self._db.schema( "entry" ),ctltable)
        else :
            qry += "from %s" % (ctltable,)

# !
#
        qry += ' where "Sf_ID"=:sfid'
        rs = self._db.query( connection = "entry", sql = qry, params = { "sfid" : sfid }, newcursor = True )
        for row in rs :

            m = pat.search( row[0] )
            if m is not None :
                if self._verbose :
                    sys.stdout.write( "* got matching ctl value %s\n", row[0] )
                rc = True
                break

        rs.cursor.close()
        return rc

    # "base" part
    #
    def _is_mandatory_tag( self, name, table = None ) :
        if self._verbose :
            sys.stdout.write( "%s._is_mandatory_tag(%s)\n" % (self.__class__.__name__,name) )

        if table is None :
            (t, c) = self._split_tagname( name )
            params = { "table" : t, "col" : c }
        else :
            params = { "table" : table, "col" : name }

        if self._schema is None :
            tbl = "adit_item_tbl a join validator_printflags p on p.dictionaryseq=a.dictionaryseq"
        else :
            tbl = "%s.adit_item_tbl a join %s.validator_printflags p on p.dictionaryseq=a.dictionaryseq" % (self._schema,self._schema)

        qry = "select p.printflag,a.dbnullable from "
        qry += tbl
        qry += " where a.tagcategory=:table and a.tagfield=:col"

        printable = False
        notnull = False
        rs = self.query( sql = qry, params = params )

# there can be only one
#
        for row in rs :
            printable = ("y" == str( row[0] ).lower())

# it's either null or "NOT NULL"
#
            if (row[1] is None) or (str( row[1] ).strip() == "") :
                notnull = False
            else :
                notnull = ("n" == str( row[1] ).strip().lower()[0])

        if printable or notnull : return True
        return False

    # Return true if tag would be printed even if the value is null.
    # This is relevant for free tables only because
    # in loop tables we print all row values if we're printing the row.
    #
    # note that if tag is not in "printable" list it shouldn't be printed
    # even if it's mandatory by this logic -- i.e. tag could be private and mandatory
    # and we're printing the "public" version of the entry.
    #
    # this needs access to entry data to figure out conditionals.
    #
    # some tags are "unconditionally" mandatory, they don't need saveframe id.
    #
    # mandatory code overrides apply in the same saveframe only.
    #
    def is_mandatory_tag( self, tag, table = None, sfid = None ) :
        if self._verbose :
            sys.stdout.write( "%s.is_mandatory_tag(%s)\n" % (self.__class__.__name__,tag) )

# if table is none, assume it's a _table.column name
#
        if table is None :
            (t, c) = self._split_tagname( tag )
        else :
            t = table
            c = tag

        if self._is_mandatory_tag( table = t, name = c ) : return True
        assert sfid is not None
        return self._check_override( sfid = sfid, table = t, name = c )

########################################
#
#
#
if __name__ == "__main__" :

    cp = ConfigParser.SafeConfigParser()
    cp.read( sys.argv[1] )

    wrp = starobj.DbWrapper( config = cp, verbose = True )
    wrp.connect()

    sd = StarDictionary( wrp, verbose = True )
    sd.print_all_tags = False
    sd.public = True

    sys.stdout.write( "*** NMR-STAR v. %s ***\n" % (sd.version,) )

    sys.stdout.write( "******* DDL ********\n" )
    for (t, r) in sd.iter_ddl_regexps() :
        sys.stdout.write( "%s : %s\n" % (t, r.pattern) )

    sys.stdout.write( "******* data saveframe categories ********\n" )
    for row in sd.iter_saveframe_categories( columns = ("replicable",), which = ("data",) ) :
        if row[1] == "N" :
            sys.stdout.write( "%s (unique)\n" % (row[0],) )
        else :
            sys.stdout.write( "%s\n" % (row[0],) )

    sys.stdout.write( "******* sf category entry_information ********\n" )
    if sd.is_mandatory_category( "entry_information" ) :
        sys.stdout.write( "is mandatory\n" )
    else :
        sys.stdout.write( "is not mandatory\n" )
    if sd.is_printable_category( "entry_information" ) :
        sys.stdout.write( "is printable\n" )
    else :
        sys.stdout.write( "is not printable\n" )
    if sd.is_unique_category( "entry_information" ) :
        sys.stdout.write( "is unique\n" )
    else :
        sys.stdout.write( "is replicable\n" )

    cmt = sd.get_saveframe_comment( "entry_information" )
    sys.stdout.write( "SF comment is\n" )
    if cmt is not None :
        sys.stdout.write( cmt[0] )
        sys.stdout.write( "\n" )
    else :
        sys.stdout.write( "ERROR: None\n" )

    sys.stdout.write( "******* mandatory tables in entry information ********\n" )
    t = sd.get_mandatory_tables( "entry_information" )
    sys.stdout.write( ">>>\n" )
    pprint.pprint( t )

    sys.stdout.write( "******* free table in entry information ********\n" )
    t = sd.get_free_table( "entry_information" )
    sys.stdout.write( ">>>\n" )
    pprint.pprint( t )

    sys.stdout.write( "******* loop tables in assembly and entity ********\n" )
    for t in sd.iter_tables( sfcategories = ("assembly","entity"), which = ("looptable",) ) :
        sys.stdout.write( "%s\n" % (t,) )

    sys.stdout.write( "******* is valid table: Atom in assembly ********\n" )
    if sd.is_valid_table( name = "Atom", category = "assembly" ) :
        sys.stdout.write( "yes\n" )
    else :
        sys.stdout.write( "no\n" )

    sys.stdout.write( "******* saveframe category for _Atom: ********\n" )
    sys.stdout.write( "%s\n" % (sd.get_saveframe_category( table = "Atom" ),) )

    sys.stdout.write( "******* is free table: _Atom: ********\n" )
    if sd.is_free_table( table = "Atom", category = "assembly" ) :
        sys.stdout.write( "yes\n" )
    else :
        sys.stdout.write( "no\n" )

    sys.stdout.write( "******* all saveframe tags: ********\n" )
    for row in sd.iter_saveframe_tags() :
        pprint.pprint( row )

    sys.stdout.write( "******* saveframe name and not null tags in _Atom and _Angle: ********\n" )
    for (t, c) in sd.iter_tags( tables = ("Atom","Angle"), which = ("sfname","notnull",) ) :
        sys.stdout.write( "_%s.%s\n" % (t,c) )

    sys.stdout.write( "******* printable tags in _Atom and _Angle: ********\n" )
    for (t, c) in sd.iter_printable_tags( tables = ("Atom","Angle") ) :
        sys.stdout.write( "_%s.%s\n" % (t,c) )

    sys.stdout.write( "******* datum count tags in _Atom_chem_shift and _Coupling_constant: ********\n" )
    for i in sd.iter_datumcount_tags( tables = ("Atom_chem_shift","Coupling_constant") ) :
        sys.stdout.write( "_%s.%s: %s\n" % i )

    sys.stdout.write( "******* is valid tag: _Atom_chem_shift.ID: ********\n" )
    if sd.is_valid_tag( "_Atom_chem_shift.ID" ) :
        sys.stdout.write( "yes\n" )
    else :
        sys.stdout.write( "no\n" )

    sys.stdout.write( "******* enumeration for _Entity.Polymer_type: ********\n" )
    for i in sd.iter_enumeration( table = "Entity", name = "Polymer_type" ) :
        sys.stdout.write( "%s\n" % i )

    sys.stdout.write( "******* is mandatory tag (uncondiitonal): _Entry.ID: ********\n" )
    if sd.is_mandatory_tag( table = "Entity", tag = "ID" ) :
        sys.stdout.write( "yes\n" )
    else :
        sys.stdout.write( "no\n" )

    sys.stdout.write( "******* parent-child IDs and labels: ********\n" )
    for i in sd.iter_parent_child_tags() :
        sys.stdout.write( "child: %s.%s -> parent %s.%s\n" % i )

#
#
