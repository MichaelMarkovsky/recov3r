# recov3r - NTFS Forensic Explorer & Recovery Tool

> A Python-based TUI application for parsing NTFS filesystems, inspecting MFT records, and recovering deleted data from disk structures.


https://github.com/user-attachments/assets/5ef25e16-d5ff-4453-b5e2-e16128123e30


**Research Notes :**  https://michaelmarkovsky.com/blog/recov3r/

---

## Capabilities

- NTFS filesystem parsing (MFT, attributes, data streams)
- Interactive partition-based exploration
- Real-time MFT table updates per selected partition
- Deleted file detection and reconstruction
- MBR-based disk support and partition detection
- Structured recovery output per partition

---

## Features

### NTFS Structure Explorer
- Full parsing of NTFS filesystem structures
- Interactive browsing of partitions
- Dynamic updates when switching partitions

---

### MFT (Master File Table) Viewer
- Browse and inspect raw MFT records
- Inspect detailed file metadata and attributes

#### Supported Attributes

| Attribute | Details |
|----------|--------|
| **`$STANDARD_INFORMATION`** | Created, Modified, Accessed, MFT Modified timestamps, file flags |
| **`$FILE_NAME`** | File name, parent reference, size, allocated size, attributes |
| **`$DATA`** | Resident and non-resident data streams, data run parsing |

---

### Deleted File Recovery
Detects deleted files by analyzing MFT record flags and reconstructs recoverable data using NTFS metadata.  
Supports full recovery of all deleted files with a single action by pressing `o` and organizes output into structured partition-based folders.

It also supports recovery of files removed via Windows (including Recycle Bin artifacts where metadata is available).

---

### Export Structure

Recovered files are stored per partition:

```text
[DISK_NAME]_Recovered/
├── Partition_1/
│   ├── recovered_file_1.txt
│   └── recovered_file_2.jpg
├── Partition_2/
│   ├── recovered_file_3.pdf
│   └── recovered_file_4.docx
└── ...
```

## Installation

### Clone repository

```bash
git clone https://github.com/MichaelMarkovsky/recov3r.git
cd recov3r
```

### Install dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Run
```bash
python main.py
```

## Disclaimer This tool is intended for: 
- Educational purposes
- Digital forensics research
- NTFS filesystem analysis Use responsibly.
- Do not use on disks without proper authorization.
