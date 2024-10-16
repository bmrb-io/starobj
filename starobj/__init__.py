#!/usr/bin/python -u
#
#

# suggested by one of the PEPs, probably doesn't do anything
#
if __name__ == "__main__" and __package__ == None :
    __package__ = "starobj"

import re
import sys
import unicodedata

from ._baseclass import BaseClass
from .db import DbWrapper
from .entry import NMRSTAREntry
from .error import Error
from .parser import StarParser
from .stardict import StarDictionary
from .startable import DataTable
from .unparser import StarWriter

SAS_PATH = "/projects/BMRB/software/SAS3"
sys.path.append( SAS_PATH )

import sas

# wrap long values in semicolons
#
LONG_VALUE = 80

# quote with ' by default
#
DEFAULT_QUOTE = sas.TOKENS["SINGLESTART"]

# values are supposed to be US-ASCII but we'll use ISO
#
ENCODING = "iso8859-15"

#
# do not use: insert a row then fetch the last one instead.
# (let sequence/autoincrement handle concurrent transactions)
#
def next_sfid( curs, verbose = False ) :

    raise DeprecationWarning( "do not use" )
# can't assert the cursor b/c it could be psycopg2 or sqlite3
#
    sql = "select max(sfid) from entry_saveframes"
    curs.execute( sql )
    row = curs.fetchone()
    if row == None : return 1
    if row[0] == None : return 1
    if int( row[0] ) < 1 : return 1
    return (int( row[0] ) + 1)

# there's no "standard" way to retrieve last inserted auto-generated key.
# just don't use this fro multiple threads.
#
def last_sfid( curs, verbose = False ) :

    raise DeprecationWarning( "use NMRSTAREntry.last_sfid() instead" )
    sql = "select max(sfid) from entry_saveframes"
    curs.execute( sql )
    row = curs.fetchone()
    if row == None : return 0
    if row[0] == None : return 0
    if int( row[0] ) < 1 : return 0
    return int( row[0] )

#
# Quote string for STAR.
#
# TODO: this needs constants from sas and probably should be moved there. OTOH this is only used for
# printing and sas doesn't do that. OTGH quoting rules should match sas parsing rules & it's easier
# if they're kept together...
# TODO: this can't handle STAR-2012's triple-quotes.
#
#
def isascii( s ) :
    if s is None : return False
    try :
        str( s ).encode( "ascii" )
        return True
    except (UnicodeDecodeError, UnicodeEncodeError) :
        return False

def toascii( s ) :
    if s is None : return None
    v = str( s )
    if isascii( v ) : return v
    if sys.version_info[0] == 3 :
        return unicodedata.normalize( "NFKD", v ).encode('ascii','ignore').decode()
    else :
        return unicodedata.normalize( "NFKD", v.decode( "utf-8" ) ).encode( "ascii", "ignore" )

# this does rstrip() because we probably never want to keep trailing whitespace
#
def sanitize( s ) :
    if s is None : return None
    string = str( s ).strip()
    if string == "" : return None
    return toascii( str( s ).rstrip() )

#
#
#
def check_quote( value, verbose = False ) :

    """returns pair (quoting style, quoted sanitized value)"""

    global LONG_VALUE
    global DEFAULT_QUOTE

#    value = toascii( value )
    string = sanitize( value )
    if string is None : return (sas.TOKENS["CHARACTERS"], ".")

# multi-line values
#  we probably always want to remove trailing whitespace
#    but not leading whitespace
#
    if "\n" in string :
        if verbose : sys.stdout.write( "Has newline\n" )

# TODO: this is where we look for \n; and return triple-quote instead
#
        if string.startswith( "\n" ) : buf = "\n;"
        else : buf = "\n;\n"
#        if value.endswith( "\n" ) : buf += value + ";\n"
#        else : buf += value + "\n;\n"
#        buf += value.rstrip() + "\n;\n"
        return (sas.TOKENS["SEMISTART"], buf + string + "\n;\n")

# otherwise return them sanitized
#
    string = string.strip()
    if len( string ) > LONG_VALUE :
        if verbose : sys.stdout.write( "Too long\n" )
        return (sas.TOKENS["SEMISTART"], "\n;\n" + string + "\n;\n")

# quote's a delimietr only at start/end of token
#
    dq1 = re.compile( "(^\")|(\s+\")" )
    dq2 = re.compile( "\"\s+" )
    has_dq = False
    m = dq1.search( string )
    if m : has_dq = True
    else :
        m = dq2.search( string )
        if m : has_dq = True

    if verbose and has_dq : sys.stdout.write( "Has double quote\n" )

    sq1 = re.compile( "(^')|(\s+')" )
    sq2 = re.compile( "'\s+" )
    has_sq = False
    m = sq1.search( string )
    if m : has_sq = True
    else :
        m = sq2.search( string )
        if m : has_sq = True

    if verbose and has_sq : sys.stdout.write( "Has single quote\n" )

    if has_sq and has_dq :
        return (sas.TOKENS["SEMISTART"], "\n;\n" + string.rstrip() + "\n;\n")

    if has_sq : return (sas.TOKENS["DOUBLESTART"], '"' + string + '"')
    if has_dq : return (sas.TOKENS["SINGLESTART"], "'" + string + "'")

    m = re.search( r"\s+", string )
    if m :
        if verbose : sys.stdout.write( "Has space\n" )

# in case some badly written lexer finds e.g. 'Peter O'Toole' confusing
#  give 'em "Peter O'Toole"
#
        if "'" in string : return (sas.TOKENS["DOUBLESTART"], '"' + string + '"')
        if '"' in string : return (sas.TOKENS["SINGLESTART"], "'" + string + "'")
        if verbose : sys.stdout.write( "Has space, no quotes\n" )
        return (DEFAULT_QUOTE, DEFAULT_QUOTE + string + DEFAULT_QUOTE)

#

    for i in sas.KEYWORDS :
        m = i.search( string )
        if m :
            if verbose : sys.stdout.write( "Has %s\n" % (i.pattern,) )
            return (DEFAULT_QUOTE, DEFAULT_QUOTE + string + DEFAULT_QUOTE)

    return (sas.TOKENS["CHARACTERS"], string)

###########################################

#
#
__all__ = ["LONG_VALUE", "ENCODING",
            "sas",
            "isascii", "toascii", "sanitize", "check_quote",
            "BaseClass", "Error", "DbWrapper",
            "StarDictionary", "NMRSTAREntry",
            "DataTable", "StarWriter", "StarParser"
        ]



#
