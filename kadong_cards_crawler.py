#!/usr/bin/env python3
"""Kadong Cards Crawler - Batch download card images from kadongcc.com.

Fetch IP → Series → Cards three-level data via IceSnowHelp API,
support IP/series filtering, concurrent downloads, CSV export,
incremental download and resume from breakpoint.
"""

import argparse
import csv
import yaml
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm


API_BASE = "https://kadongcc.com/ashx/IceSnowHelp.ashx"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://kadongcc.com/",
}

_session_local = threading.local()


def _get_session():
    if not hasattr(_session_local, "session"):
        _session_local.session = requests.Session()
        _session_local.session.headers.update(HEADERS)
    return _session_local.session


def api_call(action: str, **params) -> dict:
    """调用 IceSnowHelp API，返回 JSON 数据。"""
    payload = {"action": action, **params}
    resp = requests.post(API_BASE, data=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    # API 偶尔返回空响应，打印诊断信息
    if not resp.text.strip():
        print(f"[诊断] action={action} HTTP {resp.status_code}, body 为空 (len={len(resp.content)}), "
              f"headers={dict(resp.headers)}")
        raise ValueError(f"API 返回空响应 (action={action})")
    # 强制 UTF-8 编码
    resp.encoding = "utf-8"
    return resp.json()


def list_ips() -> list[dict]:
    """获取所有 IP 列表。"""
    result = api_call("ProductCategory", pid="0", tc="Products", page=1, pagesite=100)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("list", result.get("data", []))
    return []


def list_series(ip_id: str) -> list[dict]:
    """获取指定 IP 下的全部系列。"""
    result = api_call("ProductCategory", pid=ip_id, tc="Products", page=1, pagesite=100)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("list", result.get("data", []))
    return []


def list_cards(series_id: str) -> list[dict]:
    """获取指定系列下的全部卡牌（一次性加载，limit=10000）。"""
    result = api_call("ArticleTwoList", cid=series_id, tc="Products", page=1, limit=10000, dataorder="DataOrder desc")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("list", result.get("data", []))
    return []


def extract_card_images(card: dict) -> list[dict]:
    """从卡牌对象中提取所有图片（主图 + 关联图），含稀有度。"""
    images = []
    rarity = card.get("Title", card.get("Name", ""))
    # 主卡牌信息
    main = {
        "title": card.get("Title", card.get("Name", "未命名")),
        "picture": card.get("Picture", ""),
        "rarity": rarity,
        "id": card.get("ID", ""),
    }
    if main["picture"]:
        images.append(main)
    
    # 关联图片（RelaRelationIDList）
    rel_list = card.get("RelaRelationIDList", [])
    if isinstance(rel_list, list):
        for rel in rel_list:
            if rel.get("TypeCode") == "children1" and rel.get("Picture"):
                images.append({
                    "title": rel.get("Title", main["title"]),
                    "picture": rel.get("Picture", ""),
                    "rarity": rarity,
                    "id": rel.get("ID", ""),
                })
    return images


def build_image_url(picture: str) -> str:
    """拼接卡牌图片完整 URL。"""
    if not picture:
        return ""
    picture = picture.lstrip("/")
    if picture.startswith("http"):
        return picture
    return f"https://kadongcc.com/UserFiles/Article/children1/{picture}"


def sanitize_name(name: str) -> str:
    """去除文件名中的非法字符。"""
    for ch in r'<>:"/\|?*':
        name = name.replace(ch, "_")
    return name.strip()


def download_single(task: dict) -> dict:
    """下载单张图片（供线程池调用），返回结果字典。"""
    url = task["url"]
    save_path = task["save_path"]

    if os.path.exists(save_path):
        return {"status": "skip", "path": save_path}

    try:
        resp = _get_session().get(url, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 0:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return {"status": "success", "path": save_path}
    except Exception:
        pass
    return {"status": "fail", "path": save_path}


def export_csv(cards_list: list[dict], csv_path: str):
    """导出卡牌清单为 CSV 文件，保留已有 URL 信息。"""
    fieldnames = ["ip", "series", "card_name", "rarity", "image_url", "local_path"]
    file_exists = os.path.exists(csv_path)

    # 使用字典存储记录，key -> record
    existing_records_dict: dict[tuple, dict] = {}
    
    # 如果 CSV 文件存在，读取已有记录（保留URL信息）
    if file_exists:
        # 兼容 utf-8-sig / gbk 两种编码的旧 CSV
        encodings = ["utf-8-sig", "gbk", "utf-8"]
        for enc in encodings:
            try:
                with open(csv_path, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        key = (row["ip"], row["series"], row["card_name"], row.get("rarity", ""))
                        existing_records_dict[key] = row
                break
            except (UnicodeDecodeError, ValueError):
                continue
    
    # 无论 CSV 是否存在，都扫描输出目录下的所有卡牌图片
    output_dir = os.path.dirname(csv_path)
    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                    # 从路径解析 IP 和系列信息
                    rel_path = os.path.relpath(root, output_dir)
                    parts = rel_path.split(os.sep)
                    if len(parts) >= 2:
                        ip_name = parts[0]
                        series_name = parts[1]
                        # 从文件名解析稀有度和卡牌名
                        filename = os.path.splitext(file)[0]
                        if '-' in filename:
                            rarity, card_name = filename.split('-', 1)
                        else:
                            rarity = ""
                            card_name = filename
                        
                        key = (ip_name, series_name, card_name, rarity)
                        if key not in existing_records_dict:
                            # 构建完整记录
                            local_path = os.path.join(root, file)
                            rel_local_path = os.path.relpath(local_path, output_dir)
                            existing_records_dict[key] = {
                                "ip": ip_name,
                                "series": series_name,
                                "card_name": card_name,
                                "rarity": rarity,
                                "image_url": "",  # 本地文件没有 URL
                                "local_path": rel_local_path
                            }
                        else:
                            # 更新本地路径（如果路径有变化）
                            existing_records_dict[key]["local_path"] = os.path.relpath(os.path.join(root, file), output_dir)

    # 添加新下载的卡牌记录（覆盖本地扫描的记录，因为新记录有URL）
    for card in cards_list:
        key = (card["ip"], card["series"], card["card_name"], card.get("rarity", ""))
        existing_records_dict[key] = {
            "ip": card["ip"],
            "series": card["series"],
            "card_name": card["card_name"],
            "rarity": card["rarity"],
            "image_url": card["image_url"],
            "local_path": card["local_path"]
        }

    if not existing_records_dict:
        return

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    # 总是重新写入完整 CSV，包含所有卡牌
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in existing_records_dict.values():
            writer.writerow({
                "ip": record["ip"],
                "series": record["series"],
                "card_name": record["card_name"],
                "rarity": record["rarity"],
                "image_url": record.get("image_url", ""),
                "local_path": record["local_path"],
            })


def load_config(config_path: str = "config.yaml") -> dict:
    """从 YAML 配置文件加载配置并扁平化为 argparse 参数字典。

    优先级: config.yaml > config.example.yaml > 空字典
    """
    import os as _os

    for path in (config_path, _os.path.splitext(config_path)[0] + ".example.yaml",
                  "config.example.yaml"):
        if _os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                return _flatten_config(data)
            except Exception:
                continue
    return {}


def _flatten_config(data: dict) -> dict:
    """将嵌套的 YAML 配置扁平化为 argparse 参数名。"""
    flat = {}

    dl = data.get("download", {})
    if isinstance(dl, dict):
        if dl.get("output_dir"):
            flat["output"] = dl["output_dir"]
        if dl.get("concurrency") is not None:
            flat["concurrency"] = dl["concurrency"]

    filters = data.get("filters", {})
    if isinstance(filters, dict):
        if filters.get("ip"):
            flat["ip"] = filters["ip"]
        if filters.get("series"):
            flat["series"] = filters["series"]

    csv_cfg = data.get("csv", {})
    if isinstance(csv_cfg, dict) and csv_cfg.get("path"):
        flat["csv"] = csv_cfg["path"]

    return flat


def main():
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--yaml", "-y", default="config.yaml")
    pre_args, _ = pre_parser.parse_known_args()
    yaml_defaults = load_config(pre_args.yaml)

    parser = argparse.ArgumentParser(description="Kadong Cards Crawler")
    parser.add_argument("--yaml", "-y", default="config.yaml", help="YAML 配置文件路径（CLI 参数优先级高于配置文件）")
    parser.add_argument("--ip", type=str, default="", help="指定 IP，逗号分隔（如 哆啦A梦,奥特曼），不传则下载全部")
    parser.add_argument("--series", type=str, default="", help="指定系列，逗号分隔（如 珍藏版,豪华版），不传则下载全部")
    parser.add_argument("-o", "--output", type=str, default="output/kadong_cards", help="输出根目录")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="并发下载数（默认 5）")
    parser.add_argument("--csv", type=str, default="", help="导出卡牌清单 CSV 的路径（默认自动输出到 output 目录下）")
    parser.add_argument("--list-ip", action="store_true", help="列出所有可下载的 IP 名称后退出")
    if yaml_defaults:
        parser.set_defaults(**yaml_defaults)
    args = parser.parse_args()

    # 获取 IP 列表
    print("正在获取 IP 列表...")
    ips = list_ips()
    if not ips:
        print("未获取到 IP 列表，请检查网络或 API 是否正常。")
        sys.exit(1)
    print(f"找到 {len(ips)} 个 IP")

    # --list-ip 模式
    if args.list_ip:
        for ip in ips:
            print(f"  - {ip.get('Name', ip.get('name', '未知'))} (ID: {ip.get('ID', ip.get('id', ''))})")
        return

    # 筛选目标 IP
    target_names = [n.strip() for n in args.ip.split(",") if n.strip()] if args.ip else []
    if target_names:
        matched = []
        for ip in ips:
            name = ip.get("Name", ip.get("name", ""))
            if any(tn in name for tn in target_names):
                matched.append(ip)
        if not matched:
            print(f"未找到匹配的 IP: {', '.join(target_names)}")
            print("可用 IP:", ", ".join(ip.get("Name", ip.get("name", "")) for ip in ips))
            sys.exit(1)
        ips = matched
        print(f"筛选目标 IP: {', '.join(ip.get('Name', ip.get('name', '')) for ip in ips)}")

    # 筛选目标系列
    target_series = [n.strip() for n in args.series.split(",") if n.strip()] if args.series else []

    # 收集所有下载任务
    all_tasks = []
    csv_records = []

    for ip in ips:
        ip_name = ip.get("Name", ip.get("name", "未知"))
        ip_id = ip.get("ID", ip.get("id", ""))

        print(f"\n正在获取「{ip_name}」的系列列表...")
        series_list = list_series(str(ip_id))
        if not series_list:
            print(f"  「{ip_name}」没有系列数据，跳过")
            continue
        print(f"  找到 {len(series_list)} 个系列")

        for series in series_list:
            series_name = series.get("Name", series.get("name", ""))
            series_id = series.get("ID", series.get("id", ""))

            # 系列筛选
            if target_series and not any(ts in series_name for ts in target_series):
                continue

            print(f"  正在获取卡牌列表: {series_name}")
            rarity_tiers = list_cards(str(series_id))
            if not rarity_tiers:
                print(f"    没有卡牌数据")
                continue
            total_images = 0
            for tier in rarity_tiers:
                images = extract_card_images(tier)
                total_images += len(images)
            print(f"    {len(rarity_tiers)} 个级别, 共 {total_images} 张卡牌")

            for tier in rarity_tiers:
                images = extract_card_images(tier)
                if not images:
                    continue

                for img in images:
                    card_name = img["title"]
                    picture = img["picture"]

                    url = build_image_url(picture)
                    ext = os.path.splitext(url.split("?")[0])[1] or ".png"
                    filename = sanitize_name(f"{img['rarity']}-{card_name}") + ext
                    save_dir = os.path.join(args.output, sanitize_name(ip_name), sanitize_name(series_name))
                    save_path = os.path.join(save_dir, filename)

                    all_tasks.append({"url": url, "save_path": save_path})
                    csv_records.append({
                        "ip": ip_name,
                        "series": series_name,
                        "card_name": card_name,
                        "rarity": img["rarity"],
                        "image_url": url,
                        "local_path": save_path,
                    })

    if not all_tasks:
        print("没有需要下载的卡牌。")
        return

    print(f"\n共 {len(all_tasks)} 张卡牌待处理，开始下载（并发 {args.concurrency}）...")

    # 导出 CSV
    csv_path = args.csv if args.csv else os.path.join(args.output, "kadong_cards.csv")
    export_csv(csv_records, csv_path)
    print(f"卡牌清单已导出: {csv_path}")

    # 并发下载
    total_success = 0
    total_skip = 0
    total_fail = 0

    with tqdm(total=len(all_tasks), unit="张") as pbar:
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {executor.submit(download_single, t): t for t in all_tasks}
            for future in as_completed(futures):
                result = future.result()
                if result["status"] == "success":
                    total_success += 1
                elif result["status"] == "skip":
                    total_skip += 1
                else:
                    total_fail += 1
                pbar.update(1)

    print(f"\n完成！成功 {total_success} 张，跳过 {total_skip} 张，失败 {total_fail} 张")
    print(f"输出目录: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
