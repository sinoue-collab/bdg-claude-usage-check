#!/usr/bin/env python3
"""BDG 追加集計: Claude Code の「任せ方」の数字を共有ドライブに書く。

元の道具（claude-usage-check v0.1.0）の collect が書く <名前>.json に加えて、
<名前>.stats.json を書く。会話の本文・ファイル名は保存しない（数字だけ）。

使い方:
  python3 bdg_stats.py            # 集計して共有ドライブに書く
  python3 bdg_stats.py --dry-run  # 書かずに結果だけ見る
  python3 bdg_stats.py --markdown [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                  # summary.md に貼る「数字のまとめ」を出す
設定は元の道具の ~/.claude-usage-check/config.json（名前・格納先）をそのまま使う。
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime

VERSION = "3"

# 日本の祝日（振替休日・国民の休日を含む）。内閣府の「国民の祝日」の一覧から。
# この一覧に無い年は、祝日を見分けずに月〜金を平日として数える（年が変わる前に足す）
JP_HOLIDAYS = set("""
2025-01-01 2025-01-13 2025-02-11 2025-02-23 2025-02-24 2025-03-20 2025-04-29 2025-05-03 2025-05-04
2025-05-05 2025-05-06 2025-07-21 2025-08-11 2025-09-15 2025-09-23 2025-10-13 2025-11-03 2025-11-23
2025-11-24
2026-01-01 2026-01-12 2026-02-11 2026-02-23 2026-03-20 2026-04-29 2026-05-03 2026-05-04 2026-05-05
2026-05-06 2026-07-20 2026-08-11 2026-09-21 2026-09-22 2026-09-23 2026-10-12 2026-11-03 2026-11-23
2027-01-01 2027-01-11 2027-02-11 2027-02-23 2027-03-21 2027-03-22 2027-04-29 2027-05-03 2027-05-04
2027-05-05 2027-07-19 2027-08-11 2027-09-20 2027-09-23 2027-10-11 2027-11-03 2027-11-23
""".split())


def is_weekday_daytime(ts):
    """平日（月〜金で、祝日でない日）の 9:00〜17:59 か（PC の時刻）"""
    return ts.weekday() < 5 and ts.date().isoformat() not in JP_HOLIDAYS and 9 <= ts.hour < 18
JPY_PER_USD = 150  # 円換算のレート（仮・2026-11-21。井上が決めたら直す）
BREAK_MINUTES = 10  # これより長く空いたら休憩とみなす
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude-usage-check", "config.json")
SUBDIR = "claude-usage"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PC_TOOL_HINTS = ("claude-in-chrome", "computer-use", "computer_", "Claude_Browser", "orca computer",
                 "playwright")
AUTO_PROMPT_HEADS = ("<scheduled-task",)  # スケジュール済みのタスクが自動で入れる発言
NOT_HUMAN_HEADS = ("<task-notification", "<local-command-stdout", "<local-command-stderr",
                   "<local-command-caveat", "<bash-stdout", "<bash-stderr",
                   "<command-name>/clear", "<command-name>/compact",
                   "[Request interrupted")  # 人が打った依頼ではない自動の挿入・操作


def human_prompt_head(d):
    """人が打った発言なら先頭の文字（40字まで）を返す。そうでなければ None。

    CLAUDE.md の C-1 と同じ定義:
      - type が user、サブエージェント（isSidechain）・自動挿入（isMeta）・圧縮の要約（isCompactSummary）でない
      - 本文が文字列、または文字のまとまり（Orca・デスクトップ版）。道具の結果（tool_result）を含むものは除く
    自動実行の判定（<scheduled-task）はここでは除かず、呼び出し側で行う。
    """
    if d.get("type") != "user" or d.get("isSidechain") or d.get("isMeta") or d.get("isCompactSummary"):
        return None
    c = (d.get("message") or {}).get("content")
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        texts = [b.get("text") or "" for b in c if isinstance(b, dict) and b.get("type") == "text"]
        if not texts:
            return None
        c = texts[0]
    if not isinstance(c, str):
        return None
    return c.lstrip()[:40]


def claude_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json_atomic(path, data):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def safe_filename(name):
    s = re.sub(r'[\\/:*?"<>|\s]+', "_", name.strip())
    return s[:60] or "member"


def parse_ts(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return None


def new_day():
    return {"human_prompts": 0, "daytime_prompts": 0, "ai_responses": 0, "tool_calls": 0, "file_edits": 0,
            "files_edited": set(), "work_minutes": 0.0, "pc_ops": 0,
            "auto_sessions": 0, "auto_responses": 0, "auto_tool_calls": 0, "auto_minutes": 0.0}


def collect():
    files = glob.glob(os.path.join(claude_dir(), "projects", "**", "*.jsonl"), recursive=True)
    sessions = defaultdict(lambda: {"entrypoint": None, "first_prompt": None, "first_ts": None,
                                    "times": [], "events": []})
    seen_msg, seen_tool, seen_uuid = set(), set(), set()
    for path in files:
        try:
            f = open(path, encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with f:
            for line in f:
                if '"type":"user"' not in line and '"type":"assistant"' not in line \
                        and '"type": "user"' not in line and '"type": "assistant"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                t = d.get("type")
                ts = parse_ts(d.get("timestamp"))
                sid = d.get("sessionId")
                if t not in ("user", "assistant") or ts is None or not sid:
                    continue
                s = sessions[sid]
                s["times"].append(ts)
                if s["entrypoint"] is None and d.get("entrypoint"):
                    s["entrypoint"] = d["entrypoint"]
                msg = d.get("message") or {}
                if t == "user":
                    head = human_prompt_head(d)
                    if head is None or head.startswith(NOT_HUMAN_HEADS):
                        continue
                    if s["first_ts"] is None or ts < s["first_ts"]:
                        s["first_ts"], s["first_prompt"] = ts, head
                    if head.startswith(AUTO_PROMPT_HEADS):
                        continue
                    uid = d.get("uuid")
                    if uid:  # 会話を再開したときに、前の履歴が写されて二重になるのを防ぐ
                        if uid in seen_uuid:
                            continue
                        seen_uuid.add(uid)
                    s["events"].append((ts, "prompt", None))
                    continue
                model = msg.get("model") or ""
                if model.startswith("<"):
                    continue
                key = (msg.get("id"), d.get("requestId"))
                if key == (None, None) or key not in seen_msg:
                    # 1つの応答が何行にも分かれて記録されることがあるので、1回だけ数える
                    if key != (None, None):
                        seen_msg.add(key)
                    s["events"].append((ts, "response", None))
                for b in msg.get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    bid = b.get("id")
                    if bid:
                        if bid in seen_tool:
                            continue
                        seen_tool.add(bid)
                    name = b.get("name") or ""
                    fp = None
                    if name in EDIT_TOOLS:
                        inp = b.get("input") or {}
                        p = inp.get("file_path") or inp.get("notebook_path") or ""
                        fp = hashlib.sha1(p.encode("utf-8")).hexdigest()[:12] if p else None
                    s["events"].append((ts, "tool", (name, fp)))
    days = defaultdict(new_day)
    all_times = {False: [], True: []}  # 人が操作した会話 / 自動実行 の時刻をまとめる
    for sid, s in sessions.items():
        ep = s["entrypoint"] or ""
        auto = ep.startswith("sdk") or (s["first_prompt"] or "").startswith(AUTO_PROMPT_HEADS)
        all_times[auto].extend(s["times"])
        if s["first_ts"] is not None and auto:
            days[s["first_ts"].date().isoformat()]["auto_sessions"] += 1
        for ts, kind, extra in s["events"]:
            r = days[ts.date().isoformat()]
            if kind == "prompt":
                if not auto:
                    r["human_prompts"] += 1
                    if is_weekday_daytime(ts):  # 平日（祝日を除く）9:00〜17:59
                        r["daytime_prompts"] += 1
            elif kind == "response":
                r["ai_responses"] += 1
                if auto:
                    r["auto_responses"] += 1
            else:
                name, fp = extra
                r["tool_calls"] += 1
                if auto:
                    r["auto_tool_calls"] += 1
                if name in EDIT_TOOLS:
                    r["file_edits"] += 1
                    if fp:
                        r["files_edited"].add(fp)
                if any(h in name for h in PC_TOOL_HINTS):
                    r["pc_ops"] += 1
    # 作業時間: 会話ごとではなく、全部の会話の時刻をまとめてから足す。
    # 同時に開いた複数の会話や、再開で写された履歴の時間を二重に数えないため
    for auto, times in all_times.items():
        times = sorted(set(times))
        for a, b in zip(times, times[1:]):
            gap = (b - a).total_seconds() / 60.0
            if gap <= BREAK_MINUTES:
                days[b.date().isoformat()]["auto_minutes" if auto else "work_minutes"] += gap
    out = {}
    for day, r in days.items():
        item = dict(r)
        item["files_edited"] = len(r["files_edited"])
        item["work_minutes"] = round(r["work_minutes"], 1)
        item["auto_minutes"] = round(r["auto_minutes"], 1)
        out[day] = item
    return out, len(files)


def config():
    cfg = load_json(CONFIG_PATH)
    if not cfg or not cfg.get("name") or not cfg.get("dest"):
        print("エラー: まだ設定されていません。先に claude-usage-check の setup を実行してください。",
              file=sys.stderr)
        sys.exit(1)
    return cfg


def out_paths(cfg):
    base = os.path.join(cfg["dest"], SUBDIR, safe_filename(cfg["name"]))
    return base + ".json", base + ".stats.json"


def cmd_collect(a):
    cfg = config()
    days, nfiles = collect()
    if not days:
        print("エラー: Claude Code のログが見つかりませんでした。", file=sys.stderr)
        sys.exit(1)
    _, stats_path = out_paths(cfg)
    old = load_json(stats_path) or {}
    merged = dict(old.get("days") or {}) if old.get("member") == cfg["name"] else {}
    merged.update(days)  # 同じ日は新しい数字で上書き。ログが消えた古い日は残す
    data = {"tool": "bdg_stats", "version": VERSION, "member": cfg["name"],
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "jpy_per_usd": JPY_PER_USD, "break_minutes": BREAK_MINUTES,
            "days": dict(sorted(merged.items()))}
    tot = defaultdict(float)
    for r in days.values():
        for k, v in r.items():
            tot[k] += v
    print("読んだログ: %d ファイル / 期間: %s 〜 %s" % (nfiles, min(days), max(days)))
    print("人の発言 %d / AI の応答 %d / AI の動作 %d / ファイル編集 %d / 作業時間 %.0f 分 / 自動実行 %d 回"
          % (tot["human_prompts"], tot["ai_responses"], tot["tool_calls"], tot["file_edits"],
             tot["work_minutes"], tot["auto_sessions"]))
    if a.dry_run:
        print("（--dry-run なので書き込んでいません）")
        return
    write_json_atomic(stats_path, data)
    print("書き込みました: " + stats_path)


def in_range(day, d_from, d_to):
    return (not d_from or day >= d_from) and (not d_to or day <= d_to)


def fmt_tok(n):
    if n >= 1e6:
        return "%.1fM" % (n / 1e6)
    if n >= 1e3:
        return "%.0fK" % (n / 1e3)
    return "%d" % n


def fmt_minutes(m):
    m = int(round(m))
    return "%d時間%02d分" % (m // 60, m % 60) if m >= 60 else "%d分" % m


def cmd_markdown(a):
    cfg = config()
    usage_path, stats_path = out_paths(cfg)
    usage = (load_json(usage_path) or {}).get("days") or {}
    stats = (load_json(stats_path) or {}).get("days") or {}
    rate = (load_json(stats_path) or {}).get("jpy_per_usd") or JPY_PER_USD
    days = sorted(d for d in set(usage) | set(stats) if in_range(d, a.d_from, a.d_to))
    if not days:
        print("（対象期間のデータがありません）")
        return
    T = defaultdict(float)
    models = defaultdict(lambda: defaultdict(float))
    rows = []
    fallback_days = 0
    for d in days:
        u, s = usage.get(d) or {}, stats.get(d) or {}
        cost = u.get("cost_usd") or 0
        # 人の発言は日ごとに決める: 追加集計（stats）がある日はその数、無い日だけ元の道具の数で補う
        if d in stats:
            hp = s.get("human_prompts", 0)
        else:
            hp = u.get("prompts") or 0
            if hp:
                fallback_days += 1
        resp = u.get("responses") if d in usage else s.get("ai_responses", 0)
        resp = resp or 0
        T["cost"] += cost
        T["prompts"] += hp
        T["responses"] += resp
        for k in ("human_prompts", "daytime_prompts", "tool_calls", "file_edits", "files_edited", "work_minutes",
                  "pc_ops", "auto_sessions", "auto_responses", "auto_tool_calls", "auto_minutes",
                  "ai_responses"):
            T[k] += s.get(k) or 0
        for name, m in (u.get("models") or {}).items():
            tok = sum(m.get(k) or 0 for k in ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h"))
            models[name]["responses"] += m.get("responses") or 0
            models[name]["tokens"] += tok
            models[name]["cost"] += m.get("cost_usd") or 0
            T["tokens"] += tok
        if hp:  # 使った日 ＝ 人の発言がある日（自動実行だけの日は数えない。元の道具の active_days と同じ）
            T["active_days"] += 1
        if hp or resp:
            rows.append("| %s | %d | %d | %d | %s | ¥%s |" % (
                d, hp, resp, s.get("tool_calls") or 0,
                fmt_minutes(s.get("work_minutes") or 0), "{:,.0f}".format(cost * rate)))
    first, last = a.d_from or days[0], a.d_to or days[-1]
    span = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days + 1
    manual_tools = T["tool_calls"] - T["auto_tool_calls"]
    makase = manual_tools / T["human_prompts"] if T["human_prompts"] else 0
    auto_pct = 100.0 * T["auto_responses"] / T["ai_responses"] if T["ai_responses"] else 0
    L = []
    L.append("## 量（どれだけ使ったか）")
    L.append("")
    L.append("- 対象: %s 〜 %s" % (first, last))
    L.append("- 人の発言: %d 回（スケジュール済みのタスクなどが自動で入れた発言は除く）／ AI の応答: %d 回"
             % (T["prompts"], T["responses"]))
    L.append("- トークン: %s ／ API 換算の金額: 約 ¥%s（$%.2f。1ドル=%d円で換算）"
             % (fmt_tok(T["tokens"]), "{:,.0f}".format(T["cost"] * rate), T["cost"], rate))
    L.append("- 使った日数: %d 日（期間 %d 日のうち。人の発言がある日）" % (T["active_days"], span))
    if T["human_prompts"]:
        day_pct = 100.0 * T["daytime_prompts"] / T["human_prompts"]
        L.append("- 使用時間帯: 平日日中 %.0f%%・夜間/休日 %.0f%%（人の発言の時刻。平日日中＝月〜金・祝日を除く 9:00〜18:00）"
                 % (day_pct, 100 - day_pct))
    L.append("")
    L.append("**モデル別の内訳**")
    L.append("")
    L.append("| モデル | 応答 | トークン | 金額 |")
    L.append("|---|---:|---:|---:|")
    for name, m in sorted(models.items(), key=lambda x: -x[1]["cost"]):
        L.append("| %s | %d | %s | ¥%s |" % (name, m["responses"], fmt_tok(m["tokens"]),
                                             "{:,.0f}".format(m["cost"] * rate)))
    L.append("")
    L.append("**日別の推移**（人か AI の動きがあった日だけ）")
    L.append("")
    L.append("| 日付 | 人の発言 | AI の応答 | AI の動作 | 作業時間 | 金額 |")
    L.append("|---|---:|---:|---:|---:|---:|")
    L.extend(rows)
    L.append("")
    L.append("## 任せ方（どう使ったか）")
    L.append("")
    L.append("- 任せ度: 発言1回あたり AI が **%.1f 回** 動いた（人が操作した会話の、AI の道具の使用 %d 回 ÷ 人の発言 %d 回）"
             % (makase, manual_tools, T["human_prompts"]))
    L.append("- AI と作業した時間: **%s**（人が操作した会話。%d 分以上空いたら休憩とみなす）"
             % (fmt_minutes(T["work_minutes"]), BREAK_MINUTES))
    L.append("- 自動実行の割合: AI の応答の **%.0f%%**（自動実行 %d 回・%s。スケジュール済みのタスクとアプリの自動処理）"
             % (auto_pct, T["auto_sessions"], fmt_minutes(T["auto_minutes"])))
    L.append("- ファイルの編集: **%d 回**（のべ %d ファイル）" % (T["file_edits"], T["files_edited"]))
    L.append("- ブラウザ・PC 操作を AI に任せた回数: %d 回" % T["pc_ops"])
    if fallback_days:
        L.append("")
        L.append("※ %d 日分は追加集計（stats.json）が無いため、人の発言は元の道具の数で補った。"
                 "任せ方の数字（任せ度・作業時間など）にはその日は入っていない。" % fallback_days)
    print("\n".join(L))


def main():
    p = argparse.ArgumentParser(description="BDG 追加集計（任せ方の数字）")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--markdown", action="store_true")
    p.add_argument("--from", dest="d_from")
    p.add_argument("--to", dest="d_to")
    a = p.parse_args()
    for v in (a.d_from, a.d_to):
        if v and not DATE_RE.match(v):
            print("エラー: 日付は YYYY-MM-DD の形で指定してください（例: 2026-11-01）: " + v, file=sys.stderr)
            sys.exit(1)
    if a.markdown:
        cmd_markdown(a)
    else:
        cmd_collect(a)


if __name__ == "__main__":
    main()
