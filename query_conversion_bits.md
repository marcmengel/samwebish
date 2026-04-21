
## Map to base metadata 

* create_date   created_timestamp
* create_user   creator
* checksum      checksums
* file_name     name
* file_size     size
* parents       parents
* user          creator (alias)
* update_user   updated_by
* update_date   updated_timestamp

## need to map to sam.xxx in metadata 

* appl_name
* application
* consumed_status
* data_stream
* data_tier
* end_time
* event_count
* family
* file_format
* file_partition
* file_type
* first_event
* group
* last_event
* physical_datastream_name
* run_number
* run_type
* snapshot_file_number
* snapshot_id
* snapshot_version
* start_time
* tape_label
* update_date
* update_user
* version

## dataset related -- needs translation(?)

* dataset_def_id
* dataset_def_name
* dataset_def_name_newest_snapshot
* def_snapshot

## unsupported? 

* isdescendantof:
* isancestorof:

## Rucio related

* full_path

## ddisp related ... 

( need to query ddisp for these and convert to file id list(?))

* consumer
* consumer_process_description
* consumer_process_id
* project_description
* project_id
* project_name
* snapshot_for_project_id
* snapshot_for_project_name
