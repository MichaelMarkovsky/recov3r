from parser import get_partitions,parse_partition,filesystem_info_print,get_mft_records
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header,Footer,Static,Label,DataTable,Select
from textual.containers import Container,Horizontal,Vertical
import os
from models import TYPE_MAP,FLAGS_MFT,FILE_ATTRIBUTES,DataAttribute,NoneResidentHeader
from textual.events import Key
from pathlib import Path
import re

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

def populate_mft_list(partition,mft_list,mft_map):
    mft_records = partition.filesystem.mft_records
    for i, record in enumerate(mft_records):
        record_num = record.record_number
        magic_num = record.magic_num
        record_offset = record.record_location
        flags = record.flags
        try:
            file_name = record.file_name.filename
        except AttributeError:
            file_name = ""

        mft_list.append((str(record_num),str(magic_num),str(record_offset),str(flags),str(file_name)))

        mft_map.append(record)


def populate_del_list(partition,del_list,del_map):
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

            del_map.append(record)





def populate_del_fil_list(partition, del_list, del_map):
    mft_records = partition.filesystem.mft_records

    deleted = []
    i_map = {}
    r_map = {}

    for record in mft_records:
        if record.flags == 0:
            try:
                name = record.file_name.filename
            except AttributeError:
                name = ""

            deleted.append((record, name))

            if name.startswith("$I"):
                i_map[name] = record
            elif name.startswith("$R"):
                r_map[name] = record

    used = set()

    for i_name, i_rec in i_map.items():
        r_name = "$R" + i_name[2:]

        if r_name in r_map and i_name not in used:
            r_rec = r_map[r_name]

            # $I file holds the original path encoded as UTF-16LE
            # it starts at byte 8 (first 8 bytes are recycle bin metadata)
            raw = None
            for stream in i_rec.data:
                if stream.stream_name == "" and hasattr(stream, "data"):
                    raw = stream.data
                    break

            if raw:
                # skip the 8-byte recycle bin header, rest is UTF-16LE path
                path = raw[8:].decode("utf-16le", errors="ignore").rstrip("\x00")
                path = path.replace("\\", "/")
                r_rec.display_name = os.path.basename(path)
            else:
                r_rec.display_name = r_rec.file_name.filename if r_rec.file_name else r_name

            del_map.append(r_rec)
            del_list.append(r_rec)

            used.add(i_name)
            used.add(r_name)

    for record, name in deleted:
        if not name.startswith("$I") and not name.startswith("$R"):
            if not hasattr(record, "display_name"):
                record.display_name = name
            del_map.append(record)
            del_list.append(record)


def show_partition_metadata(partition):

    return Container(
        Static(f"Partition {partition.index}", classes="meta_title"),

        Static(
            f"Bootable : {partition.bootable}\n"
            f"Size     : {partition.partition_size} bytes\n"
            f"Hex      : {partition.hex}",
            classes="meta_body"
        ),
    )


def safe(v, default="N/A"):
    return v if v is not None else default


def decode_file_attributes(flags: int):
    if not flags:
        return []

    return [
        name
        for bit, name in FILE_ATTRIBUTES.items()
        if flags & bit
    ]

def build_metadata_view(record):

    si = getattr(record, "standard_info", None)
    fn = getattr(record, "file_name", None)
    data = getattr(record, "data", None)

    return Horizontal(
        Container(Static(build_standard_info(si)), id="meta_left"),
        Container(Static(build_file_name(fn)), id="meta_middle"),
        Container(Static(build_data(data)), id="meta_right"),
    )

def build_standard_info(si):

    if not si:
        return "STANDARD INFO\n──────────────\nNone"

    attrs = decode_file_attributes(getattr(si, "dos_file_permissions", 0))

    return (
        "STANDARD INFO\n"
        "──────────────\n"
        f"Created   : {si.created_time}\n"
        f"Modified  : {si.modified_time}\n"
        f"Accessed  : {si.accessed_time}\n"
        f"MFT Mod   : {si.mft_modified_time}\n"
        f"Attributes: {', '.join(attrs) if attrs else 'None'}\n"
        f"Version   : {si.ver_num}\n"
        f"Class ID  : {si.class_id}\n"
    )


def build_file_name(fn):
    if not fn:
        return "FILE NAME\n──────────\nNone"

    parent_record, parent_seq = fn.parent

    return (
        "FILE NAME\n"
        "──────────\n"
        f"Name      : {fn.filename}\n"
        f"Parent    : {parent_record} (seq {parent_seq})\n"
        f"Size      : {fn.real_size_file} bytes\n"
        f"Allocated : {fn.allocated_size_file} bytes\n"
        f"Length    : {fn.filename_len}\n"
        f"Flags     : {fn.flags_filename}\n"
    )

