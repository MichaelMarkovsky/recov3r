from parser import get_partitions,parse_partition,filesystem_info_print


disk_path = "./fake-ntfs/disk.img"
with open(disk_path, 'rb') as disk:
    

    try:
        partitions,partition_table,mbr_sig = get_partitions(disk,block_size=0x0200) # 0x0200  == 512 bytes
        print("Master Boot Record has been detected.")
        print("MBR signature:"+mbr_sig)
        
        print(f"\nPartition table:")
        print(partition_table)

        print(partitions)

        print("Parsing Partitions..")
        for p in partitions:
            print(f"Reading the start of the {p.index} partition at offset: {p.offset}")
            p.filesystem = parse_partition(p,disk)
            print("")
            print(p)
            
            print("")
            
            filesystem_info_print(p) 


        




    except ValueError:
         print("Master Boot Record has NOT been detected.")


