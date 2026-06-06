from tabulate import tabulate
from models import Partition,NTFSInfo

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

