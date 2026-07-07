# kadong_cards_crawler

从卡动文创（kadongcc.com）批量下载卡牌图鉴。基于 IceSnowHelp API，支持 12 个 IP 自由筛选、增量下载与断点续传，一条命令完成全部卡牌图鉴采集。

## 为什么需要这个工具？

- 卡动文创收录了哆啦A梦、蜡笔小新、鬼刀、OVERLORD 等 12 个 IP 的数千张卡牌图鉴，但没有提供批量下载入口
- 手动右键保存每张卡牌图鉴效率极低，图鉴图片散布在多个系列页面中
- 官方数据通过 IceSnowHelp API 三级结构（IP → 系列 → 卡牌图鉴）组织，直接抓取需要理解 API 调用链
- 卡牌图鉴会持续更新，需要增量下载而非每次全量重爬

**kadong_cards_crawler解决这些问题**：一条命令爬取指定 IP 的全部卡牌图鉴，增量模式下仅下载新图鉴，已下载文件自动跳过。

## ⭐亮点

- **12 个 IP 全覆盖**：哆啦A梦、蜡笔小新、鬼刀、OVERLORD、汪汪队立大功、CF穿越火线、封神、三国志8 REMAKE、鹿溟山、少年歌行、一人之下拍立得撕撕乐、动物水浒
- **三级 API 直连**：ProductCategory（IP 列表）→ ProductCategory（系列列表）→ ArticleTwoList（卡牌图鉴全量加载），不依赖浏览器
- **多线程并发下载**：默认 5 线程并行，`-c` 可调并发数，大幅提升图鉴下载速度
- **灵活筛选**：`--ip` 指定 IP，`--series` 指定系列，均支持逗号分隔多选
- **自动导出 CSV**：下载完成后自动输出卡牌图鉴清单 CSV，包含 IP、系列、卡牌名、稀有度、图片 URL、本地路径
- **增量下载**：已下载文件自动跳过，仅下载新增图鉴，支持中断后恢复
- **断点续传**：卡牌图鉴索引一次性加载（limit=10000），下载失败不丢进度
- **结构化输出**：按 IP 名 → 系列名 → 卡牌图鉴名自动建目录

## 📸效果预览

CLI 运行效果：

```text
$ python kadong_cards_crawler.py --ip 哆啦A梦

正在获取 IP 列表...
找到 12 个 IP
筛选目标 IP: 哆啦A梦

正在获取「哆啦A梦」的系列列表...
  找到 15 个系列
  正在获取卡牌图鉴列表: 卡牌｜经典版｜第1弹
    8 个级别, 共 123 张卡牌图鉴
  ...

共 1708 张卡牌图鉴待处理，开始下载（并发 5）...
卡牌图鉴清单已导出: output/kadong_cards\kadong_cards.csv
100%|██████████████████████████████████████████████████████████████████████████████| 1708/1708 [08:45<00:00,  3.25张/s]
完成！成功 1708 张，跳过 0 张，失败 0 张
输出目录: output/kadong_cards
```

输出目录结构：

```text
output/kadong_cards/
├── 哆啦A梦/
│   ├── 卡牌｜经典版｜第1弹/
│   │   ├── CP-亲密伙伴卡-01.png
│   │   ├── R-经典角色卡-01.png
│   │   ├── SR-镭射闪光卡-01.png
│   │   └── ...
│   ├── 卡牌｜豪华版｜第1弹/
│   │   └── ...
│   └── ...
├── 三国志8 REMAKE/
│   └── 卡牌｜群雄逐鹿｜第1弹/
│       ├── CP-宿命双生卡-01.png
│       └── ...
└── kadong_cards.csv

卡牌图鉴清单导出示例：

​```csv
ip,series,card_name,rarity,image_url,local_path
三国志8 REMAKE,卡牌｜群雄逐鹿｜第1弹,豪杰卡-01,SR,https://kadongcc.com/UserFiles/Article/children1/_8QHp8ALs.png,output/kadong_cards\三国志8 REMAKE\卡牌｜群雄逐鹿｜第1弹\SR-豪杰卡-01.png
哆啦A梦,卡牌｜经典版｜第1弹,亲密伙伴卡-01,CP,https://kadongcc.com/UserFiles/Article/children1/_abc123.png,output/kadong_cards\哆啦A梦\卡牌｜经典版｜第1弹\CP-亲密伙伴卡-01.png
三国志8 REMAKE,卡牌｜群雄逐鹿｜第1弹,宿命双生卡-01,CP,https://kadongcc.com/UserFiles/Article/children1/_def456.png,output/kadong_cards\三国志8 REMAKE\卡牌｜群雄逐鹿｜第1弹\CP-宿命双生卡-01.png
```

| 列名 | 说明 |
|------|------|
| ip | IP 名称 |
| series | 系列名称（格式：`卡牌｜xx版｜第N弹` 或 `周边｜xx｜第N弹`） |
| card_name | 卡牌图鉴名称 |
| rarity | 稀有度（CP / CR / DR / EX / FP / FR / R / SR / SSR / UR / SSP / 特殊SSP 等） |
| image_url | 卡动原始图片 URL |
| local_path | 本地保存路径（相对路径），实际文件名包含稀有度前缀 |

## 🚀快速开始

### 1. 克隆项目

```bash
# Gitee 镜像（国内访问快）
git clone https://gitee.com/yhl5244/kadong_cards_crawler.git
cd kadong_cards_crawler

