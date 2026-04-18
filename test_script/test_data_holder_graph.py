import asyncio
import sys
import traceback
from pathlib import Path
from typing import Any

PLUGIN_DIR = Path(__file__).resolve().parent
SCRAPER_DIR = PLUGIN_DIR / "anime_scraper"
for path in (PLUGIN_DIR, SCRAPER_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from data_holder import DataHolder  # noqa: E402

TEST_SCHEDULE_TIMES = [
    "202604",
    "202601",
    "202510",
    "202507",
    "202504",
    "202501",
    "202410",
    "202407",
    "202404",
    "202401",
    "202310",
    "202307",
    "202304",
    "202301",
    "202210",
    "202207",
    "202204",
    "202201",
    "202110",
    "202107",
    "202104",
    "202101",
    "202010",
    "202007",
    "202004",
    "202001",
    "201910",
]


class CheckRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.total = 0

    def _emit(self, status: str, stage: str, label: str, detail: str = "") -> None:
        suffix = f" | {detail}" if detail else ""
        print(f"[{status}][{stage}] {label}{suffix}")

    def pass_(self, stage: str, label: str, detail: str = "") -> None:
        self.total += 1
        self.passed += 1
        self._emit("PASS", stage, label, detail)

    def fail(self, stage: str, label: str, detail: str = "") -> None:
        self.total += 1
        self.failed += 1
        self._emit("FAIL", stage, label, detail)

    def error(self, stage: str, label: str, exc: BaseException) -> None:
        self.total += 1
        self.errors += 1
        self._emit("ERROR", stage, label, repr(exc))
        print(traceback.format_exc())

    def check_true(self, stage: str, label: str, value: Any, detail: str = "") -> bool:
        if value:
            self.pass_(stage, label, detail)
            return True
        self.fail(stage, label, detail or f"value={value!r}")
        return False

    def check_equal(self, stage: str, label: str, actual: Any, expected: Any) -> bool:
        if actual == expected:
            self.pass_(stage, label, f"expected={expected!r}")
            return True
        self.fail(stage, label, f"actual={actual!r}, expected={expected!r}")
        return False

    def check_contains(self, stage: str, label: str, actual: Any, expected: str) -> bool:
        if actual is None:
            self.fail(stage, label, f"actual=None, expected to contain {expected!r}")
            return False
        if isinstance(actual, (list, tuple, set)):
            hit = any(expected in str(item) for item in actual)
        else:
            hit = expected in str(actual)
        if hit:
            self.pass_(stage, label, f"contains={expected!r}")
            return True
        self.fail(stage, label, f"actual={actual!r}, expected to contain {expected!r}")
        return False

    def summary(self) -> int:
        print("\n=== Summary ===")
        print(f"total: {self.total}")
        print(f"passed: {self.passed}")
        print(f"failed: {self.failed}")
        print(f"errors: {self.errors}")
        return 0 if self.failed == 0 and self.errors == 0 else 1


def get_schedule_data(holder: DataHolder, schedule_time: str) -> dict[str, Any]:
    return holder.anime_datas.get(schedule_time, {})


def get_raw_detail(holder: DataHolder, schedule_time: str, anime_name: str) -> dict[str, Any] | None:
    return get_schedule_data(holder, schedule_time).get("anime_details", {}).get(anime_name)


def get_raw_daily(holder: DataHolder, schedule_time: str, weekday: str, anime_name: str) -> dict[str, Any] | None:
    return get_schedule_data(holder, schedule_time).get("daily_anime", {}).get(weekday, {}).get(anime_name)


def query_pairs(holder: DataHolder, anime_name: str) -> dict[str, list[str]]:
    rows = holder.select_with_sparql(
        f"""
        SELECT ?p ?o
        WHERE {{
            <anime://{anime_name}> ?p ?o .
        }}
        """
    )
    result: dict[str, list[str]] = {}
    for predicate, obj in rows:
        result.setdefault(predicate, []).append(obj)
    return result


def query_same_cv_anime(holder: DataHolder, anime_name: str) -> list[str]:
    rows = holder.select_with_sparql(
        f"""
        SELECT DISTINCT ?otherAnime
        WHERE {{
            <anime://{anime_name}> <anime://配音演员> ?cv .
            ?otherAnime <anime://配音演员> ?cv .
            FILTER (?otherAnime != <anime://{anime_name}>)
        }}
        """
    )
    return [row[0].replace("anime://", "") for row in rows]


async def detail_of(holder: DataHolder, anime_name: str) -> dict[str, Any]:
    details = await holder.get_anime_detail(anime_name)
    if not details:
        return {}
    return details[0]


def print_debug_context(
    holder: DataHolder,
    schedule_time: str,
    anime_name: str,
    weekday: str | None = None,
) -> None:
    print(f"--- DEBUG {schedule_time} / {anime_name} ---")
    raw_detail = get_raw_detail(holder, schedule_time, anime_name)
    print(f"raw_detail={raw_detail}")
    if weekday is not None:
        raw_daily = get_raw_daily(holder, schedule_time, weekday, anime_name)
        print(f"raw_daily={raw_daily}")
    print(f"graph_pairs={query_pairs(holder, anime_name)}")


def check_graph_value(
    runner: CheckRunner,
    pairs: dict[str, list[str]],
    label: str,
    predicate: str,
    expected: str,
) -> None:
    runner.check_contains("GRAPH", label, pairs.get(predicate, []), expected)


async def verify_fetch_health(runner: CheckRunner, holder: DataHolder, schedule_time: str) -> None:
    data = get_schedule_data(holder, schedule_time)
    daily = data.get("daily_anime", {})
    details = data.get("anime_details", {})
    runner.check_true("FETCH", f"{schedule_time} data exists", bool(data))
    runner.check_true("FETCH", f"{schedule_time} daily_anime non-empty", bool(daily), f"count={len(daily)}")
    runner.check_true(
        "FETCH", f"{schedule_time} anime_details non-empty", bool(details), f"count={len(details)}"
    )


async def verify_old_samples(runner: CheckRunner, holder: DataHolder) -> None:
    schedule_time = "202107"

    white = get_raw_detail(holder, schedule_time, "白砂水族馆")
    runner.check_true("RAW", "202107 白砂水族馆 detail exists", white is not None)
    if white:
        runner.check_equal("RAW", "白砂水族馆 日文名", white.get("title_jp"), "白い砂のアクアトープ")
        runner.check_contains("RAW", "白砂水族馆 类型", white.get("anime_type", ""), "原创")
        runner.check_contains("RAW", "白砂水族馆 标签", white.get("tags", []), "青春")
        runner.check_contains("RAW", "白砂水族馆 导演", white.get("staff", {}).get("导演", ""), "篠原俊哉")
        runner.check_contains("RAW", "白砂水族馆 cast", white.get("cast", []), "伊藤美来")
        runner.check_contains("RAW", "白砂水族馆 放送开始", white.get("broadcast", {}).get("time", ""), "7/8")
    else:
        print_debug_context(holder, schedule_time, "白砂水族馆")

    love_live = get_raw_detail(holder, schedule_time, "LoveLive! SuperStar!!")
    runner.check_true("RAW", "202107 LoveLive detail exists", love_live is not None)
    if love_live:
        runner.check_equal("RAW", "LoveLive 日文名", love_live.get("title_jp"), "ラブライブ！スーパースター!!")
        runner.check_contains("RAW", "LoveLive 标签", love_live.get("tags", []), "偶像")
        runner.check_contains("RAW", "LoveLive 放送开始", love_live.get("broadcast", {}).get("time", ""), "7/11")
    else:
        print_debug_context(holder, schedule_time, "LoveLive! SuperStar!!")

    maid = get_raw_detail(holder, schedule_time, "小林家的龙女仆 第2期")
    runner.check_true("RAW", "202107 龙女仆 detail exists", maid is not None)
    if maid:
        runner.check_equal("RAW", "龙女仆 日文名", maid.get("title_jp"), "小林さんちのメイドラゴンS")
        runner.check_contains("RAW", "龙女仆 类型", maid.get("anime_type", ""), "漫画")
        runner.check_contains("RAW", "龙女仆 放送开始", maid.get("broadcast", {}).get("time", ""), "7/7")
        runner.check_contains("RAW", "龙女仆 cast", maid.get("cast", []), "田村睦心")
    else:
        print_debug_context(holder, schedule_time, "小林家的龙女仆 第2期")

    white_graph = query_pairs(holder, "白砂水族馆")
    check_graph_value(runner, white_graph, "白砂水族馆 档期", "anime://档期", "202107")
    check_graph_value(runner, white_graph, "白砂水族馆 日文名", "anime://日文名", "白い砂のアクアトープ")
    check_graph_value(runner, white_graph, "白砂水族馆 番剧类型", "anime://番剧类型", "原创动画")
    check_graph_value(runner, white_graph, "白砂水族馆 tag", "anime://tag", "青春")
    check_graph_value(runner, white_graph, "白砂水族馆 导演", "anime://导演", "篠原俊哉")
    check_graph_value(runner, white_graph, "白砂水族馆 配音演员", "anime://配音演员", "伊藤美来")
    check_graph_value(runner, white_graph, "白砂水族馆 放送开始日期", "anime://放送开始日期", "7/8")

    love_graph = query_pairs(holder, "LoveLive! SuperStar!!")
    check_graph_value(runner, love_graph, "LoveLive 档期", "anime://档期", "202107")
    check_graph_value(runner, love_graph, "LoveLive tag", "anime://tag", "偶像")
    check_graph_value(runner, love_graph, "LoveLive 放送开始日期", "anime://放送开始日期", "7/11")
    love_detail = await detail_of(holder, "LoveLive")
    runner.check_true("GRAPH", "LoveLive 模糊查询命中", bool(love_detail), str(love_detail))

    maid_graph = query_pairs(holder, "小林家的龙女仆 第2期")
    check_graph_value(runner, maid_graph, "龙女仆 档期", "anime://档期", "202107")
    check_graph_value(runner, maid_graph, "龙女仆 番剧类型", "anime://番剧类型", "漫画改编")
    check_graph_value(runner, maid_graph, "龙女仆 放送开始日期", "anime://放送开始日期", "7/7")
    check_graph_value(runner, maid_graph, "龙女仆 配音演员", "anime://配音演员", "田村睦心")


async def verify_new_samples(runner: CheckRunner, holder: DataHolder) -> None:
    schedule_time = "202604"
    weekday = "周一 (月)"

    monday = get_schedule_data(holder, schedule_time).get("daily_anime", {}).get(weekday, {})
    runner.check_true("FETCH", "202604 周一数据存在", bool(monday), f"count={len(monday)}")

    samples = [
        ("尖帽子的魔法工坊", "22:00~", "4/6"),
        ("欺诈游戏", "23:00~", "4/6"),
        ("木头风纪委员和迷你裙JK的故事", "22:30~", "4/6"),
        ("自称恶役千金的婚约者观察记录", "21:00~", "4/6"),
    ]

    for anime_name, update_time, start_time in samples:
        daily_info = get_raw_daily(holder, schedule_time, weekday, anime_name)
        runner.check_true("RAW", f"202604 {anime_name} 周一条目存在", daily_info is not None)
        if daily_info:
            runner.check_contains("RAW", f"{anime_name} 周一时间", daily_info.get("state", []), update_time)
        else:
            print_debug_context(holder, schedule_time, anime_name, weekday)

        detail = get_raw_detail(holder, schedule_time, anime_name)
        runner.check_true("RAW", f"202604 {anime_name} detail exists", detail is not None)
        if detail:
            runner.check_contains(
                "RAW", f"{anime_name} 放送开始", detail.get("broadcast", {}).get("time", ""), start_time
            )
        else:
            print_debug_context(holder, schedule_time, anime_name, weekday)

        pairs = query_pairs(holder, anime_name)
        check_graph_value(runner, pairs, f"{anime_name} 档期", "anime://档期", schedule_time)
        check_graph_value(runner, pairs, f"{anime_name} 更新日", "anime://更新日", weekday)
        check_graph_value(runner, pairs, f"{anime_name} 更新时间", "anime://更新时间", update_time)
        check_graph_value(runner, pairs, f"{anime_name} 放送开始日期", "anime://放送开始日期", start_time)


async def verify_multi_hop_queries(runner: CheckRunner, holder: DataHolder) -> None:
    same_cv_white = query_same_cv_anime(holder, "白砂水族馆")
    runner.check_true("GRAPH", "白砂水族馆 同配音演员结果非空", bool(same_cv_white), str(same_cv_white[:10]))
    runner.check_contains("GRAPH", "白砂水族馆 同配音演员命中 RE-MAIN", same_cv_white, "RE-MAIN")
    runner.check_contains("GRAPH", "白砂水族馆 同配音演员命中 D_CIDE TRAUMEREI", same_cv_white, "D_CIDE TRAUMEREI")

    same_cv_maid = query_same_cv_anime(holder, "小林家的龙女仆 第2期")
    runner.check_true("GRAPH", "龙女仆 同配音演员结果非空", bool(same_cv_maid), str(same_cv_maid[:10]))
    runner.check_contains("GRAPH", "龙女仆 同配音演员命中 白砂水族馆", same_cv_maid, "白砂水族馆")
    runner.check_contains("GRAPH", "龙女仆 同配音演员命中 暗夜第六感2041", same_cv_maid, "暗夜第六感2041")

    same_cv_witch = query_same_cv_anime(holder, "尖帽子的魔法工坊")
    runner.check_true("GRAPH", "尖帽子的魔法工坊 同配音演员结果非空", bool(same_cv_witch), str(same_cv_witch[:10]))


async def main() -> int:
    runner = CheckRunner()
    holder = DataHolder()
    fetch_failed_schedules: list[str] = []

    print("=== Paths ===")
    print(f"plugin_dir={PLUGIN_DIR}")
    print(f"scraper_dir={SCRAPER_DIR}")
    print(f"anime_datas_path={holder.anime_datas_path}")
    print(f"anime_graph_path={holder.anime_graph_path}")
    print(f"all_anime_names_save_path={holder.all_anime_names_save_path}")
    print(f"initial_graph_triples={len(holder.anime_graph)}")
    print(f"initial_all_names={len(holder.all_anime_names)}")
    print(f"test_schedule_times={TEST_SCHEDULE_TIMES}")

    # for schedule_time in TEST_SCHEDULE_TIMES:
    #     try:
    #         print(f"\n=== Re-fetch {schedule_time} ===")
    #         await holder.update_anime_datas(schedule_time)
    #         await verify_fetch_health(runner, holder, schedule_time)
    #     except Exception as exc:
    #         fetch_failed_schedules.append(schedule_time)
    #         runner.error("FETCH", f"re-fetch {schedule_time}", exc)

    print(f"\nfetch_failed_schedules={fetch_failed_schedules}")

    if "202107" not in fetch_failed_schedules:
        try:
            await verify_old_samples(runner, holder)
        except Exception as exc:
            runner.error("RAW", "verify old-format samples", exc)
    else:
        runner.fail("RAW", "skip old-format samples", "202107 re-fetch failed")

    if "202604" not in fetch_failed_schedules:
        try:
            await verify_new_samples(runner, holder)
        except Exception as exc:
            runner.error("RAW", "verify new-format samples", exc)
    else:
        runner.fail("RAW", "skip new-format samples", "202604 re-fetch failed")

    try:
        await verify_multi_hop_queries(runner, holder)
    except Exception as exc:
        runner.error("GRAPH", "verify multi-hop queries", exc)

    return runner.summary()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
