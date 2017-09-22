#!/usr/bin/python -u
#
# NOTE: if you want "installable" egg, edit the sources and comment out every
#   sys.path.append( ... __file__ ...
# before building
#
import setuptools
setuptools.setup( name = "starobj", version = "1.0", packages = setuptools.find_packages(), py_modules = ["starobj"] )
