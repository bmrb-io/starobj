#!/usr/bin/python -u
#
# wrapper for entry access methods, part 2
#  this is the part that does the dirty work
#



import sys
import os
import collections
import pprint


# self
#
_UP = os.path.join( os.path.split( __file__ )[0], ".." )
sys.path.append( os.path.realpath( _UP ) )
import starobj

#
# Iterator for entry data. It returns only rows with "real data".
#
# Comes with a pretty ugly init and an unpleasant "has real data" check.
# And a ton of sorting rules becasue we don't use proper DB types.
#
class DataTable( starobj.BaseClass ) :

    #
    #
    def __init__( self, *args, **kwargs ) :
        super( self.__class__, self ).__init__( *args, **kwargs )
        self._db = None
        self._dict = None
        self._sfid = None
        self._table = None
        self._tags = None
        self._data_tags = None
        self._print_tags = None
        self._default_values = None
        self._rs = None
        self._print_sfids = False

    #
    #
    def __del__( self ) :
        self._stop_iteration()

    #
    #
    @property
    def db( self ) :
        """DB wrapper"""
        return self._db
    @db.setter
    def db( self, db ) :
        assert isinstance( db, starobj.DbWrapper )
        self._db = db

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

    #
    #
    @property
    def sfid( self ) :
        """Saveframe ID"""
        return self._sfid
    @sfid.setter
    def sfid( self, sfid ) :
        self._sfid = sfid

    #
    #
    @property
    def table( self ) :
        """Table (tag category)"""
        return self._table
    @table.setter
    def table( self, table ) :
        self._table = table

    # if set, limit the columns to these only
    #
    @property
    def columns( self ) :
        """List of tags in the result set"""
        return self._print_tags

    # if set, limit the columns to these only
    #
    @property
    def tags( self ) :
        """Tag list"""
        return self._tags
    @tags.setter
    def tags( self, tags ) :
        assert isinstance( tags, collections.abc.Iterable )
        self._tags = list( tags )

    #
    # iterable
    def __iter__( self ) :
        return self

    #
    #
    def __next__( self ) :
        return next(self)

    #
    #
    def reset( self ) :
        self._stop_iteration()
    def close( self ) :
        self._stop_iteration()

####################################################################################################
    #
    #
    def _stop_iteration( self ) :
        if self._verbose :
            sys.stdout.write( "%s._stop_iteration()\n" % (self.__class__.__name__,) )
        self._sfid = None
        self._table = None
        if self._tags is not None : del self._tags[:]
        if self._print_tags is not None : del self._print_tags[:]
        if self._data_tags is not None : del self._data_tags[:]
        if self._default_values is not None : self._default_values.clear()

#FIXME:        self._rs = None

    #
    #
    def _start_iteration( self ) :
        if self._verbose :
            sys.stdout.write( "%s._start_iteration()\n" % (self.__class__.__name__,) )
        assert isinstance( self._db, starobj.DbWrapper )
        assert isinstance( self._dict, starobj.StarDictionary )
        assert self._table is not None
        assert self._sfid is not None
        int( self._sfid )

# print all or select tags?
#
        collect_tags = False
        if (self._tags is None) or (len( self._tags ) < 1) :
            collect_tags = True

        if self._verbose :
            sys.stdout.write( "=> collect tags: %s\n" % ((collect_tags and "yes" or "no"),) )

        if self._print_tags is None : self._print_tags = []
        else : del self._print_tags[:]

        if self._default_values is None : self._default_values = {}
        else : self._default_values.clear()

        if self._data_tags is None : self._data_tags = []
        else : del self._data_tags[:]

# fetch tags from the dictionary, save printable ones in _data_tags. if _tags is not empty, save
# only those in _tags (this will also skip any invalid ones in _tags)
#

        qry = "select a.tagfield,a.defaultvalue,a.lclsfidflg,a.sfidflg,a.sfnameflg,a.sfcategoryflg," \
            + "a.entryidflg,a.rowindexflg,a.sfpointerflg,p.printflag,a.internalflag,a.dictionaryseq " \
            + "from adit_item_tbl a join validator_printflags p on p.dictionaryseq=a.dictionaryseq " \
            + "where a.tagcategory=:tbl order by a.dictionaryseq"

        rs = self._dict.query( sql = qry, params = { "tbl" : self._table } )
        for row in rs :

