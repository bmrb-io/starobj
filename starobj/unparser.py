#!/usr/bin/python -u
#
# Need validation dictionary in validict. schema
#
# requires postgesql 9 : order by columns not in select clause.
#

from __future__ import absolute_import

import sys
import os
import re
import pprint
import collections
import cStringIO


# self
#
_UP = os.path.join( os.path.split( __file__ )[0], ".." )
sys.path.append( os.path.realpath( _UP ) )
import starobj

# pretty-printer
#
#
class StarWriter( starobj.BaseClass ) :

    SRC = "UNP"
    TABWIDTH = 3
    ENTRY_CONNECTION = "entry"

    #
    #
    @classmethod
    def pretty_print( cls, entry, dictionary, out, errlist = None, entryid = None, comments = True,
            public = True, alltags = False, sfids = False, verbose = False ) :
        u = cls( verbose = verbose )
        if errlist is None :
            errlist = []
        u.errorlist = errlist
        u.entryid = entryid
        u.print_comments = comments
        u.entry = entry
        u.dictionary = dictionary
        u._public_tags_only = public
        u._printable_tags_only = (not alltags)
        u._sfids = sfids
        u.unparse( out )

        return u

    #
    #
    @classmethod
    def pretty_print_file( cls, entry, dictionary, filename, errlist = None, entryid = None, comments = True,
            public = True, alltage = False, sfids = False, verbose = False ) :
        rc = None
        with open( filename, "wb" ) as out :
            rc = cls.pretty_print( cls, entry, dictionary, out, errlist, entryid, comments, public, alltags, sfids, verbose )
        return rc

    #
    #
    def __init__( self, *args, **kwargs ) :
        super( self.__class__, self ).__init__( *args, **kwargs )
        if self._verbose :
            sys.stdout.write( "%s.__init__()\n" % (self.__class__.__name__,) )
        self._tabwidth = StarWriter.TABWIDTH
        self._errlist = None
        self._entryid = None
        self._public_tags_only = True
        self._printable_tags_only = True
        self._sfids = False
        self._comments = True
        self._entry = None
        self._dict = None
        self._indent = 0

# true to print out Sf_ID tags (for debugging: they're never printed out otherwise)
#
        self._print_sfids = True

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
    def entry( self ) :
        """BMRB entry wrapper"""
        return self._entry
    @entry.setter
    def entry( self, entry ) :
        assert isinstance( entry, starobj.NMRSTAREntry )
        self._entry = entry

    #
    #
    @property
    def dictionary( self ) :
        """NMR-STAR dictionary wrapper"""
        return self._dict
    @dictionary.setter
    def dictionary( self, dictionary ) :
        assert isinstance( dictionary, starobj.StarDictionary )
        self._dict = dictionary

    @property
    def print_comments( self ) :
        """Print boilerpalte comments"""
        return bool( self._comments)
    @print_comments.setter
    def print_comments( self, flag ) :
        self._comments = bool( flag )

    # indent & space between loop columns
    # anything < 3 will likely produce invalid STAR
    #
    @property
    def tabwidth( self ) :
        """num. spaces for indents and between loop columns"""
        return self._tabwidth
    @tabwidth.setter
    def tabwidth( self, width ) :
        if width is None : self._tabwidth = self.TABWIDTH
        try :
            self._tabwidth = int( width )
            if self._tabwidth < self.TABWIDTH :
                self._tabwidth = self.TABWIDTH
        except ValueError :
            self._tabwidth = self.TABWIDTH

####################################################################################################
    # the ugly part of it all is we need to check all values to see if there's any "real" data in the
    # saveframe. Actual checking is done by DataTable iterator, it returns only rows with real data
    #
    def _has_printable_data( self, sfid, tables ) :
        if self._verbose :
            sys.stdout.write( "%s._has_printable_data(%s)\n" % (self.__class__.__name__,str( sfid ),) )

        rc = False
        for table in tables :
            if self._verbose :
                sys.stdout.write( "==> checking %s\n" % (table,) )

            if rc : break
            data = starobj.DataTable( verbose = self._verbose )
            data.dictionary = self._dict
            data.db = self._entry._db
            data.sfid = sfid
            data.table = table
            for row in data :
                rc = True
                break

        data.reset()
        if self._verbose :
            sys.stdout.write( "===> %s printable data\n" % ((rc and "has" or "no"),) )
        return rc

