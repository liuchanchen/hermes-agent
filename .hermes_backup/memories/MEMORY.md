设置了全局验证 agent：修改 run_agent.py，添加了 _call_llm_simple、_verify_response、_refine_response 方法和验证闭环。验证 agent 只看原始需求+最终输出，不看中间步骤。最多5轮静默迭代。patch 在 ~/.hermes/patches/001-verify-agent.patch。git pull 后需重新 apply。
§
用户纠正了我的错误：之前写的乐道L90价格(21.99-26.99万)是错误的。正确价格是26.58-29.98万（2025款，6款配置）。用户要求多数据源交叉验证，不要写不确定的数据。
§
autohome车型ID：乐道L90=8045，零跑D19=8273。autohome数据可能有误，零跑D19转弯半径3.6m用户存疑（可能是三电机版本特有，非全系统一）。
§
懂车帝乐道L90监控：
- dongchedi_watch 是 Python 脚本：/home/jianliu/work/hermes-agent/tools/dongchedi_tool.py
- 运行方式：cd /home/jianliu/work/hermes-agent && source venv/bin/activate && python tools/dongchedi_tool.py --list-url "..." --max-details 30 --headed
- 使用 crawl4ai 库进行爬取，需要浏览器自动化
- 定时任务ID: 7c1e45b92026，每晚22:00执行，deliver已设为origin
- 数据库：~/.hermes/dongchedi_l90.db (SQLite)
- 历史输出：~/.hermes/cron/output/dongchedi_l90_YYYYMMDD.json
§
用户使用 interview skill 管理招聘流程，文件路径含空格需用引号。PDF读取用 pypdf（pdftotext不可用）。日期用 `date "+%Y-%m-%d"` 确认，不要硬编码。面试时间表：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/面试时间表.md；入职时间表：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/入职时间表.md；候选人档案：/mnt/c/Users/liuch/My Documents/warpdriveai/制度/招聘/候选人档案/
§
User requires all model calls to use max thinking/reasoning effort globally. Set agent.reasoning_effort: xhigh and delegation.reasoning_effort: xhigh in config.yaml. Note: "xhigh" is the highest available effort level — "max" is not a valid config value.
§
Remote 10.10.70.88: jianliu, sudo password="!QAZ2wsx", Ubuntu 22.04, 8× RTX 5090 (CC 12.0), driver 580.126.09, CUDA 13.0, nvcc 13.0.88, NCCL 2.28.9-1+cuda13.0, nccl-tests @ ~/work/bandwidth_test/nccl-tests/build/. DeepSeek-V4-Flash @ ~/work/models/deepseekv4_flash/ (149G). vLLM script @ ~/work/vllm_server/run_vllm_deepseekv4.sh (expert-parallel). Docker 29.4 CDI quirk: --gpus all fails, use --device='nvidia.com/gpu=all'. nvidia-container-toolkit installed.
§
Cron 健康检查 & 自动恢复机制：
- Job ID: 5aea5a03c148，每天18:00执行
- 数据收集脚本：~/.hermes/scripts/cron_health_collector.py（检查cron output目录+agent.log中的delivery error）
- 诊断逻辑：检查cronjob list的last_status和last_delivery_error
- 自动修复：执行失败→cronjob(action='run')重新执行；推送失败→读取cached output用send_message重新发送
- enabled_toolsets: [terminal, web, search]