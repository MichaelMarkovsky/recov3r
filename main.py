from parser import get_partitions,parse_partition,filesystem_info_print,get_mft_records
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header,Footer,Static,Label,DataTable,Select
from textual.containers import Container,Horizontal,Vertical
import os
from models import TYPE_MAP


def parse(disk_path):
    #disk_path = "./fake-ntfs/disk.img"
    with open(disk_path, 'rb') as disk:
        

        try:
            partitions,partition_table,mbr_sig = get_partitions(disk,block_size=0x0200) # 0x0200  == 512 bytes
            print("Master Boot Record has been detected.")
            print("MBR signature:"+mbr_sig)
            
            print(f"\nPartition table:")
            print(partition_table)

            print(partitions)
            
            # Here i parse the start of the partitions , to get the $MFT location
            print("Parsing Partitions..")
            for p in partitions:
                print(f"Reading the start of the {p.index} partition at offset: {p.offset}")
                p.filesystem = parse_partition(p,disk)
                print("")
                print(p)
                
                print("")
                
                filesystem_info_print(p) 

            print("")

            # Here i parse the $MFT
            for p in partitions:
                # Parse NTFS
                if p.type_name == 'NTFS':
                    p.filesystem.mft_records = get_mft_records(p,disk)
            
            
        except ValueError:
             print("Master Boot Record has NOT been detected.")

        return partitions


def get_imgs():
    # Get all images from currect path,recursively
    path = "./"

    # to store files in a list
    list_img = []

    # dirs=directories
    for (root, dirs, file) in os.walk(path):
        for f in file:
            if '.img' in f:
                list_img.append(os.path.join(root, f))

    return list_img






partition_list = [
        ("Index","Bootable","File System","Size"),
]

def populate_partition_list(partitions,partition_list):
    for partition in partitions:
        index = partition.index
        bootable = partition.bootable
        type_name = TYPE_MAP.get(partition.type_name, "Unknown")
        partition_size = partition.partition_size

        p_size_megabytes = partition_size / (1024 * 1024)

        partition_list.append((index,bootable,type_name,p_size_megabytes))


# TUI:
class recov3rApp(App):
    ansi_color=None,
    CSS_PATH = "styles.tcss"

    def compose(self) -> ComposeResult:
        yield Vertical(
            Container(
                Select(
                    [(img, img) for img in get_imgs()],
                    prompt="Choose disk image"
                )
            ),
            Horizontal(
                DataTable(id="table_partitions"),
                DataTable(id="table_mft"),
                DataTable(id="table_deleted"),
                classes="tables"
            ),
            Static("PP")
          )

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        disk_path = event.value

        if disk_path != None:
            # Try to get the disk
             
            self.notify("Found it") # Notification
            partitions_table = self.query_one("#table_partitions", DataTable)
            partitions_table.cursor_type = "row"
            partitions = parse(disk_path)
            
            # Add titles
            partitions_table.add_columns(*partition_list[0])
           
            # Populate partition list
            populate_partition_list(partitions,partition_list)

            # Add rows
            partitions_table.add_rows(partition_list[1:])




if __name__ == "__main__":
    app = recov3rApp()
    app.run()