def build_data(data):
    if data is None:
        return "DATA\n────\nNone"

    # Handle list (new format)
    if isinstance(data, list):
        if not data:
            return "DATA\n────\nNone"
        # show all streams
        parts = []
        for stream in data:
            name = stream.stream_name if stream.stream_name else "<default>"
            parts.append(f"[Stream: {name}]\n{_build_single_data(stream)}")
        return "\n\n".join(parts)

    return _build_single_data(data)


def _build_single_data(data):
    if hasattr(data, "data"):  # resident DataAttribute
        raw = data.data or b""
        try:
            text = raw.decode("utf-8", errors="replace")
        except:
            text = repr(raw)
        return (
            "DATA (RESIDENT)\n"
            "───────────────\n"
            f"{text}"
        )

    if hasattr(data, "data_runs"):  # non-resident
        lines = [
            "DATA (NON-RESIDENT)",
            "───────────────────",
            f"VCN Start : {data.starting_vcn}",
            f"VCN End   : {data.last_vcn}",
            "",
            "RUN LIST:",
        ]
        for i, (lcn, length) in enumerate(data.data_runs):
            lines.append(f"{i}: LCN={lcn} LEN={length}")
        return "\n".join(lines)

    return f"DATA\n────\nUnknown type: {type(data).__name__}"

def safe_name(name):
    name = str(name)
    name = name.split("\x00")[0]
    return re.sub(r'[<>:"/\\|?*]', "_", name)





def recover_nonresident_stream(disk, stream, partition, output_path):
        cluster_size = partition.filesystem.cluster_size
        partition_offset = int(partition.offset, 16)
        real_size = stream.real_size_attribute  # don't write padding past this

        written = 0

        with open(output_path, "wb") as dst:
            for lcn, length in stream.data_runs:
                byte_offset = partition_offset + lcn * cluster_size
                run_bytes = length * cluster_size

                disk.seek(byte_offset)
                data = disk.read(run_bytes)

                # last run may be padded - trim to real file size
                remaining = real_size - written
                if len(data) > remaining:
                    data = data[:remaining]

                dst.write(data)
                written += len(data)

                if written >= real_size:
                    break

def recover_record(disk, record, partition, partition_dir):
    base_name = safe_name(
        getattr(record, "display_name", None) or f"record_{record.record_number}"
    )

    for stream in record.data:
        # pick output filename
        if stream.stream_name:
            out_name = f"{base_name}__{stream.stream_name}"
        else:
            out_name = base_name

        output_path = f"{partition_dir}/{out_name}"

        if stream.resident:   
            with open(output_path, "wb") as f:
                    f.write(stream.data)

        else:  # non-resident
            if hasattr(stream, "data_runs") and stream.data_runs:
                recover_nonresident_stream(disk, stream, partition, output_path)









