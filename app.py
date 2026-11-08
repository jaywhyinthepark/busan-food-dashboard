from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st


DATA = Path(__file__).resolve().parent / "data"
RANKINGS = {
    "음식 점포 수": ("food", "{:,.0f}개"),
    "주민 1천 명당 음식 점포 수": ("density", "{:,.1f}개"),
    "음식업 특화도": ("specialization", "{:.2f}배"),
}
QUESTIONS = {
    "연제구 연산동": "매출이 가장 많이 발생하는 요일과 시간대는 언제인가요?",
    "부산진구 부전동": "인근 주민·직장인·방문객 중 어느 고객층의 매출 비중이 가장 큰가요?",
    "중구 남포동3가": "방문객과 단골 손님이 각각 어느 정도이며, 방문객이 적은 날에는 매출이 얼마나 달라지나요?",
    "금정구 오륜동": "평일과 주말의 매출 차이는 어느 정도이며, 그에 맞춰 식재료 발주량을 어떻게 조정하시나요?",
    "금정구 금성동": "주중·주말이나 계절에 따라 손님 수와 재료비 부담이 어떻게 달라지나요?",
}


@st.cache_data
def load_data():
    areas = pd.read_csv(DATA / "areas.csv", dtype={"code": str})
    points = pd.read_csv(DATA / "food_map.csv", dtype={"code": str})
    city_share = areas["food"].sum() / areas["stores"].sum()
    areas["share"] = areas["food"] / areas["stores"]
    areas["specialization"] = areas["share"] / city_share
    areas["density"] = 1000 * areas["food"] / areas["population"].where(areas["population"] > 0)
    return areas, points, city_share


def show_ranking(areas):
    metric = st.radio("정렬 기준", list(RANKINGS), key="ranking")
    field, fmt = RANKINGS[metric]
    ranked = (areas.dropna(subset=[field])
              .sort_values([field, "area"], ascending=[False, True]).head(5))
    table = ranked[["area"]].rename(columns={"area": "법정구역"})
    table[metric] = ranked[field].map(fmt.format)
    if metric != "음식 점포 수":
        table["음식 점포 수"] = ranked["food"].map("{:,}개".format)
    if field == "density":
        table["주민등록인구"] = ranked["population"].map("{:,}명".format)
    if field == "specialization":
        table["전체 점포 수"] = ranked["stores"].map("{:,}개".format)
    table.insert(0, "순위", range(1, len(table) + 1))
    st.dataframe(table, hide_index=True, width="stretch")
    if field == "density":
        st.caption("주민등록인구 0명인 지역은 순위에서 제외한다. 인구가 적으면 점포 수가 적어도 이 비율이 커질 수 있다.")
    elif field == "specialization":
        st.caption("1배는 부산 전체와 같은 음식업 구성비다. 전체 점포 수가 적은 지역은 분모를 함께 확인한다.")


def show_map(points, area):
    if points.empty:
        st.info("이 지역에 지도에 표시할 음식 점포 좌표가 없다.")
        return
    subtype_totals = points.groupby("subtype")["count"].sum().sort_values(ascending=False)
    subtype = st.selectbox("지도 업종", ["전체 음식업", *subtype_totals.index], key=f"subtype-{area.code}")
    visible = points if subtype == "전체 음식업" else points[points["subtype"] == subtype]
    grid = visible.groupby(["lat", "lon"], as_index=False)["count"].sum()
    grid["radius"] = (grid["count"] ** 0.5 * 5).clip(upper=75)
    layer = pdk.Layer(
        "ScatterplotLayer", grid, get_position="[lon, lat]", get_radius="radius",
        get_fill_color=[8, 126, 118, 175], radius_min_pixels=3, pickable=True,
    )
    spread = max(grid["lat"].max() - grid["lat"].min(), grid["lon"].max() - grid["lon"].min())
    zoom = 14.5 if spread < 0.012 else (13 if spread < 0.045 else 11.5)
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=grid["lat"].median(), longitude=grid["lon"].median(), zoom=zoom),
        map_style="light",
        tooltip={"text": "이 위치의 점포 수: {count}개"},
    ), height=390)
    st.caption(f"지도 표시 {grid['count'].sum():,}개 · 좌표를 소수 셋째 자리로 반올림해 묶었다. 원의 크기는 점포 수를 나타낸다.")
    if points["count"].sum() < area.food:
        st.caption(f"이 지역 음식 점포 {area.food:,}개 중 좌표 확인이 필요한 점포는 지도 집계에서 빠져 있다.")
    common = " · ".join(f"{name} {count:,}개" for name, count in subtype_totals.head(3).items())
    st.caption(f"좌표가 있는 점포의 주요 세부 업종  {common}")


