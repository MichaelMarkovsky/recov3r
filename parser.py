from tabulate import tabulate
from models import Partition,NTFSInfo,MFTRecord,StandardInformation,FileNameAttribute,DataAttribute,NoneResidentHeader,AttributeListAttribute
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
        file_system = partition[4]

        # - calculating where the partition begins
        starting_lba = partition[8:11]
        starting_lba_rev = int.from_bytes(starting_lba, byteorder='little') # Reads in little endian
        partition_offset = hex(starting_lba_rev * block_size)

        partition_hex = " ".join(f"{b:02X}" for b in partition)

        partition_size = block_size * int.from_bytes(partition[12:15], byteorder='little') 

        # Check if partition is empty (all is =0)
        if not any(partition):
            ptable_rows.append([partition_index, "Empty"])
        else:
            partitions.append(Partition(partition_index,partition_hex,bootable,file_system,partition_offset,partition_size))
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
    #partition_size = int.from_bytes(data[0x28:0x30], byteorder='little') * bytes_per_sector

    # Finding MFT offset
    mft_cluster = int.from_bytes(data[0x30:0x38], "little")
    mft_offset = mft_cluster * cluster_size
    mft_location = hex(mft_offset + partition_location)

    
    

    return NTFSInfo(bytes_per_sector,sectors_per_cluster,cluster_size,mft_cluster,mft_offset,mft_location)



def filesystem_info_print(p):
        # Filesystem information:
        print(f"Filesystem of Partition information: {p.index}")
        print(f"Bytes per sector: {p.filesystem.bytes_per_sector}")
        print(f"Sectors per cluster: {p.filesystem.sectors_per_cluster}")
        print(f"Cluster size: {p.filesystem.cluster_size}")
        megabytes = p.partition_size / (1024 * 1024)
        print(f"Partition size: {megabytes:.2f} MB")

        print(f"$MFT starts in {p.filesystem.mft_cluster} clusters.")
        print(f"$MFT starts {p.filesystem.mft_offset} bytes after the start of the partition")
        print(f"$MFT Location: {p.filesystem.mft_location}")



