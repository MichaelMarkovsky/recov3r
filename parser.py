from tabulate import tabulate
from models import Partition,NTFSInfo,MFTRecord,StandardInformation,FileNameAttribute
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

    records = []

    while record_index<4:
        record_location = mft_location + 1024 * record_index
        print()
        print(f"Record number {record_index} location: {hex(record_location)}")

        disk.seek(record_location)
        data = disk.read(1024) # Read exactly one record     
        

        records.append(record_parser(data,record_index,record_location))
        print()
        record_index+=1
    return records 


def record_parser(record,record_index,record_location):
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

    
    record_obj = MFTRecord(
            record_number=record_index,
            record_location=record_location
    )

    offset = 0
    record_header = record[offset:offset+42]


    # Parsing the header of a record:
    magic_num = record_header[0x00:0x05].decode("ascii")
    offset_to_attribute = int.from_bytes(record_header[0x14:0x16], "little")
    flags = int.from_bytes(record_header[0x16:0x18], "little") # 0 = deleted file , 1 = active file , 2 = deleted directory , 3 active directory , 4/8 = none standard
    
    record_obj.magic_num=magic_num
    record_obj.flags=flags


    offset += offset_to_attribute
    
    
    while True:
        attribute_header = record[offset:offset+16]

        if len(attribute_header) < 16:
                break

        # Attribute Header 
        attribute_type = hex(get_int(attribute_header,0x00,0x04))
        attribute_type_int = get_int(attribute_header, 0x00, 0x04)

        attribute_length_total =  get_int(attribute_header,0x04,0x08)
        resident_flag =  hex(get_int(attribute_header,0x08,0x9)) # either resident or non-resident flag

         # STOP CONDITION (end of attribute list)
        if attribute_type_int in (0xFFFFFFFF, 0x00000000):
            break

        if attribute_type not in ("0x10", "0x30", "0x80"):
            offset += attribute_length_total
            continue

        if resident_flag == "0x0":
            #print("Attribute is Resident")

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
                dos_file_permissions = get_int(metadata,0x20,0x24)
                max_numb_ver = get_int(metadata,0x24,0x28)
                ver_num = get_int(metadata,0x28,0x2c)
                class_id = get_int(metadata,0x2c,0x30)
               
                # Create object for storing STANDARD_INFORMATION
                # Append to the object the parsed data
                record_obj.standard_info = StandardInformation(
                    resident=resident_flag,
                    created_time=file_creation_time,
                    modified_time=file_altered_time,
                    mft_modified_time=mft_changed_time,
                    accessed_time=file_read_time,
                    dos_file_permissions=dos_file_permissions,
                    ver_num=ver_num,
                    class_id=class_id
                )
            

                
            if attribute_type == "0x30":
                parent_record = metadata[0x00:0x08]
                file_creation_time =  get_filetime_str(metadata,0x08)
                file_altered_time = get_filetime_str(metadata,0x10)
                mft_changed_time = get_filetime_str(metadata,0x18)
                file_read_time = get_filetime_str(metadata,0x20)
                allocated_size_file = get_int(metadata,0x28,0x30)
                real_size_file = get_int(metadata,0x30,0x38)
                flags_filename = get_int(metadata,0x38,0x3c)
                filename_len = get_int(metadata,0x40,0x42)
                filename = get_bytes(metadata, 0x42, filename_len * 2).decode("utf-16le")

                record_obj.file_name = FileNameAttribute(
                    resident=resident_flag,
                    parent_record=parent_record,
                    created_time=file_creation_time,
                    modified_time=file_altered_time,
                    mft_modified_time=mft_changed_time,
                    accessed_time=file_read_time,
                    allocated_size_file=allocated_size_file,
                    real_size_file=real_size_file,
                    flags_filename=flags_filename,
                    filename_len=filename_len,
                    filename=filename
                   )


            
        else:
            print("Attribute is NOT Resident")

        # MOVE TO NEXT ATTRIBUTE
        if attribute_length_total == 0:
            break

        
        offset += attribute_length_total
    print(record_obj)
    return record_obj
    


