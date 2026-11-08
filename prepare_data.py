"""Build the dashboard CSVs from the verified Busan workbook."""

import argparse
import csv
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook


DATA_DIR = Path(__file__).resolve().parent / "data"


def write_csv(name, fields, rows):
    with (DATA_DIR / name).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        writer.writerows(rows)


def prepare(workbook_path):
    book = load_workbook(workbook_path, read_only=True, data_only=True, keep_links=False)
    try:
        areas = {}
        for row in book["집계표_값"].iter_rows(min_row=3, max_col=17, values_only=True):
            code, food, total, population, name = (row[i] for i in (0, 10, 11, 12, 16))
            if code == "총합계" or code is None:
                continue
            code = str(code)
            if (
                len(code) != 10 or not code.isdecimal() or code in areas
                or not isinstance(name, str) or not name.startswith("부산광역시 ")
                or not isinstance(population, int) or population < 0
                or not isinstance(total, int) or not 0 <= (food or 0) <= total or total <= 0
            ):
                raise ValueError(f"집계표_값의 코드·지역명·인구·점포 수를 확인해라: {code}")
            name = name.removeprefix("부산광역시 ")
            areas[code] = (name, name.split()[0], population, total, food or 0)

        source = next(sheet for sheet in book if sheet.title.startswith("소상공인시장진흥공단_상가"))
        rows = source.values
        columns = {name: i for i, name in enumerate(next(rows))}
        indexes = [columns[name] for name in (
            "법정동코드", "상권업종대분류코드", "상권업종소분류명", "경도", "위도",
        )]
        all_counts, food_counts, cells = Counter(), Counter(), Counter()
        for row in rows:
            code, category, subtype, lon, lat = (row[i] for i in indexes)
            code = str(code)
            all_counts[code] += 1
            if category != "I2":
                continue
            food_counts[code] += 1
            if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                if 128 < lon < 130 and 34 < lat < 36:
                    cells[code, subtype or "미분류", f"{lat:.3f}", f"{lon:.3f}"] += 1
    finally:
        book.close()

    if set(areas) != set(all_counts) or any(
        all_counts[code] != area[3] or food_counts[code] != area[4]
        for code, area in areas.items()
    ):
        raise ValueError("상가 원본과 집계표의 법정동별 전체·음식 점포 수가 다르다.")
    DATA_DIR.mkdir(exist_ok=True)
    write_csv("areas.csv", ("code", "area", "district", "population", "stores", "food"),
              ((code, *area) for code, area in sorted(areas.items())))
    write_csv("food_map.csv", ("code", "subtype", "lat", "lon", "count"),
              ((*key, count) for key, count in sorted(cells.items())))
    print(f"지역 {len(areas):,}곳 | 전체 점포 {sum(all_counts.values()):,}개 | "
          f"음식 점포 {sum(food_counts.values()):,}개 | 지도 반영 {sum(cells.values()):,}개")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="집계표_값과 상가 원본이 있는 xlsx")
    prepare(parser.parse_args().workbook)
