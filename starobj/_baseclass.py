#!/usr/bin/python -u
#
#

from __future__ import absolute_import
#import os
import sys

class BaseClass( object ) :

    #
    #
    def __init__( self, verbose = False ) :

        self._verbose = bool( verbose )
    #
    #
    @property
    def verbose( self ) :
        """Debugging flag"""
        return bool( self._verbose )
    @verbose.setter
    def verbose( self, flag ) :
        self._verbose = bool( flag )
#
#
if __name__ == "__main__" :

    sys.stdout.write( "Move along\n" )

#
