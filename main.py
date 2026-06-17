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
                if p.type_name == 7:
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
            if f.endswith(('.img', '.vhd')):
                list_img.append(os.path.join(root, f))

    return list_img




def populate_partition_list(partitions,partition_list):
    for partition in partitions:
        index = partition.index
        bootable = partition.bootable
        type_name = TYPE_MAP.get(partition.type_name, "Unknown")
        partition_size = partition.partition_size

        p_size_megabytes = partition_size / (1024 * 1024)

        partition_list.append((str(index),str(bootable),str(type_name),str(p_size_megabytes)))

def populate_mft_list(partition,mft_list):
    mft_records = partition.filesystem.mft_records
    for record in mft_records:
        record_num = record.record_number
        magic_num = record.magic_num
        record_offset = record.record_location
        flags = record.flags
        try:
            file_name = record.file_name.filename
        except AttributeError:
            file_name = ""

        mft_list.append((str(record_num),str(magic_num),str(record_offset),str(flags),str(file_name)))

def populate_del_list(partition,del_list):
    mft_records = partition.filesystem.mft_records
    for record in mft_records:
        # Only added deleted 
        if record.flags == 0 :
            record_num = record.record_number
            try:
                file_name = record.file_name.filename
            except AttributeError:
                file_name = ""
            del_list.append((str(record_num),str(file_name)))







# TUI:
class recov3rApp(App):
    ansi_color=None,
    CSS_PATH = "styles.tcss"

    def on_mount(self):
        self.partitions = []
        self.partition_list = [] # List of partitions for table (TUI)
        #self.mft_list = [,]
        self.deleted_list = []


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
            Static("MetaData")
          )

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        disk_path = event.value
        

        if disk_path and disk_path != Select.NULL:
            # Try to get the disk
             
            #self.notify("Found it") # Notification
            partitions_table = self.query_one("#table_partitions", DataTable)
            partitions_table.cursor_type = "row"

            # Clear the table
            partitions_table.clear(columns=True)
            self.partition_list.clear()
            self.partitions.clear()

            self.partitions = parse(disk_path)


            # Add Headers
            headers = ("Index", "Bootable", "File System", "Size")
            rows = []

           
            # Populate partition list
            populate_partition_list(self.partitions,rows)


            if not rows:
                return
            
            # Add headers
            partitions_table.add_columns(*headers)
            # Add rows
            partitions_table.add_rows(rows)


    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        table = event.data_table  # or event.control
        
        # Update both MFT and Deleted files tables
        if table.id == "table_partitions":
            # =========== MFT Table ============
            mft_table = self.query_one("#table_mft", DataTable)


            row_index = event.cursor_row
            partition = self.partitions[row_index]


            # Add Headers
            headers = ("Record Number","Magic Number","Record Offset","Flags","File Name")
            rows = []

           
            # Populate partition list
            populate_mft_list(partition,rows)
            
            #self.notify(str(len(rows)))

            if not rows:
                return

             # Clear the table
            mft_table.clear(columns=True)


            mft_table.add_columns(*headers)
            mft_table.add_rows(rows)



            # ========= Deleted Files Table ===========
            del_table = self.query_one("#table_deleted", DataTable)

            headers_del = ("Record Number","File Name")
            rows_del = []

            populate_del_list(partition,rows_del)

            if not rows_del:
                return

            del_table.clear(columns=True)


            del_table.add_columns(*headers_del)
            del_table.add_rows(rows_del)








        elif table.id == "table_mft":
            # handle MFT selection separately
            pass



if __name__ == "__main__":
    app = recov3rApp()
    app.run()