# special cases
#
            if self._table == "Entry_interview" :
                if row[0] in ( "BMRB_deposition", "PDB_deposition", "View_mode", "Use_previous_BMRB_entry",
                               "Previous_BMRB_entry_used", "Previous_BMRB_entry_owner") :
                    continue
            if (self._table == "Deposited_data_files") and (row[0] in ("Precheck_flag", "Validate_flag")) :
                    continue
            if self._table == "Entry" :
                if row[0] in ( "BMRB_annotator", "BMRB_internal_directory_name", "Author_approval_type",
                               "Assigned_PDB_ID", "Assigned_PDB_deposition_code", "Assigned_restart_ID") :
                    continue
            if (self._table == "Upload_data") and (row[0] == "Data_file_immutable_flag") :
                    continue

# row index?
#
# select tags
#
            if not collect_tags :
                if not row[0] in self._tags :
                    continue

# print sf ids? -- this is a separate flag, not useful for anything except debugging.
#
            if self._verbose :
                sys.stdout.write( "table: %s, tag: %s, row[9]: %s, printable_tags_only: %s, public_tags_only: %s\n" \
                % (self._table, row[0], row[9], (self._dict.printable_tags_only and "yes" or "no"),
                (self._dict.public_tags_only and "yes" or "no")) )

            if (row[0] == "Sf_ID") and not self._print_sfids :
                continue

# print flag is O, Y, or N. "N" + "printable_only" = don't print
#
            if ("n" == str( row[9] ).strip().lower()) and self._dict.printable_tags_only :
                continue

# exclude internal-only tags in public mode
#
            if self._dict.public_tags_only and ("y" == str( row[10] ).strip().lower() ) :
                continue

# save this one
#
            self._print_tags.append( row[0] )

# "real data" items
#
# if print flag is yes, print regardless
#
            if "y" == str( row[9] ).strip().lower() :
                self._data_tags.append( row[0] )
            else :

# local id or sf id or sf name or sf category or entry id: unreal data
#
                if ("y" == str( row[2] ).strip().lower()) \
                or ("y" == str( row[3] ).strip().lower()) \
                or ("y" == str( row[4] ).strip().lower()) \
                or ("y" == str( row[5] ).strip().lower()) \
                or ("y" == str( row[6] ).strip().lower()) :
# is rowindex "real data"? -- it may be primary key?
                    continue

# defaults
            if row[1] is not None : self._default_values[row[0]] = row[1]

# if we're still here:
#
            if self._verbose :
                sys.stdout.write( "Still here, appending %s to data_tags\n" % (row[0],) )
            self._data_tags.append( row[0] )

# out of while loop
#
# nothing to return
#
        if len( self._print_tags ) < 1 :
            self._stop_iteration()
            raise StopIteration

# build query
# hardcoded "Sf_ID"
#
        colstr = '","'.join( c for c in self._print_tags )
        qry = 'select "%s" from "%s" where "Sf_ID"=:sfid' % (colstr,self._table,)