####################################################################################################
    #
    #
    def unparse( self, out ) :
        if self._verbose :
            sys.stdout.write( "%s.unparse()\n" % (self.__class__.__name__,) )

        sfcats = []
        sfids = []
        tables = []
        for i in self._dict.iter_saveframe_categories() :
            if self._dict.is_printable_category( i[0] ) :
                sfcats.append( i[0] )
        if len( sfcats ) < 1 :
            self._errlist.append( starobj.Error( starobj.Error.WARN, 0, self.SRC,
                "No printable saveframe categories" ) )
            return False

        out.write( "data_%s\n\n" % (self._entry.id,) )

# foreach printable saveframe category
#
        for sfcat in sfcats :
            freetable = self._dict.get_free_table( category = sfcat )
            if freetable is None :
                self._errlist.append( starobj.Error( starobj.Error.CRIT, 0, self.SRC,
                    "No free table in saveframe category %s" % (sfcat,) ) )
                return False

            sfidtag = None
            entryidtag = None
            for i in self._dict.iter_tags( columns = ("sfidflg", "entryidflg",), which = ("sfid","entryid",),
                    tables = (freetable,) ) :
                if i[2] == "Y" :
                    sfidtag = i[1]
                if i[3] == "Y" :
                    entryidtag = i[1]

# entry id must be filled in
#
            if (sfidtag is None) or (entryidtag is None) :
                self._errlist.append( starobj.Error( starobj.Error.CRIT, 0, self.SRC,
                    "No entry/saveframe ID tags in %s" % (freetable,) ) )
                return False

            if self._verbose :
                sys.stdout.write( "- Unparse saveframe category %s\n" % (sfcat,) )

            del sfids[:]
            qry = 'select "%s" from "%s" where "%s"=:id order by "%s"' % (sfidtag,freetable,entryidtag,sfidtag)
            rs = self._entry.query( sql = qry, params = { "id" : self._entry.id } )
            for row in rs :
                sfids.append( row[0] )

            if len( sfids ) < 1 :
                if self._verbose :
                    sys.stdout.write( "No saveframe IDs to unparse in %s\n" % (sfcat,) )
                continue

            if self._verbose :
                sys.stdout.write( "-- with %d saveframes\n" % (len( sfids ),) )

            del tables[:]
            for i in self._dict.iter_tables( sfcategories = (sfcat,) ) :
                tables.append( i )

# should never happen: there's freetable at least
#
            if len( tables ) < 1 :
                raise Exception( "Dictionary problem: No tables in saveframe category %s" % (sfcat,) )

            if self._verbose :
                sys.stdout.write( "--- with %d tables\n" % (len( tables ),) )

# foreach saveframe
#
# comment[1] is True if the comment's to be printed before every saveframe instead of just the first one
# it's never true as of 20170309
#
            if self._comments : comment = self._dict.get_saveframe_comment( sfcat )
            else : comment = None

# If saveframe category is mandatory, print out the 1st saveframe even if it has no real data,
# generate an error message if there's no real data (?).
# Otherwise print saveframe if it has real data. The ugly part: figuring out if it has real data
# requires fetching the values and then we do it again to print them.
#
# Print saveframe comments,
# but only on top of the first saveframe in the category, unless "every" flag is set,
# but only if we're printing the saveframe out (has real data)
#
            sf_printed = False
            for sfid in sfids :

                if self._has_printable_data( sfid, tables ) :
                    if (comment is not None) and (comment not in (".", "?") ) :
#                        sys.stdout.write( "--- comment is\n" )
#                        pprint.pprint( comment )
                        for j in range( self._indent * self._tabwidth ) : out.write( " " )
                        out.write( comment[0] )
                        if not comment[0].endswith( "\n" ) : out.write( "\n" )
                        out.write( "\n" )

# comment[1] is "every" flag: if true, print above every saveframe
#
                        if not comment[1] : comment = None

                    if not self.unparse_saveframe( out, sfid, freetable, tables ) :
                        return False
                    sf_printed = True

# if no saveframes printed for the category
#
            if not sf_printed :

# check if it's a mandatory saveframe category
#
                if self._rdict.is_mandatory_category( sfcat ) :
                    if self._verbose : 
                        sys.stdout.write( "!!! No real data in mandatory saveframe category %s" % (sfcat,) )
                    self._errlist.append( starobj.Error( starobj.Error.ERR, 0, self.SRC,
                        "No real data in mandatory saveframe category %s" % (sfcat,) ) )

# unparse free table anyway
#
                    if (comment is not None) and (comment not in (".", "?")) :
                        for j in range( self._indent * self._tabwidth ) : out.write( " " )
                        out.write( comment[0] )
                        if not comment[0].endswith( "\n" ) : out.write( "\n" )
                        out.write( "\n" )
                    if not self.unparse_saveframe( out, sfid, freetable, tables ) :
                        return False

        return True

