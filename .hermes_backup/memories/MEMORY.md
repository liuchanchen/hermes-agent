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
在主机10.10.70.98上，临时使用用户qs和密码!QAZ2wsx登录，然后创建sudo用户jianliu，密码为!QAZ2wsx，并为jianliu@10.10.70.98配置SSH密钥，后续登录使用jianliu用户。
§
服务器 10.10.70.95:8000 上运行的 vLLM 服务使用 MiniMax M2 模型（非 DeepSeek V4），max_model_len 为 80,920 tokens，配置包括 tensor-parallel-size 8、expert-parallel、gpu-memory-utilization 0.85、kv-cache-dtype fp8，API key 为 ***.95-vllm。
§
在 10.10.70.98 上，临时用户 qs 的密码是 !QAZ2wsx，需创建 sudo 用户 jianliu 并设置密码 !QAZ2wsx，后续登录使用 jianliu。
§
在10.10.70.98上，vLLM的CMake配置因缺少CUDA_nvrtc_LIBRARY而失败，已安装cuda-nvrtc-13-2和cuda-nvrtc-dev-13-2，需要重新尝试安装。
§
技能库更新流程要求：每次会话至少产生一次技能更新，即使很小；更新目标为类级别技能，每个技能有丰富的SKILL.md和引用文件；更新需通过skill_manage工具进行，且SKILL.md必须放在允许路径下。
§
vLLM 在 ds4-sm120 节点上的 CMake 配置因缺少 CUDA_nvrtc_LIBRARY 而失败，已安装 cuda-nvrtc-13-2 和 cuda-nvrtc-dev-13-2 但尚未验证修复效果。
§
在 ds4-sm120 节点上，vLLM 的 CMake 配置阶段因 CUDA_nvrtc_LIBRARY 链接问题失败，需要解决 nvrtc 依赖才能继续安装。
§
主机10.10.70.98的临时登录用户为qs，密码为!QAZ2wsx；需创建sudo用户jianliu，密码为!QAZ2wsx，并为其配置SSH密钥路径；后续登录应使用jianliu用户。
§
技能库更新流程要求：每次会话至少产生一个技能更新，即使很小；更新需通过 skill_manage 工具操作，且 SKILL.md 必须位于允许路径下（如 skills/ 目录），直接写入根目录 SKILL.md 会被拒绝。
§
技能库更新流程中，直接写入SKILL.md会被工具拒绝（不在允许路径下），必须通过skill_manage工具进行patch操作。
§
用户要求验证工作时不修改项目文件，仅通过源读取、shell检查、浏览器/网络证据或提供的工具句柄进行验证，并返回证据支持的检查结果和最终裁决（PASS/FAIL/PARTIAL）。
§
在 10.10.70.98 上创建了用户 jianliu，密码为 !QAZ2wsx，并配置了 SSH 密钥路径，后续登录使用 jianliu 作为用户名。