from tabulate import tabulate
from models import Partition

def get_partitions(disk_location,block_size):
    # Open the file in binary read mode ('rb')
    with open(disk_location, 'rb') as file:
        # Read exactly 50 bytes from the beginning
        mbr = file.read(512)

    #========== MBR (Master Boot Record) =============
    print(mbr)
    print(f"\n=====================")

    mbr_signature = (mbr[510:512]).hex()
   
    print("MBR signature:"+mbr_signature)

    if mbr_signature == "55aa":
        print("Master Boot Record has been detected.")
    else:
         print("Master Boot Record has NOT been detected.")

    print("=====================")
   

    print(f"\nPartition table:")
    # Checking if avaliable partitions
    partition_table = (mbr[446:510])
    partition_list = []
    ptable = [] # A printable table for easier visualization
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
            ptable.append([partition_index, "Empty"])
        else:
            partition_list.append(Partition(partition_index,partition_hex,bootable,file_system,partition_offset))
            ptable.append([partition_index,partition_hex,bootable,file_system,partition_offset])

        
        partition_index += 1

    print(tabulate(ptable, headers=ptable_headers, tablefmt="grid"))

    return partition_list



