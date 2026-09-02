
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
* SAM and MetaCat queries have different syntax; some amount of translation is required.
* SAM queries can blend project information, location information, and other metadata queries; this could be implemented with a MetaCat plugin to include DataDispatcher project info, and one for Rucio location info, or by 
  * There is already a MetaCat Rucio-replicas plugin to get rse info from Rucio, which may include paths as well as rses in the rse data
  * Could do one for DataDispatcher that  would take a project number and get you the file status info for the files in the project as metadatas

* You can mimic SAM project behavior by creating DataDispatcher projects with a "project_name" attribute -- you can findProject them with project list with an attribute match, yeilding a project id... 
* Rucio Rules vs SAM locations -- If we just tell Rucio a file exists, but do not add any sort of rule , Rucio will just delete it because no rules want it.  So we need to have a dataset for "all current SAM file locations at RSE x" and add files to it  when we add the locations to SAM, and remove files from it when we remove the SAM locations, so that Rucio will clean up.   Note that folks using SAM will go in and directly remove the file behind Rucios back and then remove the location, so this will hopefully let Rucio figure it out (?) 

## Extra notes on project-based queries

So a SAM query that uses project_name, etc. and/or checks for project data (completion_status, etc.) needs to be converted to a MetaCat query that uses a data_dispatchr filter; but the filter needs *input*, so we should rely on a dataset existing named default:snapshot_for_project_<project_name> as the input query to the filter, which will add the project info for each file.   To make this a continuing feature ,when we start a project under samwebish, we need to not only hand the project files to data_dispatcher, and a project_name= metadata attribute, but we need to create a default:snapshot_for_project_<project_name> datset in metacat  to go with it, with the same files.   Then when we later convert the query for the project, the metacat dataset will exist.   

I sort of wonder whether we should add that behavior to the base data_dispatcher client, where it always does that, or just have it be a property of samwebish...
