用户纠正数据时要求多数据源交叉验证，不要写不确定的数据。autohome页面参数可能存在错误，页面"暂无"不等于真的没有。
§
User prefers step-by-step operation with verification after each stage when doing multi-step operations (e.g., fix NCCL → verify → install nvcc → verify → compile nccl-tests → verify).
§
用户要求每天晚上10点执行/dongchedi-l90-watch脚本，结果需要包含商家地址信息和车型信息，新增和下架的信息需要额外给出，最后给出车型统计。
§
用户要求安装来自 https://clawhub.ai/wallstreetinsights/wallstreetcn-news 的 skill。
§
用户希望添加一个技能，将 .hermes_backup 推送到远程 GitHub，提交信息格式为 'backup hermes ' + 日期。
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