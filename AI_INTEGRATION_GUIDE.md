# AI Agent Tooling Integration & Execution Guide (OmniTool & SlobTools)

Welcome, AI Agent! This document serves as the absolute guide to understanding, selecting, and executing the developer tooling and OS controllers available in this workspace.

There are **two distinct toolsets** available on this Windows system. You must understand their division of labor and select the correct tool depending on your task.

---

## 🧭 Architectural Division

```
                     ┌──────────────────────────────────────────┐
                     │            AI AGENT / EXECUTIVE          │
                     └────────────────────┬─────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌─────────────────────────┐                     ┌─────────────────────────┐
     │  SlobTools (Python)     │                     │   OmniTool (C++ Binary) │
     │  - Code Editing & Diffs │                     │   - Real-time Screen    │
     │  - File Read/Write/BOM  │                     │   - Mouse/Key Emulator  │
     │  - Excel Data Mining    │                     │   - Physical HID (COM)  │
     │  - Developer Utils/JSON │                     │   - UIA Event Listener  │
     │  - AI Memory System     │                     │   - MJPEG HTTP Server   │
     └─────────────────────────┘                     └─────────────────────────┘
```

1. **SlobTools (`D:\soft\SlobTools\`)**: **Your Workspace Utilities**.
   - Written in Python, running on top of a full environment.
   - Use these for **editing code files** (safe GBK/UTF-8 backups), **reading text/code files**, **Excel processing**, **JSON formatting**, and **dialogue memory management**.
   - These are shortcuts mapped directly to system PATH. You can call them by their short names (e.g., `read_file`, `write_file`).

2. **OmniTool (`D:\GITHUB\FastNet\omni_tool\bin\omni_tool.exe`)**: **The OS Controller & Sensor**.
   - Compiled in C++, ultra-fast, zero external runtimes.
   - Use this for **GUI Automation**, **low-level input simulation**, **screen capture (pixel-level)**, **Win32 UIAutomation event listening**, **named-pipe HUD rendering**, and **MJPEG screen streaming**.
   - Call this via `D:\GITHUB\FastNet\omni_tool\bin\omni_tool.exe <subcommand>`.

---

## 🛠️ SlobTools Quick Reference (AI Developer Toolbox)

All tools are located in `D:\soft\SlobTools\` and have `.cmd` wrapper scripts. You can call them globally without typing `python`.

### 1. File Reading & Writing (Mandatory for Code Edits)
* **`read_file <file>`**: Automatically detects UTF-8 / GBK / ASCII encoding.
  - *Example*: `read_file main.cpp --start 10 --end 30` (Reads lines 10-30).
  - *Example*: `read_file data.log --search "ERROR" --context 2` (Searches with context).
* **`write_file <file>`**: Safely writes files, keeping the original encoding. **Always generates a backup file (`.bak`) automatically before modifying.**
  - *Append*: `write_file config.txt --mode append --content "port=8080"`
  - *Replace Lines*: `write_file utils.py --mode replace --start 12 --end 15 --content "def foo():\n    return 42"`
  - *Global Replace*: `write_file main.cpp --mode patch --old "old_func()" --new "new_func()"`

### 2. Folder Encoding Conversion
* **`gbktoutf8 <src_dir> <dest_dir>`**: Batch converts text files from GBK to UTF-8.
* **`utf8togbk <src_dir> <dest_dir>`**: Batch converts text files from UTF-8 to GBK.

### 3. Excel Processing
* **`read_excel <file>`**: Reads worksheets, rows, cells, colors, or formulas.
  - *Read data*: `read_excel data.xlsx --mode read --sheet "Sheet1" --start 2 --end 20`
  - *Read formulas*: `read_excel data.xlsx --mode formula --cells B2:D5`
  - *Stat columns*: `read_excel data.xlsx --mode stats --cols "Salary"`
* **`write_excel <file>`**: Writes Excel data while fully preserving formulas and formatting.
  - *Example*: `write_excel data.xlsx --mode set-cell --cells A1=Name B1=Score C1="=SUM(B2:B10)"`
* **`cmpexcel <file1> <file2>`**: Diff two Excel files, highlighting inserted/deleted rows and cell changes.

### 4. Code & Text Utilities
* **`filetree [path]`**: Prints ASCII directory tree, excluding `node_modules`, `build`, `.git`, etc.
* **`count_code_lines [path]`**: Counts physical, comment, and blank lines across 30+ languages.
* **`json_tool <format|minify|clean> <data|file>`**: Beautifies, minifies, or strips backslashes from JSON.
* **`dev_tool <time|base64|url|hash> <args>`**: Base64/URL coder, timestamp switcher, or MD5/SHA256 hasher.

---

## 🖥️ OmniTool Full Subcommand Reference (C++ OS Executive)

Executable path: `D:\GITHUB\FastNet\omni_tool\bin\omni_tool.exe`
Below is the **exhaustive documentation** of all 20 subcommands of `omni_tool` mapped from the codebase.

### 1. `input` (Mouse, Keyboard, Touch & Controller Simulation)
* **`click -x <X> -y <Y> [-b left|right|middle] [-d]`**: Simulates mouse click. `-d` triggers double-click.
* **`move -x <X> -y <Y> [-r]`**: Moves mouse cursor. `-r` makes it relative.
* **`drag --x1 <X1> --y1 <Y1> --x2 <X2> --y2 <Y2>`**: Mouse drag-and-drop.
* **`scroll -n <count> -d up|down|left|right`**: Simulates mouse scroll wheel.
* **`text -t <text> [-d delay_ms]`**: Types the specified text with an optional delay per character.
* **`key -k <key> -a stroke|press|release`**: Triggers single key action.
* **`combo -c <key1+key2+...>`**: Executes keys combination (e.g., `ctrl+alt+delete`, `win+r`).
* **`touch --x1 <X1> --y1 <Y1> --x2 <X2> --y2 <Y2> ...`**: Simulates multi-point physical touch.
* **`vpad ...`**: Virtual gamepad controller simulation.
* **`[-p,--physical] <COM>`**: **COM Port Redirection**. Redirects inputs through CH9329 USB serial board.
  - *Example*: `omni_tool.exe input -p COM3 click -x 100 -y 100` (Sends hardware click).

### 2. `win` (Window Layout & Management)
* **`active`**: Returns active window handle (`HWND`), PID, coordinates, title, and ClassName.
* **`list`**: Lists all visible window titles, handles, and their owning PIDs.
* **`set --hwnd <HWND> --state show|hide|minimize|maximize|restore`**: Changes window state.
* **`move --hwnd <HWND> --x <X> --y <Y> --w <W> --h <H>`**: Resizes and moves window.

### 3. `capture` (Sensory Capturer & Vision Processing)
* **`pixel -x <X> -y <Y>`**: Returns RGB color and Hex string of the specified pixel.
* **`monitors`**: Lists active displays, resolutions, coordinates, and DPI scaling ratios.
* **`record [-o <file>] [-t <secs>]`**: Captures and records screen/audio loopback.
* **`ocr [-r <region>]`**: Performs screen character extraction (requires Tesseract).
* **`detect [-t <template>] [-m]`**: Direct image template matching or screen refresh motion detection.
* **`[-o,--output] <file>` / `[-r,--region] <x,y,w,h>`**: Global capture options.

### 4. `proc` (Process Supervision)
* **`list`**: Prints all running processes with their PID, memory usage, and image name.
* **`start --path <path> [--args <args>]`**: Spawns a process in the active session.
* **`kill --pid <PID>`**: Hard kills target process by its ID.

### 5. `stream` (High-speed MJPEG Streaming Server)
* **`-p <port>`**: Starts Winsock HTTP stream. Point browser to `http://localhost:<port>` to watch.
* **`-f <fps>`**: Sets screen frame rate.
* **`-o,--stdout`**: Streams raw RGBA pixels to stdout for pipe redirect (stops HTTP server).
* **`-w <window>` / `-i <pid>` / `-n <name>`**: Targets specific window/process instead of desktop.

### 6. `read` (Encoding-aware File Reader)
* **`-f <file>`**: Automatically detects file encoding (GBK/UTF-8/BOM) and outputs as UTF-8.

### 7. `write` (Multi-encoded File Writer)
* **`-f <file> -c <content> [-e gbk|utf-8|utf-16] [-b]`**: Writes file. `-b` decodes content from Base64.

### 8. `fs` (File System Atom Commands)
* **`append -f <file> -c <content>`**: Appends text to target file.
* **`copy -s <src> -d <dest>`**: Copies file or directories recursively.
* **`move -s <src> -d <dest>`**: Renames or moves directories/files.
* **`delete -f <path>`**: Hard deletes target file or folder (bypasses recycle bin).
* **`mkdir -d <path>`**: Creates nested folders.
* **`list -d <path>`**: Lists directory contents with metadata (size, modify time).
* **`attr -f <path> ...`**: Edits system attributes (readonly, hidden, system).
* **`link -s <src> -d <dest> [-j]`**: Creates hard/soft link or Directory Junction (`-j`).
* **`shred -f <file>`**: Safely overrides file with random numbers before deletion (shredder).

### 9. `clipboard` (OS Clipboard Conduit)
* **`read`**: Returns clipboard string content.
* **`write -t <text>`**: Writes string to system clipboard.

### 10. `sys` (OS Commands & Contexts)
* **`cmd -c <command>`**: Runs CLI command (with safety filter refusing dangerous items like `rm -rf /`).
* **`env [--name <K> --value <V>]`**: Reads or writes system environment variables.
* **`reg ...`**: Reads/writes Windows Registry registry entries.
* **`power shutdown|reboot|logoff|sleep`**: Adjusts system power state.
* **`time [--set <time>] [--timezone <tz>]`**: Reads or sets system time and timezone.
* **`user add|delete --name <U> --password <P>`**: Manages local user accounts.
* **`cert add|remove --file <cert>`**: Manages trusted root certificates.
* **`log --level <L> --limit <N>`**: Queries system event logs.
* **`restore create|rollback --name <name>`**: System snapshot/backup configuration.

### 11. `net` (Network Diagnostics & Packet Filtering)
* **`listen -p <port> [-t timeout]`**: Listens for incoming TCP connections and prints received data.
* **`send --ip <IP> --port <P> --data <data>`**: Sends TCP payload.
* **`ports`**: Lists active connections and port owners (similar to `netstat -ano`).
* **`status`**: Pings gateways and lists active network interface IP addresses.
* **`wifi scan|connect|disconnect --ssid <SSID> --password <P>`**: Connects/disconnects Wi-Fi.
* **`ip`**: Switches network adapters between static IP/DNS and DHCP dynamic allocation.
* **`download --url <URL> -o <file>`**: Streams web files to local storage.
* **`serial ...`**: Directly reads/writes raw COM serial ports.
* **`filter --port <P> --action block|allow`**: Captures/drops packets (WinDivert/eBPF driver hook).
* **`wol --mac <MAC>`**: Broadcasts Wake-on-LAN magic packets.
* **`scan --ip-range <range> --port <P>`**: Scans network IP subnet and active ports.

### 12. `hw` (Hardware & Power Diagnostics)
* **`volume -v <percentage> [-m]`**: Configures audio master volume or toggles mute (`-m`).
* **`brightness --level <percentage>`**: Changes hardware monitor backlight brightness.
* **`privacy camera|microphone allow|deny`**: Hardware security toggle (toggles OS device permissions).
* **`listen`**: Captures device arrival/removal events (e.g., USB flash drive plug-in).
* **`usb eject -d <letter>`**: Safely ejects USB device by its drive letter.
* **`print -f <file>`**: Directly feeds documents to print spooler.
* **`battery`**: Returns power source status, charging status, and remaining battery percentage.

### 13. `ai` (AI Integrations & Speech Wrappers)
* **`ollama generate|embeddings -m <model> -c <content>`**: Interacts with local Ollama API.
* **`vector add|search -d <db> ...`**: Local lightweight SQLite-backed RAG vector database.
* **`compile -f <src> -l cpp|python`**: Compiles and safely runs code inside isolation sandbox.
* **`similarity -a <A> -b <B> -t levenshtein|semantic`**: Distance/Embedding similarity比对.
* **`speech -m <model> -f <audio.wav>`**: Subprocess wrapper for `whisper-cli.exe` (ASR speech to text).
* **`speak -m <model> -t <text> -o <out.wav>`**: Subprocess wrapper for `piper.exe` (TTS text to speech).

### 14. `db` (Structured Databases)
* **`query -f <db_file> --sql <SQL>`**: Dynamically loads SQLite engine and runs SQL query.
* **`redis get|set|del|hash|list|stats ...`**: Raw TCP RESP protocol Redis cache manipulator.
* **`format json|xml -f <file>`**: Validates, cleans, and formats structure files.

### 15. `virt` (Virtualization & Sandbox ACL)
* **`docker start|stop|list ...`**: Container lifecycle commands.
* **`vm list|snapshot|restore ...`**: Hyper-V & VMware virtual machine control.
* **`sandbox run|acl --path <path>`**: Runs processes inside AppContainer/adjusts directory ACLs.
* **`vhd create|mount|unmount ...`**: Virtual disk image management.

### 16. `uia` (UIAutomation無障礙感知)
* **`tree [--pid <PID>]`**: Traverses and dumps target process or desktop UIAutomation elements tree.
* **`action --hwnd <H> --automation-id <id> --action click|setValue`**: Delivers events to UI elements.
* **`hotkey --keys <key> --cmd <command>`**: Spawns daemon to listen for system global hotkeys.
* **`listen [-t focus|structure|all] [-d secs]`**: Focus and structure change listener. Logs JSON Lines.

### 17. `drv` (Kernel Drivers & Monitoring)
* **`driver load|unload --path <sys> --name <name>`**: Loads/unloads Windows kernel drivers.
* **`monitor`**: Returns CPU core temperature, frequency, and GPU Telemetry.
* **`flush`**: Frees physical RAM cache memory and cleans GPU VRAM page files.
* **`uefi read|write --name <name> --guid <guid>`**: Modifies UEFI/BIOS NVRAM environment variables.
* **`usbmon`**: Captures raw USB packets from Windows USB bus.
* **`tpm ...`**: Transmits raw command packets to TPM security chip via TBS API.

### 18. `mem` (Memory Analysis & Process Injection)
* **`read` / `write --pid <PID> --address <addr> --size <size>`**: Inspects/modifies virtual memory.
* **`inject --pid <PID> --path <dll_path>`**: Injects dynamic link library into target process.
* **`dump --pid <PID> -o <file>`**: Minidumps full process memory space.
* **`thread suspend|resume --tid <TID>`**: Suspends or resumes threads.
* **`hook ...`** / **`obfuscate ...`**: Detours API hookers and obfuscates active memory.

### 19. `onnx` (ONNX inference API)
* **`-m <model> -i <image>`**: Point-and-match visual object inference. Degrades to mock simulator if ONNX SDK is missing in compilation.

### 20. `hud` (Named-Pipe GUI monitor)
* **`-c,--close`**: Closes bottom-right HUD window.
* **`-t,--test <msg>`**: Submits a test log line to HUD.

---

## 💡 AI Best Practices & Execution Rules

1. **Editing Source Code**:
   * **Rule**: You **MUST** use `write_file` (from SlobTools) to edit any project files. Never use raw terminal redirects (`echo > file` or `cat > file`) as it breaks encodings and lacks backups.
   * **Workflow**: Review changes first via `--dry-run` or `--diff` mode of `write_file` before committing writes.

2. **Reading/Searching Code**:
   * **Rule**: Use `read_file` for specific files. Use `search_source` or `rg` for finding keywords across the workspace.

3. **Win32 Interactive Automation**:
   * **Workflow**:
     1. Start the HUD: `omni_tool.exe hud` (in background).
     2. Get window coordinates: `omni_tool.exe win active` or `omni_tool.exe uia tree`.
     3. Perform inputs: `omni_tool.exe input click -x <X> -y <Y>` (or use `-p COM3` for physical HID).
     4. Capture screen and verify: `omni_tool.exe capture -o verify.png`.

4. **Graceful Degradation**:
   * Be prepared to handle warnings (e.g. `[Warning] 无法打开 CH9329 物理串口: COM...` or `ONNX Runtime 库在编译期未启用`). Your logic should parse these logs and transition to fallback/simulation mode without raising errors.
