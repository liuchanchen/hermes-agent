Reasoning effort: agent+delegation均xhigh于config.yaml; "max"无效,xhigh即最高.
§
70.93: TGU01-Pro x8(openEuler,WD580). nvidia-smi被stub挡→wd-smi(--query-gpu可用). backstage=198.18.0.206(SSH blocked). pwd均!QAZ2wsx;SSH须完整IP(10.10.70.92). 70.92/96有xuechenli/yirongpan(sudo,docker).
§
70.96: host细节→skill remote-server-70-96; PD配方/排障→skill pd-disaggregation. 空闲监控cron=a3007169683e.
§
70.90: jianliu/!QAZ2wsx SSH可用。GitLab 10.10.50.23(SSH免密,@liujian),克隆用 git@10.10.50.23:tgu01-pro/<repo>.git.
§
12.12: docker exec jianliu_sw2_public_19255; modelscope续传可能误删<2GB文件→删后立即重启. DS-V4-Flash-0731在/home/public/models/. SSH登录shell就绪慢(40-120s,PAM);监控prompt等待已修(0915).
§
70.99(oem-99): 0825重装→TGU01F, 监控=warpdgpu-smi(无--query-gpu); fantgpu/wd-smi移除. 0904当日×2→×8卡漂移, 重装频繁.
§
用户明确要求：除非用户要求，否则不要安装工具/软件包（apt-get/pip/conda等均被拒绝）。需要解析图片/文档内容时，先请用户自行抽取或提供文本，而非自行安装OCR。技能库更新：需通过skill_manage进行，SKILL.md必须位于允许路径，每会话至少一次小更新。
§
TGU算力: TGU02-F 500T/TGU01-F 250T/TGU02-H2 200T/TGU02-H 100T; B300=2250T, H200≈989T.
§
70.88: docker stop杀不掉benchmark管理的vLLM(supervisor自动重启容器),需同kill harness PID;镜像迁移先比Image ID,同ID retag即可;88=GPU监控共享宿主(8787). 0915起NVML错配(rc=18)待重启修复.
§
vLLM基准对比须防JIT编译偏置:先后执行顺序致compile cache不对称(先跑冷编译~700s,后跑~90s);timed窗口内TileLang/Triton JIT波(jit_monitor.py:135)造成延迟尖峰,对比易失真.
§
远程sudo密码含`!`: 用set +H或base64编码密码; sudo -S与需stdin命令冲突→先`sudo -S -v`缓存; 107登录shell conda损坏污染stdout→`bash --noprofile --norc -c`包远程命令; docker跨机传镜像: save到tar→cat|ssh docker load,勿用sudo -S docker load; ssh一行命令内pkill -f含自身cmdline的pattern→自杀(exit 255),用backend[.]main或先杀后起.
§
70.107: jianliu账号已删(0904). 用liujian/985202Qs~(域账号,WSL直连); qs(!QAZ2wsx可用,uid1000,sudo+docker)加的sudo; b64管道避!展开. 监控已纳管. 106:同账密liujian(0911),qs加sudo已验证root;docker组未加(用sudo docker).
§
GPU监控: /home/jianliu/work/gpu-monitor. WSL实例=systemd user服务gpu-monitor.service(0904起; 用miniconda python,系统python3缺pexpect). 共享实例=70.88:8787(nodes-88.yaml). idle=mem≤64MiB持续15min(持显存不算). 技能devops/gpu-cluster-monitor(0904断数据复盘+前端兜底修复).
§
用户纠错(0905,Notion PD页):对比结论没写明baseline就用'GPU减半'——baseline是4卡混部,实际是PD 8卡输给4卡。教训:对比结论必须同句写明比较基准(卡数/实例规格),比例词(减半/翻倍)无参照点=未验证。已入technical-scheme-writing skill。
§
70.106: 监控改liujian(0915). 66: 重装过,密码拒,key可用(6卡). 88实例已修,66/106/12.12恢复;88/94待重启修NVML.