def show_questions(area):
    st.subheader("상담에서 확인할 질문")
    first = QUESTIONS.get(area.area, "주 고객은 누구이며 매출이 집중되는 요일이나 시간대는 언제인가요?")
    st.markdown(
        f"1. {first}\n"
        "2. 카드·배달앱 매출은 며칠 뒤에 들어오고, 식재료비나 임차료는 언제 지급하시나요?\n"
        "3. 매출이 적은 달에는 고정비와 기존 대출 상환금을 어떤 재원으로 충당하시나요?"
    )
    st.caption("점포 분포를 참고해 준비한 질문이다. 자금 필요와 상환 여력은 실제 상담에서 확인한다.")


def main():
    st.set_page_config(page_title="부산 음식업 상권 대시보드", layout="wide")
    st.title("부산 음식업 상권 대시보드")
    st.caption("2026년 9월 · 법정구역별 음식 점포 분포를 비교하고 소상공인 상담 질문을 준비한다.")
    areas, points, city_share = load_data()
    summary = st.columns(3)
    summary[0].metric("분석 법정구역", f"{len(areas):,}곳")
    summary[1].metric("부산 음식 점포", f"{areas['food'].sum():,}개")
    summary[2].metric("부산 음식업 구성비", f"{city_share:.1%}")

    left, right = st.columns([1, 1.55], gap="large")
    with left:
        st.subheader("지표별 상위 5곳")
        show_ranking(areas)
        with st.expander("지표 계산 기준"):
            st.markdown(
                "- **주민 1천 명당 음식 점포 수**: 음식 점포 수 ÷ 주민등록인구 × 1,000\n"
                "- **음식업 구성비**: 음식 점포 수 ÷ 전체 점포 수\n"
                "- **음식업 특화도**: 지역 음식업 구성비 ÷ 부산 전체 음식업 구성비"
            )
            st.caption("주민등록인구를 분모로 쓰므로 방문객과 직장인 규모는 별도로 확인해야 한다.")
    with right:
        st.subheader("법정구역별 점포 분포")
        ordered = areas.sort_values(["food", "area"], ascending=[False, True])
        names = ordered.set_index("code")["area"]
        district = st.selectbox("구·군", ["부산 전체", *sorted(areas["district"].unique())])
        options = ordered if district == "부산 전체" else ordered[ordered["district"] == district]
        code = st.selectbox(
            "법정구역", options["code"].tolist(), format_func=names.get, key=f"area-{district}",
        )
        area = ordered.loc[ordered["code"] == code].iloc[0]
        metrics = st.columns(3)
        metrics[0].metric("음식 점포", f"{area.food:,}개", help=f"전체 점포 {area.stores:,}개")
        metrics[1].metric("주민등록인구", f"{area.population:,}명")
        metrics[2].metric("음식업 특화도", f"{area.specialization:.2f}배")
        density = f"{area.density:,.1f}개" if pd.notna(area.density) else "산출 불가(인구 0명)"
        st.caption(f"전체 점포 {area.stores:,}개 · 음식업 구성비 {area.share:.1%} · 주민 1천 명당 음식 점포 수 {density}")
        show_map(points[points["code"] == code], area)
        show_questions(area)

    st.divider()
    st.caption(
        "출처: [소상공인시장진흥공단 상가(상권)정보](https://www.data.go.kr/data/15083033/fileData.do) · "
        "[행정안전부 법정동별 주민등록 인구통계](https://jumin.mois.go.kr/)"
    )


if __name__ == "__main__":
    main()
