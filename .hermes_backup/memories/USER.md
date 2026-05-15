用户纠正数据时要求多数据源交叉验证，不要写不确定的数据。autohome页面参数可能存在错误，页面"暂无"不等于真的没有。
§
User prefers step-by-step operation with verification after each stage when doing multi-step operations (e.g., fix NCCL → verify → install nvcc → verify → compile nccl-tests → verify).
§
用户要求安装来自 https://clawhub.ai/wallstreetinsights/wallstreetcn-news 的 skill。
§
用户要求将备份功能扩展到所有数据库文件，而不仅仅是当前技能中的数据库。
§
用户重视对话上下文的连续性，当Hermes忘记之前说过的话（如"想吃披萨"然后问位置后又忘了目的）时会不满并被指正。需要始终保持任务目标跟踪，特别是在加载新技能或切换上下文时不能丢失原始用户需求。
§
用户调用了 codex-session 技能，要求遵循其指令，该技能用于显式调用 OpenAI Codex 并自动保持会话连续性。
§
用户要求助手在收到英文提示时只输出英文翻译，不附加其他语言或评论。
§
用户使用中文与Hermes交互，期望Hermes在调用Codex前将中文提示翻译成英文。
§
用户希望在使用Codex时，其中文输入应先被翻译成英文再执行，而不是直接传入中文。
§
用户使用中文与Hermes交互，期望Hermes将中文提示翻译成英文后再传给Codex。
§
用户期望 Hermes 在调用 Codex 前将中文提示翻译成英文。
§
用户要求在执行远程操作时遵循 remote-70-88 技能的指令，该技能涉及 SSH 连接、CUDA/nvcc 安装、NCCL 版本管理、编译 nccl-tests 和运行带宽测试。
§
用户要求主动更新技能库，即使变化很小也不应错过学习机会，且技能库应保持类级别结构，每个技能有丰富的 SKILL.md 和 references/ 目录，而不是扁平的长列表。
§
用户在一周前创建了一个名为 remote-70-88 的技能，但该技能现在不可见或无法使用。
§
用户偏好: 偏好更新应写入 SKILL.md（技能文件），而不是 memory。修改技能时优先使用 patch（skill_manage action='patch'）更新已加载的技能，而不是创建新技能。
§
不要将远程服务器脚本/报告备份到本地 Windows 路径 — 用户认为没必要。所有测试结果应通过 Notion 管理。
§
用户希望使用 GitHub 上 jasl/vllm 仓库的 ds4-sm120 分支来运行 vLLM 服务器，而非官方镜像。
§
用户希望使用远程 GPU 服务器 10.10.70.88 进行 vLLM 服务部署，使用 vllm/vllm-openai:latest 镜像。
§
用户希望使用远程GPU服务器10.10.70.88，并遵循remote-70-88技能中的工作流进行操作。