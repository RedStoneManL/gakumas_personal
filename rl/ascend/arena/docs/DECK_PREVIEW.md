# 卡组图标预览接口

给人检查完整卡组的独立展示功能，接收现有训练入场包，不需要创建考试、启动 Node 或运行策略。显示输入顺序、每个副本、日文原名、强化、定制等级、成长、附加能力，以及入场包中的 P 道具、饮料、体力和已配置倍率。

## Python 调用

```python
from gakumas_arena import hif_round2_entry
from gakumas_arena.preview import write_deck_preview

entry = hif_round2_entry()  # 换成 RL 那边实际使用的完整 entry
path = write_deck_preview(entry, "outputs/deck.html", title="HIF 本战 2 · 当前卡组")
print(path)  # 返回绝对路径，用浏览器打开
```

默认从本地缓存读取原始 PNG，并把用到的图片嵌入 HTML。生成后的文件可以离线打开或直接发给他人，不需要附带图片文件夹。缓存缺图时才从固定的上游版本下载；已缓存的图片不会再次请求网络。

已有考试实例可传 `exam.export_entry()`；它表示开局补牌之前的入场卡组。要检视其他时点的卡组，调用方应明确传入该时点的副本列表并设置相应标题。列表顺序只表示传入顺序，不表示真实抽牌顺序。

也接受单独的卡牌列表：

```python
from gakumas_arena.preview import write_deck_preview

cards = [709, 709, {"definition_id": 647, "instance_id": "my-copy",
                    "customizations": {}, "growth": {"score": 5}, "bindings": []}]
path = write_deck_preview(cards, "outputs/custom-deck.html", idol_id=140)
```

`definition_id` 是 **gktools 的卡牌 ID**；不同强化版本有各自 ID。字典格式沿用 Arena 副本格式，整数会生成展示用的 `entry:000` 等副本 ID。`idol_id` 是 gktools **P 偶像 ID**，例如 140 对应广的角色 ID 8；展示器会转换后选择对应角色的卡面，不能直接把 140 拼入图片文件名。未知卡牌不会被删掉或猜成相似卡，会显示占位卡及 ID；预览不替代引擎合法性校验。

## 给其他程序的三个入口

| 接口 | 返回值与用途 |
|---|---|
| `deck_preview_data(entry_or_cards, **options)` | 可 JSON 序列化的展示数据；含 `arena-deck-preview/1`、逐副本信息、图片 data URL、统计和数据来源 hash，供其他前端使用 |
| `render_deck_html(entry_or_cards, **options)` | 完整 HTML 字符串，供本地 HTTP 服务返回或写入报告 |
| `write_deck_preview(entry_or_cards, output, **options)` | 写 HTML 文件，返回绝对 `Path`；自动创建父目录 |

共同选项：

| 选项 | 默认值与含义 |
|---|---|
| `title` | `"我的卡组"` |
| `idol_id` | `None`，读取 `entry.context.idol_id` |
| `image_source` | `"local"`，缓存并内嵌 PNG；显式选 `"github"` / `"gktools_cdn"` 才使用远程图片链接 |
| `cache_dir` | `None`，使用下面说明的共享缓存目录 |
| `allow_download` | `True`，仅下载缓存缺失或损坏的图；`False` 保证生成过程也不请求网络 |

此模块的公开导入路径是 `gakumas_arena.preview`，与计分执行入口分开。

完整入场包可以直接作为 JSON 请求体调用 `render_deck_html(payload)`，以 `text/html; charset=utf-8` 返回；不需要额外改卡组格式。本功能本身不启动服务或上传卡组。

## 命令行

```powershell
.venv/Scripts/python.exe -m gakumas_arena.preview docs/examples/training_ready/entry.json --output outputs/deck.html --title "HIF 本战 2 · 当前卡组"
```

输入文件可以是完整 entry，也可以是卡牌数组。浏览器预览支持按主动/精神/定制筛选、按卡名或 ID 搜索、点击查看各副本详情、打印或保存为 PDF。打印会包含所有卡牌，即便屏幕上使用了筛选。

## 本地图片库与离线生成

此仓库默认缓存目录为 `data/image_cache/<上游 commit>/`，相对于 Arena 仓库而非运行命令的工作目录。缓存包含原始 PNG；全量下载清单 `manifest.json` 记录来源版本、相对资源键、SHA-256、文件大小和失败项。缓存不打包进 Python 包，也不进入 Git。

需要换目录或多进程共享时，传 `cache_dir="D:/shared/arena-images"`，或设置环境变量 `GAKUMAS_ARENA_IMAGE_CACHE`。优先级是参数 → 环境变量 → 仓库默认目录；每个目录下按 commit 隔离版本。安装到只读 Python 环境时应指定可写目录。

一次下载当前版本的所有图标，包括角色变体、P 道具和饮料：

```powershell
.venv/Scripts/python.exe -m gakumas_arena.preview_images
```

当前索引共 **3,901 张**：3,396 张卡牌图标（含角色变体）、477 张 P 道具、28 张饮料。命令可以重复运行，复用已通过 PNG 完整性检查的文件；失败项会记入清单并返回非零退出码。支持 `--cache-dir`、`--workers 8`；加 `--offline` 只检查现有缓存。

预加载后，生成过程也可以禁止网络：

```python
write_deck_preview(entry, "outputs/deck.html", allow_download=False)
```

```powershell
.venv/Scripts/python.exe -m gakumas_arena.preview docs/examples/training_ready/entry.json --output outputs/deck.html --offline
```

本地缓存缺失或下载失败时，该图保留占位提示，并记录在 `deck_preview_data(...)["source"]["image_errors"]`；不会偷偷切回远程图片。`source.local_images` 给出命中缓存、下载成功和失败数量。修复缓存后重新生成 HTML 即可。

## 图标来源和边界

定义使用已固定的 golden 数据；图片文件索引来自同一上游版本 `6c3d00648c32ea72a05086a18c63ab62e0d0c7e5`，见 [图片索引来源](../gakumas_arena/preview_assets/PROVENANCE.json)。匹配顺序沿用上游：该角色版本 → 默认角色 6 版本 → 通用图标。

默认 HTML 的文字、图片、数据、样式和交互都在一个文件中，浏览时没有外部资源请求。原始 PNG 从固定 GitHub 版本下载到本地，图像校验通过后原样保存；HTML 中同时保留源 URL 和 SHA-256 供追溯。页面底部的来源链接只有点击时才访问上游。

当前固定索引覆盖 870 个卡牌定义中的 864 个；865–870 尚无对应图片索引，仍显示其完整卡名和定义。P 道具定义 478–484 也尚无对应图片索引。展示只调用已有定义，不修改 golden 文件、训练状态、计分或训练版本。原图中的数值不会被重绘为定制后的数值；定制、成长和附加能力单独显示。

验收：`.venv/Scripts/python.exe -m pytest tests/test_deck_preview.py -q`。示例见 [HIF 卡组预览](examples/deck_preview.html)。
