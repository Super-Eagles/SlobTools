并发部署与管理工具 (cp_update.py) 使用说明
编写人：老殷 | 发布日期：2026-05-15 15:00

此次要执行的命令
/lib/systemd/system/redis-server.service

#看目标电脑是否可以连接
python cp_update.py . 12
#看文件在不在
python cp_update.py /lib/systemd/system/redis-server.service 0
#替换文件
python cp_update.py ./system 7 /lib/systemd/system
#看一下有没有换成新的
python cp_update.py "ls -ltr /lib/systemd/system/redis-server.service" 9
========================================================================

准备工作
========================================================================

环境：必须在有 Python 2.7 的 Linux 或 Windows WSL 环境下运行。

配置：(需与脚本放在同一目录下)

ip.txt  : 填入所有目标电脑的 IP 地址（每行一个）。

pgm.txt : 填入要管理的服务程序名。

权限：本脚本会自动提权(sudo)，并能自动识别文件该归属哪个用户/用户组，
不用担心权限搞错，不需要手动执行 chown。

========================================================================
2. 命令怎么写？
格式：
python cp_update.py [路径或命令] [模式编号] [进程名] [远端路径] [启动方式]

提示：如果看不懂参数，直接看下面的【模式详解】示例，照着改就行。

★ 几个重要的小知识：

启动方式：'d' 代表后台直接启动，'t' 代表在黑窗口(终端)里启动。

备份功能：模式 2, 3, 4, 7 都会自动在远端创建 BAK 文件夹，可随时找回旧版本。

操作日志：每次操作的结果都会记录在本地的 upload_result.log 里。

========================================================================
3. 模式详解：要做什么？
【A. 探测与检测】 (不改动远端任何东西)
模式 12：看看电脑通不通

场景：刚开始工作，先检查哪些电脑是开着的。

示例：python cp_update.py . 12

模式 0：看看文件在不在

场景：确认某台电脑上是不是已经有这个程序了。

示例：python cp_update.py /data/main_bin 0

模式 9：执行任意命令 (全能模式)

场景：想看磁盘空间(df -h)、看系统时间(date)、看文件列表(ls)。

示例：python cp_update.py "df -h" 9

【B. 程序更新】 (最常用的部署功能)
模式 3：更新单个文件并重启

场景：修改了一个文件，想让它生效。

流程：脚本会自动：杀掉进程 -> 备份旧的 -> 传新的 -> 自动后台重启。

示例：python cp_update.py /local/TdsService 3 TdsService d

模式 4：更新整个目录并重启

场景：整个程序包都换了。

流程：脚本会自动：杀进程 -> 整个目录备份并覆盖 -> 自动后台重启。

示例：python cp_update.py ./MainDir 4 MainNodeV3 /remote/MainDir d

【C. 文件搬运】 (只传文件，不重启)
模式 2：传文件并自动备份

场景：只想换个配置文件，不需要重启程序。

示例：python cp_update.py ./config.ini 2

模式 7：同步整个目录

场景：比如要把整个资源包传到所有机器。

示例：python cp_update.py ./Resource 7 /data/Resource

模式 11：把远程的文件抓回来

场景：某台电脑报错了，想把它的日志取回本地看。

提示：抓回来的文件会自动加上 IP 后缀，防止覆盖。

示例：python cp_update.py /data/log.txt 11 ./my_logs

【D. 进程与系统管理】
模式 5：进程保活

场景：发现程序掉了，把它拉起来；如果已经在运行，则不管它。

示例：python cp_update.py /data/exe_path 5 TdsService d

模式 6：纯杀进程

场景：想要停止所有电脑上的某个程序。

示例：python cp_update.py . 6 TdsService

模式 10：强力删除

场景：清理垃圾文件，支持通配符（如 tmp*）。

示例：python cp_update.py "/data/tmp*" 10

模式 8：批量重启电脑

场景：电脑卡死了，需要全站重启操作系统。

示例：python cp_update.py . 8

========================================================================
4. 脚本代码索引 (能自己动手的根据行数定位自行修改)
核心提权逻辑 : L126
业务查杀逻辑 : L230
并发引擎底层 : L332
具体任务实现 : L391