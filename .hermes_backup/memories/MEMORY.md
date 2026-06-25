User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
vLLM decode deadlock: 97% GPU util but /v1/completions hangs. Verify with /v1/models + quick POST before benchmarks. pkill requires USER CONSENT — user runs kill manually. GLM-5.1-NVFP4 on 70.96: TP8/bond0/bf16/prefix-cache, vllm-ds4 venv.
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
用户负责 WarpDriveAI 招聘，用 interview 技能管理简历、面试、入职。
§
70.93: WarpDrive TGU01-Pro x8(openEuler24.03,WD580.159.03). nvidia-smi blocked(stub exit 113,use wd-smi). No host CUDA/NCCL. Docker deepseek-v4-flash(NCCL 2.27.7+cuda13.0). backstage=198.18.0.206(SSH blocked). All servers pwd:!QAZ2wsx. SSH shorthand(70.92等)→70.0.0.x错误,必须完整IP(10.10.70.92). 70.92+96新增xuechenli/yirongpan(sudo,docker,!QAZ2wsx). vLLM at 192.168.12.12:19258(运行中,需API key)。
§
用户调用了 interview 技能，该技能用于管理 WarpDriveAI 的面试日程、候选人、简历和入职时间线。
§
单节点TP=8服务器在10.10.70.88:8000上运行，修复KV缓存问题后（gpu-memory-utilization=0.96, max-model-len=8192），GPU内存利用率50.8%，KV缓存约7.5 GiB。