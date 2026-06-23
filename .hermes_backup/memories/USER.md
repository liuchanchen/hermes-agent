用户纠正数据时要求多数据源交叉验证，不要写不确定的数据。autohome页面参数可能存在错误，页面"暂无"不等于真的没有。
§
User prefers step-by-step operation with verification after each stage when doing multi-step operations (e.g., fix NCCL → verify → install nvcc → verify → compile nccl-tests → verify).
§
用户要求助手在收到英文提示时只输出英文翻译，不附加其他语言或评论。
§
用户要求主动更新技能库，即使变化很小也不应错过学习机会，且技能库应保持类级别结构，每个技能有丰富的 SKILL.md 和 references/ 目录，而不是扁平的长列表。
§
用户偏好: 偏好更新应写入 SKILL.md（技能文件），而不是 memory。修改技能时优先使用 patch（skill_manage action='patch'）更新已加载的技能，而不是创建新技能。
§
不要将远程服务器脚本/报告备份到本地 Windows 路径 — 用户认为没必要。所有测试结果应通过 Notion 管理。
§
用户希望使用 GitHub 上 jasl/vllm 仓库的 ds4-sm120 分支来运行 vLLM 服务器，而非官方镜像。
§
用户期望在每次会话结束后审查对话并主动更新技能库，将学到的技能和教训组织为CLASS级别条目，每个条目包含丰富的SKILL.md和references/目录。
§
GPU cluster ops engineer managing multi-node Blackwell (SM 12.0) servers. Deep vLLM expertise. Uses Chinese interaction, expects English before Codex. Prefers step-by-step with verification, structured matrix planning, quantifiable metrics. Demands active class-level skill library updates, real SSH commands not speculation.
§
用户管理 vLLM 2-node cluster (70.96 master + 70.98 worker) for DeepSeek V4 Pro, PP=2, RoCE v2 via bond0 (192.168.66.0/24). Actual RDMA IPs are 192.168.66.10/20 — 10.10.71.x subnet does not exist. RDMA device names differ per node: rocep200s0f0 on 96, mlx5_bond_0 on 98. Worker-first startup order recommended.
§
用户参与 WarpDriveAI 的招聘工作，负责管理面试时间表、候选人简历和入职时间线。