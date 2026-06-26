User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
70.92: /data/venvs/vllm-ds4/, /data/vllm-ds4-sm120/, DS-V4-Flash at /data/models/deepseekv4_flash, /data/ chown'd jianliu, cudagraph_mode(not wdgraph_mode).
§
用户负责 WarpDriveAI 招聘，用 interview 技能管理简历、面试、入职。
§
70.93: WarpDrive TGU01-Pro x8(openEuler24.03,WD580.159.03). nvidia-smi blocked(stub exit 113,use wd-smi). No host CUDA/NCCL. Docker deepseek-v4-flash(NCCL 2.27.7+cuda13.0). backstage=198.18.0.206(SSH blocked). All servers pwd:!QAZ2wsx. SSH shorthand(70.92等)→70.0.0.x错误,必须完整IP(10.10.70.92). 70.92+96新增xuechenli/yirongpan(sudo,docker,!QAZ2wsx). vLLM at 192.168.12.12:19258(运行中,需API key)。
§
skill_manage action='patch' uses bare skill name from skills_list() (no category prefix like 'devops/').
§
用户启用了 interview 技能，该技能用于管理 WarpDriveAI 的面试日程、候选人、简历和入职时间线。
§
MiniMax M2.7 TP+EP 启动脚本存在语法错误，导致启动失败（exit code 2），而非 NCCL P2P 问题。
§
用户要求将 /data/models/deepseekv4_pro/ 从 10.10.70.88 复制到 10.10.70.98，使用 rsync -aP --partial 通过 SSH 传输，约 806 GiB，传输正在进行中。
§
WarpDriveAI 使用 interview 技能管理面试日程、候选人简历、入职时间线和候选人档案。
§
用户要求Hermes在每次对话后主动审查并更新技能库，即使更新很小，也要避免无作为。技能库应设计为类级别的技能，每个技能有丰富的SKILL.md和references/目录，而不是扁平的单一技能条目列表。
§
用户有一个远程服务器技能，IP地址为10.10.70.98。
§
在主机10.10.70.98上，临时使用qs用户登录，密码为!QAZ2wsx，然后创建sudo用户jianliu，密码为!QAZ2wsx，并为jianliu@10.10.70.98配置SSH密钥，后续登录使用jianliu用户。
§
用户 jianliu 通过 rsync 从 10.10.70.88 向 10.10.70.98 传输 deepseekv4_pro 模型数据，传输已完成（exit code 0）。
§
70.95 上的 vLLM 服务运行 MiniMax M2 模型，max_model_len 为 80,920 tokens，配置包括 tensor-parallel-size 8、expert-parallel、gpu-memory-utilization 0.85、kv-cache-dtype fp8，API key 为 ***.95-vllm，端口 8000。
§
服务器 10.10.70.98 的临时登录用户为 qs，密码为 !QAZ2wsx；需创建 sudo 用户 jianliu，密码为 !QAZ2wsx，并为其配置 SSH 密钥，后续登录使用 jianliu。
§
vLLM fork 已从 70.88 复制到 70.98 的 /data/vllm-ds4-sm120/，包含完整 .git 历史和 ds4-sm120 分支（commit b709b75），大小为 6.2 GB。