class recov3rApp(App):
    ansi_color = True
    CSS_PATH = "styles_v2_transparent.tcss"
    BINDINGS = [
        ("o", "recover", "Recover Disk"),
        ("q", "quit", "Quit"),
    ]
    ENABLE_COMMAND_PALETTE = False

    def on_mount(self):
        self.query_one("#table_partitions").border_title = "Partitions"
        self.query_one("#table_mft").border_title = "$MFT"
        self.query_one("#table_deleted").border_title = "Deleted Files"
        self.query_one("#table_del_final").border_title = "Deleted Reconstracted Files"

        self.partitions = []

        self.partition_list = []

        self.deleted_list = []
        self.deleted_list_filtered = []

        self.mft_map = []
        self.del_map = []
        self.del_map_filtered = []

        self.cache = {}

        self.disk_path = None

    # ================= CACHE BUILDER =================
    def build_partition_cache(self, index):
        if index in self.cache:
            return

        partition = self.partitions[index]

        # -------- MFT --------
        mft_rows = []
        mft_map = []
        populate_mft_list(partition, mft_rows, mft_map)

        # -------- Deleted --------
        del_rows = []
        del_map = []
        populate_del_list(partition, del_rows, del_map)

        # -------- Reconstructed --------
        rec_rows = []
        rec_map = []
        populate_del_fil_list(partition, rec_rows, rec_map)

        self.cache[index] = {
            "mft_rows": mft_rows,
            "mft_map": mft_map,
            "del_rows": del_rows,
            "del_map": del_map,
            "rec_records": rec_rows,
            "rec_map": rec_map,
        }

    # ================= UI =================
    def compose(self) -> ComposeResult:
        self.metadata = Container(id="metadata")
        
        yield Vertical(
            Container(
                Select([(img, img) for img in get_imgs()], prompt="Choose disk image"),
                id="select_container",
            ),

            Horizontal(
                DataTable(id="table_partitions"),
                DataTable(id="table_mft"),
                DataTable(id="table_deleted"),
                DataTable(id="table_del_final"),
                classes="tables"
            ),

            self.metadata,
            Footer(),
       )

    # ================= LOAD DISK =================
    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        disk_path = event.value
        self.disk_path = disk_path

        if not disk_path or disk_path == Select.NULL:
            return

        self.partitions = parse(disk_path)
        self.cache.clear()

        table = self.query_one("#table_partitions", DataTable)
        table.cursor_type = "row"
        table.clear(columns=True)

        headers = ("Index", "Bootable", "File System", "Size (MB)")
        rows = []

        populate_partition_list(self.partitions, rows)

        table.add_columns(*headers)
        table.add_rows(rows)

    # ================= PARTITION CLICK =================
    @on(DataTable.RowHighlighted)
    def on_row_selected(self, event: DataTable.RowHighlighted):

        table = event.data_table

        if table.id != "table_partitions":
            return

        index = event.cursor_row

        # build cache once
        self.build_partition_cache(index)
        data = self.cache[index]

        # ================= MFT =================
        mft_table = self.query_one("#table_mft", DataTable)
        mft_table.cursor_type = "row"
        mft_table.clear(columns=True)

        mft_headers = ("Record Number", "Magic Number", "Record Offset", "Flags", "File Name")
        mft_table.add_columns(*mft_headers)

        mft_table.add_rows(data["mft_rows"])
        self.mft_map = data["mft_map"]

        # ================= DELETED =================
        del_table = self.query_one("#table_deleted", DataTable)
        del_table.cursor_type = "row"
        del_table.clear(columns=True)

        del_table.add_columns("Record Number", "File Name")
        del_table.add_rows(data["del_rows"])

        self.del_map = data["del_map"]

        # ================= RECONSTRUCTED =================
        rec_table = self.query_one("#table_del_final", DataTable)
        rec_table.cursor_type = "row"
        rec_table.clear(columns=True)

        rec_table.add_columns("Record Number", "File Name")

        self.del_map_filtered = data["rec_map"]

        rows = [
            (
                str(rec.record_number),
                getattr(
                    rec,
                    "display_name",
                    getattr(getattr(rec, "file_name", None), "filename", "")
                )
            )
            for rec in data["rec_records"]
        ]

        rec_table.add_rows(rows)

    # ================= METADATA CLICK =================
    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted):

        table = event.data_table
        index = event.cursor_row

        if index is None or not table.has_focus:
            return

        if table.id == "table_partitions":
            partition = self.partitions[index]
            self.metadata.remove_children()
            self.metadata.mount(show_partition_metadata(partition))

        elif table.id == "table_mft":
            entry = self.mft_map[index]
            self.metadata.remove_children()
            self.metadata.mount(build_metadata_view(entry))

        elif table.id == "table_deleted":
            entry = self.del_map[index]
            self.metadata.remove_children()
            self.metadata.mount(build_metadata_view(entry))

        elif table.id == "table_del_final":
            entry = self.del_map_filtered[index]
            self.metadata.remove_children()
            self.metadata.mount(build_metadata_view(entry))




    @on(Key)
    def on_key(self, event: Key):
        if event.key.lower() != "o":
            return

        recovered_dir = f"./{self.disk_path}_Recovered"
        os.makedirs(recovered_dir, exist_ok=True)

        with open(self.disk_path, "rb") as disk:
            for partition_index in range(len(self.partitions)):
                self.build_partition_cache(partition_index)

                rec_map = self.cache[partition_index]["rec_map"]
                partition = self.partitions[partition_index]

                partition_dir = f"{recovered_dir}/Partition_{partition_index}"
                os.makedirs(partition_dir, exist_ok=True)

                for record in rec_map:
                    #for stream in record.data:
                        #self.notify(f"{getattr(record, 'display_name', '?')} | resident={stream.resident} | has_data={hasattr(stream, 'data')} | data={getattr(stream, 'data', None)}")

                    try:
                        recover_record(disk, record, partition, partition_dir)
                        self.notify(f"Recovered: {getattr(record, 'display_name', record.record_number)}")
                    except Exception as e:
                        self.notify(f"Error on record {record.record_number}: {e}")






if __name__ == "__main__":
    app = recov3rApp()
    app.run()

