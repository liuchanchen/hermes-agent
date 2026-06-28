User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
70.93: WarpDrive TGU01-Pro x8(openEuler24.03,WD580.159.03). nvidia-smi blocked(stub exit 113,use wd-smi). No host CUDA/NCCL. Docker deepseek-v4-flash(NCCL 2.27.7+cuda13.0). backstage=198.18.0.206(SSH blocked). All servers pwd:!QAZ2wsx. SSH shorthand(70.92等)→70.0.0.x错误,必须完整IP(10.10.70.92). 70.92+96新增xuechenli/yirongpan(sudo,docker,!QAZ2wsx). vLLM at 192.168.12.12:19258(运行中,需API key)。
§
skill_manage action='patch' uses bare skill name from skills_list() (no category prefix like 'devops/').
§
MiniMax M2.7 TP+EP 启动脚本存在语法错误，导致启动失败（exit code 2），而非 NCCL P2P 问题。
§
用户要求Hermes在每次对话后主动审查并更新技能库，即使更新很小，也要避免无作为。技能库应设计为类级别的技能，每个技能有丰富的SKILL.md和references/目录，而不是扁平的单一技能条目列表。
§
在10.10.70.98上，临时使用qs用户登录，密码为!QAZ2wsx，然后创建sudo用户jianliu，密码为!QAZ2wsx，并为其设置SSH密钥路径，后续登录使用jianliu用户。
§
用户 jianliu 通过 rsync 从 10.10.70.88 向 10.10.70.98 传输 deepseekv4_pro 模型数据，传输已完成（exit code 0）。
§
70.95 上的 vLLM 服务运行 MiniMax M2 模型，max_model_len 为 80,920 tokens，配置为 tensor-parallel-size 8、expert-parallel、gpu-memory-utilization 0.85、kv-cache-dtype fp8，API key 为 ***.95-vllm，端口 8000。
§
在 10.10.70.98 上，临时使用 qs 用户登录，密码为 !QAZ2wsx，然后创建 sudo 用户 jianliu，密码为 !QAZ2wsx，并为其设置 SSH 密钥路径，后续登录使用 jianliu。
§
vLLM fork 已复制到 10.10.70.98 的 /data/vllm-ds4-sm120/，包含完整 .git 历史，分支 ds4-sm120，提交 b709b75。
§
在10.10.70.98上，vLLM的CMake配置因缺少CUDA_nvrtc_LIBRARY而失败，已安装cuda-nvrtc-13-2和cuda-nvrtc-dev-13-2，需要重新运行CMake或pip install。
§
用户要求验证工作时不修改项目文件，只能使用源读取、shell检查、浏览器/网络证据或提供的工具句柄，并返回证据支持的检查结果和最终裁决（PASS/FAIL/PARTIAL）。
§
技能库更新流程要求：每次会话至少产生一次技能更新，即使很小；更新目标为类级别技能，每个技能有丰富的SKILL.md和引用文件；更新需通过skill_manage工具进行，且SKILL.md必须放在允许路径下。
§
vLLM 在 ds4-sm120 节点上的 CMake 配置阶段因缺少 CUDA nvrtc 库而失败，已安装 cuda-nvrtc-13-2 和 cuda-nvrtc-dev-13-2 包以修复此问题。
§
远程服务器技能中有一个IP地址为10.10.70.98的服务器。
§
李馨蔚的入职日为2026年5月20日（后天），入职流程中还有多项待确认事项（Offer发送、背调完成、入职材料准备、工位/设备准备）。
§
在 ds4-sm120 节点上，vLLM 的 CMake 配置阶段因 CUDA_nvrtc_LIBRARY 链接问题失败，需要解决 nvrtc 依赖才能继续安装。
§
用户通过rsync命令将/data/models/deepseekv4_pro/从10.10.70.88传输到10.10.70.98，传输已完成（exit code 0）。