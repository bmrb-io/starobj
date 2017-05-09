# starobj

Table-based storage for BMRB's NMR-STAR 3.x.

The tables are relational, `sqlite3` and `psycopg2` are supported.

The code is pure python, main componenets are

* database loader (`parser.py`),
* pretty printer (`unparser.py`),
* NMR-STAR data access classes (`entry.py` and startable.py`)
* NMR-STAR dictionary wrapper (`stardict.py`)
* and a poor man's DB abstraction layer (`db.py`)

## NMR-STAR relational mappings

The format of NMR-STAR 3 (and PDB's mmCIF) tag names is `_**table**.**column**`, that is: underscore -
table name (aka tag category) - dot - column name (aka tag name), maikng the mapping from NMR-STAR/mmCIF
to relational tables straightforward. The gotchas:

* Because some of the names are SQL reserved words, this library double-quotes them all and makes 
them case-sensitive as a side-effect. This is important to remember when writing your own SQL statements
to access the data.

* NMR-STAR uses "saveframe" block and has several "special" tags and rules to maintain saveframe information
in the relational tables:

  * `Sf_framecode` tags contain the name of the parent saveframe (saveframe names must be unique within
    the entry),
  * `Sf_category` tags contain the category, or type, of the parent saveframe,
  * "local ID" tags, typically named `ID`, contain the number of the saveframe of a given type within
    the entry. The `(Sf_category, ID)` tuple must be unique within the entry.
  * `Entry_ID` tags contain entry ID. `(Entry_ID, Sf_category, ID)` is the unique key for the saveframe. 
    Every data table in the saveframe has a corresponding foreign key tuple that links it to its parent 
    saveframe.
  * Last but not least, there is a convenience key: `Sf_ID` that is autoincremented insteger, unique per
    saveframe accross the entire database with multiple entries. It is regenerated on database reload,
    `Sf_ID` tags never appear in the NMR-STAR files.
