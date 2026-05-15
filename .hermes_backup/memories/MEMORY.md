用户使用 interview skill 管理招聘流程。文件路径含空格需用引号。PDF 读取用 pypdf。日期用 `date "+%Y-%m-%d"` 确认。简历目录：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/简历；候选人档案：.../候选人档案/；面试时间表：.../面试时间表.md；入职时间表：.../入职时间表.md。
§
User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
面试管理技能已创建，包含5个核心功能：简历归档、简历摘要、面试时间表、入职时间表、候选人档案。文件路径约定：简历目录为 /mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/简历，下载目录为 /mnt/c/Users/liuch/Downloads，档案目录为 /mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/候选人档案，时间表为 .../招聘/面试时间表.md，入职表为 .../招聘/入职时间表.md。
§
在 vLLM 0.20.0 中，即使配置了 --reasoning-parser deepseek_v4，Hermes 模型也无法通过任何已知参数格式（包括 extra_body.chat_template_kwargs、reasoning_effort、extra_body.reasoning、extra_body.thinking.type）激活思考模式，所有测试均返回 reasoning: null。
§
用户要求技能库更新为类级别技能，每个技能包含丰富的SKILL.md和references/目录，而不是扁平的一会话一技能的条目列表。
§
用户确认在Hermes CLI中启用了show_reasoning: true后，看到了Reasoning内容，但该内容实际上是模型在content中输出的普通CoT（chain-of-thought），并非DeepSeek thinking mode的reasoning_content字段。API返回的response中只有'323'（2个token），没有reasoning_content字段，说明thinking mode并未真正激活。
§
技能收集的目标是构建一个类级别指令和经验知识的库，每个技能应是宽泛的伞状技能并带有标记的子部分，而不是多个狭窄的技能。
§
Hermes 的 Curator 后台进程在 2026-05-06 06:15 UTC 自动运行，将 remote-70-88 和 remote-70-66 技能吸收进 remote-deploy umbrella 技能，随后将 remote-deploy 作为过时技能删除，导致三个技能全部消失。
§
Long IO 16384/16384 测试默认运行次数为 2 次，而非之前声称的 1 次。
§
用户通过调用 remote-70-88 技能，要求使用 vllm/vllm-openai:latest 镜像在远程 GPU 服务器 10.10.70.88 上启动 vLLM 服务。
§
70.95: MiniMax-M2.7-NVFP4, DP=8+EP, 8×RTX 5090 (32 GB), --max-model-len 16384, --gpu-memory-utilization 0.96, start script at /data/venvs/vllm-ds4/start_minimax_m2_nvfp4_70.95.sh
§
用户通过调用 remote-70-88 技能，要求使用 SSH 连接 GPU 服务器 10.10.70.88 进行远程操作，包括 CUDA 安装、NCCL 管理、编译 nccl-tests 和运行带宽测试。
§
Long IO 16384/16384 测试运行次数为 2 次，而非之前声称的 1 次。
§
用户要求验证工作结果时不得修改项目文件，只能通过源读取、shell检查、浏览器/网络证据或提供的工具句柄进行验证，并返回基于证据的检查结果和最终裁决（PASS/FAIL/PARTIAL）。
§
远程 GPU 服务器 10.10.70.88 上运行着 vLLM 服务，监听端口 8000，使用 4 张 NVIDIA GeForce RTX 5090 GPU，每张显存使用约 30GB。
§
用户要求重新运行 test_deepseekv4_throughput_cache.py 脚本，并发数分别为 32 和 64。