####################################################################################################
    #
    # Unparse single saveframe.
    # (freetable & tables are here so I don't have to run query again.)
    #
    def unparse_saveframe( self, out, sfid, freetable, tables ) :
        if self._verbose :
            sys.stdout.write( "%s.unparse_saveframe(%s)\n" % (self.__class__.__name__,sfid,) )

        sfname = self._entry.get_saveframe_name( sfid )
        if sfname is None :
            self._errlist.append( starobj.Error( starobj.Error.CRIT, 0, self.SRC,
                "No name for saveframe %s" % (str( sfid )) ) )
            return False

        for j in range( self._indent * self._tabwidth ) : out.write( " " )
        out.write( "save_" )
        out.write( sfname )
        out.write( "\n" )
        self._indent += 1

# free table is always printed
#

        self.unparse_free_table( out, sfid, freetable )

        for table in tables :
            if table == freetable : continue
            self.unparse_loop_table( out, sfid, table )

        self._indent -= 1
        for j in range( self._indent * self._tabwidth ) : out.write( " " )
        out.write( "save_\n\n" )

        return True

####################################################################################################
    #
    #
    def unparse_free_table( self, out, sfid, name ) :
        if self._verbose :
            sys.stdout.write( "%s.unparse_free_table(%s,%s)\n" % (self.__class__.__name__,sfid,name,) )

        rc = False
        rows = starobj.DataTable( verbose = self._verbose )
        rows.db = self._entry._db
        rows.dictionary = self._dict
        rows.sfid = sfid
        rows.table = name

#        rows.all_rows = True ??
        for row in rows :
            rc = True
# whitespace
            taglen = 0
            for tag in rows.columns :
                if len( tag ) > taglen :
                    taglen = len( tag )
# _ category .
            taglen += 2
            taglen += len( name )
# framecodes
            framecodes = []
            for i in self._dict.iter_tags( tables = (name,), which = ("sfpointer",) ) :
                framecodes.append( i[1] )

            for i in range( len( rows.columns ) ) :
                if self._verbose : sys.stdout.write( "* %s - %s\n" % (rows.columns[i], row[i],) )

                tag = "_%s.%s" % (name, rows.columns[i])
# spec. cases
#
# ADIT-NMR housekeeping tags -- don't write them out at all
#
                if name == "Entry_interview" \
                and rows.columns[i] in ("PDB_deposition", "BMRB_deposition", "View_mode", "Use_previous_BMRB_entry",
                                        "Previous_BMRB_entry_used", "Previous_BMRB_entry_owner") :
                    continue
                if (name == "Deposited_data_files") and (rows.columns[i] in ("Precheck_flag", "Validate_flag")) :
                    continue

# now write out the tag
#
                for j in range( self._indent * self._tabwidth ) : out.write( " " )
                out.write( tag )


# ...  but massage the values
#
# offset entry and citation titles
#
                if (row[i] is not None) and (rows.columns[i] == "Title") and (name in ("Entry", "Citation")) :
                    if (row[i] is None) or (str( row[i] ).strip() in (".", "?")) :
                        for j in range( len( tag ), taglen ) : out.write( " " )
                        for j in range( self._tabwidth ) : out.write( " " )
                        out.write( ".\n" )
                        continue
                    out.write( "\n;\n" )
                    out.write( starobj.toascii( str( row[i] ).rstrip() ) )
                    out.write( "\n;\n" )
                    continue

# wrap sequence at 20 cols
#
                if (row[i] is not None) and (name == "Entity") and \
                ((rows.columns[i] == "Polymer_seq_one_letter_code") or (rows.columns[i] == "Polymer_seq_one_letter_code_can")) :
                    if (row[i] is None) or (str( row[i] ).strip() in (".", "?")) :
                        for j in range( len( tag ), taglen ) : out.write( " " )
                        for j in range( self._tabwidth ) : out.write( " " )
                        out.write( ".\n" )
                        continue

# this makes an array of 20-character chunks
#
                    tmp = starobj.toascii( row[i] )
                    tmp = re.sub( r"\s+", "", tmp )
                    buf = cStringIO.StringIO()
                    for j in range( 1, len( tmp ) + 1 ) :
                        buf.write( tmp[j - 1] )
                        if ((j % 20) == 0) and (j != 1) : buf.write( "\n" )
                    val = buf.getvalue()
                    out.write( "\n;\n" )
                    out.write( starobj.toascii( val ) )
                    out.write( "\n;\n" )
                    continue

                if self._verbose :
                    sys.stdout.write( "** tag length: %d, max tag length: %d, tab width: %d\n" % (len( tag ),taglen,self._tabwidth) )

