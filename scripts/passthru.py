#!/usr/bin/python -u
#
#

"""parse/unparse"""

from __future__ import absolute_import

import sys
import os
import ConfigParser
import argparse

STAROBJ_DIR = os.path.abspath( os.path.join( os.path.split( __file__ )[0], ".." ) )
sys.path.append( STAROBJ_DIR )
import starobj
import scripts


#
#
def passthru( config, infile = None, outfile = None, public = False, alltags = False, types = False, verbose = False, time = False ) :

    with scripts.timer( label = "starobj", silent = (not time) ) :
        errors = []
        with scripts.timer( label = "init", silent = (not time) ) :
            wrp = starobj.DbWrapper( config = cp, verbose = verbose ) # True )
            wrp.connect()

            sd = starobj.StarDictionary( wrp, verbose = verbose )
            sd.printable_tags_only = (not alltags)
            sd.public_tags_only = public

        with scripts.timer( label = "parse", silent = (not time) ) :
            if infile is None :
                p = starobj.StarParser.parse( db = wrp, dictionary = sd, fp = sys.stdin, errlist = errors, types = types, verbose = verbose )
            else :
                p = starobj.StarParser.parse_file( db = wrp, dictionary = sd, filename = infile, errlist = errors, types = types, verbose = verbose )
            if len( errors ) > 0 :
                sys.stderr.write( "--------------- parse errors -------------------\n" )
                for e in errors :
                    sys.stderr.write( str( e ) )
                    sys.stderr.write( "\n" )

                del errors[:]

        if outfile is None : return
        with scripts.timer( label = "pretty-print", silent = (not time) ) :
            star = starobj.NMRSTAREntry( wrp, verbose = verbose )
            with open( outfile, "w" ) as out :
                u = starobj.StarWriter.pretty_print( entry = star, dictionary = sd, out = out, errlist = errors, verbose = verbose )

                if len( errors ) > 0 :
                    sys.stderr.write( "--------------- unparse errors -------------------\n" )
                    for e in errors :
                        sys.stderr.write( str( e ) )
                        sys.stderr.write( "\n" )

#
#
#
if __name__ == "__main__" :

    ap = argparse.ArgumentParser( description = "read and write NMR-STAR file" )
    ap.add_argument( "--time", help = "print out timings", dest = "time", action = "store_true",
        default = False )
    ap.add_argument( "-v", "--verbose", help = "print lots of messages to stdout", dest = "verbose",
        action = "store_true", default = False )

    ap.add_argument( "-c", "--config", help = "config file", dest = "conffile", required = True )
    ap.add_argument( "-i", "--infile", help = "input file (default: stdin)", dest = "infile" )
    ap.add_argument( "-o", "--outfile", help = "output file (default: stdout)", dest = "outfile" )

    ap.add_argument( "-p", "--public", help = "print 'release' version of the file", dest = "public",
        action = "store_true", default = False )
    ap.add_argument( "-a", "--all_tags", help = "print all NMR-STAR tags", dest = "all_tags",
        action = "store_true", default = False )
    ap.add_argument( "-t", "--types", help = "use proper data types (by default everything is text)", 
        dest = "types", action = "store_true", default = False )

    args = ap.parse_args()


    cp = ConfigParser.SafeConfigParser()
    cp.read( args.conffile )

    passthru( cp, infile = args.infile, outfile = args.outfile, public = args.public, alltags = args.all_tags, 
        types = args.types, verbose = args.verbose, time = args.time )



