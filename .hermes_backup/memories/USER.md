用户纠正数据时要求多数据源交叉验证，不要写不确定的数据。autohome页面参数可能存在错误，页面"暂无"不等于真的没有。
§
User: step-by-step operation with verification after each stage (NCCL fixes, benchmarks, config changes)
§
用户要求主动更新技能库，即使变化很小也不应错过学习机会，且技能库应保持类级别结构，每个技能有丰富的 SKILL.md 和 references/ 目录，而不是扁平的长列表。
§
用户偏好: 偏好更新应写入 SKILL.md（技能文件），而不是 memory。修改技能时优先使用 patch（skill_manage action='patch'）更新已加载的技能，而不是创建新技能。
§
不要将远程服务器脚本/报告备份到本地 Windows 路径 — 用户认为没必要。所有测试结果应通过 Notion 管理。
§
用户期望在每次会话结束后审查对话并主动更新技能库，将学到的技能和教训组织为CLASS级别条目，每个条目包含丰富的SKILL.md和references/目录。
§
WarpDriveAI GPU engineer. Manages vLLM clusters: 70.88(8×RTX5090,DS-V4-Flash), 70.96+98(TGU SM12.0,GLM5.2+DS-V4-Pro). Chinese-speaking, prefers direct execution+step-verify. Use official scripts directly. Active skill updates each session.
§
70.96+70.98: DS-V4-Pro PP=2, RDMA 192.168.66.10/20, worker-first startup
§
用户参与 WarpDriveAI 招聘，管理面试日程和候选人（interview skill）。使用两种标签: `test`(测试)、`algo`(算法/工程)。期望批量操作（批量归档简历、批量打标签、批量删除）。通过简历文件名结构化模式推断候选人信息。
§
70.88(8×RTX5090)单节点DS-V4-Flash: start_dsv4_flash_1node.sh; bench: run_vllm_bench_serve.sh(吞吐) + run_vllm_decode_bench_serve.sh(解码变并发). Workflow: kill+vrfy mem→restart→health→bench w/ env vars(CONCURRENCY,REQUESTS)
§
用户坚持模型数据必须实际复制到目标节点本地磁盘，不接受符号链接替代方案。用户对"命令被阻塞"的反馈方式是直接拒绝（而不是纠正参数），要求尊重其准入决策。用户期望在单次会话中持续完成任务直到用户明确更改目标，不满足于便捷方案。
§
长任务(权重复制/传输)须实时报告速度(MB/s)、进度%与ETA。
§
报告文件位置时须区分宿主机vs容器内路径，注明所在镜像与查看命令（用户会去宿主机核对）。