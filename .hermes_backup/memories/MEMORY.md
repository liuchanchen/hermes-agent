用户使用 interview skill 管理招聘流程，文件路径含空格需用引号。PDF读取用 pypdf（pdftotext不可用）。日期用 `date "+%Y-%m-%d"` 确认，不要硬编码。面试时间表：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/面试时间表.md；入职时间表：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/入职时间表.md；候选人档案：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/候选人档案/
§
User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
面试管理技能已创建，包含5个核心功能：简历归档、简历摘要、面试时间表、入职时间表、候选人档案。文件路径约定：简历目录为 /mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/简历，下载目录为 /mnt/c/Users/liuch/Downloads，档案目录为 /mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/候选人档案，时间表为 .../招聘/面试时间表.md，入职表为 .../招聘/入职时间表.md。
§
每日3点运行的Dream Cron（ID: 1b38a660ab9a）执行四阶段流水线：calibrate → collect → merge → index，用于扫描新会话、提取重要信息、合并到MEMORY.md和USER.md、解决冲突并清理过时内容。
§
中国纯电车落地价：指导价27万的在沪落地约26.5-27万。免购置税和车船税，国家补贴约1-2万，保险上牌杂费约5000-8000元。
§
DeepSeek V4 Flash: vLLM 0.20.0 ignores all thinking params (chat_template_kwargs/reasoning_effort/extra_body.thinking). No thinking mode active. API: 192.168.12.12:19258, model /home/public/models/deepseekv4/, script ~/work/hermes-agent/run_vllm_deepseekv4.sh. Docker: --device='nvidia.com/gpu=all'.
§
用户询问将微信 Token 备份到 GitHub 是否存在安全问题。
§
有一个每日定时任务 'Daily Dream Refinement'，在每天 3:00 AM 运行，脚本为 ~/.hermes/scripts/dream_cycle.py，执行四阶段流水线（calibrate → collect → merge → index），用于扫描新会话、提取重要信息、合并到 MEMORY.md 和 USER.md、解决冲突并清理过时内容，结果仅本地保存。
§
用户调用了 codex-session 技能，要求遵循其指令，该技能用于显式调用 OpenAI Codex 并自动保持会话连续性。
§
Hermes 无法连接 ChatGPT 网页版，因为它没有公开的 API 接口。
§
Hermes 无法通过 ChatGPT 网页版（chatgpt.com）的 API 接口调用模型，因为网页版没有公开的 API 端点。
§
用户询问是否可以使用ChatGPT网页版来回答，Hermes明确告知不行，因为ChatGPT网页版没有公开的API接口，Hermes需要通过API端点调用模型。
§
Codex CLI 已升级到 0.128.0，模型为 gpt-5.5，会话续传功能正常，使用 ~/.codex/last_session_for_hermes 标记维持 active 状态。
§
用户要求使用 Codex 工具来调查中文提示未被翻译成英文的问题，而不是手动分析。
§
用户要求添加一个名为 claude-code-best 的技能，用于修改和检查内部代码。
§
当前 Verifier Agent 设计存在高优先级问题：不是可靠验证器（无工具/检索/执行能力，同模型）、强 fail-open 设计（空输出/缺少VERDICT/异常/空响应均通过）、prompt 注入漏洞（原始请求和响应直接拼接）、同模型 refine 可能使答案更差（无护栏）。
§
乐道L90各车型整备质量数据已从汽车之家获取，用户要求交叉验证。