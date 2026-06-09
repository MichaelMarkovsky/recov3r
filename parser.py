from tabulate import tabulate
from models import Partition,NTFSInfo
import struct 
from datetime import datetime, timedelta


def get_partitions(disk,block_size):
    # Open the file in binary read mode ('rb')
    # Read exactly 50 bytes from the beginning

    mbr = disk.read(512)

    #========== MBR (Master Boot Record) =============
    mbr_signature = (mbr[510:512]).hex()
   
    if mbr_signature != "55aa":
        raise ValueError("Invalid MBR signature")
 
   

    # Checking if avaliable partitions
    partition_table = (mbr[446:510])
    partitions = []
    ptable_rows = [] # A printable table for easier visualization
    ptable_headers = ["Number","Hex","Bootable","File System","Partition Begins At"]

    partition_index = 1
    for i in range(0,len(partition_table),16):
        partition = partition_table[i:i+16]
        bootable = False
        file_system = ""


        # Analizing the partition bytes:
        # - checking if the partition is bootable
        if partition[0:1].hex() == "00":
            bootable = False
        else:
            bootable = True

        # - checking for type of file system
        if partition[4:5].hex() == "07":
            file_system = "NTFS"

        # - calculating where the partition begins
        starting_lba = partition[8:11]
        starting_lba_rev = int.from_bytes(starting_lba, byteorder='little') # Reads in little endian
        partition_offset = hex(starting_lba_rev * block_size)


        partition_hex = " ".join(f"{b:02X}" for b in partition)

        # Check if partition is empty (all is =0)
        if not any(partition):
            ptable_rows.append([partition_index, "Empty"])
        else:
            partitions.append(Partition(partition_index,partition_hex,bootable,file_system,partition_offset))
            ptable_rows.append([partition_index,partition_hex,bootable,file_system,partition_offset])

        
        partition_index += 1

    ptable = (tabulate(ptable_rows, headers=ptable_headers, tablefmt="grid"))

    return partitions,ptable,mbr_signature







# This parses the start of a partition to get the start of the MFT
def parse_partition(partition,disk):
    partition_location = int(partition.offset,16) 

    disk.seek(partition_location)   # go to offset
    data = disk.read(512)      
    #print(data)

    bytes_per_sector = int.from_bytes(data[11:13], byteorder='little')
    sectors_per_cluster = int.from_bytes(data[13:14], byteorder='little')
    cluster_size = bytes_per_sector * sectors_per_cluster # bytes
    partition_size = int.from_bytes(data[0x28:0x30], byteorder='little') * bytes_per_sector

    # Finding MFT offset
    mft_cluster = int.from_bytes(data[0x30:0x38], "little")
    mft_offset = mft_cluster * cluster_size
    mft_location = hex(mft_offset + partition_location)

    
    

    return NTFSInfo(bytes_per_sector,sectors_per_cluster,cluster_size,partition_size,mft_cluster,mft_offset,mft_location)



def filesystem_info_print(p):
        # Filesystem information:
        print(f"Filesystem of Partition information: {p.index}")
        print(f"Bytes per sector: {p.filesystem.bytes_per_sector}")
        print(f"Sectors per cluster: {p.filesystem.sectors_per_cluster}")
        print(f"Cluster size: {p.filesystem.cluster_size}")
        megabytes = p.filesystem.partition_size / (1024 * 1024)
        print(f"Partition size: {megabytes:.2f} MB")

        print(f"$MFT starts in {p.filesystem.mft_cluster} clusters.")
        print(f"$MFT starts {p.filesystem.mft_offset} bytes after the start of the partition")
        print(f"$MFT Location: {p.filesystem.mft_location}")



def get_mft_records(partition,disk):
    mft_location = int(partition.filesystem.mft_location,16) 
    disk.seek(mft_location)

    record_index = 0

    while record_index<4:
        record_location = mft_location + 1024 * record_index
        print()
        print(f"Record number {record_index} location: {hex(record_location)}")

        disk.seek(record_location)
        data = disk.read(1024) # Read exactly one record     
        #print(data)
        record_parser(data,record_location)
        print()
        record_index+=1


