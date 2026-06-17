from dataclasses import dataclass,field
from datetime import datetime, timedelta

@dataclass
class Partition:
    index: int # number of partition in the partition table in MBR
    hex: str # represendation of the partition in hex
    bootable: bool 
    type_name: int # file system type 
    offset: int # location of the partition in the disk
    partition_size: int

    filesystem: object | None = None # object for more partition information

@dataclass
class NTFSInfo:
    bytes_per_sector: int 
    sectors_per_cluster: int
    cluster_size: int

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
    attr_list: AttributeListAttribute | None = None
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



@dataclass
class AttributeListAttribute:
    resident: bool

    al_type:int
    al_record_len:int
    al_name_len:int
    al_offset_name:int
    al_starting_vcn:int
    al_base_file_ref_attr:int
    al_attr_id:int
    al_name:str




@dataclass
class NoneResidentHeader:
    resident: bool

    starting_vcn: int
    last_vcn: int
    offset_to_dataruns: int
    compression_unit_size:int
    padding:int
    real_size_attribute: int
    allocated_size_attribute:int
    initialized_data_size:int
    attribute_name:int
    data_runs:int # (LCN,run-len-size)



# This map is for suggested filesystem from partition table
TYPE_MAP = {
    0x00: "Empty",
    0x01: "FAT12",
    0x04: "FAT16",
    0x05: "Extended",
    0x06: "FAT16",
    0x07: "NTFS/exFAT",
    0x0B: "FAT32",
    0x0C: "FAT32 (LBA)",
    0x0E: "FAT16 (LBA)",
    0x0F: "Extended (LBA)",
    0x82: "Linux swap",
    0x83: "Linux filesystem",
    0x8E: "Linux LVM",
}

FLAGS_MFT = {
    0: "Deleted File",
    1: "Active File",
    2: "Deleted Directory",
    3: "Active Directory",
    4: "Non-standard (4)",
    5: None,
    6: None,
    7: None,
    8: "Non-standard (8)",
}

FILE_ATTRIBUTES = {
    0x1: "READ_ONLY",
    0x2: "HIDDEN",
    0x4: "SYSTEM",
    0x20: "ARCHIVE",
    0x100: "TEMPORARY",
    0x200: "SPARSE_FILE",
    0x400: "REPARSE_POINT",
    0x800: "COMPRESSED",
    0x1000: "OFFLINE",
    0x2000: "NOT_CONTENT_INDEXED",
    0x4000: "ENCRYPTED",
}
