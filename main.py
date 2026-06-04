from parser import get_partitions


partitions = get_partitions('./fake-ntfs/disk.img',block_size=0x0200) # 0x0200 == 512 bytes
print(partitions)