# GitHub 原仓库
git clone https://github.com/5244DragonLin/kadong_cards_crawler.git
cd kadong_cards_crawler
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行

```bash
# 下载全部 12 个 IP
python kadong_cards_crawler.py

# 只下载哆啦A梦
python kadong_cards_crawler.py --ip 哆啦A梦

# 下载多个 IP
python kadong_cards_crawler.py --ip 哆啦A梦,蜡笔小新,鬼刀

# 指定输出目录
python kadong_cards_crawler.py --ip 鬼刀 -o ./my_cards
```

### 4. 配置文件（可选）

复制示例配置并按需修改。**`--yaml` 参数默认即为 `config.yaml`，不传也会自动读取当前目录下的 `config.yaml`**，因此存在 `config.yaml` 时直接运行即可：

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml 修改输出目录、并发数等

# 方式一：不传 --yaml，自动加载当前目录的 config.yaml（最常用）
python kadong_cards_crawler.py

# 方式二：仅当配置文件改名或不在当前目录时，才需要显式指定
python kadong_cards_crawler.py --yaml /path/to/other_config.yaml
```

命令行参数优先级高于配置文件（如 `--ip`、`-o` 等会覆盖 `config.yaml` 中的同名项）。

`config.example.yaml` 中可配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api.base_url` | IceSnowHelp API 地址 | `kadongcc.com/ashx/...` |
| `download.output_dir` | 输出根目录 | `output/kadong_cards` |
| `download.concurrency` | 并发下载线程数 | `5` |
| `filters.ip` | 筛选 IP 名称（逗号分隔） | 空（全部） |
| `filters.series` | 筛选系列名称 | 空（全部） |
| `csv.path` | CSV 导出**文件**路径（含文件名，如 `output/kadong_cards.csv`；只填目录会报错） | 自动输出到 output 目录 |

> ⚠️ YAML 中路径建议使用正斜杠 `/`（如 `E:/BaiduSyncdisk/...`），脚本会自动兼容。

## ⌨️CLI 模式

```
python kadong_cards_crawler.py [选项]
```

### 筛选选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--ip` | 指定 IP，逗号分隔（如 哆啦A梦,蜡笔小新）。不传则下载全部 | 全部 |
| `--series` | 指定系列，逗号分隔（如 珍藏版,豪华版）。匹配系列名含指定关键词的系列 | 全部 |
| `--list-ip` | 列出所有可下载的 IP 名称后退出 | — |

### 下载选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-c, --concurrency` | 并发下载线程数 | `5` |
| `-o, --output` | 输出根目录 | `output/kadong_cards` |
| `--csv` | 导出卡牌清单 CSV 的**完整文件路径**（含文件名，如 `output/my_list.csv`；只填目录会报错） | `output/kadong_cards/kadong_cards.csv` |

## 📂项目结构

```text
卡动图鉴爬虫/
├── kadong_cards_crawler.py
├── requirements.txt
├── config.example.yaml  # 示例配置文件
├── README.md
├── LICENSE
└── .gitignore
```

## ❓️FAQ

**增量下载怎么用？**

直接重复运行相同命令。已下载的图鉴会自动跳过（按路径判断），仅下载新增卡牌图鉴。如果卡牌图鉴已更新，需要先删除旧文件再重新运行。

**下载中断了怎么办？**

重新运行相同命令。已下载的图鉴不会重复下载，从中断处继续即可。

**如何查看有哪些 IP？**

```bash
python kadong_cards_crawler.py --list-ip
```

**下载速度慢怎么办？**

增加并发数：`-c 10` 或更高。瓶颈在卡动 CDN 带宽，建议 5~10 个并发为宜，避免对服务器造成过大压力。

## 🤝贡献

欢迎提 Issue 和 PR！

### 已知问题 / 待改进点

- [ ] 支持下载同名卡牌图鉴的高清大图版本

### 贡献流程

Fork → 创建分支 → 提交修改 → 发起 Pull Request。

## 📋更新日志

### v1.0

- 首个可用版本

## 🔗 关联项目

- **[doraemon-card-collection](https://github.com/5244DragonLin/doraemon-card-collection)** — 哆啦A梦卡牌收藏站，使用本工具采集的图鉴目录生成 `data.js`
  - GitHub：https://github.com/5244DragonLin/doraemon-card-collection
  - Gitee：https://gitee.com/yhl5244/doraemon-card-collection

## ☕捐赠

你的支持是我坚持开源的动力。

| 支付宝 | 微信 |
|--------|------|
| ![支付宝](./assets/donate_alipay.jpg) | ![微信](./assets/donate_wechat.jpg) |

## ⚠️免责声明

本工具仅供学习交流使用，不得用于任何违反法律法规或侵犯第三方权益的用途。
因使用本工具产生的一切后果由使用者自行承担，作者不承担任何法律责任。

## 📃许可证

MIT
