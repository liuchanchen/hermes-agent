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
70.88: venv /data/venvs/vllm-ds4/, ens20f0=100Mb/s瓶颈, ens35f0np0/1 DOWN.
§
RTX 5090 32GB OOM with Wan2.2-T2V-A14B: model loads ~29.6 GiB leaving no headroom. Use cpu_offload flags (--vae-cpu-offload, --text-encoder-cpu-offload, --dit-cpu-offload) to reduce GPU memory.
§
Servers: SSH key:88/92/95/96/98; pwd:93/94(!QAZ2wsx). 70.88(RTX5090×8,Xeon8558P,proxy). 70.92(RTX5090×8,Gold6530,vllm0.6.0.dev0). 70.98(Blackwell 98GB×8,vllm0.1.dev1+ds4-sm120). 70.96+98 cluster PP=2 RoCEv2 bond0.
§
Cluster: 70.96+98 PP=2 RoCEv2 bond0(192.168.66.0/24), RDMA 192.168.66.10/20, worker-first startup.
§
DS-V4-Flash bench (2048in/500out, TP8+EP): 70.92(RTX5090×8,16K) 0%=570tok/s,40%=655,80%=976; 70.98(Blackwell×8,16K) 0%=646tok/s,40%=805,80%=1019; 70.98(Blackwell×8,1M) 0%=309tok/s,40%=351,80%=407. 1M context: TPOT +126%, throughput -52% vs 16K. Blackwell +13-23% throughput, -41% TTFT@0%cache vs RTX5090.
§
70.92: /data/venvs/vllm-ds4/, /data/vllm-ds4-sm120/, DS-V4-Flash at /data/models/deepseekv4_flash, /data/ chown'd jianliu, cudagraph_mode(not wdgraph_mode).
§
用户使用 'interview' 技能管理 WarpDriveAI 的招聘流程，包括候选人简历、面试时间表、入职时间线和候选人档案。
§
用户负责 WarpDriveAI 的招聘工作，使用 interview 技能管理候选人简历、面试时间表和入职时间线。
§
User is involved in hiring processes for WarpDriveAI, managing interview timetables, candidates, resumes, and onboard timelines.