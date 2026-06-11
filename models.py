from dataclasses import dataclass,field
from datetime import datetime, timedelta

@dataclass
class Partition:
    index: int # number of partition in the partition table in MBR
    hex: str # represendation of the partition in hex
    bootable: bool 
    type_name: str # file system type , for printing
    offset: int # location of the partition in the disk
    filesystem: object | None = None # object for more partition information

@dataclass
class NTFSInfo:
    bytes_per_sector: int 
    sectors_per_cluster: int
    cluster_size: int
    partition_size: int
    mft_cluster: int # in how many clusters the $MFT is in, from the partition
    mft_offset: int # how many bytes the $MFT is from the partition
    mft_location: int # location of partition from sector 0
    mft_records: list[MFTRecord] = field(default_factory=list)

@dataclass
class MFTRecord:
    record_number: int
    record_location: int

    # Record header
    magic_num: str| None = None
    flags: int | None = None# 0 = deleted file , 1 = active file , 2 = deleted directory , 3 active directory , 4/8 = none standard

    # Attributes
    standard_info: StandardInformation | None = None
    file_name: FileNameAttribute | None = None
    data: DataAttribute | None = None

@dataclass
class StandardInformation:
    # Header
    resident: bool

    # Metadata (Resident)
    created_time: datetime
    modified_time: datetime
    mft_modified_time: datetime
    accessed_time: datetime

    dos_file_permissions: int
    ver_num: int
    class_id: int


@dataclass
class FileNameAttribute:
    #Header
    resident: bool
    
    # Metadata (Resident)
    parent_record: int

    created_time: datetime
    modified_time: datetime
    mft_modified_time: datetime
    accessed_time: datetime
    
    allocated_size_file: int
    real_size_file: int
    flags_filename: int
    filename_len: int
    filename: str



@dataclass
class DataAttribute:
    resident: bool

    # resident
    data: bytes | None = None

    # non-resident
    data_runs: list | None = None
    allocated_size: int | None = None
    real_size: int | None = None
