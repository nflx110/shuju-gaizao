# -*- coding: utf-8 -*-
import json
import urllib.request


GROUP_IDS = [535, 852, 853, 854, 855, 999, 1000, 1001, 1002, 1174, 1579, 1608, 1630, 1631, 1655]


def calculate_monitor_count() -> int:
    total_num = 0
    for group in GROUP_IDS:
        get_url = f"http://qamp.qiyi.domain/get_case_list/?group_id={group}&_=1730891788826"
        with urllib.request.urlopen(get_url, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if len(res.get("case_list") or []) > 0:
            for item in res["case_list"]:
                if item.get("is_valid"):
                    total_num += 1
    return total_num
