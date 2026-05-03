# PEP Mirofish — 课本人物 Agent 化预处理流水线

把人教版小学语文 3 上 / 3 下 / 4 上 / 4 下 共 4 册书的主要人物（约 10–15 个）做成 AI agent，
让它们针对用户给定主题进行角色对话。

本仓库 = MiroFish 的**前置预处理流水线**。MiroFish 已能在 :3000/:5001 跑通，
我们只补它没有的能力：PDF 拆分、多模态识图、跨课文角色合并、打包种子素材。

## 端到端流程

```
4 册 PDF
   ↓ step1_split   PyMuPDF 拆课文 + 导插图
   ↓ step2_clean   去页眉页脚/注音/版权页
   ↓ step3_vision  Qwen-VL-Max 识别课本插图人物（含「文本未点名」场景）
   ↓ step4_extract Qwen-Plus 抽角色：性格/爱好/关系/台词
   ↓ step5_merge   跨课文角色合并 → 主要人物表 (10-15 人)
   ↓ step6_review  Gradio UI 半自动审核
   ↓ step7_pack    打包 seed.md
   ↓
MiroFish 上传 seed.md → GraphRAG → persona → 多 agent 互动
```

## 目录约定

```
pdfs/                     # 放 4 册 PDF: 三上.pdf / 三下.pdf / 四上.pdf / 四下.pdf
pipeline/                 # 流水线脚本
artifacts/                # 中间产物 + 最终 seed.md
.env                      # DASHSCOPE_API_KEY / MIROFISH_DIR
```

## 安装

```bash
cd "/Users/moyipeng/Documents/Claude/Projects/PEP Mirofish"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填 DASHSCOPE_API_KEY 和 MIROFISH_DIR
```

## 跑流水线

```bash
# 仅跑某册先冒烟
python -m pipeline.step1_split --only 三上

# 全量
python -m pipeline.step1_split
# ... 后续 step2/3/4/5 见各 PR
```

## 跟 MiroFish 联调

预处理跑完后，`artifacts/seed.md` 通过 MiroFish UI 手动上传作为种子素材。
后续的 GraphRAG / persona / agent 由 MiroFish 自动完成。
