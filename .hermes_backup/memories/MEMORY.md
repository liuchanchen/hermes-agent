User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
GLM-5.1-FP8 Blackwell: TP8 PP2 EP8, TRITON_MLA+eager+block64. SM12 shared mem 99KB < Triton's 100KB = enforce-eager needed. Skill: mlops/glm5-fp8-blackwell.
§
用户要求技能库更新为类级别技能，每个技能包含丰富的SKILL.md和references/目录，而不是扁平的一会话一技能的条目列表。
§
vLLM decode deadlock: 97% GPU util but /v1/completions hangs. Verify with /v1/models + quick POST before benchmarks. pkill requires USER CONSENT — user runs kill manually. GLM-5.1-NVFP4 on 70.96: TP8/bond0/bf16/prefix-cache, vllm-ds4 venv.
§
技能收集的目标是构建一个类级别指令和经验知识的库，每个技能应是宽泛的伞状技能并带有标记的子部分，而不是多个狭窄的技能。
§
70.88: venv /data/venvs/vllm-ds4/, models /data/models/ (Qwen3.6-35B, deepseekv4_pro), ~/work/models/deepseekv4_flash(149G). Proxy 10.60.140:7890. ens20f0=100Mb/s(瓶颈), ens35f0np0/1 DOWN.
§
RTX 5090 32GB OOM with Wan2.2-T2V-A14B: model loads ~29.6 GiB leaving no headroom. Use cpu_offload flags (--vae-cpu-offload, --text-encoder-cpu-offload, --dit-cpu-offload) to reduce GPU memory.
§
远程服务器 10.10.70.93 (oem93)、10.10.70.95 (oem95)、10.10.70.96 (oem96) 已配置免密码 SSH 密钥认证，用户 jianliu 可通过 ssh jianliu@<IP> 直接登录，旧密码 !QAZ2wsx 不再需要。
§
免密码 SSH: 70.88/92/95/96/98。70.93/94需密码(!QAZ2wsx)。Cluster: 70.96 master + 70.98 worker, PP=2, RoCE v2 bond0 (192.168.66.0/24). RDMA: 192.168.66.10/20. Worker-first startup.
§
70.98: /data/models/(dsv4_pro,glm5_fp8,dsv4_flash,Qwen3.6-35B-A3B-FP8,Qwen3.6-35B-A3B-NVFP4). Docker v29.4.0+vllm/vllm-openai:nightly image loaded. gcc→gcc-11. vllm build: CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11'. SSH 88→98可,98→88不可. ens20f0=100Mb/s瓶颈,bond0=100GbE. vllm bench脚本: ~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/
§
70.92: 8×RTX 5090 32GB, Gold 6530×2. NCCL 2.28.9. /data/venvs/vllm-ds4/ needs Python3.12 (deadsnakes ppa). DS-V4-Flash at /home/public/models/tgu01/deepseekv4_flash/. /data/ owned by rapidsdb—sudo needed. No proxy. sudo:!QAZ2wsx.
§
用户使用 'interview' 技能管理 WarpDriveAI 的招聘流程，包括候选人简历、面试时间表、入职时间线和候选人档案。