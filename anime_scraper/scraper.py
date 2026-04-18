import asyncio
import time

try:
    from .scraper_2601 import get_today_recommend
    from .scraper_2604 import download_new_anime_datas as download_new_anime_datas_2604
    from .scraper_2601 import download_new_anime_datas as download_new_anime_datas_2601
except ImportError:
    from scraper_2601 import get_today_recommend
    from scraper_2604 import download_new_anime_datas as download_new_anime_datas_2604
    from scraper_2601 import download_new_anime_datas as download_new_anime_datas_2601

ROUTE_THRESHOLD = "202604"
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


def _resolve_scraper(schedule_time: str):
    if schedule_time >= ROUTE_THRESHOLD:
        return "2604", download_new_anime_datas_2604
    return "2601", download_new_anime_datas_2601


async def download_new_anime_datas(schedule_time: str) -> dict:
    _, scraper = _resolve_scraper(schedule_time)
    return await scraper(schedule_time)


def _safe_display_text(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    return value.encode("gbk", errors="replace").decode("gbk")


def _summarize_result(schedule_time: str, route_name: str, data: dict) -> tuple[str, dict]:
    daily_data = data.get("daily_anime", {})
    detail_data = data.get("anime_details", {})
    daily_count = len(daily_data)
    detail_count = len(detail_data)
    anime_count = sum(len(v) for v in daily_data.values() if isinstance(v, dict))

    sample_day = next(iter(daily_data), "-")
    sample_anime = "-"
    if sample_day != "-" and isinstance(daily_data.get(sample_day), dict) and daily_data[sample_day]:
        sample_anime = next(iter(daily_data[sample_day]))
    sample_detail = next(iter(detail_data), "-")

    issue_messages = []
    if schedule_time != "202007" and daily_count == 0:
        issue_messages.append("daily=0")
    if detail_count == 0:
        issue_messages.append("details=0")
    if detail_count > 0:
        invalid_detail_count = sum(
            1 for item in detail_data.values() if not item.get("anime_type") or item.get("anime_type") == "未知"
        )
        if invalid_detail_count > 0:
            issue_messages.append(f"unknown_type={invalid_detail_count}")

    result = {
        "route": route_name,
        "schedule_time": schedule_time,
        "daily_count": daily_count,
        "anime_count": anime_count,
        "detail_count": detail_count,
        "sample_day": sample_day,
        "sample_anime": sample_anime,
        "sample_detail": sample_detail,
        "issues": issue_messages,
    }
    status = "WARN" if issue_messages else "OK"
    return status, result


if __name__ == '__main__':
    success = []
    warnings = []
    failed = []
    total_start_time = time.time()

    for index, schedule_time in enumerate(TEST_SCHEDULE_TIMES, start=1):
        start_time = time.time()
        route_name, scraper = _resolve_scraper(schedule_time)
        try:
            data = asyncio.run(scraper(schedule_time))
            elapsed = time.time() - start_time
            status, result = _summarize_result(schedule_time, route_name, data)
            result["elapsed"] = elapsed

            if status == "WARN":
                warnings.append(result)
                print(
                    f"[WARN] ({index}/{len(TEST_SCHEDULE_TIMES)}) {schedule_time} route={route_name} "
                    f"daily={result['daily_count']} anime={result['anime_count']} details={result['detail_count']} "
                    f"sample_day={_safe_display_text(result['sample_day'])} sample_anime={_safe_display_text(result['sample_anime'])} "
                    f"sample_detail={_safe_display_text(result['sample_detail'])} issues={','.join(result['issues'])} elapsed={elapsed:.2f}s"
                )
            else:
                success.append(result)
                print(
                    f"[OK]   ({index}/{len(TEST_SCHEDULE_TIMES)}) {schedule_time} route={route_name} "
                    f"daily={result['daily_count']} anime={result['anime_count']} details={result['detail_count']} "
                    f"sample_day={_safe_display_text(result['sample_day'])} sample_anime={_safe_display_text(result['sample_anime'])} "
                    f"sample_detail={_safe_display_text(result['sample_detail'])} elapsed={elapsed:.2f}s"
                )
        except Exception as e:
            elapsed = time.time() - start_time
            failed.append((schedule_time, route_name, str(e), elapsed))
            print(
                f"[FAIL] ({index}/{len(TEST_SCHEDULE_TIMES)}) {schedule_time} route={route_name} "
                f"error={e} elapsed={elapsed:.2f}s"
            )

    total_elapsed = time.time() - total_start_time
    print("=" * 80)
    print(
        f"summary: success={len(success)} warn={len(warnings)} fail={len(failed)} total={len(TEST_SCHEDULE_TIMES)} elapsed={total_elapsed:.2f}s"
    )

    if warnings:
        print("warnings:")
        for item in warnings:
            print(
                f" - {item['schedule_time']} route={item['route']}: daily={item['daily_count']} anime={item['anime_count']} "
                f"details={item['detail_count']} issues={','.join(item['issues'])}"
            )

    if failed:
        print("failed schedules:")
        for schedule_time, route_name, error, elapsed in failed:
            print(f" - {schedule_time} route={route_name}: error={error} elapsed={elapsed:.2f}s")
