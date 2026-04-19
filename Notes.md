
# samwebish -- sam-web like API for Rucio/MetaCat/DataDispatcher

## Overview

To facilitate migrating experiments with embedded software bases from SAM to
the RMD suite (Rucio+MetaCat+DataDispatcher), this document proposes a thin 
API that provides the SAM-web api for the newer toolsets.   Functionality not 
provided by SAM would then be available by directly accessing Rucio and/or MetaCat.

## Areas of focus

While the behavior of the RMD suite is generally a superset of the SAM packages,
there are areas where differing semantics need to be accounted for:

* SAM does not use namespaces in naming, so suitable mapping from SAM names to metacat namespace+name and Rucio scope+name needs to be defined, possibly configurably
* SAM "dataset definitions" can be mapped to "saved queries" in MetaCat
* SAM "snapshots" can be mapped to MetaCat "datasets", possibly with a naming convention like
  sam_snapshot:snap_N for snapshot id N in SAM
* SAM projects can be mapped to Data Dispatcher projects, with the SAM project name stored in the project metadata, as perhaps "sam.project_name":"xyz"
* SAM file metadata can generally be stored in Metacat, with many of the SAM builtin fields (run numbers, etc.) moved to the metadata dictionary in a category named SAM, and the user defined metadata fields left as is.
* Adding general SAM file locations to Rucio would require an RSE that was not configured as "deterministic"
* SAM "node" info in locations ("enstore:", "dcache:", etc.)  could be RSE's in Rucio, either directly or through a mapping
* Files declared to Rucio via SAM would require automatic addition of suitable retention/replication rules.
* SAM and MetaCat queries have subtly different syntax; some amount of translation is required.
* SAM queries can blend project information and other metadata queries; this could possilby be implemented with a MetaCat plugin to include DataDispatcher project info, or by teaching the tranlation layer (above) to convert project related query info into file_id in (id1, id2, id3...) after querying DataDispatcher to get the file_id list.