def record_parser(record,record_location):
    def get_int(data,fro,to):
        return int.from_bytes(data[fro:to], "little")

    def get_bytes(data,fro,to):
        return data[fro:to]


    
    def get_filetime_str(data, start):
        ft = int.from_bytes(data[start:start+8], "little")

        if ft == 0:
            return "EMPTY / INVALID"

        dt = datetime(1601, 1, 1) + timedelta(microseconds=ft / 10)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Values of different types of attributes (offsets)
    record_attr = {
        "$STANDARD_INFORMATION": {
            "values": {
                "file_creation": (0x00,0x08), 
                "file_altered": (0x08,0x10), 
                "mft_changed":(0x10,0x18), 
                "file_read": (0x18,0x20),
                "file_permissions":(0x20,0x24)
            },
            # file permission flags
            "flags":{ 
                "read_only": 0x0001,
                "hidden": 0x0002,
                "system":0x0004,
                "archive":0x0020,
                "device":0x0040,
                "normal":0x0080,
                "tenporary":0x0100,
                "sparse_file":0x0200,
                "reparse_point":0x0400,
                "compressed":0x0800,
                "offline":0x1000,
                "not_content_indexed":0x2000,
                "enctypted":0x4000
            }
        },
        "$FILENAME":
        {
            "values":{
                "parent_dir": (0x00,0x08),
                "file_creation": (0x08,0x10),
                "file_altered": (0x10,0x18),
                "mft_changed":(0x18,0x20), 
                "file_read": (0x20,0x28),
                "allocated_size_file": (0x28,0x30),
                "real_size_file":(0x30,0x38),
                "flags":(0x38,0x3c),
                "filename_len":(0x40,0x41),
                "filename": ("rest", 0x42) # Till L
            },
            # file flags
            "flags":{
                "read_only": 0x0001,
                "hidden": 0x0002,
                "system":0x0004,
                "archive":0x0020,
                "device":0x0040,
                "normal":0x0080,
                "tenporary":0x0100,
                "sparse_file":0x0200,
                "reparse_point":0x0400,
                "compressed":0x0800,
                "offline":0x1000,
                "not_content_indexed":0x2000,
                "enctypted":0x4000,
                "directory":0x10000000,
                "index_view":0x20000000
            }
        },
        "$DATA": {
            "values":{
                "data":(0x00) # Till end of data
            }
        }
    }




    offset = 0
    record_header = record[offset:offset+42]


    # Parsing the header of a record:
    magic_num = record_header[0x00:0x05].decode("ascii")
    offset_to_attribute = int.from_bytes(record_header[0x14:0x16], "little")
    flags = int.from_bytes(record_header[0x16:0x18], "little") # 0 = deleted file , 1 = active file , 2 = deleted directory , 3 active directory , 4/8 = none standard
    
    


    offset += offset_to_attribute
    attribute_header = record[offset:offset+16]

    # Attribute Header 
    attribute_type = hex(get_int(attribute_header,0x00,0x04))
    attribute_length_total =  hex(get_int(attribute_header,0x04,0x08))
    resident_flag =  hex(get_int(attribute_header,0x08,0x9)) # either resident or non-resident flag
         
    
    if resident_flag == "0x0":
        print("Attribute is Resident")

        # Since its a resident attribute, i now continue to read the header of the resident attribute
        attribute_header = record[offset:offset+22]

        attribute_length = get_int(attribute_header,0x10,0x14)
        offset_to_metadata = get_int(attribute_header,0x14,0x16)



        base = offset
        meta_start = base + offset_to_metadata
        meta_end = meta_start + attribute_length

        metadata = record[meta_start:meta_end]


        # Getting the attribute of STANDARD_INFORMATION
        if attribute_type == "0x10":
            file_creation_time =  get_filetime_str(metadata,0x00)
            file_altered_time = get_filetime_str(metadata,0x08)
            mft_changed_time = get_filetime_str(metadata,0x10)
            file_read_time = get_filetime_str(metadata,0x18)

            

            print(f"Magic number: {magic_num}")
            print(f"Offset to first attribute: {offset_to_attribute} bytes")
            print(f"Flags: {flags}")
            print(f"Attribute location: {hex(offset_to_attribute)}")
            print("Attributes:")
            print("-----------")
            print(f"Attribute type: {attribute_type}")
            print(f"Attribute length total (including this header): {attribute_length_total}")
            print(f"Resident/None-Resident flags: {resident_flag}")
            print(f"Offset to metadata of the attribute: {offset_to_metadata}")
            print(f"File Creation time:{file_creation_time}")
            print(f"File Altered time:{file_altered_time}")
            print(f"MFT changed time:{mft_changed_time}")
            print(f"File Read time:{file_read_time}")

        if attribute_type == "0x30":
            parent_dir = metadata[0x00:0x08].decode("ascii")



            print(f"Magic number: {magic_num}")
            print(f"Offset to first attribute: {offset_to_attribute} bytes")
            print(f"Flags: {flags}")
            print(f"Attribute location: {hex(offset_to_attribute)}")
            print("Attributes:")
            print("-----------")
            print(f"Attribute type: {attribute_type}")
            print(f"Attribute length total (including this header): {attribute_length_total}")
            print(f"Resident/None-Resident flags: {resident_flag}")
            print(f"Offset to metadata of the attribute: {offset_to_metadata}")
            print(f"Parent directory: {parent_dir}")





            print(f"META OFFSET:{metadata}")
            print(meta_start)
            print(meta_end)

        
    else:
        print("Attribute is NOT Resident")


    
    #print(get_bytes(metadata,0x00,0x08))


