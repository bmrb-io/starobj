#!/usr/bin/python -u
#
#

"""error message class"""

from __future__ import absolute_import


#
#
#
class Error( object ) :

    LONG_MESSAGE = 60

    Severity = ("CRIT", "ERR", "WARN", "INFO")
    CRIT = 0
    ERR  = 1
    WARN = 2
    INFO = 3

    svr = CRIT
    line = -1
    src = ""
    tag = ""
    val = ""
    msg = ""

    def __init__( self, svr, line, src, msg ) :
        self.svr = svr
        self.line = line
        self.src = src
        self.msg = msg

    def __str__( self ) :
        if len( str( self.msg ) ) > self.LONG_MESSAGE :
            self.msg = str( self.msg ).strip()[:self.LONG_MESSAGE]
        return ("%4s:%5s:%5d:%s:%s:%s" % (self.Severity[self.svr], self.src, self.line, 
            self.tag, self.val, self.msg))

#
#
#
if __name__ == "__main__" :
    print "Nothing to see here"
#
#
