#!/usr/bin/python -u
#
#

from __future__ import absolute_import

# suggested by one of the PEPs, probably doesn't do anything
#
if __name__ == "__main__" and __package__ == None :
    __package__ = "starobj"

import sys
PY3 = (sys.version_info[0] == 3)
if PY3 : raise NotImplementedError( "python 3 no use" )

import unicodedata
import re

SAS_PATH = "/share/dmaziuk/projects/sas/SAS/python/"
#SAS_PATH = "/bmrb/lib/python27"
sys.path.append( SAS_PATH )
import sas

from ._baseclass import BaseClass

from .error import Error
from .db import DbWrapper
from .stardict import StarDictionary
from .parser import StarParser
from .unparser import StarWriter
from .startable import DataTable
from .entry import NMRSTAREntry

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

def sanitize( s ) :
    if s is None : return None
    string = str( s ).strip()
    if string == "" : return None
    return toascii( string )

def check_quote( value, verbose = False ) :

    global LONG_VALUE
    global DEFAULT_QUOTE

    value = toascii( value )
    string = sanitize( value )
    if string is None : return (sas.TOKENS["CHARACTERS"], ".")

# return multi-line values as is
#
    if "\n" in string :
        if verbose : sys.stdout.write( "Has newline\n" )

# TODO: this is where we look for \n; and return triple-quote instead
#
        if value.startswith( "\n" ) : buf = ";"
        else : buf = ";\n"
        if value.endswith( "\n" ) : buf += value
        else : buf += value + "\n;\n"
        return (sas.TOKENS["SEMISTART"], buf)

# otherwise return them sanitized
#
    if len( string ) > LONG_VALUE :
        if verbose : sys.stdout.write( "Too long\n" )
        return (sas.TOKENS["SEMISTART"], "\n;\n" + string + "\n;\n")

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
        return (sas.TOKENS["SEMISTART"], "\n;\n" + string + "\n;\n")

    if has_sq : return (sas.TOKENS["DOUBLESTART"], '"' + string + '"')
    if has_dq : return (sas.TOKENS["SINGLESTART"], "'" + string + "'")

    m = re.search( r"\s+", string )
    if m :
        if verbose : sys.stdout.write( "Has space\n" )

# technically not needed but most code out there can't handle them unquoted
#
        if "'" in string : return (sas.TOKENS["DOUBLESTART"], '"' + string + '"')
        if '"' in string : return (sas.TOKENS["SINGLESTART"], "'" + string + "'")
        if verbose : sys.stdout.write( "Has space, no quotes\n" )
        return (DEFAULT_QUOTE, DEFAULT_QUOTE + string + DEFAULT_QUOTE)

    for i in sas.KEYWORDS :
        m = i.search( string )
        if m :
            if verbose : sys.stdout.write( "Has %s\n" % (i.pattern,) )
            return (DEFAULT_QUOTE, DEFAULT_QUOTE + string + DEFAULT_QUOTE)

    return (sas.TOKENS["CHARACTERS"], string)

#
#
__all__ = ["PY3", "LONG_VALUE", "ENCODING",
            "sas",
            "isascii", "toascii", "sanitize", "check_quote",
            "BaseClass", "Error", "DbWrapper",
            "StarDictionary", "NMRSTAREntry",
            "DataTable", "StarWriter", "StarParser"
        ]



#