# always update the version
#
                if (rows.columns[i] == "NMR_STAR_version") and (name == "Entry") :
                    (qs,val) = starobj.check_quote( self._dict.version )
                else :
                    (qs,val) = starobj.check_quote( row[i], verbose = self._verbose )

                if qs == starobj.sas.TOKENS["SEMISTART"] :
                    out.write( "\n" )
                else :
                    for j in range( len( tag ), taglen ) :
                        out.write( " " )
                    for j in range( self._tabwidth ) :
                        out.write( " " )
                if (framecodes is not None) and (rows.columns[i] in framecodes) :
                    if not val in (".", "?") :

# framecode: replace spaces with underscore
#
                        tmp = val
                        if qs != starobj.sas.TOKENS["CHARACTERS"] :
                            tmp = re.sub( r"\s+", "_", row[i] )
                            if starobj.check_quote( tmp, verbose = self._verbose )[0] != starobj.sas.TOKENS["CHARACTERS"] :
                                raise Exception( "Invalid framecode value: >>%s<<" % (str( row[i] ),) )

                        val = "$%s" % (starobj.toascii( tmp ),)
                    if self._verbose : sys.stdout.write( "*** FRAMECODE (free table): |%s|\n" % (val,) )
                out.write( val )
                out.write( "\n" )

        rows.reset()
        if not rc : raise Exception( "Free table not printed!" )
        return rc

####################################################################################################
#
# column widths for pretty-printing the loops
#
    def _find_col_widths( self, table, tags, sfid, framecodes ) :
        if self._verbose :
            sys.stdout.write( "%s._find_col_widths( %s, %s )\n" % (self.__class__.__name__,table,str( sfid )) )
        assert isinstance( tags, collections.Iterable )
        assert len( tags ) > 0

# can't just query for max(length(TAG)) because that doesn't factor in the quoting
#

        widths = {}
        for t in tags : widths[t] = 1

        colstr = '","'.join( t for t in tags )

# sfid tagname is always Sf_ID. ideally we'd query the dictionary for the name.
#
        sql = 'select "%s" from "%s" where "Sf_ID"=:sfid' % (colstr, table)
        rs = self._entry.query( sql = sql, params = { "sfid" : sfid }, newcursor = True )
        for row in rs :
            for i in range(len(row)) :
                (qs, val) = starobj.check_quote( row[i], verbose = self._verbose )

                if qs == starobj.sas.TOKENS["SEMISTART"] : continue   # doesn't count
                if (framecodes is not None) and (tags[i] in framecodes) :
                    if not val in (".", "?") : val = "$" + val

                if len( val ) > widths[tags[i]] :
                    widths[tags[i]] = len( val )

        rs.cursor.close()
        if self._verbose :
            pprint.pprint( widths )

        if len( widths ) < 1 : raise Exception( "Can't find column widths for %s!", (table,) )
        return widths

####################################################################################################
    # this takes forever to nicely indent and align everything
    #
    def unparse_loop_table( self, out, sfid, name ) :
        if self._verbose :
            sys.stdout.write( "%s.unparse_loop_table(%s,%s)\n" % (self.__class__.__name__,sfid,name,) )

# framecodes
        framecodes = []
        for i in self._dict.iter_tags( tables = (name,), which = ("sfpointer",) ) :
            framecodes.append( i[1] )

        rows = starobj.DataTable( verbose = self._verbose )
        rows.db = self._entry._db
        rows.dictionary = self._dict
        rows.sfid = sfid
        rows.table = name

        firstrow = True
        widths = None
        for row in rows :

            if self._verbose :
                sys.stdout.write( "--------------- row ----------\n" )
                pprint.pprint( row )

            if firstrow :
                widths = self._find_col_widths( table = name, tags = rows.columns, sfid = sfid, framecodes = framecodes )

                out.write( "\n" )
                for j in range( self._indent * self._tabwidth ) : out.write( " " )
                out.write( "loop_\n" )
                self._indent += 1
                for tag in rows.columns :
                    for j in range( self._indent * self._tabwidth ) : out.write( " " )
                    out.write( "_%s.%s\n" % (name, tag) )
                out.write( "\n" )
                firstrow = False

# Ugh
# if 1st value is not in semicolons, indent the row
#
            (qs, val) = starobj.check_quote( row[0], verbose = self._verbose )
            if qs != starobj.sas.TOKENS["SEMISTART"] :
                for j in range( self._indent * self._tabwidth ) : out.write( " " )