def get_mft_records(partition,disk):
    mft_location = int(partition.filesystem.mft_location,16) 
    # The tactic is to get the first MFT record which points to itself, get runlist and calculate the total amount of records there are in the MFT. (Currently works for a linear MFT, fragment 1)

    disk.seek(mft_location)
    mft_record_data = disk.read(1024)

    mft_record = record_parser(mft_record_data,0,mft_location)
    mft_runlist = mft_record.data[0].data_runs

    total_clusters = sum(length for _, length in mft_runlist)
    mft_size_bytes = total_clusters * partition.filesystem.cluster_size
    num_of_records = mft_size_bytes // 1024

    print(f"[+] MFT size: {mft_size_bytes} bytes")
    print(f"[+] MFT records: {num_of_records}")

    records = []
    record_index = 0
   
    for lcn,cluster_count in mft_runlist:
        run_start = (int(partition.offset, 16) + lcn * partition.filesystem.cluster_size)
        run_size_bytes = cluster_count * partition.filesystem.cluster_size

        records_in_run = run_size_bytes // 1024

        for i in range(records_in_run):
            record_location = run_start + i * 1024

            disk.seek(record_location)
            data = disk.read(1024)

            # safety check (optional but recommended)
            if data[:4] not in (b'FILE', b'FILE0'):
                continue

            record = record_parser(data, record_index, record_location)
            records.append(record)

            print(f"Record {record_index} @ {hex(record_location)}")
            record_index += 1
        
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

    def get_runlist(data, start, end):
        runlist = data[start:end]

        fragments = []

        i = 0
        current_lcn = 0

        while i < len(runlist):
            header = runlist[i]

            if header == 0:
                break

            length_size = header & 0x0F
            offset_size = header >> 4

            i += 1  #  move past header

            length = int.from_bytes(
                runlist[i:i+length_size],
                "little"
            )
            i += length_size

            offset = int.from_bytes(
                runlist[i:i+offset_size],
                "little",
                signed=True
            )
            i += offset_size

            current_lcn += offset

            fragments.append((current_lcn, length))

        return fragments    
    
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
        resident_flag =  get_int(attribute_header,0x08,0x9) # either resident or non-resident flag

        name_len = get_int(attribute_header, 0x09, 0x0a)
        offset_to_name = get_int(attribute_header, 0x0a, 0x0c)
        flags_header = get_int(attribute_header, 0x0c, 0x0e)
        attr_id = get_int(attribute_header, 0x0e, 0x10)

        if attribute_type_int not in (0xFFFFFFFF, 0x00000000):
            print(attribute_type)
            
            
         # STOP CONDITION (end of attribute list)
        if attribute_type_int in (0xFFFFFFFF, 0x00000000):
            break

        if attribute_type_int not in (0x10, 0x20, 0x30, 0x80,0x90):
        # Move to the next attribute seamlessly and skip processing
            offset += attribute_length_total
            continue
        
        

       
        if resident_flag == 0:
            # Attribute is Resident"

            # Since its a resident attribute, i now continue to read the header of the resident attribute
            attribute_header = record[offset:offset+24]

            attribute_length = get_int(attribute_header,0x10,0x14)
            offset_to_metadata = get_int(attribute_header,0x14,0x16)



            base = offset
            meta_start = base + offset_to_metadata
            meta_end = meta_start + attribute_length

            metadata = record[meta_start:meta_end]



            if name_len > 0:
                name_abs = offset + offset_to_name
                stream_name = record[name_abs : name_abs + name_len * 2].decode("utf-16le")
            else:
                stream_name = ""
                        
            # Getting the attribute of STANDARD_INFORMATION
            if attribute_type_int == 0x10:
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
                
            if attribute_type_int == 0x20:
                al_type =  get_int(metadata,0x00,0x04)
                al_record_len = get_int(metadata,0x04,0x06)
                al_name_len = get_int(metadata,0x06,0x07)
                al_offset_name = get_int(metadata,0x07,0x08)
                al_starting_vcn = get_int(metadata,0x08,0x10)
                al_base_file_ref_attr = get_int(metadata,0x10,0x18)
                al_attr_id = get_int(metadata,0x18,0x1a)
                al_name = get_bytes(metadata,0x1a,al_name_len*2).decode("utf-16le")
               
                record_obj.attr_list = AttributeListAttribute(
                    resident=resident_flag,
                    al_type=al_type,
                    al_record_len=al_record_len,
                    al_name_len=al_name_len,
                    al_offset_name=al_offset_name,
                    al_starting_vcn=al_starting_vcn,
                    al_base_file_ref_attr=al_base_file_ref_attr,
                    al_attr_id=al_attr_id,
                    al_name=al_name
                )
                           
            if attribute_type_int == 0x30:
                parent_record = metadata[0x00:0x08]
                file_creation_time =  get_filetime_str(metadata,0x08)
                file_altered_time = get_filetime_str(metadata,0x10)
                mft_changed_time = get_filetime_str(metadata,0x18)
                file_read_time = get_filetime_str(metadata,0x20)
                allocated_size_file = get_int(metadata,0x28,0x30)
                real_size_file = get_int(metadata,0x30,0x38)
                flags_filename = get_int(metadata,0x38,0x3c)
                filename_len = get_int(metadata,0x40,0x41)
                filename = get_bytes(metadata, 0x42,0x42 + filename_len * 2).decode("utf-16le")

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

            if attribute_type_int == 0x80:
                data_res = get_bytes(metadata,0x00,attribute_length)

                record_obj.data.append(DataAttribute(
                    resident=True,
                    offset_data = (offset_to_metadata + offset),
                    data_length = attribute_length,
                    stream_name=stream_name,
                    data = data_res
                ))

            if attribute_type_int == 0x90:
               pass 
                          
        else:
            # Attribute is NOT Resident
            
            attribute_header = record[offset:offset+attribute_length]
           
            
            starting_vcn = get_int(attribute_header,0x10,0x18)
            last_vcn = get_int(attribute_header,0x18,0x20)
            offset_to_dataruns = get_int(attribute_header,0x20,0x22)
            compression_unit_size= get_int(attribute_header,0x22,0x24)
            padding= get_int(attribute_header,0x24,0x28)
            allocated_size_attribute= get_int(attribute_header,0x28,0x30)
            real_size_attribute= get_int(attribute_header,0x30,0x38)
            initialized_data_size= get_int(attribute_header,0x38,0x40)
            attribute_name= get_int(attribute_header,0x40,2 * name_len)
            data_runs= get_runlist(attribute_header, offset_to_dataruns,attribute_length)

            if name_len > 0:
                name_abs = offset + offset_to_name
                stream_name = record[name_abs : name_abs + name_len * 2].decode("utf-16le")
            else:
                stream_name = ""
            

            if attribute_type_int == 0x10:
                record_obj.standard_info = NoneResidentHeader(
                    resident=resident_flag,
                    starting_vcn=starting_vcn,
                    last_vcn=last_vcn,
                    offset_to_dataruns=offset_to_dataruns,
                    compression_unit_size=compression_unit_size,
                    padding=padding,
                    real_size_attribute=real_size_attribute,
                    allocated_size_attribute=allocated_size_attribute,
                    initialized_data_size=initialized_data_size,
                    attribute_name=attribute_name,
                    data_runs=data_runs
                )
            if attribute_type_int == 0x20:
                 record_obj.attr_list = NoneResidentHeader(
                    resident=resident_flag,
                    starting_vcn=starting_vcn,
                    last_vcn=last_vcn,
                    offset_to_dataruns=offset_to_dataruns,
                    compression_unit_size=compression_unit_size,
                    padding=padding,
                    real_size_attribute=real_size_attribute,
                    allocated_size_attribute=allocated_size_attribute,
                    initialized_data_size=initialized_data_size,
                    attribute_name=attribute_name,
                    data_runs=data_runs
                )
            if attribute_type_int == 0x30:
                record_obj.file_name = NoneResidentHeader(
                    resident=resident_flag,
                    starting_vcn=starting_vcn,
                    last_vcn=last_vcn,
                    offset_to_dataruns=offset_to_dataruns,
                    compression_unit_size=compression_unit_size,
                    real_size_attribute=real_size_attribute,
                    padding=padding,
                    allocated_size_attribute=allocated_size_attribute,
                    initialized_data_size=initialized_data_size,
                    attribute_name=attribute_name,
                    data_runs=data_runs
                )

            if attribute_type_int == 0x80:
                record_obj.data.append(NoneResidentHeader(
                    resident=False,
                    starting_vcn=starting_vcn,
                    last_vcn=last_vcn,
                    offset_to_dataruns=offset_to_dataruns,
                    compression_unit_size=compression_unit_size,
                    real_size_attribute=real_size_attribute,
                    padding=padding,
                    allocated_size_attribute=allocated_size_attribute,
                    initialized_data_size=initialized_data_size,
                    attribute_name=attribute_name,
                    data_runs=data_runs,
                    stream_name=stream_name
                ))



        # MOVE TO NEXT ATTRIBUTE
        if attribute_length_total == 0:
            break

        
        offset += attribute_length_total

    #if record_obj.file_name is not None:
    #    print(record_obj.file_name.filename)

    #print(record_obj)
    return record_obj
    