# sorting: need stable row ordering for diffs.
# the defalt is sort by row index, or by primary key, or by all columns in dictionary order.
#
# special cases can be removed after we fix all data types in the db. i.e. never.
#
# this orders by columns not in select so may not work in e.g. older postgres.
#
# spec. cases

        sort = None

        if self._table == "PDBX_poly_seq_scheme" :
            sort = 'cast("Entity_assembly_ID" as integer),cast("Entity_ID" as integer),cast("Comp_index_ID" as integer)'

        if self._table == "PDBX_nonpoly_scheme" :
            sort = 'cast("Entity_ID" as integer),cast("Comp_index_ID" as integer)'

        if self._table == "Entity_poly_seq" :
            sort = 'cast("Comp_index_ID" as integer)'

        if self._table == "Entity_comp_index_alt" :
            sort = 'cast("Entity_comp_index_ID" as integer)'

        if self._table == "Release" :
            sort = 'cast("Release_number" as integer) desc'

        if self._table == "Entity_atom_list" :
            sort = 'cast("ID" as integer)'

        if self._table == "Chem_comp_atom" :
            sort = 'cast("PDBX_ordinal" as integer),"Type_symbol","Atom_ID"' # ordinal should override the rest if not null

        if self._table == "Chem_comp_bond" :
            sort = 'cast("ID" as integer)'

        if self._table == "Ambiguous_atom_chem_shift" :
            sort = 'cast("Ambiguous_shift_set_ID" as integer),cast("Atom_chem_shift_ID" as integer)'

        if self._table in ("Chem_shift_experiment", "Coupling_constant_experiment", "RDC_experiment",
                            "Heteronucl_NOE_experiment", "Heteronucl_T1_experiment", "Heteronucl_T1rho_experiment",
                            "Heteronucl_T2_experiment", "Order_parameter_experiment", "Binding_experiment") :
            sort = 'cast("Experiment_ID" as integer)'

        if self._table == "Experiment_file" :
            sort = 'cast("Experiment_ID" as integer),"Name"'

        if self._table in ("Chem_shift_software", "Spectral_peak_software", "Coupling_constant_software", "RDC_software",
                            "Heteronucl_NOE_software", "Heteronucl_T1_software", "Heteronucl_T1rho_software",
                            "Heteronucl_T2_software" ) :
            sort = 'cast("Software_ID" as integer)'

        if self._table == "Audit" :
            sort = 'cast("Revision_ID" as integer)'

        if self._table == "Spectral_dim" :
            sort = 'cast("ID" as integer)'

        if self._table == "Peak" :
            sort = 'cast("ID" as integer)'

        if self._table == "Peak_general_char" :
            sort = 'cast("Peak_ID" as integer),"Measurement_method",cast("Intensity_val" as float)'

        if self._table == "Peak_char" :
            if self._verbose : print(("Table is Peak_char:", self._table))
            sort = 'cast("Peak_ID" as integer),cast("Spectral_dim_ID" as integer)'

        if self._table == "Assigned_peak_chem_shift" :
            sort = """cast("Peak_ID" as integer),cast("Spectral_dim_ID" as integer),cast("Peak_contribution_ID" as integer),cast("Set_ID" as integer),
                cast("Magnetization_linkage_ID" as integer),cast("Assembly_atom_ID" as integer),cast("Assigned_chem_shift_list_ID" as integer),
                cast("Atom_chem_shift_ID" as integer),cast("Entity_assembly_ID" as integer),cast("Entity_ID" as integer),cast("Comp_index_ID" as integer),
                "Atom_ID" """

        if self._table == "Spectral_transition_general_char" :
            sort = 'cast("Spectral_transition_ID" as integer),"Measurement_method",cast("Intensity_val" as float)'

        if self._table == "Spectral_transition_char" :
            sort = 'cast("Spectral_transition_ID" as integer),cast("Spectral_dim_ID" as integer)'

        if self._table == "Constraint_file" :
            sort = 'cast("ID" as integer)'

        if self._table == "Binding_partners" :
            sort = 'cast("Binding_result_ID" as integer)'

        if sort is None :
            cols = self._dict.get_sort_key( self._table )
            if cols is not None :
                sort = " order by "
                for c in cols :
                    if c[1] == "int" : sort += 'cast("%s" as integer),' % (c[0],)
                    elif c[1] == "float" : sort += 'cast("%s" as float),' % (c[0],)
                    else : sort += '"%s",' % (c[0],)
                sort = sort[:-1]
        else :
            sort = ' order by ' + sort

# None should never happen but just in case...
#
        if sort is not None :
            qry += sort

        if self._verbose :
            sys.stdout.write( qry + "\n" )

        self._rs = self._db.query( connection = starobj.StarWriter.ENTRY_CONNECTION, sql = qry,
                params = { "sfid" : self._sfid } )

# at this point next() can fetch the next row
#
        return

    #
    # return only "real data" columns
    #
    def __next__( self ) :
        if self._verbose :
            sys.stdout.write( "%s._next()\n" % (self.__class__.__name__,) )
        if self._rs is None :
            self._start_iteration()

        row = next(self._rs)
        if self._verbose :
            sys.stdout.write( "___ data table: next row\n" )
            pprint.pprint( row )
        return row

#        raise StopIteration


#
#
#
if __name__ == "__main__" :
    print("Nothing to see here")
#