# now foreach value
#
            for i in range( len( row ) ) :
                if i > 0 :
                    (qs, val) = starobj.check_quote( row[i], verbose = self._verbose )

# if it's in semicolons, write it out between newlines
#
                if qs == starobj.sas.TOKENS["SEMISTART"] :
                    if self._verbose :
                        sys.stdout.write( ";;; writing |%s|\n" % (val,) )
#                    out.write( "\n" )
                    out.write( val )
#                    out.write( "\n" )

# then align the next one w/ previous row (lengths[i] is 1 for semicolon-quoted values)
#
                    offset = 0
                    for j in range ( i + 1 ) :
                        if self._verbose :
                            sys.stdout.write( "> Offset = %d, i = %d, j = %d\n" % (offset,i,j) )
                        if j < len( widths ) :
                            offset += widths[rows.columns[j]]
                            offset += self._tabwidth
                    if self._verbose :
                            sys.stdout.write( ">> Offset = %d\n" % (offset,) )
                    for j in range( self._indent * self._tabwidth ) : out.write( " " )
                    for j in range( offset ) : out.write( " " )

# otherwise see if it's a framecode
#
                else :
                    if self._verbose :
                        sys.stdout.write( "len(val)=%d, width[i]=%d, range:" % (len(val), widths[rows.columns[i]]) )
                        pprint.pprint( range( len( val ), widths[rows.columns[i]] ) )

# can't have spaces in framecodes
#
                    if rows.columns[i] in framecodes :
                        if self._verbose :
                            sys.stdout.write( "***** FRAMECODE %s\n" % (val) )
                        if not val in (".", "?") :
                            tmp = val
                            if qs != starobj.sas.TOKENS["CHARACTERS"] :
                                tmp = re.sub( r"\s+", "_", row[i] )
                                (qs, val) = starobj.check_quote( tmp, verbose = self._verbose )
                                if qs != starobj.sas.TOKENS["CHARACTERS"] :
                                    raise Exception( "Invalid framecode value: >>%s<<" % (str( row[i] ),) )

# quote() above should've asciified it
#
                            val = "$%s" % (tmp,)
                        if self._verbose :
                            sys.stdout.write( "*** FRAMECODE: |%s|\n" % (val,) )

                    if self._verbose :
                        sys.stdout.write( "** writing |%s|\n" % (val,) )
                    out.write( val )
                    if i < (len( row ) - 1 ) :
                        for j in range( widths[rows.columns[i]] - len( val ) ) :
                            out.write( " " )
                        for j in range( self._tabwidth ) : out.write( " " )
            out.write( "\n" )

        if self._verbose :
            sys.stdout.write( "<<<<<<<<<<< out of the loop %s, first=%s\n" % (name,(firstrow and "true" or "false")) )
        if not firstrow :
            self._indent -= 1
            for j in range( self._indent * self._tabwidth ) : out.write( " " )
            out.write( "stop_\n" )

        return




####################################################################################################
#
#
if __name__ == "__main__" :

    import ConfigParser

    cp = ConfigParser.SafeConfigParser()
    cp.read( sys.argv[1] )

    wrp = starobj.DbWrapper( config = cp, verbose = False ) # True )
    wrp.connect()

    sd = starobj.StarDictionary( wrp, verbose = True )
    sd.printable_tags_only = True # False
    sd.public_tags_only = False # True

    errors = []

    p = starobj.StarParser.parse_file( db = wrp, dictionary = sd, filename = sys.argv[2],
        errlist = errors, verbose = False )
    if len( errors ) > 0 :
        sys.stderr.write( "--------------- parse errors -------------------" )
        for e in errors :
            sys.stderr.write( e )
            sys.stderr.write( "\n" )

    del errors[:]

    star = starobj.NMRSTAREntry( wrp, verbose = False ) # True )
    sys.stdout.write( "*****************************************************\n" )
    rs = star.query( sql = "select * from entry_saveframes order by sfid" )
    for row in rs :
        pprint.pprint( row )
    sys.stdout.write( "*****************************************************\n" )

    with open( "StarWriter.out.str", "w" ) as out :
        u = StarWriter.pretty_print( entry = star, dictionary = sd, out = out, errlist = errors,
            verbose = True )

    if len( errors ) > 0 :
        sys.stderr.write( "--------------- unparse errors -------------------" )
        for e in errors :
            sys.stderr.write( e )
            sys.stderr.write( "\n" )

#
# eof
