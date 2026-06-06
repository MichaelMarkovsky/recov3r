from dataclasses import dataclass


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
    mft_records: list[MFTRecord] | None = None

@dataclass
class MFTRecord:
    record_number: int
    filename: str | None
    flags: int
